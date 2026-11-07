"""Special-interest stations as GeoJSON, each with an ITU-R P.1546 field-strength contour.

The contour radius is the distance at which the predicted field strength falls to a threshold: the
T/R 25-08 coordination trigger where that recommendation covers the TX frequency, otherwise the caller's
threshold. Predictions assume an all-land path over flat terrain (``h1`` = antenna height above ground),
a rural receiver at 10 m, 50 % locations and an omnidirectional antenna at the station's maximum e.r.p.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated, Any, Literal

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from ific import special_interest
from ific.propagation import p1546, tr2508

log = logging.getLogger("ific.stations")

router = APIRouter(prefix="/api/stations", tags=["stations"])

TIME_PCTS = (1, 10, 50)
DEFAULT_TIME_PCT = 10
DEFAULT_THRESHOLD_DBUV = 30.0
THRESHOLD_RANGE_DBUV = (-20.0, 120.0)
H2_M = 10.0
LOC_PCT = 50.0
RX_ENV: p1546.RxEnv = "rural"
D_MIN_KM, D_MAX_KM = 1.0, 1000.0
# TX-frequency colour bins follow where the disc's meaning changes:
#   0  below 30 MHz       no disc, below ITU-R P.1546
#   1  30-470 MHz         disc to the T/R 25-08 trigger (its upper limit is inclusive)
#   2  470 MHz-1 GHz      disc to the map threshold
#   3  1-4 GHz            disc to the map threshold (P.1546's upper limit is inclusive)
#   4  above 4 GHz        no disc, above ITU-R P.1546
# The 1 GHz split only breaks up the large 470-4000 MHz group; it carries no regulatory meaning.
BAND_LIMITS_HZ = (p1546.F_RANGE_MHZ[0] * 1e6, tr2508.RANGE_MHZ[1] * 1e6, 1e9, p1546.F_RANGE_MHZ[1] * 1e6)

ContourBound = Literal["exact", "below_1km", "at_least_1000km"]
NoContourReason = Literal[
    "missing_tx_frequency",
    "outside_p1546_range",
    "no_power",
    "unsupported_power_type",
    "missing_antenna_height",
    "antenna_height_out_of_range",
]


def get_db(request: Request) -> Iterator[duckdb.DuckDBPyConnection]:
    cursor = request.app.state.db.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


Db = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]


class ContourOut(BaseModel):
    radius_km: float
    bound: ContourBound
    threshold_dbuv: float
    threshold_source: Literal["tr2508", "user"]
    threshold_citation: str | None
    threshold_note: str | None
    time_pct: float
    loc_pct: float
    h1_m: float
    h2_m: float
    erp_dbw: float
    f_mhz: float
    assumptions: list[str]


class StationProps(BaseModel):
    source_row: int
    station_no: int
    licence_class: str | None
    tx_hz: int | None
    rx_hz: int | None
    bandwidth_hz: int | None
    effective_agl_m: float | None
    effective_asl_m: float | None
    ground_height_m: float | None
    azimuth_deg: float | None
    directivity: str | None
    ant_gain_db: float | None
    polarisation: str | None
    emission_class: str | None
    radiated_power_dbw: float | None
    band_bin: int | None
    m4_services: list[str]
    quality_flags: list[str]
    contour: ContourOut | None
    no_contour_reason: NoContourReason | None


class PointGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]


class StationFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: int
    geometry: PointGeometry
    properties: StationProps


class ModelOut(BaseModel):
    p1546_version: str
    p1546_reference: str
    tr2508_citation: str
    tr2508_range_mhz: tuple[float, float]
    time_pct: float
    loc_pct: float
    h2_m: float
    rx_env: str
    path: str
    terrain: str
    antenna: str
    user_threshold_dbuv: float
    radius_range_km: tuple[float, float]


class StationCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    model: ModelOut
    features: list[StationFeature]


class OverlapOut(BaseModel):
    side: str
    m4_id: int
    overlap_lower_hz: int
    overlap_upper_hz: int
    services_in_finland: str | None
    sub_band_usage: str | None
    class_of_station: str | None
    direction: str | None


class StationDetail(StationFeature):
    raw: dict[str, Any]
    m4_overlaps: list[OverlapOut]
    p1546_steps: dict[str, float] | None
    model: ModelOut


_PROP_COLUMNS = [
    "source_row",
    "station_no",
    "licence_class",
    "lon",
    "lat",
    "tx_hz",
    "rx_hz",
    "bandwidth_hz",
    "effective_agl_m",
    "effective_asl_m",
    "ground_height_m",
    "azimuth_deg",
    "directivity",
    "ant_gain_db",
    "polarisation",
    "emission_class",
    "radiated_power_dbw",
    "radiated_power_type",
    "quality_flags",
]
_RAW_COLUMNS = [
    "channel_bandwidth",
    "tx_frequency",
    "rx_frequency",
    "transmission_bandwidth",
    "mast_height_m",
    "mast_type",
    "ant_agl_m",
    "ant_asl_m",
    "radiated_power",
    "radiated_power_type",
    "radiated_power_unit",
    "feeder_loss_db",
]


def band_bin(tx_hz: int | None) -> int | None:
    if tx_hz is None:
        return None
    p1546_lo, tr2508_hi, split, p1546_hi = BAND_LIMITS_HZ
    if tx_hz < p1546_lo:
        return 0
    if tx_hz <= tr2508_hi:
        return 1
    if tx_hz < split:
        return 2
    if tx_hz <= p1546_hi:
        return 3
    return 4


def _field(f_mhz: float, t_pct: float, d_km: float, h1_m: float, erp_dbw: float) -> p1546.FieldResult:
    return p1546.field_strength(
        f_mhz,
        t_pct,
        [("land", d_km)],
        h1_m=h1_m,
        h2_m=H2_M,
        erp_dbw=erp_dbw,
        loc_pct=LOC_PCT,
        rx_env=RX_ENV,
        ha_m=h1_m,
    )


@lru_cache(maxsize=16384)
def solve_radius(
    f_mhz: float, t_pct: float, h1_m: float, erp_dbw: float, threshold_dbuv: float
) -> tuple[float, ContourBound]:
    """Distance in km where E falls to the threshold, by bisection in log-distance over 1-1000 km."""

    def e(d: float) -> float:
        return _field(f_mhz, t_pct, d, h1_m, erp_dbw).e_dbuv_m

    if e(D_MIN_KM) < threshold_dbuv:
        return D_MIN_KM, "below_1km"
    if e(D_MAX_KM) >= threshold_dbuv:
        return D_MAX_KM, "at_least_1000km"
    lo, hi = math.log(D_MIN_KM), math.log(D_MAX_KM)
    while hi - lo > 1e-7:
        mid = (lo + hi) / 2
        if e(math.exp(mid)) >= threshold_dbuv:
            lo = mid
        else:
            hi = mid
    return math.exp((lo + hi) / 2), "exact"


def contour(
    row: dict[str, Any], time_pct: float, user_threshold_dbuv: float
) -> tuple[ContourOut | None, NoContourReason | None]:
    tx_hz = row["tx_hz"]
    if tx_hz is None:
        return None, "missing_tx_frequency"
    f_mhz = tx_hz / 1e6
    if not (p1546.F_RANGE_MHZ[0] <= f_mhz <= p1546.F_RANGE_MHZ[1]):
        return None, "outside_p1546_range"
    if row["effective_agl_m"] is None:
        return None, "missing_antenna_height"
    if row["effective_agl_m"] > p1546.H1_MAX_M:
        return None, "antenna_height_out_of_range"
    if row["radiated_power_dbw"] is None:
        return None, "no_power"
    assumptions = ["h1_flat_terrain", "path_assumed_land"]
    if row["radiated_power_type"] is None:
        assumptions.append("power_type_assumed_erp")
    elif row["radiated_power_type"] != "E":
        return None, "unsupported_power_type"
    if row["directivity"] == "D":
        assumptions.append("omni_worst_case")

    trig = tr2508.trigger(f_mhz, row["bandwidth_hz"])
    if trig is not None:
        threshold, source, citation, note = trig.e_dbuv_m, "tr2508", trig.citation, trig.note
        if time_pct != tr2508.TIME_PCT:
            assumptions.append("tr2508_time_differs")
    else:
        threshold, source, citation, note = user_threshold_dbuv, "user", None, None

    h1 = row["effective_agl_m"]
    erp = row["radiated_power_dbw"]
    radius, bound = solve_radius(f_mhz, time_pct, h1, erp, threshold)
    engine = _field(f_mhz, time_pct, radius, h1, erp)
    return (
        ContourOut(
            radius_km=radius,
            bound=bound,
            threshold_dbuv=threshold,
            threshold_source=source,
            threshold_citation=citation,
            threshold_note=note,
            time_pct=time_pct,
            loc_pct=LOC_PCT,
            h1_m=h1,
            h2_m=H2_M,
            erp_dbw=erp,
            f_mhz=f_mhz,
            assumptions=[*assumptions, *engine.assumptions],
        ),
        None,
    )


def _model(time_pct: float, user_threshold_dbuv: float) -> ModelOut:
    return ModelOut(
        p1546_version=p1546.VERSION,
        p1546_reference=p1546.REFERENCE,
        tr2508_citation=tr2508.CITATION,
        tr2508_range_mhz=tr2508.RANGE_MHZ,
        time_pct=time_pct,
        loc_pct=LOC_PCT,
        h2_m=H2_M,
        rx_env=RX_ENV,
        path="land",
        terrain="flat (h1 = antenna height above ground)",
        antenna="omnidirectional at maximum e.r.p.",
        user_threshold_dbuv=user_threshold_dbuv,
        radius_range_km=(D_MIN_KM, D_MAX_KM),
    )


def _rows(con: duckdb.DuckDBPyConnection, source_row: int | None = None) -> list[dict[str, Any]]:
    cols = list(dict.fromkeys(_PROP_COLUMNS + _RAW_COLUMNS))
    # A station without a position cannot be a GeoJSON point; the parser flags such rows, the map omits them.
    where = "WHERE s.lon IS NOT NULL AND s.lat IS NOT NULL" + (
        " AND s.source_row = ?" if source_row is not None else ""
    )
    sql = f"""
        SELECT {", ".join(f"s.{c}" for c in cols)},
               coalesce((SELECT list(DISTINCT o.services_in_finland ORDER BY o.services_in_finland)
                         FROM {special_interest.OVERLAP_VIEW} o
                         WHERE o.source_row = s.source_row AND o.side = 'tx'
                           AND o.services_in_finland IS NOT NULL), []) AS m4_services
        FROM {special_interest.TABLE} s {where}
        ORDER BY s.source_row
    """
    cur = con.execute(sql, [source_row] if source_row is not None else [])
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]


def _feature(row: dict[str, Any], time_pct: float, threshold_dbuv: float) -> StationFeature:
    c, reason = contour(row, time_pct, threshold_dbuv)
    props = StationProps(
        **{k: row[k] for k in StationProps.model_fields if k in row},
        band_bin=band_bin(row["tx_hz"]),
        contour=c,
        no_contour_reason=reason,
    )
    return StationFeature(
        id=row["source_row"], geometry=PointGeometry(coordinates=(row["lon"], row["lat"])), properties=props
    )


def _check_time_pct(time_pct: int) -> None:
    if time_pct not in TIME_PCTS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"time_pct must be one of {TIME_PCTS}")


TimePct = Annotated[int, Query(description="Time percentage: 1, 10 or 50")]
Threshold = Annotated[
    float,
    Query(
        ge=THRESHOLD_RANGE_DBUV[0],
        le=THRESHOLD_RANGE_DBUV[1],
        description="dB(uV/m), used where T/R 25-08 does not apply",
    ),
]


@router.get("", response_model=StationCollection)
def list_stations(
    con: Db, time_pct: TimePct = DEFAULT_TIME_PCT, threshold_dbuv: Threshold = DEFAULT_THRESHOLD_DBUV
) -> StationCollection:
    _check_time_pct(time_pct)
    started = time.perf_counter()
    features = [_feature(row, time_pct, threshold_dbuv) for row in _rows(con)]
    log.info(
        "stations: %d features, time_pct=%s threshold=%s in %.3f s (radius cache %s)",
        len(features),
        time_pct,
        threshold_dbuv,
        time.perf_counter() - started,
        solve_radius.cache_info(),
    )
    return StationCollection(model=_model(time_pct, threshold_dbuv), features=features)


@router.get("/{source_row}", response_model=StationDetail)
def get_station(
    con: Db,
    source_row: int,
    time_pct: TimePct = DEFAULT_TIME_PCT,
    threshold_dbuv: Threshold = DEFAULT_THRESHOLD_DBUV,
) -> StationDetail:
    _check_time_pct(time_pct)
    rows = _rows(con, source_row)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no station with source_row {source_row}")
    row = rows[0]
    feature = _feature(row, time_pct, threshold_dbuv)
    c = feature.properties.contour
    steps = _field(c.f_mhz, c.time_pct, c.radius_km, c.h1_m, c.erp_dbw).steps if c else None
    overlaps = con.execute(
        f"""
        SELECT side, m4_id, overlap_lower_hz, overlap_upper_hz, services_in_finland, sub_band_usage,
               class_of_station, direction
        FROM {special_interest.OVERLAP_VIEW} WHERE source_row = ? ORDER BY side DESC, overlap_lower_hz, m4_id
        """,
        [source_row],
    )
    names = [d[0] for d in overlaps.description]
    return StationDetail(
        **feature.model_dump(),
        raw={k: row[k] for k in _RAW_COLUMNS},
        m4_overlaps=[OverlapOut(**dict(zip(names, r, strict=True))) for r in overlaps.fetchall()],
        p1546_steps=steps,
        model=_model(time_pct, threshold_dbuv),
    )
