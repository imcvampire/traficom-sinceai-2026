"""Synthetic table of Finnish frequencies of special interest, one row per station assignment.

The CSV is a one-time conversion of the challenge XLSX: English header only, plus a `source_row`
column holding the original Excel row number so findings can cite the spreadsheet directly.
"""

import csv
import logging
import math
import re
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import duckdb

from ific.config import Settings
from ific.m4 import SourceStatus, _ensure_source, _Source, parse_freq_hz, replace_table

log = logging.getLogger("ific.db")

SOURCE_ID = "special_interest_station"
TABLE = "ref.special_interest_station"
OVERLAP_VIEW = "ref.special_interest_m4_overlap"

PARSER_VERSION = "2"
MIN_AGL_M = 1.0
# Traficom: licence class carries no analysis meaning; unlabelled rows count as "others".
DEFAULT_LICENCE_CLASS = "MUUT"
ASL_TOLERANCE_M = 1.0
# Generous box around mainland Finland and Åland; the source warns some synthetic points fall outside.
FINLAND_BBOX = {"lat": (59.5, 70.1), "lon": (19.0, 31.6)}

_HEADER = [
    "source_row",
    "Station number",
    "Class of licence",
    "Longitude",
    "Latitude",
    "Ground height (m)",
    "Mast height (m)",
    "Mast type",
    "Channel bandwidth",
    "TX frequency",
    "RX frequency",
    "Ant height AGL (m)",
    "Ant height ASL (m)",
    "Ant gain (dB)",
    "Class of transmission",
    "Transmission bandwidth",
    "Radiation direction (°)",
    "Polarisation",
    "Radioation power",
    "Radioation power (ITU)",
    "Radiation power unit",
    "Transmission line (dB)",
    "Directivity",
]

COLUMNS: list[tuple[str, str]] = [
    ("source_row", "INTEGER PRIMARY KEY"),
    ("station_no", "BIGINT NOT NULL"),
    ("licence_class", "VARCHAR"),
    ("lon", "DOUBLE"),
    ("lat", "DOUBLE"),
    ("ground_height_m", "DOUBLE"),
    ("mast_height_m", "DOUBLE"),
    ("mast_type", "VARCHAR"),
    ("channel_bandwidth", "VARCHAR"),
    ("tx_frequency", "VARCHAR"),
    ("rx_frequency", "VARCHAR"),
    ("ant_agl_m", "DOUBLE"),
    ("ant_asl_m", "DOUBLE"),
    ("ant_gain_db", "DOUBLE"),
    ("emission_class", "VARCHAR"),
    ("transmission_bandwidth", "VARCHAR"),
    ("azimuth_deg", "DOUBLE"),
    ("polarisation", "VARCHAR"),
    ("radiated_power", "DOUBLE"),
    ("radiated_power_type", "VARCHAR"),
    ("radiated_power_unit", "VARCHAR"),
    ("feeder_loss_db", "DOUBLE"),
    ("directivity", "VARCHAR"),
    ("tx_hz", "BIGINT"),
    ("rx_hz", "BIGINT"),
    ("bandwidth_hz", "BIGINT"),
    ("tx_lower_hz", "BIGINT"),
    ("tx_upper_hz", "BIGINT"),
    ("rx_lower_hz", "BIGINT"),
    ("rx_upper_hz", "BIGINT"),
    ("effective_agl_m", "DOUBLE"),
    ("effective_asl_m", "DOUBLE"),
    ("radiated_power_dbw", "DOUBLE"),
    ("quality_flags", "VARCHAR[] NOT NULL"),
]

_DESIGNATOR_RE = re.compile(r"(\d+(?:\.\d+)?)([HKMG])(\d*)")
_DESIGNATOR_SCALE = {"H": 1, "K": 10**3, "M": 10**6, "G": 10**9}
_POWER_TO_W = {"mW": 1e-3, "W": 1.0, "kW": 1e3}
_EDITION_RE = re.compile(r"_(v\d{8})$")

_OVERLAP_VIEW_SQL = f"""
CREATE OR REPLACE VIEW {OVERLAP_VIEW} AS
WITH band AS (
    SELECT source_row, station_no, licence_class, 'tx' AS side,
           tx_lower_hz AS lower_hz, tx_upper_hz AS upper_hz
    FROM {TABLE} WHERE tx_lower_hz IS NOT NULL
    UNION ALL
    SELECT source_row, station_no, licence_class, 'rx', rx_lower_hz, rx_upper_hz
    FROM {TABLE} WHERE rx_lower_hz IS NOT NULL
)
SELECT
    b.source_row,
    b.station_no,
    b.licence_class,
    b.side,
    b.lower_hz,
    b.upper_hz,
    a.id AS m4_id,
    greatest(b.lower_hz, a.sub_band_lower_hz) AS overlap_lower_hz,
    least(b.upper_hz, a.sub_band_upper_hz) AS overlap_upper_hz,
    a.services_in_finland,
    a.sub_band_usage,
    a.class_of_station,
    a.direction
FROM band b
JOIN ref.m4_allocation a
  ON (b.lower_hz < a.sub_band_upper_hz AND b.upper_hz > a.sub_band_lower_hz)
  OR (b.lower_hz = b.upper_hz AND b.lower_hz BETWEEN a.sub_band_lower_hz AND a.sub_band_upper_hz)
"""


def parse_designator_bandwidth_hz(s: str) -> int | None:
    """Parse an ITU necessary-bandwidth designator such as `16K0`, `8M00`, `300k` or `7,6k`."""
    if s == "":
        return None
    m = _DESIGNATOR_RE.fullmatch(s.strip().replace(",", ".").upper())
    if not m or (m.group(3) and "." in m.group(1)):
        raise ValueError(f"unparseable bandwidth designator: {s!r}")
    digits = m.group(1) + (f".{m.group(3)}" if m.group(3) else "")
    hz = Decimal(digits) * _DESIGNATOR_SCALE[m.group(2)]
    if hz != hz.to_integral_value():
        raise ValueError(f"bandwidth designator is not a whole number of Hz: {s!r}")
    return int(hz)


def _band(center: int | None, bandwidth: int | None) -> tuple[int | None, int | None]:
    if center is None:
        return None, None
    if bandwidth is None:
        return center, center
    return center - bandwidth // 2, center + (bandwidth - bandwidth // 2)


class _Row:
    def __init__(self, rec: dict[str, str]) -> None:
        self.rec = rec
        self.flags: list[str] = []

    def text(self, col: str) -> str | None:
        return self.rec[col].strip() or None

    def parse[T](self, col: str, parser: Callable[[str], T]) -> T | None:
        value = self.text(col)
        if value is None:
            return None
        try:
            return parser(value)
        except ValueError:
            self.flags.append(f"unparseable:{col}")
            return None

    def num(self, col: str) -> float | None:
        return self.parse(col, float)


def _station_row(rec: dict[str, str]) -> tuple:
    r = _Row(rec)
    flags = r.flags

    licence_class = r.text("Class of licence")
    if licence_class is None:
        licence_class = DEFAULT_LICENCE_CLASS
        flags.append("licence_class_defaulted")

    lon, lat = r.num("Longitude"), r.num("Latitude")
    if lon is not None and lat is not None:
        (lat_min, lat_max), (lon_min, lon_max) = FINLAND_BBOX["lat"], FINLAND_BBOX["lon"]
        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
            flags.append("outside_finland_bbox")

    tx_hz = r.parse("TX frequency", parse_freq_hz)
    rx_hz = r.parse("RX frequency", parse_freq_hz)
    if tx_hz is None:
        flags.append("missing_tx_frequency")
    if rx_hz is None:
        flags.append("missing_rx_frequency")

    channel_bw = r.parse("Channel bandwidth", parse_freq_hz)
    designator_bw = r.parse("Transmission bandwidth", parse_designator_bandwidth_hz)
    # Traficom: when channel and transmission bandwidth disagree, the larger value is a dataset typo
    # (e.g. station 440557, 2500 kHz vs 118600k), so the smaller one is used.
    known_bw = [bw for bw in (channel_bw, designator_bw) if bw is not None]
    bandwidth_hz = min(known_bw, default=None)
    if channel_bw is None and designator_bw is not None:
        flags.append("bandwidth_from_designator")
    elif len(set(known_bw)) > 1:
        flags.append("bandwidth_mismatch")
    if bandwidth_hz is None:
        flags.append("missing_bandwidth")

    ground = r.num("Ground height (m)")
    agl, asl = r.num("Ant height AGL (m)"), r.num("Ant height ASL (m)")
    effective_agl = agl
    if agl is not None and agl < MIN_AGL_M:
        effective_agl = MIN_AGL_M
        flags.append("agl_clamped")
    effective_asl = asl
    if asl is None and ground is not None and effective_agl is not None:
        effective_asl = ground + effective_agl
        flags.append("asl_derived")
    elif None not in (asl, ground, agl) and abs(ground + agl - asl) > ASL_TOLERANCE_M:
        flags.append("asl_inconsistent")

    power, unit = r.num("Radioation power"), r.text("Radiation power unit")
    power_dbw = None
    if power is None:
        flags.append("missing_power")
    elif unit not in _POWER_TO_W:
        flags.append("unparseable:Radiation power unit")
    elif power <= 0:
        flags.append("nonpositive_power")
    else:
        power_dbw = 10 * math.log10(power * _POWER_TO_W[unit])

    return (
        int(rec["source_row"]),
        int(rec["Station number"]),
        licence_class,
        lon,
        lat,
        ground,
        r.num("Mast height (m)"),
        r.text("Mast type"),
        r.text("Channel bandwidth"),
        r.text("TX frequency"),
        r.text("RX frequency"),
        agl,
        asl,
        r.num("Ant gain (dB)"),
        r.text("Class of transmission"),
        r.text("Transmission bandwidth"),
        r.num("Radiation direction (°)"),
        r.text("Polarisation"),
        power,
        r.text("Radioation power (ITU)"),
        unit,
        r.num("Transmission line (dB)"),
        r.text("Directivity"),
        tx_hz,
        rx_hz,
        bandwidth_hz,
        *_band(tx_hz, bandwidth_hz),
        *_band(rx_hz, bandwidth_hz),
        effective_agl,
        effective_asl,
        power_dbw,
        flags,
    )


def station_rows(path: Path) -> list[tuple]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != _HEADER:
            raise ValueError(f"{path}: unexpected header {reader.fieldnames}")
        rows: list[tuple] = []
        seen: dict[tuple, int] = {}
        for rec in reader:
            if None in rec:
                raise ValueError(f"{path}: source_row {rec['source_row']} has extra fields")
            content = tuple(v for k, v in rec.items() if k != "source_row")
            if content in seen:
                log.warning(
                    "%s: source_row %s duplicates source_row %d, dropped",
                    SOURCE_ID,
                    rec["source_row"],
                    seen[content],
                )
                continue
            try:
                row = _station_row(rec)
            except ValueError as e:
                raise ValueError(f"{path}: source_row {rec['source_row']}: {e}") from e
            seen[content] = row[0]
            rows.append(row)
    return rows


def _load(con: duckdb.DuckDBPyConnection, path: Path) -> int:
    return replace_table(con, TABLE, COLUMNS, station_rows(path))


def _edition(path: Path) -> str | None:
    m = _EDITION_RE.search(path.stem)
    return m.group(1) if m else None


def ensure_special_interest(con: duckdb.DuckDBPyConnection, settings: Settings) -> SourceStatus:
    """Load the station table if the CSV changed, then (re)create the M4 overlap view.

    Must run after `m4.ensure_m4`: the view joins `ref.m4_allocation`.
    """
    path = settings.special_interest_csv
    if not path.is_file():
        raise FileNotFoundError(
            f"special-interest source not found at {path}; set IFIC_DATA_DIR to the data directory"
        )
    source = _Source(SOURCE_ID, path, TABLE, "TRUE", _load, PARSER_VERSION)
    status = _ensure_source(con, source, settings.data_dir, lambda: _edition(path))
    con.execute(_OVERLAP_VIEW_SQL)
    return status
