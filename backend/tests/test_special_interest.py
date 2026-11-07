import csv
import shutil
from pathlib import Path

import pytest

from ific import db, m4, special_interest
from ific.config import Settings

REPO_DATA = Path(__file__).resolve().parents[2] / "data"

BASE_RECORD = {
    "source_row": "13",
    "Station number": "5931",
    "Class of licence": "BC",
    "Longitude": "24.64014",
    "Latitude": "60.17766",
    "Ground height (m)": "44",
    "Mast height (m)": "325",
    "Mast type": "KIINTEÄ",
    "Channel bandwidth": "300.000 kHz",
    "TX frequency": "87.900 MHz",
    "RX frequency": "87.900 MHz",
    "Ant height AGL (m)": "248",
    "Ant height ASL (m)": "292",
    "Ant gain (dB)": "",
    "Class of transmission": "F9EHF",
    "Transmission bandwidth": "300k",
    "Radiation direction (°)": "",
    "Polarisation": "H",
    "Radioation power": "60",
    "Radioation power (ITU)": "",
    "Radiation power unit": "kW",
    "Transmission line (dB)": "",
    "Directivity": "ND",
}


@pytest.mark.parametrize(
    ("text", "hz"),
    [
        ("300k", 300_000),
        ("16K0", 16_000),
        ("8M00", 8_000_000),
        ("7,6k", 7_600),
        ("0,1G", 100_000_000),
        ("10k0", 10_000),
        ("", None),
    ],
)
def test_parse_designator_bandwidth_hz(text: str, hz: int | None) -> None:
    assert special_interest.parse_designator_bandwidth_hz(text) == hz


@pytest.mark.parametrize("text", ["abc", "300", "1.5K2", "5X", "0,5H"])
def test_parse_designator_bandwidth_hz_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        special_interest.parse_designator_bandwidth_hz(text)


def _write_csv(path: Path, records: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(BASE_RECORD))
        writer.writeheader()
        writer.writerows(records)
    return path


def _rows(tmp_path: Path, *overrides: dict[str, str]) -> list[dict[str, object]]:
    records = [{**BASE_RECORD, "source_row": str(13 + i), **o} for i, o in enumerate(overrides)]
    rows = special_interest.station_rows(_write_csv(tmp_path / "si.csv", records))
    names = [col for col, _ in special_interest.COLUMNS]
    return [dict(zip(names, row, strict=True)) for row in rows]


def test_clean_row_is_parsed_without_flags(tmp_path: Path) -> None:
    (row,) = _rows(tmp_path, {})
    assert row["quality_flags"] == []
    assert row["tx_hz"] == 87_900_000
    assert (row["tx_lower_hz"], row["tx_upper_hz"]) == (87_750_000, 88_050_000)
    assert row["radiated_power_dbw"] == pytest.approx(47.7815, abs=1e-4)
    assert row["effective_asl_m"] == 292


@pytest.mark.parametrize(
    ("override", "flag"),
    [
        ({"Class of licence": ""}, "licence_class_defaulted"),
        ({"TX frequency": ""}, "missing_tx_frequency"),
        ({"RX frequency": ""}, "missing_rx_frequency"),
        ({"Channel bandwidth": "", "Transmission bandwidth": ""}, "missing_bandwidth"),
        ({"Channel bandwidth": ""}, "bandwidth_from_designator"),
        ({"Channel bandwidth": "2500 kHz", "Transmission bandwidth": "118600k"}, "bandwidth_mismatch"),
        ({"Ant height AGL (m)": "-28", "Ant height ASL (m)": ""}, "agl_clamped"),
        ({"Ant height ASL (m)": ""}, "asl_derived"),
        ({"Ant height ASL (m)": "10"}, "asl_inconsistent"),
        ({"Radioation power": "", "Radiation power unit": ""}, "missing_power"),
        ({"Radioation power": "0"}, "nonpositive_power"),
        ({"Radiation power unit": "dBW"}, "unparseable:Radiation power unit"),
        ({"Latitude": "58.9"}, "outside_finland_bbox"),
        ({"TX frequency": "87.9MHz?"}, "unparseable:TX frequency"),
    ],
)
def test_quality_flags(tmp_path: Path, override: dict[str, str], flag: str) -> None:
    (row,) = _rows(tmp_path, override)
    assert flag in row["quality_flags"]


def test_clamped_agl_feeds_derived_asl(tmp_path: Path) -> None:
    (row,) = _rows(tmp_path, {"Ant height AGL (m)": "-28", "Ant height ASL (m)": ""})
    assert row["ant_agl_m"] == -28
    assert row["effective_agl_m"] == special_interest.MIN_AGL_M
    assert row["effective_asl_m"] == 44 + special_interest.MIN_AGL_M


@pytest.mark.parametrize(
    ("channel", "designator", "hz"),
    [("2500 kHz", "118600k", 2_500_000), ("9.000 kHz", "10k0", 9_000), ("16 kHz", "12k5", 12_500)],
)
def test_bandwidth_mismatch_uses_smaller(tmp_path: Path, channel: str, designator: str, hz: int) -> None:
    (row,) = _rows(tmp_path, {"Channel bandwidth": channel, "Transmission bandwidth": designator})
    assert row["bandwidth_hz"] == hz
    assert "bandwidth_mismatch" in row["quality_flags"]


def test_missing_licence_class_defaults_to_others(tmp_path: Path) -> None:
    (row,) = _rows(tmp_path, {"Class of licence": ""})
    assert row["licence_class"] == special_interest.DEFAULT_LICENCE_CLASS


def test_missing_bandwidth_gives_point_band(tmp_path: Path) -> None:
    (row,) = _rows(tmp_path, {"Channel bandwidth": "", "Transmission bandwidth": ""})
    assert row["tx_lower_hz"] == row["tx_upper_hz"] == 87_900_000


def test_exact_duplicate_rows_are_dropped(tmp_path: Path) -> None:
    rows = _rows(tmp_path, {}, {}, {"TX frequency": "88.000 MHz"})
    assert [r["source_row"] for r in rows] == [13, 15]


def test_unexpected_header_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "si.csv"
    path.write_text("Station number,TX frequency\n1,87.9 MHz\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected header"):
        special_interest.station_rows(path)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    data = tmp_path / "data"
    for sub in ("api", "m4", "special_interest"):
        shutil.copytree(REPO_DATA / sub, data / sub)
    return Settings(data_dir=data, db_dir=tmp_path / "db")


def test_load_real_csv_and_overlap_view(settings: Settings) -> None:
    con = db.connect(settings.db_path, settings.db_storage_version)
    m4.ensure_m4(con, settings)

    status = special_interest.ensure_special_interest(con, settings)

    assert (status.action, status.rows) == ("loaded", 873)
    assert con.execute(
        "SELECT edition, row_count FROM ref.source WHERE source_id = ?", [special_interest.SOURCE_ID]
    ).fetchone() == ("v05112026", 873)
    assert con.execute(
        f"SELECT COUNT(*) FROM {special_interest.TABLE} WHERE 'licence_class_defaulted' = ANY(quality_flags)"
    ).fetchone() == (294,)
    assert con.execute(
        f"SELECT COUNT(*) FROM {special_interest.TABLE} WHERE licence_class IS NULL"
    ).fetchone() == (0,)
    unmatched = con.execute(
        f"""
        SELECT COUNT(*) FROM {special_interest.TABLE}
        WHERE tx_hz IS NOT NULL
          AND source_row NOT IN (SELECT source_row FROM {special_interest.OVERLAP_VIEW})
        """
    ).fetchone()
    assert unmatched == (0,)
    bad_overlap = con.execute(
        f"SELECT COUNT(*) FROM {special_interest.OVERLAP_VIEW} WHERE overlap_lower_hz > overlap_upper_hz"
    ).fetchone()
    assert bad_overlap == (0,)


def test_reload_skips_unchanged_and_reloads_changed(settings: Settings) -> None:
    con = db.connect(settings.db_path, settings.db_storage_version)
    m4.ensure_m4(con, settings)
    special_interest.ensure_special_interest(con, settings)

    assert special_interest.ensure_special_interest(con, settings).action == "up_to_date"

    path = settings.special_interest_csv
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(lines[:-1]), encoding="utf-8")
    status = special_interest.ensure_special_interest(con, settings)
    assert (status.action, status.rows) == ("loaded", 872)


def test_missing_csv_raises(settings: Settings) -> None:
    con = db.connect(settings.db_path, settings.db_storage_version)
    settings.special_interest_csv.unlink()
    with pytest.raises(FileNotFoundError, match="special-interest source"):
        special_interest.ensure_special_interest(con, settings)


def test_parser_version_change_forces_reload(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    con = db.connect(settings.db_path, settings.db_storage_version)
    m4.ensure_m4(con, settings)
    special_interest.ensure_special_interest(con, settings)

    monkeypatch.setattr(special_interest, "PARSER_VERSION", special_interest.PARSER_VERSION + "-next")

    assert special_interest.ensure_special_interest(con, settings).action == "loaded"
