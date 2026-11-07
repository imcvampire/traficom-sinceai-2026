import shutil
from pathlib import Path

from ific import db, ingest

FIXTURES = Path(__file__).parent / "fixtures" / "brific"
ISSUE_N = 9997
ISSUE_N1 = 9998


def fixture_exporter(mdb: Path, table: str, out: Path) -> None:
    no = ingest.terra_issue_no(mdb)
    src = FIXTURES / str(no) / f"{table}.csv"
    if not src.exists():
        raise ingest.IngestError(f"mdb-export {mdb.name} {table} failed: no such table")
    shutil.copyfile(src, out)


def fixture_mdb(tmp_path: Path, issue: int, content: bytes | None = None) -> Path:
    path = tmp_path / f"brific{issue}.mdb"
    path.write_bytes(content if content is not None else f"brific-fixture-{issue}-v1".encode())
    return path


def loaded_db(tmp_path: Path, issues: tuple[int, ...] = (ISSUE_N, ISSUE_N1)):
    con = db.connect(tmp_path / "db" / "ific.duckdb", "v1.5.0")
    for issue in issues:
        ingest.ensure_terra_issue(con, issue, fixture_mdb(tmp_path, issue), export=fixture_exporter)
    return con


def assessed(tmp_path: Path, issues: tuple[int, ...] = (ISSUE_N, ISSUE_N1)):
    """Fixture issues ingested with M4 loaded; returns the connection and {issue: {terrakey: result}}."""
    from ific import m4
    from ific.config import settings
    from ific.terra.assess import assess_issue

    con = loaded_db(tmp_path, issues)
    m4.ensure_m4(con, settings)
    return con, {n: {r["terrakey"]: r for r in assess_issue(con, n)} for n in issues}
