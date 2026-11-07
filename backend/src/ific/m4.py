import hashlib
import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Literal

import duckdb
import pypdf

from ific.config import Settings

log = logging.getLogger("ific.db")

_FREQ_RE = re.compile(r"^([\d.]+)\s*(Hz|kHz|MHz|GHz)$")
_FREQ_SCALE = {"Hz": 1, "kHz": 10**3, "MHz": 10**6, "GHz": 10**9}
_EDITION_RE = re.compile(r"RADIO FREQUENCY REGULATION (\d+ [A-Z]+/\d{4}M)")

REGULATION_DOC = "m4-radio-frequency-regulation-en"
NOTES_DOC = "m4-explanatory-notes-en"

# (JSON field, column, SQL type)
_ALLOCATION_FIELDS: list[tuple[str, str, str]] = [
    ("ID", "id", "BIGINT PRIMARY KEY"),
    ("Frequency_band_lower_limit", "frequency_band_lower_limit", "VARCHAR"),
    ("Frequency_band_upper_limit", "frequency_band_upper_limit", "VARCHAR"),
    ("Services_in_Finland", "services_in_finland", "VARCHAR"),
    ("Additional_information", "additional_information", "VARCHAR"),
    ("Sub_band_lower_limit", "sub_band_lower_limit", "VARCHAR"),
    ("Sub_band_upper_limit", "sub_band_upper_limit", "VARCHAR"),
    ("Sub_band_lower_limit__Hz_", "sub_band_lower_hz", "BIGINT NOT NULL"),
    ("Sub_band_upper_limit__Hz_", "sub_band_upper_hz", "BIGINT NOT NULL"),
    ("Sub_band_width", "sub_band_width", "VARCHAR"),
    ("Sub_band_usage", "sub_band_usage", "VARCHAR"),
    ("Mode_of_traffic", "mode_of_traffic", "VARCHAR"),
    ("Class_of_station", "class_of_station", "VARCHAR"),
    ("Direction", "direction", "VARCHAR"),
    ("Radiated_power", "radiated_power", "VARCHAR"),
    ("Transmitter_power", "transmitter_power", "BIGINT"),
    ("Channel_spacing", "channel_spacing", "VARCHAR"),
    ("Bandwidth", "bandwidth", "VARCHAR"),
    ("Duplex_separation", "duplex_separation", "VARCHAR"),
    ("Duplex_band_lower_limit", "duplex_band_lower_limit", "VARCHAR"),
    ("Duplex_band_upper_limit", "duplex_band_upper_limit", "VARCHAR"),
    ("Class_of_emission", "class_of_emission", "VARCHAR"),
    ("Standard_type", "standard_type", "VARCHAR"),
    ("Comment", "comment", "VARCHAR"),
]
# (parsed column, JSON limit-string field)
_PARSED_LIMITS: list[tuple[str, str]] = [
    ("band_lower_hz", "Frequency_band_lower_limit"),
    ("band_upper_hz", "Frequency_band_upper_limit"),
    ("duplex_lower_hz", "Duplex_band_lower_limit"),
    ("duplex_upper_hz", "Duplex_band_upper_limit"),
]


@dataclass(frozen=True)
class SourceStatus:
    source_id: str
    action: Literal["loaded", "up_to_date"]
    rows: int
    ms: int


@dataclass(frozen=True)
class _Source:
    source_id: str
    path: Path
    table: str
    rows_where: str
    load: Callable[[duckdb.DuckDBPyConnection, Path], int]
    # Bump when parsing rules change so an unchanged file is still reloaded.
    parser_version: str = ""


def parse_freq_hz(s: str) -> int | None:
    if s == "":
        return None
    m = _FREQ_RE.match(s.strip())
    if not m:
        raise ValueError(f"unparseable frequency: {s!r}")
    hz = Decimal(m.group(1)) * _FREQ_SCALE[m.group(2)]
    if hz != hz.to_integral_value():
        raise ValueError(f"frequency is not a whole number of Hz: {s!r}")
    return int(hz)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pages(path: Path) -> list[str]:
    if path.suffix == ".txt":
        pages = path.read_text(encoding="utf-8").split("\f")
    else:
        pages = [page.extract_text() or "" for page in pypdf.PdfReader(path).pages]
    while pages and not pages[-1].strip():
        pages.pop()
    if not pages:
        raise ValueError(f"no text extracted from {path}")
    return pages


def _doc_path(m4_dir: Path, doc_id: str) -> Path:
    txt = m4_dir / f"{doc_id}.txt"
    return txt if txt.exists() else m4_dir / f"{doc_id}.pdf"


def _allocation_rows(path: Path) -> list[tuple]:
    records = json.loads(path.read_text(encoding="utf-8"))["value"]
    expected = {field for field, _, _ in _ALLOCATION_FIELDS}
    rows = []
    for rec in records:
        if set(rec) != expected:
            raise ValueError(
                f"{path}: ID {rec.get('ID')} has unexpected fields {sorted(set(rec) ^ expected)}"
            )
        try:
            parsed = [parse_freq_hz(rec[field]) for _, field in _PARSED_LIMITS]
        except ValueError as e:
            raise ValueError(f"{path}: ID {rec['ID']}: {e}") from e
        if rec["Sub_band_lower_limit__Hz_"] > rec["Sub_band_upper_limit__Hz_"]:
            raise ValueError(f"{path}: ID {rec['ID']}: sub-band lower limit exceeds upper limit")
        rows.append((*(rec[field] for field, _, _ in _ALLOCATION_FIELDS), *parsed))
    return rows


def replace_table(
    con: duckdb.DuckDBPyConnection, table: str, columns: Sequence[tuple[str, str]], rows: Sequence[tuple]
) -> int:
    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(f"CREATE TABLE {table} ({', '.join(f'{col} {typ}' for col, typ in columns)})")
    if not rows:
        return 0
    # One columnar insert: row-wise executemany costs seconds for ~6k rows.
    unnests = ", ".join(f"unnest(?::{typ.split()[0]}[])" for _, typ in columns)
    con.execute(f"INSERT INTO {table} SELECT {unnests}", [list(col) for col in zip(*rows, strict=True)])
    return len(rows)


def _load_allocation(con: duckdb.DuckDBPyConnection, path: Path) -> int:
    columns = [(col, typ) for _, col, typ in _ALLOCATION_FIELDS]
    columns += [(col, "BIGINT") for col, _ in _PARSED_LIMITS]
    return replace_table(con, "ref.m4_allocation", columns, _allocation_rows(path))


def _page_loader(doc_id: str) -> Callable[[duckdb.DuckDBPyConnection, Path], int]:
    def load(con: duckdb.DuckDBPyConnection, path: Path) -> int:
        pages = _pages(path)
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS ref.m4_page (
                doc_id  VARCHAR NOT NULL,
                page_no INTEGER NOT NULL,
                text    VARCHAR NOT NULL,
                PRIMARY KEY (doc_id, page_no)
            )
            """
        )
        con.execute("DELETE FROM ref.m4_page WHERE doc_id = ?", [doc_id])
        con.executemany(
            "INSERT INTO ref.m4_page VALUES (?, ?, ?)",
            [(doc_id, i, text) for i, text in enumerate(pages, start=1)],
        )
        return len(pages)

    return load


def _edition(regulation_path: Path) -> str:
    for page in _pages(regulation_path):
        if m := _EDITION_RE.search(page):
            return m.group(1)
    raise ValueError(f"{regulation_path}: M4 edition header not found")


def _table_rows(con: duckdb.DuckDBPyConnection, table: str, where: str) -> int | None:
    schema, name = table.split(".")
    exists = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = ? AND table_name = ?", [schema, name]
    ).fetchone()
    if not exists:
        return None
    return con.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]


def _ensure_source(
    con: duckdb.DuckDBPyConnection, src: _Source, data_dir: Path, edition: Callable[[], str]
) -> SourceStatus:
    started = time.perf_counter()
    sha = _sha256(src.path) + (f":{src.parser_version}" if src.parser_version else "")
    manifest = con.execute(
        "SELECT sha256, row_count FROM ref.source WHERE source_id = ?", [src.source_id]
    ).fetchone()
    if manifest and manifest[0] == sha and _table_rows(con, src.table, src.rows_where) == manifest[1]:
        ms = round((time.perf_counter() - started) * 1000)
        log.info("%s: up to date (%d rows, %d ms)", src.source_id, manifest[1], ms)
        return SourceStatus(src.source_id, "up_to_date", manifest[1], ms)

    con.execute("BEGIN TRANSACTION")
    try:
        rows = src.load(con, src.path)
        con.execute(
            """
            INSERT OR REPLACE INTO ref.source
            VALUES (?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            [
                src.source_id,
                src.path.relative_to(data_dir).as_posix(),
                sha,
                src.path.stat().st_size,
                edition(),
                rows,
            ],
        )
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        log.exception("%s: load failed, previous data kept", src.source_id)
        raise
    ms = round((time.perf_counter() - started) * 1000)
    log.info("%s: loaded %d rows from %s (%d ms)", src.source_id, rows, src.path, ms)
    return SourceStatus(src.source_id, "loaded", rows, ms)


def ensure_m4(con: duckdb.DuckDBPyConnection, settings: Settings) -> list[SourceStatus]:
    regulation = _doc_path(settings.m4_dir, REGULATION_DOC)
    edition = cache(lambda: _edition(regulation))
    sources: Sequence[_Source] = [
        _Source("m4_allocation", settings.m4_allocation_json, "ref.m4_allocation", "TRUE", _load_allocation),
        _Source(
            "m4_regulation",
            regulation,
            "ref.m4_page",
            f"doc_id = '{REGULATION_DOC}'",
            _page_loader(REGULATION_DOC),
        ),
        _Source(
            "m4_notes",
            _doc_path(settings.m4_dir, NOTES_DOC),
            "ref.m4_page",
            f"doc_id = '{NOTES_DOC}'",
            _page_loader(NOTES_DOC),
        ),
    ]
    for src in sources:
        if not src.path.is_file():
            raise FileNotFoundError(
                f"M4 source {src.source_id} not found at {src.path}; set IFIC_DATA_DIR to the data directory"
            )
    return [_ensure_source(con, src, settings.data_dir, edition) for src in sources]
