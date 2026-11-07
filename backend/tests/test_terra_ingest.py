from pathlib import Path

from terra_fixtures import ISSUE_N, ISSUE_N1, fixture_exporter, fixture_mdb, loaded_db

from ific import ingest
from ific.config import Settings


def _count(con, table: str, issue: int) -> int:
    return con.execute(f"SELECT count(*) FROM terra.{table} WHERE ific_no = ?", [issue]).fetchone()[0]


def test_fixture_ingest_counts_types_and_noop(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    assert _count(con, "fxm_terra", ISSUE_N) == 13 and _count(con, "fxm_terra", ISSUE_N1) == 15
    assert _count(con, "fxm_ant_diag", ISSUE_N) == 4 and _count(con, "fxm_target", ISSUE_N) == 2
    assert _count(con, "ref_stn_cls", ISSUE_N) == 28
    assert dict(con.execute("SELECT ific_no, assignment_count FROM terra.issue").fetchall()) == {
        ISSUE_N: 13,
        ISSUE_N1: 15,
    }
    types = dict(
        con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'terra' AND table_name = 'fxm_terra'"
        ).fetchall()
    )
    assert types["terrakey"] == "BIGINT" and types["freq_assgn"] == "DOUBLE" and types["d_rcv"] == "TIMESTAMP"
    assert types["adm"] == "VARCHAR"
    path = tmp_path / f"brific{ISSUE_N}.mdb"
    assert ingest.ensure_terra_issue(con, ISSUE_N, path, export=fixture_exporter).action == "up_to_date"


def test_changed_file_replaces_only_that_issue(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    before = con.execute(
        "SELECT * FROM terra.fxm_terra WHERE ific_no = ? ORDER BY terrakey", [ISSUE_N1]
    ).fetchall()
    path = fixture_mdb(tmp_path, ISSUE_N, b"brific-fixture-v2")
    assert ingest.ensure_terra_issue(con, ISSUE_N, path, export=fixture_exporter).action == "loaded"
    assert _count(con, "fxm_terra", ISSUE_N) == 13
    after = con.execute(
        "SELECT * FROM terra.fxm_terra WHERE ific_no = ? ORDER BY terrakey", [ISSUE_N1]
    ).fetchall()
    assert after == before


def test_changed_table_set_reloads(tmp_path: Path) -> None:
    con = loaded_db(tmp_path, (ISSUE_N,))
    con.execute("UPDATE terra.issue SET filters = 'tables: fxm_terra'")
    path = tmp_path / f"brific{ISSUE_N}.mdb"
    assert ingest.ensure_terra_issue(con, ISSUE_N, path, export=fixture_exporter).action == "loaded"


def test_cast_failure_keeps_the_type_and_the_raw_text(tmp_path: Path) -> None:
    con = loaded_db(tmp_path, (ISSUE_N,))

    def odd_height(mdb: Path, table: str, out: Path) -> None:
        fixture_exporter(mdb, table, out)
        if table == "fxm_ant":
            out.write_text(out.read_text().replace(",44,", ",44 m,", 1))

    path = fixture_mdb(tmp_path, ISSUE_N1)
    ingest.ensure_terra_issue(con, ISSUE_N1, path, export=odd_height)
    col_type = con.execute(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_schema = 'terra' AND table_name = 'fxm_ant' AND column_name = 'hgt_agl'"
    ).fetchone()[0]
    assert col_type == "DOUBLE"  # another issue's odd value never changes how this column is read
    assert _count(con, "fxm_ant", ISSUE_N1) == 15
    assert con.execute(
        "SELECT hgt_agl, hgt_agl_raw FROM terra.fxm_ant WHERE ific_no = ? AND terrakey = 90000001", [ISSUE_N1]
    ).fetchone() == (None, "44 m")
    assert con.execute(
        "SELECT hgt_agl, hgt_agl_raw FROM terra.fxm_ant WHERE ific_no = ? AND terrakey = 90000003", [ISSUE_N]
    ).fetchone() == (30.0, None)


def test_discovery_prefers_download_dir(tmp_path: Path) -> None:
    dl = tmp_path / "brific"
    (dl / "3076").mkdir(parents=True)
    (dl / "3076" / "brific3076.mdb").write_bytes(b"x")
    root = tmp_path / "root"
    root.mkdir()
    for name in ("brific3076.mdb", "brific3075.mdb", "ific3074.mdb"):
        (root / name).write_bytes(b"x")
    found = ingest.discover_terra_issues(Settings(terra_download_dir=dl), project_root=root)
    assert found == {3075: root / "brific3075.mdb", 3076: dl / "3076" / "brific3076.mdb"}
    assert ingest.discover_issues(Settings(watcher_download_dir=dl), project_root=root) == {
        3074: root / "ific3074.mdb"
    }
