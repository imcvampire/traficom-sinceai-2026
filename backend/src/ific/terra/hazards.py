"""The `field_strength_border` hazard: P.1546 field strength from a foreign transmitter at Finnish border
points, compared with the criterion's trigger. Deterministic: Tier 1 is an all-sea worst case at the nearest
point, Tier 2 evaluates mixed land/sea paths at the nearest points.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from ific.propagation import p1546
from ific.riia.geometry import unit
from ific.terra import refdata
from ific.terra.method import (
    MAX_BORDER_POINTS,
    PATH_STEP_KM,
    SCREENING_RANGE_KM,
    TIER1_MARGIN_DB,
)
from ific.terra.relevance import _border, border_distances

HAZARD_ID = "field_strength_border"
RX_ENV: p1546.RxEnv = "rural"
SEA: p1546.PathKind = "sea_cold"
_LEN_ND = 3  # path segment lengths are rounded to 1 m before P.1546, so stored inputs reproduce E exactly


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360.0


def path_segments(lat1: float, lon1: float, lat2: float, lon2: float, d_km: float) -> list[tuple[str, float]]:
    """Great-circle path in 1 km steps, each step classified at its midpoint; runs merged into zones."""
    n = max(1, math.ceil(d_km / PATH_STEP_KM))
    a, b = unit(lat1, lon1), unit(lat2, lon2)
    omega = math.acos(min(1.0, max(-1.0, float(np.dot(a, b)))))
    f = (np.arange(n) + 0.5) / n
    if omega < 1e-12:
        pts = np.repeat(a[None, :], n, axis=0)
    else:
        pts = (np.sin((1 - f) * omega)[:, None] * a + np.sin(f * omega)[:, None] * b) / math.sin(omega)
    lat = np.degrees(np.arcsin(np.clip(pts[:, 2], -1, 1)))
    lon = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    land = refdata.is_land(lon, lat)
    step = d_km / n
    segs: list[list[Any]] = []
    for is_l in land.tolist():
        kind = "land" if is_l else SEA
        if segs and segs[-1][0] == kind:
            segs[-1][1] += 1
        else:
            segs.append([kind, 1])
    out = [(k, round(c * step, _LEN_ND)) for k, c in segs]
    k, last = out[-1]
    out[-1] = (k, round(round(d_km, _LEN_ND) - sum(length for _, length in out[:-1]), _LEN_ND))
    return out


def _attenuation(antenna: dict[str, Any], bearing: float) -> float:
    pattern = antenna.get("diagram") or []
    if not pattern:
        return 0.0
    az = np.array([p["azm"] for p in pattern], dtype=float)
    at = np.array([p["attn"] for p in pattern], dtype=float)
    return float(np.interp(bearing % 360.0, az, at, period=360.0))


def _field(f: float, t: float, path: list[tuple[str, float]], h1: float, h2: float, erp: float, loc: float):
    return p1546.field_strength(f, t, path, h1, h2, erp, loc, RX_ENV)


def _point(lat: float, lon: float, d: float, brg: float) -> dict[str, float]:
    return {"lat": lat, "lon": lon, "distance_km": d, "bearing_deg": brg}


def not_evaluated(outcome: str, reason: str) -> dict[str, Any]:
    return {"hazard_id": HAZARD_ID, "outcome": outcome, "reason": reason, "tier": 0}


def evaluate(a: dict[str, Any], criterion: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Evaluate one relevant TX assignment against its criterion; returns the hazard and assumption ids.

    An input P.1546 rejects (e.g. h1 below 1 m on a path with sea) gives `not_assessed` for this assignment
    only, so one odd notice cannot fail the whole issue.
    """
    try:
        return _evaluate(a, criterion)
    except ValueError as e:
        return {**not_evaluated("not_assessed", "p1546_input_out_of_range"), "detail": str(e)}, []


def _evaluate(a: dict[str, Any], criterion: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    assumptions: list[str] = []
    ant, site = a["antenna"], a["site"]
    f, bw = a["f_mhz"], a["bw_khz"]
    if site is None:
        return not_evaluated("not_assessed", "missing_site"), assumptions
    if not (p1546.F_RANGE_MHZ[0] <= f <= p1546.F_RANGE_MHZ[1]):
        return not_evaluated("not_assessed", "outside_p1546_range"), assumptions
    if ant is None or ant["pwr_dbw"] is None:
        return not_evaluated("not_assessed", "missing_power"), assumptions
    if ant["erp_dbw"] is None:
        return not_evaluated("not_assessed", "unsupported_power_type"), assumptions
    h1 = ant["hgt_agl_m"]
    if h1 is None:
        return not_evaluated("not_assessed", "missing_antenna_height"), assumptions
    if not (0 < h1 <= p1546.H1_MAX_M):
        return not_evaluated("not_assessed", "antenna_height_out_of_range"), assumptions
    trig = refdata.trigger(criterion, f, bw)
    if trig is None:
        return not_evaluated("not_assessed", "no_criterion_in_registry"), assumptions
    if ant["pwr_eiv"] == "I":
        assumptions.append("A-T-EIRP-ERP")
    if ant["rows"] > 1:
        assumptions.append("A-T-ANT-MAX")
    assumptions.append("A-T-ANT-DIAG" if ant["diagram"] else "A-T-ANT-OMNI")
    if criterion["id"] == "ecc-rec-11-04":
        assumptions.append("A-T-ECC-NONPREF")

    t, loc, h2, erp = criterion["time_pct"], criterion["loc_pct"], criterion["rx_height_m"], ant["erp_dbw"]
    params = {
        "f_mhz": f,
        "bw_khz": bw,
        "h1_m": h1,
        "h2_m": h2,
        "time_pct": t,
        "loc_pct": loc,
        "erp_dbw": erp,
        "rx_env": RX_ENV,
        "bw_correction_db": trig.bandwidth_correction_db,
    }
    trigger_out = {
        "base_dbuv_m": trig.base_dbuv_m,
        "bandwidth_correction_db": trig.bandwidth_correction_db,
        "e_dbuv_m": trig.e_dbuv_m,
        "evaluation_km": trig.evaluation_km,
        "note": trig.note,
    }
    d = border_distances(site["lat"], site["lon"])
    blat, blon = _border()
    order = np.lexsort((blon, blat, d))
    near = [int(i) for i in order if d[i] <= SCREENING_RANGE_KM]
    if not near:
        return not_evaluated("not_assessed", "beyond_p1546_distance"), assumptions
    base = {
        "hazard_id": HAZARD_ID,
        "criterion_id": criterion["id"],
        "trigger": trigger_out,
        "parameters": params,
    }

    def dist(i: int) -> float:
        return round(max(float(d[i]), 1.0), _LEN_ND)

    i0 = near[0]
    if float(d[i0]) < 1.0:
        assumptions.append("A-T-DMIN-1KM")
    brg0 = bearing_deg(site["lat"], site["lon"], float(blat[i0]), float(blon[i0]))
    # Mixed paths lie between the all-land and all-sea values and E falls with distance, so the larger of the
    # two at the nearest point bounds Tier 2. Below about 100 MHz land can exceed cold sea, hence both.
    bounds = {kind: _field(f, t, [(kind, dist(i0))], h1, h2, erp, loc).e_dbuv_m for kind in (SEA, "land")}
    upper_kind = max(bounds, key=lambda k: (bounds[k], k == SEA))
    upper = bounds[upper_kind]
    tier1 = {
        "point": _point(float(blat[i0]), float(blon[i0]), float(d[i0]), brg0),
        "path": [{"kind": upper_kind, "length_km": dist(i0)}],
        "e_upper_dbuv": upper,
        "margin_upper_db": upper - trig.e_dbuv_m,
    }
    if upper <= trig.e_dbuv_m - TIER1_MARGIN_DB:
        return {**base, "outcome": "screened_out", "reason": "tier1_upper_bound_below_trigger", "tier": 1,
                "tier1": tier1, "tier2": None}, assumptions  # fmt: skip

    candidates = near[:MAX_BORDER_POINTS]
    if ant["diagram"] and ant["azm_max_e"] is not None:
        bearings = {i: bearing_deg(site["lat"], site["lon"], float(blat[i]), float(blon[i])) for i in near}
        beam = min(near, key=lambda i: (abs((bearings[i] - ant["azm_max_e"] + 180) % 360 - 180), d[i]))
        if beam not in candidates:
            candidates.append(beam)
    worst: dict[str, Any] | None = None
    for i in candidates:
        lat, lon, di = float(blat[i]), float(blon[i]), dist(i)
        brg = bearing_deg(site["lat"], site["lon"], lat, lon)
        path = path_segments(site["lat"], site["lon"], lat, lon, di)
        res = _field(f, t, path, h1, h2, erp, loc)
        attn = _attenuation(ant, brg)
        e = res.e_dbuv_m - attn
        if worst is None or e > worst["e_dbuv"]:
            worst = {
                "i": i,
                "e": res,
                "e_dbuv": e,
                "attn": attn,
                "path": path,
                "point": _point(lat, lon, di, brg),
            }
    assert worst is not None
    di = worst["point"]["distance_km"]
    e_land = _field(f, t, [("land", di)], h1, h2, erp, loc).e_dbuv_m - worst["attn"]
    e_sea = _field(f, t, [(SEA, di)], h1, h2, erp, loc).e_dbuv_m - worst["attn"]
    margin = worst["e_dbuv"] - trig.e_dbuv_m
    if any(k == SEA for k, _ in worst["path"]):
        assumptions.append("A-T-SEA-COLD")
    other = [
        {"trigger_dbuv_m": lv["trigger_dbuv_m"] + trig.bandwidth_correction_db, "case": lv["case"],
         "margin_db": worst["e_dbuv"] - lv["trigger_dbuv_m"] - trig.bandwidth_correction_db}
        for lv in criterion.get("other_levels", []) if lv["evaluation_km"] == trig.evaluation_km
    ]  # fmt: skip
    tier2 = {
        "worst_point": worst["point"],
        "path": [{"kind": k, "length_km": length} for k, length in worst["path"]],
        "e_p1546_dbuv": worst["e"].e_dbuv_m,
        "antenna_attenuation_db": worst["attn"],
        "e_dbuv": worst["e_dbuv"],
        "margin_db": margin,
        "points_evaluated": len(candidates),
        "e_all_land_dbuv": e_land,
        "e_all_sea_dbuv": e_sea,
        "p1546": {
            "version": p1546.VERSION,
            "inputs": worst["e"].inputs,
            "steps": worst["e"].steps,
            "assumptions": list(worst["e"].assumptions),
        },
        "other_levels": other,
    }
    outcome = "exceeds" if margin > 0 else "meets"
    return {
        **base,
        "outcome": outcome,
        "reason": None,
        "tier": 2,
        "tier1": tier1,
        "tier2": tier2,
    }, assumptions


def reproduce(hazard: dict[str, Any]) -> float:
    """Re-run P.1546 from a stored Tier 2 result (the AC6 reproducibility check)."""
    p, t2 = hazard["parameters"], hazard["tier2"]
    path = [(s["kind"], s["length_km"]) for s in t2["path"]]
    res = _field(p["f_mhz"], p["time_pct"], path, p["h1_m"], p["h2_m"], p["erp_dbw"], p["loc_pct"])
    return res.e_dbuv_m - t2["antenna_attenuation_db"]
