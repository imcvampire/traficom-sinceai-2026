"""IFIC `.mdb` ingest: Space issues (`ific<no>.mdb`) into the DuckDB `space` schema (a schema named `ific`
would collide with the `ific.duckdb` catalog), terrestrial BR IFIC issues (`brific<no>.mdb`) into `terra`.

Finland-involvement semantics, checked on the 3074 data (the IFIC PDF parts are not downloaded, so this is
inferred from the database and the SNS field names, not from the PDF):

- `provn` lists, per assignment group, the administrations the BR identified under each coordination provision
  (`coord_prov`, e.g. `9.11`, `9.14`, `9.21/C`, `A30A#7.1`). `adm` names the identified administration; `ctry`
  is empty for every FIN row in 3074. `agree_st` is a BR status code (3074 FIN rows: Q, F, P, V, T) kept
  verbatim.
- `tr_aff_ntw` lists networks the BR found affected; `adm` and `sat_name` name the affected network (FIN10300
  and FIN10400 at 22.8°E in 3074).
- Units differ between tables (BR IFIC Preface, Section III): `grp` and `c_pfd` frequencies are in MHz,
  `mask_info.freq_min/max` in GHz (3074: `5.925`), `c_pfd.bdwdth` in kHz.
- `srv_cls` gives each group's class of station (`stn_cls`, Preface Table 3) and nature of service (`nat_srv`,
  Table 4); the pfd check matches Table 21-4 rows on the space-station class.
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
_TERRA_ISSUE_RE = re.compile(r"^brific(\d{4})\.mdb$", re.IGNORECASE)
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
    "srv_cls": None,
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


def manifest_filters() -> str:
    """Tables loaded and row filters applied; a change re-loads issues whose file is unchanged."""
    return "; ".join([f"tables: {','.join(sorted(TABLES))}", *(f"{t}: {w}" for t, w in TABLES.items() if w)])


def ensure_issue(
    con: duckdb.DuckDBPyConnection, ific_no: int, path: Path, export: Exporter | None = None
) -> IssueStatus:
    """Load one Space IFIC issue. Unchanged sha256 and table set is a no-op; otherwise that issue's rows are
    replaced atomically.
    """
    export = export or mdb_export
    started = time.perf_counter()
    if not path.is_file():
        raise IngestError(f"IFIC {ific_no}: {path} not found")
    ensure_schema(con)
    sha = _sha256(path)
    manifest = con.execute(
        "SELECT sha256, notice_count, filters FROM space.issue WHERE ific_no = ?", [ific_no]
    ).fetchone()
    if manifest and manifest[0] == sha and manifest[2] == manifest_filters():
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
            con.execute(
                "INSERT OR REPLACE INTO space.issue VALUES (?, ?, ?, ?, ?, ?, current_timestamp)",
                [ific_no, _display(path), sha, path.stat().st_size, counts["notice"], manifest_filters()],
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


# --- Terrestrial BR IFIC (`brific<no>.mdb`) -----------------------------------------------------------------
#
# Each terrestrial issue is a delta: its ADD/MODIFY/SUPPRESS rows carry the issue's own `pub_no`, and the
# RECORDED rows it ships are the before-states those MODIFY/SUPPRESS rows target (`fxm_target`). The `ref_*`
# code tables are loaded per issue because the assessment cites the issue's own copy.

TERRA_TABLES: tuple[str, ...] = (
    "fxm_terra",
    "fxm_tx",
    "fxm_ant",
    "fxm_ant_diag",
    "fxm_geo",
    "fxm_geo_pt",
    "fxm_coord",
    "fxm_target",
    "fxm_pub_hist",
    "fxm_fdg",
    "fxm_rmks",
    "ge06_notice_group",
    "ge06_adm_affected_broad",
    "ge06_affected_os",
    "ref_stn_cls",
    "ref_stn_cls_nat_srv",
    "ref_nat_srv",
    "ref_notice_typ",
    "ref_adm",
)

_TERRA_BIGINT = ("terrakey", "geo_key", "target", "ant_key", "terrakey_os", "groupkey", "fs_contourkey")
_TERRA_DOUBLE = (
    "freq_assgn",
    "freq_min",
    "freq_max",
    "freq_carr",
    "bdwdth",
    "lat_dec",
    "long_dec",
    "radius",
    "pwr_dbw",
    "gain_max",
    "hgt_agl",
    "eff_hgtmax",
    "azm_max_e",
    "bmwdth",
    "site_alt",
    "azm",
    "attn",
)
_TERRA_INTEGER = ("pub_no",)


def _terra_column_type(name: str) -> str:
    if name in _TERRA_BIGINT:
        return "BIGINT"
    if name in _TERRA_DOUBLE:
        return "DOUBLE"
    if name in _TERRA_INTEGER:
        return "INTEGER"
    # mdb_export writes dates as `%Y-%m-%d %H:%M:%S` (four-digit years), so no century pivot is needed.
    if name.startswith("d_"):
        return "TIMESTAMP"
    return "VARCHAR"


def terra_issue_no(path: Path) -> int | None:
    m = _TERRA_ISSUE_RE.match(path.name)
    return int(m.group(1)) if m else None


def discover_terra_issues(settings: Settings, project_root: Path | None = None) -> dict[int, Path]:
    """Terrestrial BR IFIC databases in `terra_download_dir/<no>/`, then the project root."""
    project_root = project_root or PROJECT_ROOT
    found: dict[int, Path] = {}
    candidates = [
        *sorted(settings.terra_download_dir.glob("*/brific*.mdb")),
        *sorted(project_root.glob("brific*.mdb")),
    ]
    for path in candidates:
        no = terra_issue_no(path)
        if no is not None and path.is_file():
            found.setdefault(no, path)
    return dict(sorted(found.items()))


def ensure_terra_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS terra")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS terra.issue (
            ific_no          INTEGER PRIMARY KEY,
            path             VARCHAR NOT NULL,
            sha256           VARCHAR NOT NULL,
            bytes            BIGINT  NOT NULL,
            assignment_count BIGINT  NOT NULL,
            filters          VARCHAR NOT NULL,
            loaded_at        TIMESTAMPTZ NOT NULL
        )
        """
    )


def terra_manifest_filters() -> str:
    return f"tables: {','.join(sorted(TERRA_TABLES))}"


def _columns(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> dict[str, str]:
    return dict(
        con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = ?",
            [schema, table],
        ).fetchall()
    )


def _load_terra_table(con: duckdb.DuckDBPyConnection, ific_no: int, table: str, csv_path: Path) -> int:
    """Load one export as text, then cast each typed column.

    Column types never change with the data, so one issue's odd value cannot change how other issues are
    read. A value that does not cast is stored as NULL and its text kept in `<col>_raw` (logged once); rows
    are never dropped.
    """
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        header = next(csv.reader(f), None)
    if not header:
        raise IngestError(f"{table}: export is empty (no header row)")
    bad = [c for c in header if not _COLUMN_RE.match(c)]
    if bad:
        raise IngestError(f"{table}: unexpected column names {bad[:3]}")
    existing = _columns(con, "terra", table)
    wanted = {c: existing.get(c, _terra_column_type(c)) for c in header}
    raw = "_terra_raw"
    varchar_cols = "{" + ", ".join(f"'{c}': 'VARCHAR'" for c in header) + "}"
    con.execute(
        f"CREATE OR REPLACE TEMP TABLE {raw} AS SELECT * FROM read_csv(?, header = true, "
        f"auto_detect = false, columns = {varchar_cols}, quote = '\"', escape = '\"')",
        [str(csv_path)],
    )
    types: dict[str, str] = dict(wanted)
    raw_cols: list[str] = []
    for col, typ in wanted.items():
        if typ != "VARCHAR" and not col.endswith("_raw"):
            failed = con.execute(
                f'SELECT count(*) FROM {raw} WHERE "{col}" IS NOT NULL AND TRY_CAST("{col}" AS {typ}) IS NULL'
            ).fetchone()[0]
            if failed:
                log.warning(
                    "terra brific=%d %s.%s: %d values do not cast to %s; stored as NULL, text in %s_raw",
                    ific_no, table, col, failed, typ, col,
                )  # fmt: skip
                raw_cols.append(col)
    if not existing:
        cols = ", ".join(f'"{c}" {t}' for c, t in types.items())
        con.execute(f'CREATE TABLE terra."{table}" (ific_no INTEGER NOT NULL, {cols})')
        existing = _columns(con, "terra", table)
    for col, typ in [*types.items(), *((f"{c}_raw", "VARCHAR") for c in raw_cols)]:
        if col not in existing:
            con.execute(f'ALTER TABLE terra."{table}" ADD COLUMN "{col}" {typ}')
    select = ", ".join(
        f'"{c}"' if t == "VARCHAR" else f'TRY_CAST("{c}" AS {t}) AS "{c}"' for c, t in types.items()
    )
    for c in raw_cols:
        select += f', CASE WHEN TRY_CAST("{c}" AS {types[c]}) IS NULL THEN "{c}" END AS "{c}_raw"'
    con.execute(
        f'INSERT INTO terra."{table}" BY NAME SELECT {ific_no}::INTEGER AS ific_no, {select} FROM {raw}'
    )
    con.execute(f"DROP TABLE {raw}")
    return con.execute(f'SELECT count(*) FROM terra."{table}" WHERE ific_no = ?', [ific_no]).fetchone()[0]


def ensure_terra_issue(
    con: duckdb.DuckDBPyConnection, ific_no: int, path: Path, export: Exporter | None = None
) -> IssueStatus:
    """Load one terrestrial BR IFIC issue into `terra`; same no-op and atomic-replace rules as `ensure_issue`.

    `IssueStatus.notices` counts the issue's `fxm_terra` rows.
    """
    export = export or mdb_export
    started = time.perf_counter()
    if not path.is_file():
        raise IngestError(f"BR IFIC {ific_no}: {path} not found")
    ensure_terra_schema(con)
    sha = _sha256(path)
    manifest = con.execute(
        "SELECT sha256, assignment_count, filters FROM terra.issue WHERE ific_no = ?", [ific_no]
    ).fetchone()
    if manifest and manifest[0] == sha and manifest[2] == terra_manifest_filters():
        ms = round((time.perf_counter() - started) * 1000)
        log.info("brific=%d up to date (%d assignments, %d ms)", ific_no, manifest[1], ms)
        return IssueStatus(ific_no, "up_to_date", manifest[1], ms)

    with tempfile.TemporaryDirectory(prefix=f"brific{ific_no}-") as tmp:
        exports: dict[str, Path] = {}
        for table in TERRA_TABLES:
            out = Path(tmp) / f"{table}.csv"
            export(path, table, out)
            exports[table] = out
        con.execute("BEGIN TRANSACTION")
        try:
            counts: dict[str, int] = {}
            for table, out in exports.items():
                if _columns(con, "terra", table):
                    con.execute(f'DELETE FROM terra."{table}" WHERE ific_no = ?', [ific_no])
                counts[table] = _load_terra_table(con, ific_no, table, out)
            con.execute(
                "INSERT OR REPLACE INTO terra.issue VALUES (?, ?, ?, ?, ?, ?, current_timestamp)",
                [
                    ific_no,
                    _display(path),
                    sha,
                    path.stat().st_size,
                    counts["fxm_terra"],
                    terra_manifest_filters(),
                ],
            )
            con.execute("COMMIT")
        except BaseException as e:
            con.execute("ROLLBACK")
            log.exception("brific=%d load failed, previous rows kept", ific_no)
            if isinstance(e, duckdb.Error):
                raise IngestError(f"BR IFIC {ific_no}: load failed: {e}") from e
            raise
    ms = round((time.perf_counter() - started) * 1000)
    log.info(
        "brific=%d tables=%d assignments=%d duration_ms=%d",
        ific_no,
        len(TERRA_TABLES),
        counts["fxm_terra"],
        ms,
    )
    return IssueStatus(ific_no, "loaded", counts["fxm_terra"], ms)


def terra_table_counts(con: duckdb.DuckDBPyConnection, ific_no: int) -> dict[str, int]:
    return {
        t: con.execute(f'SELECT count(*) FROM terra."{t}" WHERE ific_no = ?', [ific_no]).fetchone()[0]
        for t in TERRA_TABLES
    }


def ingested_terra_issues(con: duckdb.DuckDBPyConnection) -> dict[int, tuple[str, int]]:
    ensure_terra_schema(con)
    return {
        no: (p, n)
        for no, p, n in con.execute("SELECT ific_no, path, assignment_count FROM terra.issue").fetchall()
    }
