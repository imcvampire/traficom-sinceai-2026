from pathlib import Path

import pytest
from riia_fixtures import FIXTURE_ISSUE, fixture_exporter, fixture_mdb, loaded_db

from ific import db, ingest
from ific.config import Settings


def test_fixture_load_types_and_filters(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    assert (
        con.execute("SELECT count(*) FROM space.notice WHERE ific_no = ?", [FIXTURE_ISSUE]).fetchone()[0] == 5
    )
    assert con.execute("SELECT notice_count FROM space.issue").fetchone()[0] == 5
    assert con.execute("SELECT count(*) FROM space.provn").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM space.tr_aff_ntw").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM space.mask_info").fetchone()[0] == 0
    types = dict(
        con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'space' AND table_name = 'grp'"
        ).fetchall()
    )
    assert types["ific_no"] == "INTEGER" and types["grp_id"] == "BIGINT"
    assert types["freq_min"] == "DOUBLE" and types["d_wic"] == "TIMESTAMP" and types["beam_name"] == "VARCHAR"
    assert (
        "provn: adm = 'FIN' OR ctry = 'FIN'" in con.execute("SELECT filters FROM space.issue").fetchone()[0]
    )


def test_second_call_is_noop_and_changed_hash_reloads(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    path = tmp_path / f"ific{FIXTURE_ISSUE}.mdb"
    assert ingest.ensure_issue(con, FIXTURE_ISSUE, path, export=fixture_exporter).action == "up_to_date"
    path.write_bytes(b"fixture-v2")
    status = ingest.ensure_issue(con, FIXTURE_ISSUE, path, export=fixture_exporter)
    assert status.action == "loaded" and status.notices == 5
    assert con.execute("SELECT count(*) FROM space.notice").fetchone()[0] == 5


def test_failure_rolls_back_to_previous_rows(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    path = tmp_path / f"ific{FIXTURE_ISSUE}.mdb"
    path.write_bytes(b"fixture-broken")

    def broken(mdb: Path, table: str, out: Path) -> None:
        fixture_exporter(mdb, table, out)
        if table == "orbit":
            out.write_text("ntc_id,orb_id,nbr_sat_pl\nnot-a-number,1,1\n")

    with pytest.raises(ingest.IngestError):
        ingest.ensure_issue(con, FIXTURE_ISSUE, path, export=broken)
    assert con.execute("SELECT count(*) FROM space.notice").fetchone()[0] == 5
    assert con.execute("SELECT count(*) FROM space.orbit").fetchone()[0] == 4
    assert con.execute("SELECT sha256 FROM space.issue").fetchone()[0] != ingest._sha256(path)


def test_missing_binary_raises_ingest_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest.shutil, "which", lambda _: None)
    con = db.connect(tmp_path / "db" / "ific.duckdb", "v1.5.0")
    with pytest.raises(ingest.IngestError, match="mdb-export not found"):
        ingest.ensure_issue(con, FIXTURE_ISSUE, fixture_mdb(tmp_path))


def test_missing_table_raises_ingest_error(tmp_path: Path) -> None:
    con = db.connect(tmp_path / "db" / "ific.duckdb", "v1.5.0")

    def no_orbit(mdb: Path, table: str, out: Path) -> None:
        if table == "orbit":
            raise ingest.IngestError("mdb-export ific9999.mdb orbit failed: no such table")
        fixture_exporter(mdb, table, out)

    with pytest.raises(ingest.IngestError, match="orbit"):
        ingest.ensure_issue(con, FIXTURE_ISSUE, fixture_mdb(tmp_path), export=no_orbit)
    assert con.execute("SELECT count(*) FROM space.issue").fetchone()[0] == 0


def test_discover_issues_scans_download_dir_and_root(tmp_path: Path) -> None:
    dl = tmp_path / "ific"
    (dl / "3074").mkdir(parents=True)
    (dl / "3074" / "ific3074.mdb").write_bytes(b"x")
    root = tmp_path / "root"
    root.mkdir()
    (root / "ific3083.mdb").write_bytes(b"x")
    (root / "ific3074.mdb").write_bytes(b"x")
    (root / "brific3076.mdb").write_bytes(b"x")
    found = ingest.discover_issues(Settings(watcher_download_dir=dl), project_root=root)
    assert found == {3074: dl / "3074" / "ific3074.mdb", 3083: root / "ific3083.mdb"}


def test_unexpected_column_name_is_rejected(tmp_path: Path) -> None:
    con = db.connect(tmp_path / "db" / "ific.duckdb", "v1.5.0")

    def hostile(mdb: Path, table: str, out: Path) -> None:
        fixture_exporter(mdb, table, out)
        if table == "geo":
            out.write_text('ntc_id,"x"" VARCHAR); DROP TABLE space.notice; --"\n1,2\n')

    with pytest.raises(ingest.IngestError, match="unexpected column names"):
        ingest.ensure_issue(con, FIXTURE_ISSUE, fixture_mdb(tmp_path), export=hostile)
