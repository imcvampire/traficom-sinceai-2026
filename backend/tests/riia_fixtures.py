import shutil
from pathlib import Path

from ific import db, ingest

FIXTURES = Path(__file__).parent / "fixtures" / "ific"
FIXTURE_ISSUE = 9999


def fixture_exporter(mdb: Path, table: str, out: Path) -> None:
    src = FIXTURES / f"{table}.csv"
    if not src.exists():
        raise ingest.IngestError(f"mdb-export {mdb.name} {table} failed: no such table")
    shutil.copyfile(src, out)


def fixture_mdb(tmp_path: Path, content: bytes = b"fixture-v1") -> Path:
    path = tmp_path / f"ific{FIXTURE_ISSUE}.mdb"
    path.write_bytes(content)
    return path


def loaded_db(tmp_path: Path):
    con = db.connect(tmp_path / "db" / "ific.duckdb", "v1.5.0")
    ingest.ensure_issue(con, FIXTURE_ISSUE, fixture_mdb(tmp_path), export=fixture_exporter)
    return con
