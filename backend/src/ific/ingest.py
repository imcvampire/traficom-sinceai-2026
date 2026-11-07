"""Space IFIC `.mdb` ingest into the DuckDB `space` schema (a schema named `ific` would collide with the
`ific.duckdb` catalog).

Finland-involvement semantics, checked on the 3074 data (the IFIC PDF parts are not downloaded, so this is
inferred from the database and the SNS field names, not from the PDF):

- `provn` lists, per assignment group, the administrations the BR identified under each coordination provision
  (`coord_prov`, e.g. `9.11`, `9.14`, `9.21/C`, `A30A#7.1`). `adm` names the identified administration; `ctry`
  is empty for every FIN row in 3074. `agree_st` is a BR status code (3074 FIN rows: Q, F, P, V, T) kept
  verbatim.
- `tr_aff_ntw` lists networks the BR found affected; `adm` and `sat_name` name the affected network (FIN10300
  and FIN10400 at 22.8°E in 3074).
"""

import csv
import logging
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import duckdb

from ific.config import PROJECT_ROOT, Settings
from ific.m4 import _sha256

log = logging.getLogger("ific.ingest")

_ISSUE_RE = re.compile(r"^ific(\d{4})\.mdb$", re.IGNORECASE)
_COLUMN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

_BIGINT = ("ntc_id", "grp_id", "aff_ntc_id")
_DOUBLE = (
    "freq_min",
    "freq_max",
    "pep_max",
    "pwr_ds_max",
    "gain",
    "long_nom",
    "inclin_ang",
    "op_ht_km",
    "apog_km",
    "perig_km",
    "pfd",
    "bdwdth",
    "tol_east",
    "tol_west",
    "right_asc",
    "bore_long",
    "bore_lat",
    "maj_axis",
    "min_axis",
    "long_dec",
    "lat_dec",
    "noise_t",
)
_INTEGER = ("nbr_sat_pl", "nbr_plane", "orb_id", "seq_no", "wic_no")
_TIMESTAMP = ("d_wic",)

# table -> row filter applied on load (recorded in the manifest)
TABLES: dict[str, str | None] = {
    "notice": None,
    "com_el": None,
    "grp": None,
    "emiss": None,
    "s_beam": None,
    "geo": None,
    "non_geo": None,
    "orbit": None,
    "c_pfd": None,
    "mask_info": None,
    "srv_area": None,
    "e_stn": None,
    "es_ctry": None,
    "provn": "adm = 'FIN' OR ctry = 'FIN'",
    "tr_aff_ntw": "adm = 'FIN'",
}

Exporter = Callable[[Path, str, Path], None]


class IngestError(RuntimeError):
    pass


@dataclass(frozen=True)
class IssueStatus:
    ific_no: int
    action: Literal["loaded", "up_to_date"]
    notices: int
    ms: int


def _column_type(name: str) -> str:
    if name in _BIGINT:
        return "BIGINT"
    if name in _DOUBLE:
        return "DOUBLE"
    if name in _INTEGER:
        return "INTEGER"
    if name in _TIMESTAMP:
        return "TIMESTAMP"
    return "VARCHAR"


def mdb_export(mdb: Path, table: str, out: Path) -> None:
    binary = shutil.which("mdb-export")
    if binary is None:
        raise IngestError("mdb-export not found on PATH; install mdbtools (e.g. `brew install mdbtools`)")
    with out.open("wb") as f:
        proc = subprocess.run(
            [binary, "-D", "%Y-%m-%d", "-T", "%Y-%m-%d %H:%M:%S", str(mdb), table],
            stdout=f,
            stderr=subprocess.PIPE,
        )
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="replace").strip()
        raise IngestError(f"mdb-export {mdb.name} {table} failed: {detail or f'exit {proc.returncode}'}")


def issue_no(path: Path) -> int | None:
    m = _ISSUE_RE.match(path.name)
    return int(m.group(1)) if m else None


def discover_issues(settings: Settings, project_root: Path | None = None) -> dict[int, Path]:
    """Space IFIC databases in the watcher download dir, then the project root (`brific*` is terrestrial)."""
    project_root = project_root or PROJECT_ROOT
    found: dict[int, Path] = {}
    candidates = [
        *sorted(settings.watcher_download_dir.glob("*/ific*.mdb")),
        *sorted(project_root.glob("ific*.mdb")),
    ]
    for path in candidates:
        no = issue_no(path)
        if no is not None and path.is_file():
            found.setdefault(no, path)
    return dict(sorted(found.items()))


def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS space")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS space.issue (
            ific_no      INTEGER PRIMARY KEY,
            path         VARCHAR NOT NULL,
            sha256       VARCHAR NOT NULL,
            bytes        BIGINT  NOT NULL,
            notice_count BIGINT  NOT NULL,
            filters      VARCHAR NOT NULL,
            loaded_at    TIMESTAMPTZ NOT NULL
        )
        """
    )


def _table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    return bool(
        con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'space' AND table_name = ?", [table]
        ).fetchone()
    )


def _load_table(con: duckdb.DuckDBPyConnection, ific_no: int, table: str, csv_path: Path) -> int:
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        header = next(csv.reader(f), None)
    if not header:
        raise IngestError(f"{table}: export is empty (no header row)")
    bad = [c for c in header if not _COLUMN_RE.match(c)]
    if bad:
        raise IngestError(f"{table}: unexpected column names {bad[:3]}")
    types = {col: _column_type(col) for col in header}
    if not _table_exists(con, table):
        cols = ", ".join(f'"{c}" {t}' for c, t in types.items())
        con.execute(f'CREATE TABLE space."{table}" (ific_no INTEGER NOT NULL, {cols})')
    else:
        existing = {
            r[0]
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'space' AND "
                "table_name = ?",
                [table],
            ).fetchall()
        }
        for col in header:
            if col not in existing:
                con.execute(f'ALTER TABLE space."{table}" ADD COLUMN "{col}" {types[col]}')
    where = TABLES[table]
    type_sql = "{" + ", ".join(f"'{c}': '{t}'" for c, t in types.items()) + "}"
    rel = (
        f"SELECT {ific_no}::INTEGER AS ific_no, * FROM read_csv(?, header = true, auto_detect = false, "
        f"columns = {type_sql}, timestampformat = '%Y-%m-%d %H:%M:%S', quote = '\"', escape = '\"')"
    )
    if where:
        rel = f"SELECT * FROM ({rel}) WHERE {where}"
    con.execute(f'INSERT INTO space."{table}" BY NAME {rel}', [str(csv_path)])
    return con.execute(f'SELECT count(*) FROM space."{table}" WHERE ific_no = ?', [ific_no]).fetchone()[0]


def _display(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix() if path.is_relative_to(PROJECT_ROOT) else path.name


def ensure_issue(
    con: duckdb.DuckDBPyConnection, ific_no: int, path: Path, export: Exporter | None = None
) -> IssueStatus:
    """Load one Space IFIC issue. Unchanged sha256 is a no-op; a changed file replaces that issue's rows
    atomically.
    """
    export = export or mdb_export
    started = time.perf_counter()
    if not path.is_file():
        raise IngestError(f"IFIC {ific_no}: {path} not found")
    ensure_schema(con)
    sha = _sha256(path)
    manifest = con.execute(
        "SELECT sha256, notice_count FROM space.issue WHERE ific_no = ?", [ific_no]
    ).fetchone()
    if manifest and manifest[0] == sha:
        ms = round((time.perf_counter() - started) * 1000)
        log.info("ific=%d up to date (%d notices, %d ms)", ific_no, manifest[1], ms)
        return IssueStatus(ific_no, "up_to_date", manifest[1], ms)

    with tempfile.TemporaryDirectory(prefix=f"ific{ific_no}-") as tmp:
        exports: dict[str, Path] = {}
        for table in TABLES:
            out = Path(tmp) / f"{table}.csv"
            export(path, table, out)
            exports[table] = out
        con.execute("BEGIN TRANSACTION")
        try:
            counts: dict[str, int] = {}
            for table, out in exports.items():
                if _table_exists(con, table):
                    con.execute(f'DELETE FROM space."{table}" WHERE ific_no = ?', [ific_no])
                counts[table] = _load_table(con, ific_no, table, out)
            filters = "; ".join(f"{t}: {w}" for t, w in TABLES.items() if w)
            con.execute(
                "INSERT OR REPLACE INTO space.issue VALUES (?, ?, ?, ?, ?, ?, current_timestamp)",
                [ific_no, _display(path), sha, path.stat().st_size, counts["notice"], filters],
            )
            con.execute("COMMIT")
        except BaseException as e:
            con.execute("ROLLBACK")
            log.exception("ific=%d load failed, previous rows kept", ific_no)
            if isinstance(e, duckdb.Error):
                raise IngestError(f"IFIC {ific_no}: load failed: {e}") from e
            raise
    ms = round((time.perf_counter() - started) * 1000)
    log.info("ific=%d tables=%d notices=%d duration_ms=%d", ific_no, len(TABLES), counts["notice"], ms)
    return IssueStatus(ific_no, "loaded", counts["notice"], ms)


def ingested_issues(con: duckdb.DuckDBPyConnection) -> dict[int, tuple[str, int]]:
    ensure_schema(con)
    return {
        no: (p, n)
        for no, p, n in con.execute("SELECT ific_no, path, notice_count FROM space.issue").fetchall()
    }
