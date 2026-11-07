import shutil
from pathlib import Path

import pytest

from ific import db, m4
from ific.config import Settings

REPO_DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.mark.parametrize(
    ("text", "hz"),
    [
        ("8.3 kHz", 8300),
        ("2173.500 kHz", 2173500),
        ("1.5 GHz", 1500000000),
        ("100 Hz", 100),
        ("", None),
    ],
)
def test_parse_freq_hz(text: str, hz: int | None) -> None:
    assert m4.parse_freq_hz(text) == hz


@pytest.mark.parametrize("text", ["abc", "12 THz", "kHz", "0.5 Hz"])
def test_parse_freq_hz_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        m4.parse_freq_hz(text)


@pytest.fixture
def data_copy(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    shutil.copytree(REPO_DATA / "api", data / "api")
    shutil.copytree(REPO_DATA / "m4", data / "m4")
    return data


@pytest.fixture
def settings(tmp_path: Path, data_copy: Path) -> Settings:
    return Settings(data_dir=data_copy, db_dir=tmp_path / "db")


def _loaded_at(con) -> dict[str, object]:
    return dict(con.execute("SELECT source_id, epoch_us(loaded_at) FROM ref.source").fetchall())


def test_initial_load(settings: Settings) -> None:
    con = db.connect(settings.db_path, settings.db_storage_version)
    statuses = m4.ensure_m4(con, settings)

    assert {s.source_id: s.action for s in statuses} == {
        "m4_allocation": "loaded",
        "m4_regulation": "loaded",
        "m4_notes": "loaded",
    }
    assert con.execute("SELECT COUNT(*) FROM ref.m4_allocation").fetchone()[0] == 5917
    assert (
        con.execute("SELECT COUNT(*) FROM ref.m4_allocation WHERE band_lower_hz IS NULL").fetchone()[0] == 0
    )
    assert (
        con.execute(
            "SELECT COUNT(*) FROM ref.m4_allocation "
            "WHERE (duplex_band_lower_limit = '') <> (duplex_lower_hz IS NULL)"
        ).fetchone()[0]
        == 0
    )
    pages = dict(con.execute("SELECT doc_id, COUNT(*) FROM ref.m4_page GROUP BY doc_id").fetchall())
    assert pages[m4.REGULATION_DOC] > 0
    assert pages[m4.NOTES_DOC] > 0
    assert con.execute("SELECT COUNT(*) FROM ref.m4_page WHERE trim(text) = ''").fetchone()[0] == 0
    manifest = con.execute(
        "SELECT source_id, edition, row_count FROM ref.source ORDER BY source_id"
    ).fetchall()
    assert {row[1] for row in manifest} == {"4 AG/2026M"}
    assert dict((row[0], row[2]) for row in manifest)["m4_regulation"] == pages[m4.REGULATION_DOC]


def test_second_run_is_up_to_date(settings: Settings) -> None:
    con = db.connect(settings.db_path, settings.db_storage_version)
    m4.ensure_m4(con, settings)
    before = _loaded_at(con)

    statuses = m4.ensure_m4(con, settings)

    assert {s.action for s in statuses} == {"up_to_date"}
    assert _loaded_at(con) == before


def test_changed_file_reloads_only_that_source(settings: Settings) -> None:
    con = db.connect(settings.db_path, settings.db_storage_version)
    m4.ensure_m4(con, settings)
    before = _loaded_at(con)
    path = settings.m4_allocation_json
    path.write_bytes(path.read_bytes().replace(b"Passive system", b"passive system", 1))

    statuses = m4.ensure_m4(con, settings)

    assert {s.source_id: s.action for s in statuses} == {
        "m4_allocation": "loaded",
        "m4_regulation": "up_to_date",
        "m4_notes": "up_to_date",
    }
    after = _loaded_at(con)
    assert after["m4_allocation"] > before["m4_allocation"]
    assert after["m4_regulation"] == before["m4_regulation"]
    assert (
        con.execute("SELECT comment FROM ref.m4_allocation WHERE id = 1").fetchone()[0].startswith("passive")
    )


def test_dropped_table_reloads(settings: Settings) -> None:
    con = db.connect(settings.db_path, settings.db_storage_version)
    m4.ensure_m4(con, settings)
    con.execute("DROP TABLE ref.m4_allocation")

    statuses = m4.ensure_m4(con, settings)

    assert {s.source_id: s.action for s in statuses}["m4_allocation"] == "loaded"
    assert con.execute("SELECT COUNT(*) FROM ref.m4_allocation").fetchone()[0] == 5917


def test_unparseable_limit_keeps_previous_rows(settings: Settings) -> None:
    con = db.connect(settings.db_path, settings.db_storage_version)
    m4.ensure_m4(con, settings)
    before = con.execute(
        "SELECT sha256, epoch_us(loaded_at) FROM ref.source WHERE source_id = 'm4_allocation'"
    ).fetchone()
    path = settings.m4_allocation_json
    original = path.read_bytes()
    corrupted = original.replace(
        b'"Frequency_band_lower_limit":"8.3 kHz"', b'"Frequency_band_lower_limit":"8.3 kHertz"', 1
    )
    assert corrupted != original
    path.write_bytes(corrupted)

    with pytest.raises(ValueError, match="ID 1: unparseable"):
        m4.ensure_m4(con, settings)

    assert con.execute("SELECT COUNT(*) FROM ref.m4_allocation").fetchone()[0] == 5917
    assert (
        con.execute(
            "SELECT sha256, epoch_us(loaded_at) FROM ref.source WHERE source_id = 'm4_allocation'"
        ).fetchone()
        == before
    )


def test_failure_inside_transaction_rolls_back(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    con = db.connect(settings.db_path, settings.db_storage_version)
    m4.ensure_m4(con, settings)
    con.execute("DELETE FROM ref.source WHERE source_id = 'm4_allocation'")

    def fail(*_: object) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(m4, "_edition", fail)
    with pytest.raises(RuntimeError, match="boom"):
        m4.ensure_m4(con, settings)

    assert con.execute("SELECT COUNT(*) FROM ref.m4_allocation").fetchone()[0] == 5917


def test_missing_source_names_override(settings: Settings) -> None:
    con = db.connect(settings.db_path, settings.db_storage_version)
    settings.m4_allocation_json.unlink()

    with pytest.raises(FileNotFoundError, match="IFIC_DATA_DIR"):
        m4.ensure_m4(con, settings)


def test_db_file_uses_compatible_storage_version(settings: Settings) -> None:
    db.connect(settings.db_path, "v1.5.0").close()

    # Header bytes 8-11 are "DUCK", byte 12 is the storage version; 68 is readable by DuckDB 1.5.
    header = settings.db_path.read_bytes()[8:13]
    assert header == b"DUCK\x44"
