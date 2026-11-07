"""pfd on Finnish territory against RR Table 21-4 (doc: 'pfd on Finnish territory vs RR Table 21-4').

Deterministic: no random generator and no receiver population. For a downlink group g and a matching
Table 21-4 row r: "pfd_ref = P_ref + G_s(point) − 10·log10(4π·d(point)²)" and
"margin = pfd_ref − limit_r(δ(point))", the worst margin over Finland kept. The checks of a notice that share
a row and an outcome are reported as one.
"""

import math
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from ific.riia.geometry import R_EARTH_KM, ecef, enu_basis, look_angles
from ific.riia.hazards import OUTCOME_RANK, Geometry, Overrides, _satellite_gain, spreading_db
from ific.riia.orbits import gso_ecef
from ific.riia.pfd_limits import (
    CLASS_CITE,
    KNOWN_CLASSES,
    SERVICE_CLASSES,
    SERVICE_LABEL,
    Limit,
    Limits,
    NotEvaluable,
)

PFD_CHECK_VERSION = "art21-1"
DELTA_STEP_DEG = 0.5

ASSUMPTIONS = {
    "pfd_peak_gain": "Non-GSO beams, and GSO beams without boresight, use peak gain toward all of Finland",
    "pfd_density_flat": "Without pwr_ds_max, the power density is flat over B_n (pep_max − 10·log10 B_n)",
    "cpfd_flat": "A notified pfd is rescaled to the reference bandwidth, flat over the carrier width",
    "pfd_notice_gain": "The beam of the group has no gain; the highest beam gain of the notice is used",
    "cpfd_min_delta": "A notified pfd (no δ given) is compared with the limit at the lowest δ from Finland",
    "pfd_near_db": "near_limit: margin within 3 dB below the Table 21-4 limit",
    "pfd_mask_notified_not_loaded": "A pfd mask is notified (mask_info); its values are not in the IFIC .mdb",
    "pfd_lowest_altitude": "Non-GSO: slant range at the lowest altitude of the constellation (perigee)",
    "pfd_density_inconsistent": (
        "pwr_ds_max puts more power in its averaging band (4 kHz below 15 GHz, 1 MHz above) than pep_max in"
        " the whole carrier, so it is treated as a data error and pep_max is used"
    ),
}
# AP4 C.8: pwr_ds_max is averaged over the worst 4 kHz below 15 GHz, over the worst 1 MHz above.
PDS_AVG_SPLIT_HZ = 15e9
PDS_TOLERANCE_DB = 0.5


@dataclass(frozen=True)
class Params:
    near_db: float = 3.0
    use_boresight: bool = True
    cpfd_delta: str = "min"
    gain_offset_db: float = 0.0


DEFAULT_PARAMS = Params()


@dataclass(frozen=True)
class Emission:
    pep_dbw: float | None
    pds_dbw_hz: float | None
    bn_hz: float
    pds_dropped: bool = False

    @classmethod
    def of(cls, pep: float | None, pds: float | None, bn_hz: float, f_hz: float) -> "Emission":
        """Drop a pwr_ds_max that holds more power in its averaging band than pep_max in the carrier."""
        avg = 1e6 if f_hz > PDS_AVG_SPLIT_HZ else 4e3
        if (
            pep is not None
            and pds is not None
            and pds + 10 * math.log10(min(avg, bn_hz)) > pep + PDS_TOLERANCE_DB
        ):
            return cls(pep, None, bn_hz, True)
        return cls(pep, pds, bn_hz)

    def p_ref_dbw(self, ref_bw_hz: float) -> tuple[float, bool] | None:
        """Power in the reference bandwidth (dBW) and whether the flat-density assumption was needed."""
        if self.bn_hz < ref_bw_hz:
            if self.pep_dbw is not None:
                return self.pep_dbw, False
            return self.pds_dbw_hz + 10 * math.log10(self.bn_hz), False
        if self.pds_dbw_hz is not None:
            return self.pds_dbw_hz + 10 * math.log10(ref_bw_hz), False
        return self.pep_dbw - 10 * math.log10(self.bn_hz) + 10 * math.log10(ref_bw_hz), True


@dataclass(frozen=True)
class PfdGroup:
    grp_id: int
    f_lo_hz: float
    f_hi_hz: float
    emissions: tuple[Emission, ...]
    gain_dbi: float | None
    bore: tuple[float, float] | None
    psi0_deg: float | None
    stn_cls: tuple[str, ...]
    masked: bool = False
    gain_from_notice: bool = False


@dataclass(frozen=True)
class NotifiedPfd:
    f_lo_hz: float
    f_hi_hz: float
    pfd_dbw_m2: float
    bw_hz: float | None


@dataclass(frozen=True)
class Grid:
    lat: np.ndarray
    lon: np.ndarray

    @classmethod
    def of(cls, points: tuple[tuple[float, float], ...]) -> "Grid":
        a = np.asarray(points, dtype=float).reshape(-1, 2)
        return cls(a[:, 0], a[:, 1])


@dataclass
class _Sky:
    """Visible (δ, spreading) per satellite position, shared by every group of one notice."""

    positions: list[tuple[float | None, np.ndarray, np.ndarray, np.ndarray]]
    lowest_delta: float | None
    highest_delta: float | None


def _input(name: str, value: Any, unit: str | None, source: str, cite: str) -> dict[str, Any]:
    if isinstance(value, float):
        value = round(value, 4)
    return {"name": name, "value": value, "unit": unit, "source": source, "cite": cite}


def _assumptions(ids: list[str]) -> list[dict[str, Any]]:
    return [{"id": i, "text": ASSUMPTIONS[i], "sensitive": False} for i in dict.fromkeys(ids)]


def _overlap(a_lo: float, a_hi: float, b_lo: float, b_hi: float) -> bool:
    return a_lo < b_hi and b_lo < a_hi


def _gso_sky(geom: Geometry, grid: Grid) -> _Sky:
    site = ecef(grid.lat, grid.lon, R_EARTH_KM)
    e, n, u = enu_basis(grid.lat, grid.lon)
    positions = []
    lons = dict.fromkeys([geom.lon_deg, geom.lon_deg - geom.tol_west, geom.lon_deg + geom.tol_east])
    for lon in lons:
        el, _, rng = look_angles(site, e, n, u, gso_ecef(lon)[None, :])
        vis = el >= 0.0
        positions.append((lon, np.flatnonzero(vis), el[vis], spreading_db(rng[vis])))
    deltas = [p[2] for p in positions if p[2].size]
    return _Sky(
        positions,
        float(min(d.min() for d in deltas)) if deltas else None,
        float(max(d.max() for d in deltas)) if deltas else None,
    )


def ngso_slant_range_km(delta_deg: np.ndarray, alt_km: float) -> np.ndarray:
    """Range from a ground point to a satellite at altitude h seen at elevation δ (spherical Earth)."""
    r, d = R_EARTH_KM + alt_km, np.radians(delta_deg)
    return np.sqrt(r**2 - (R_EARTH_KM * np.cos(d)) ** 2) - R_EARTH_KM * np.sin(d)


def _ngso_sky(geom: Geometry, grid: Grid) -> _Sky:
    const = geom.constellation
    deltas = np.arange(0.0, 90.0 + DELTA_STEP_DEG / 2, DELTA_STEP_DEG)
    min_lat = float(np.abs(grid.lat).min())
    reach = np.array([const.max_reach_lat_deg(float(d)) >= min_lat for d in deltas])
    d = deltas[reach]
    rng = ngso_slant_range_km(d, geom.min_alt_km)
    return _Sky(
        [(None, np.zeros(d.size, dtype=int), d, spreading_db(rng))],
        float(d.min()) if d.size else None,
        float(d.max()) if d.size else None,
    )


def _matches(row: Limit, grp: PfdGroup, orbit: str, heo: bool) -> bool:
    if not _overlap(row.f_lo_hz, row.f_hi_hz, grp.f_lo_hz, grp.f_hi_hz):
        return False
    if not row.stn_cls & set(grp.stn_cls):
        return False
    if row.orbit != "any" and row.orbit != orbit:
        return False
    return not (orbit == "ngso" and row.ngso_class is not None and (row.ngso_class == "heo") != heo)


def _services(row: Limit, grp: PfdGroup) -> str:
    return ", ".join(SERVICE_LABEL[s] for s in row.services if set(grp.stn_cls) & set(SERVICE_CLASSES[s]))


def _base(grp: PfdGroup | None, row: Limit | None, orbit: str, limits: Limits) -> dict[str, Any]:
    return {
        "grp_id": grp.grp_id if grp else None,
        "row_id": row.id if row else None,
        "band_hz": [grp.f_lo_hz, grp.f_hi_hz] if grp else None,
        "service": _services(row, grp) if row and grp else None,
        "orbit": orbit,
        "ref_bw_hz": row.ref_bw_hz if row else None,
        "source": None,
        "pfd_dbw_m2": None,
        "limit_dbw_m2": None,
        "delta_deg": None,
        "margin_db": None,
        "near_limit": False,
        "reason": None,
        "inputs": [],
        "citations": [c for c in (row.cite if row else None, _review_cite(limits) if row else None) if c],
        "assumptions": [],
    }


def _review_cite(limits: Limits) -> str:
    return f"{limits.cite}, data/ref/rr21_pfd_limits.json (review {limits.review_status})"


def _not(outcome: str, reason: str, grp: PfdGroup | None, row: Limit | None, orbit: str, limits: Limits):
    return {**_base(grp, row, orbit, limits), "outcome": outcome, "reason": reason}


def _calculated(
    grp: PfdGroup, row: Limit, geom: Geometry, sky: _Sky, n_sats: int | None, params: Params, grid: Grid
) -> dict[str, Any] | None:
    """Worst margin over Finland of the calculated pfd, or None when the group has no power or gain."""
    best = None
    for e in grp.emissions:
        p = e.p_ref_dbw(row.ref_bw_hz)
        if p is not None and (best is None or p[0] > best[0][0]):
            best = (p, e)
    if best is None or grp.gain_dbi is None:
        return None
    (p_ref, flat), emission = best
    worst = None
    for lon, idx, delta, spread in sky.positions:
        if not delta.size:
            continue
        if geom.kind == "gso" and params.use_boresight and grp.bore is not None and grp.psi0_deg is not None:
            site = ecef(grid.lat[idx], grid.lon[idx], R_EARTH_KM)
            gain = _satellite_gain(grp, site, replace(geom, lon_deg=lon), Overrides()) + params.gain_offset_db
            boresight = True
        else:
            gain = np.full(delta.size, grp.gain_dbi + params.gain_offset_db)
            boresight = False
        pfd = p_ref + gain - spread
        margin = pfd - row.at(delta, n_sats)
        i = int(np.argmax(margin))
        if worst is None or margin[i] > worst["margin"]:
            worst = {
                "margin": float(margin[i]),
                "pfd": float(pfd[i]),
                "delta": float(delta[i]),
                "lon": lon,
                "point": (float(grid.lat[idx[i]]), float(grid.lon[idx[i]])) if geom.kind == "gso" else None,
                "boresight": boresight,
            }
    if worst is None:
        return None
    worst.update(p_ref=p_ref, flat=flat, bn_hz=emission.bn_hz, pds_dropped=emission.pds_dropped)
    return worst


def _evaluate(
    grp: PfdGroup,
    row: Limit,
    geom: Geometry,
    sky: _Sky,
    notified: list[NotifiedPfd],
    orbit: str,
    limits: Limits,
    params: Params,
    grid: Grid,
) -> dict[str, Any]:
    n_sats = geom.constellation.size if geom.kind == "ngso" and geom.constellation is not None else None
    try:
        row.at(0.0, n_sats)
    except NotEvaluable as e:
        return _not("not_assessed", str(e), grp, row, orbit, limits)
    if sky.lowest_delta is None:
        return _not("not_applicable", "Never visible from Finland", grp, row, orbit, limits)

    out = _base(grp, row, orbit, limits)
    assumptions: list[str] = []
    inputs = [
        _input("Space-station classes", ", ".join(grp.stn_cls), None, "data", f"space.srv_cls; {CLASS_CITE}"),
        _input("Reference bandwidth", row.ref_bw_hz, "Hz", "rr", row.cite),
    ]
    if n_sats is not None:
        inputs.append(_input("Satellites in the constellation (N)", n_sats, None, "data", "space.orbit"))
    reasons = []
    overlapping = [
        c
        for c in notified
        if _overlap(c.f_lo_hz, c.f_hi_hz, grp.f_lo_hz, grp.f_hi_hz)
        and _overlap(c.f_lo_hz, c.f_hi_hz, row.f_lo_hz, row.f_hi_hz)
    ]
    usable = [c for c in overlapping if c.bw_hz]
    if overlapping and not usable:
        reasons.append("notified pfd without reference bandwidth; calculated pfd used")

    calc = _calculated(grp, row, geom, sky, n_sats, params, grid)
    if calc is not None:
        inputs += [
            _input("Power in the reference bandwidth", calc["p_ref"], "dBW", "data", "space.emiss"),
            _input("Necessary bandwidth B_n", calc["bn_hz"], "Hz", "data", "space.emiss.design_emi"),
            _input("Satellite peak gain", grp.gain_dbi, "dBi", "data", "space.s_beam.gain"),
            _input("Calculated pfd at the worst point", calc["pfd"], "dB(W/m²)", "physics", "free space"),
            _input("Calculated margin", calc["margin"], "dB", "physics", "pfd − Table 21-4 limit"),
        ]
        if calc["point"] is not None:
            inputs.append(
                _input(
                    "Worst point (lat, lon)",
                    f"{calc['point'][0]:.2f}, {calc['point'][1]:.2f}",
                    "°",
                    "physics",
                    "Finland grid 0.25° × 0.5°",
                )
            )
            inputs.append(
                _input("Satellite longitude at the worst point", calc["lon"], "°E", "data", "space.geo")
            )
        else:
            inputs.append(
                _input("Lowest altitude", geom.min_alt_km, "km", "data", "space.orbit.perig_km / op_ht_km")
            )
            assumptions.append("pfd_lowest_altitude")
        if not calc["boresight"]:
            assumptions.append("pfd_peak_gain")
        if calc["flat"]:
            assumptions.append("pfd_density_flat")
        if calc["pds_dropped"]:
            assumptions.append("pfd_density_inconsistent")
        if grp.gain_from_notice:
            assumptions.append("pfd_notice_gain")

    if usable:
        # Flat over the carrier only: the power in a band is capped by the carrier width B_n.
        bn = max((e.bn_hz for e in grp.emissions), default=math.inf)

        def scaled(c: NotifiedPfd) -> float:
            return c.pfd_dbw_m2 + 10 * math.log10(min(row.ref_bw_hz, bn) / min(c.bw_hz, bn))

        c = max(usable, key=scaled)
        pfd = scaled(c)
        delta = sky.lowest_delta if params.cpfd_delta == "min" else sky.highest_delta
        limit = float(row.at(delta, n_sats))
        inputs.insert(
            2,
            _input(
                "Notified pfd",
                f"{c.pfd_dbw_m2:g} in {c.bw_hz / 1e3:g} kHz",
                "dB(W/m²)",
                "data",
                "space.c_pfd",
            ),
        )
        assumptions += ["cpfd_flat", "cpfd_min_delta"]
        out.update(
            source="notified", pfd_dbw_m2=pfd, limit_dbw_m2=limit, delta_deg=delta, margin_db=pfd - limit
        )
        if calc is not None and calc["margin"] > 0 >= pfd - limit:
            reasons.append(
                f"the calculated pfd exceeds the limit by {calc['margin']:.1f} dB; notified value used"
            )
    elif calc is not None:
        out.update(
            source="calculated",
            pfd_dbw_m2=calc["pfd"],
            limit_dbw_m2=calc["pfd"] - calc["margin"],
            delta_deg=calc["delta"],
            margin_db=calc["margin"],
        )
    else:
        return _not("not_assessed", "No power or gain in the notice", grp, row, orbit, limits)

    if grp.masked:
        assumptions.append("pfd_mask_notified_not_loaded")
        inputs.append(_input("pfd mask notified", "values not in the .mdb", None, "data", "space.mask_info"))
    inputs += geom.inputs
    margin = out["margin_db"]
    out.update(
        outcome="exceeds" if margin > 0 else "meets",
        near_limit=-params.near_db <= margin <= 0,
        reason="; ".join(reasons) or None,
        inputs=inputs,
        assumptions=_assumptions(assumptions + ["pfd_near_db"]),
    )
    if row.note:
        out["citations"].append(row.note)
    return out


def _group_checks(
    grp: PfdGroup,
    geom: Geometry | None,
    sky: _Sky | None,
    orbit: str,
    notified: list[NotifiedPfd],
    limits: Limits,
    params: Params,
    grid: Grid,
) -> list[dict[str, Any]]:
    if not grp.stn_cls:
        return [
            _not("not_assessed", "No space-station class (srv_cls) for this group", grp, None, orbit, limits)
        ]
    heo = bool(geom and geom.heo)
    rows = [r for r in limits.rows if _matches(r, grp, orbit, heo)]
    if not rows:
        unknown = sorted(set(grp.stn_cls) - KNOWN_CLASSES)
        if unknown and not set(grp.stn_cls) & KNOWN_CLASSES:
            return [
                _not("not_assessed", f"Unknown station class {', '.join(unknown)}", grp, None, orbit, limits)
            ]
        return [
            _not(
                "not_applicable",
                "No Table 21-4 limit in this band for this service and orbit",
                grp,
                None,
                orbit,
                limits,
            )
        ]
    out = []
    for row in rows:
        if not row.encoded:
            out.append(_not("not_assessed", row.reason, grp, row, orbit, limits))
        elif geom is None or sky is None:
            out.append(
                _not("not_assessed", "No orbit or GSO position for this notice", grp, row, orbit, limits)
            )
        else:
            out.append(_evaluate(grp, row, geom, sky, notified, orbit, limits, params, grid))
    return out


def _collapse(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One check per (row, outcome kind, reason): the worst group, with counts of the groups it stands for."""
    buckets: dict[tuple, list[dict[str, Any]]] = {}
    for c in checks:
        evaluated = c["margin_db"] is not None
        key = (
            c["row_id"] or "",
            "evaluated" if evaluated else c["outcome"],
            None if evaluated else c["reason"],
        )
        buckets.setdefault(key, []).append(c)
    out = []
    for key in sorted(buckets, key=lambda k: (k[0], k[1], k[2] or "")):
        group = buckets[key]
        worst = max(
            group,
            key=lambda c: (c["margin_db"] if c["margin_db"] is not None else -math.inf, -(c["grp_id"] or 0)),
        )
        worst = {
            **worst,
            "n_groups": len(group),
            "n_groups_exceeding": sum(1 for c in group if c["outcome"] == "exceeds"),
        }
        out.append(worst)
    seen: dict[str, int] = {}
    for c in out:
        rid = c["row_id"] or "none"
        seen[rid] = seen.get(rid, 0) + 1
        c["check_id"] = f"{rid}#{seen[rid]}"
    return out


def failed(reason: str, orbit: str, limits: Limits) -> list[dict[str, Any]]:
    return _collapse([_not("not_assessed", reason, None, None, orbit, limits)])


def notice_checks(
    groups: list[PfdGroup],
    notified: list[NotifiedPfd],
    geom: Geometry | None,
    ntc_type: str,
    act_code: str | None,
    limits: Limits,
    grid: Grid,
    params: Params = DEFAULT_PARAMS,
) -> list[dict[str, Any]]:
    """The pfd checks of one notice, in (row_id, outcome kind) order."""
    orbit = {"G": "gso", "N": "ngso"}.get(ntc_type, "es")
    if act_code == "S":
        return _collapse([_not("not_applicable", "Suppressed notice", None, None, orbit, limits)])
    if not groups:
        return []
    sky = None
    if geom is not None and geom.kind == "gso" and geom.lon_deg is not None:
        sky = _gso_sky(geom, grid)
    elif (
        geom is not None
        and geom.kind == "ngso"
        and geom.constellation is not None
        and geom.min_alt_km is not None
    ):
        sky = _ngso_sky(geom, grid)
    else:
        geom = None
    checks = []
    for grp in sorted(groups, key=lambda g: g.grp_id):
        checks += _group_checks(grp, geom, sky, orbit, notified, limits, params, grid)
    return _collapse(checks)


def summarise(checks: list[dict[str, Any]], limits: Limits) -> dict[str, Any]:
    margins = [c["margin_db"] for c in checks if c["margin_db"] is not None]
    return {
        "pfd_check_version": PFD_CHECK_VERSION,
        "pfd_limits_sha256": limits.sha256,
        "pfd_limits_review": limits.review_status,
        "pfd_outcome": min(
            (c["outcome"] for c in checks), key=OUTCOME_RANK.__getitem__, default="not_applicable"
        ),
        "max_pfd_margin_db": max(margins) if margins else None,
        "pfd_near_limit": any(c["near_limit"] for c in checks),
        "pfd_checks": checks,
    }
