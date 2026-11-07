"""Concern triage for manual review: the expert's triggers as readings off stored riia-1 results (no score).

- `exceeds`: a receiver violates a criterion point (the defined limit).
- `near_limit`: no violation, but the 95th-percentile exceedance is within `NEAR_LIMIT_DB` of a criterion
  level
  ("close-by exceedance"; adjacent-band hazards carry "near the frequency").
- `main_beam`: a directional, high-gain Finnish station (not an omnidirectional class at its class gain) whose
  half-power beam contains the GSO position notified in the IFIC ("high-gain antenna in direct line toward the
  transmitter").
"""

import csv
import io
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import duckdb
import numpy as np

from ific.riia import MODEL_VERSION, store
from ific.riia.geometry import R_EARTH_KM, ecef, enu_basis, look_angles, off_axis_deg
from ific.riia.hazards import QUANTIFIED_MODES
from ific.riia.orbits import gso_ecef
from ific.riia.receivers import Receiver, StationsPopulation, load_classes

NEAR_LIMIT_DB = 6.0
GROUPS = (
    ("A", "Stations source: a criterion is exceeded"),
    ("B", "Stations source: a GSO position lies in a Finnish station's main beam"),
    ("C", "Stations source: within 6 dB of a criterion (near limit)"),
    ("D", "Generic population only: a criterion is exceeded"),
)


def half_power_beamwidth_deg(gain_dbi: float) -> float:
    """θ3dB ≈ 70·λ/D with 20·log10(D/λ) = G − 7.7 (Rec. ITU-R F.699 note)."""
    return 70.0 / 10 ** ((gain_dbi - 7.7) / 20)


def min_off_axis_deg(az: float, el_lo: float, el_hi: float, sat_az: float, sat_el: float) -> float:
    """Smallest angle between the satellite direction and any pointing (az, el) with el in [el_lo, el_hi]."""
    el = np.linspace(el_lo, el_hi, max(2, int((el_hi - el_lo) * 10) + 1))
    return float(
        off_axis_deg(np.full(el.size, az), el, np.full(el.size, sat_az), np.full(el.size, sat_el)).min()
    )


def is_near_limit(h: dict[str, Any]) -> bool:
    return h["outcome"] == "meets" and any(
        e["p95_db"] is not None and e["p95_db"] >= -NEAR_LIMIT_DB for e in h["exceedance_db"]
    )


def _worst_p95(h: dict[str, Any]) -> float | None:
    vals = [e["p95_db"] for e in h["exceedance_db"] if e["p95_db"] is not None]
    return max(vals) if vals else None


@dataclass(frozen=True)
class MainBeam:
    station: str
    service_class: str
    band_mhz: str
    azimuth_deg: float
    gain_dbi: float
    sat_az_deg: float
    sat_el_deg: float
    off_axis_deg: float
    hpbw_deg: float


def main_beam_hits(hazards: list[dict[str, Any]], stations: list[Receiver], lon_nom: float) -> list[MainBeam]:
    """Directional stations of the live hazards whose main beam can contain the GSO nominal position."""
    cf = load_classes()
    sat = gso_ecef(lon_nom)
    hits: dict[str, MainBeam] = {}
    for h in hazards:
        if h["mode"] not in QUANTIFIED_MODES or h["outcome"] in ("not_applicable", "screened_out"):
            continue
        cls = cf.classes[h["service_class"]]
        bands = {(lo, hi) for lo, hi in h["bands_hz"]}
        el_lo, el_hi = (
            (cls.distributions["pointing_elev_deg"].low, cls.distributions["pointing_elev_deg"].high)
            if "pointing_elev_deg" in cls.distributions
            else (90.0, 90.0)
        )
        for r in stations:
            if r.azimuth_deg is None or r.service_class != cls.id or (r.f_lo_hz, r.f_hi_hz) not in bands:
                continue
            lat, lon = np.array([r.lat]), np.array([r.lon])
            e, n, u = enu_basis(lat, lon)
            site = ecef(lat, lon, R_EARTH_KM + (r.height_m or 0.0) / 1e3)
            el, az, _ = look_angles(site, e, n, u, sat[None, :])
            if el[0] < cls.min_elev_deg:
                continue
            gain = r.gain_dbi if r.gain_dbi is not None else cls.gain_dbi
            if cls.pattern == "omni" and gain <= cls.gain_dbi:
                continue
            hpbw = half_power_beamwidth_deg(gain)
            off = min_off_axis_deg(r.azimuth_deg, el_lo, el_hi, float(az[0]), float(el[0]))
            if off <= hpbw / 2 and (r.id not in hits or off < hits[r.id].off_axis_deg):
                hits[r.id] = MainBeam(
                    r.id,
                    cls.id,
                    f"{r.f_lo_hz / 1e6:.3f}–{r.f_hi_hz / 1e6:.3f}",
                    r.azimuth_deg,
                    gain,
                    float(az[0]),
                    float(el[0]),
                    off,
                    hpbw,
                )
    return sorted(hits.values(), key=lambda m: m.off_axis_deg)


def _hazard_line(h: dict[str, Any]) -> str:
    p95 = _worst_p95(h)
    share = "—" if h["share_violating"] is None else f"{h['share_violating']:.0%}"
    return f"{h['hazard_id']} (share {share}, p95 {'—' if p95 is None else f'{p95:+.1f} dB'})"


def triage(
    con: duckdb.DuckDBPyConnection, ific_no: int, as_of: date
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stations_pop = StationsPopulation()
    stations = stations_pop.receivers(con)
    lon_nom = dict(
        con.execute("SELECT ntc_id, long_nom FROM space.geo WHERE ific_no = ?", [ific_no]).fetchall()
    )
    generic = {n["ntc_id"]: n for n in store.list_notices(con, ific_no, "generic-m4", as_of)[0]}
    rows = []
    for summary in store.list_notices(con, ific_no, "stations", as_of)[0]:
        ntc = summary["ntc_id"]
        detail = store.get_notice(con, ific_no, "stations", ntc, as_of)
        live = [h for h in detail["hazards"] if h["mode"] in QUANTIFIED_MODES]
        exceeds = [h for h in live if h["outcome"] == "exceeds"]
        near = [h for h in live if is_near_limit(h)]
        beams = main_beam_hits(live, stations, lon_nom[ntc]) if lon_nom.get(ntc) is not None else []
        g = generic.get(ntc)
        group = (
            "A"
            if exceeds
            else "B"
            if beams
            else "C"
            if near
            else "D"
            if g and g["worst_outcome"] == "exceeds"
            else None
        )
        if group is None:
            continue
        reg = detail["regulatory"]
        rows.append(
            {
                "group": group,
                "ntc_id": ntc,
                "sat_name": summary["sat_name"],
                "adm": summary["adm"],
                "stage": reg["stage"],
                "orbit": summary["orbit"],
                "long_nom": lon_nom.get(ntc),
                "stations_worst": summary["worst_outcome"],
                "stations_share": summary["max_share_violating"],
                "stations_max_p95_db": max(
                    (p for h in live if (p := _worst_p95(h)) is not None), default=None
                ),
                "exceeds": [_hazard_line(h) for h in exceeds],
                "near_limit": [_hazard_line(h) for h in near],
                "main_beam": beams,
                "generic_worst": g["worst_outcome"] if g else None,
                "generic_share": g["max_share_violating"] if g else None,
                "br_fin": reg["fin_identified"],
                "br_provisions": sorted({f["coord_prov"] for f in reg["findings"]}),
            }
        )
    order = {k: i for i, (k, _) in enumerate(GROUPS)}
    rows.sort(
        key=lambda r: (
            order[r["group"]],
            -(r["stations_share"] or 0.0),
            -(r["stations_max_p95_db"] if r["stations_max_p95_db"] is not None else -math.inf),
            r["ntc_id"],
        )
    )
    return rows, stations_pop.excluded


def to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    cols = [
        "group",
        "ntc_id",
        "sat_name",
        "adm",
        "stage",
        "orbit",
        "long_nom",
        "stations_worst",
        "stations_share",
        "stations_max_p95_db",
        "exceeds",
        "near_limit",
        "main_beam",
        "generic_worst",
        "generic_share",
        "br_fin",
        "br_provisions",
        "reviewer_verdict",
        "reviewer_note",
    ]
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(
            {
                **{k: r.get(k) for k in cols},
                "exceeds": "; ".join(r["exceeds"]),
                "near_limit": "; ".join(r["near_limit"]),
                "main_beam": "; ".join(
                    f"{m.station} off-axis {m.off_axis_deg:.1f}° (θ3dB {m.hpbw_deg:.1f}°)"
                    for m in r["main_beam"]
                ),
                "br_provisions": " ".join(r["br_provisions"]),
                "stations_share": None if r["stations_share"] is None else round(r["stations_share"], 4),
                "stations_max_p95_db": None
                if r["stations_max_p95_db"] is None
                else round(r["stations_max_p95_db"], 2),
                "generic_share": None if r["generic_share"] is None else round(r["generic_share"], 4),
                "reviewer_verdict": "",
                "reviewer_note": "",
            }
        )
    return buf.getvalue()


def report(ific_no: int, as_of: date, rows: list[dict[str, Any]], excluded: dict[str, int]) -> str:
    counts = {k: sum(1 for r in rows if r["group"] == k) for k, _ in GROUPS}
    lines = [
        f"# Concern review: IFIC {ific_no}, model {MODEL_VERSION}",
        "",
        f"- `as_of` {as_of.isoformat()}. Receiver sources: `stations` (frequencies-of-interest dataset) and"
        " `generic-m4`. Readings, not a score; see `backend/src/ific/riia/review.py` for the definitions.",
        f"- Near-limit margin: {NEAR_LIMIT_DB:g} dB (assumption). Main beam: off-axis ≤ θ3dB/2, θ3dB ≈ 70·λ/D"
        " from the station gain (class gain when missing); pointing elevation spans the class range.",
        "- Stations excluded: "
        + (", ".join(f"{v} {k}" for k, v in sorted(excluded.items())) or "none")
        + ".",
        "- The CSV next to this file has the same rows plus empty `reviewer_verdict` and `reviewer_note`"
        " columns.",
        "",
        "| Group | Meaning | Notices |",
        "|---|---|---|",
        *(f"| {k} | {label} | {counts[k]} |" for k, label in GROUPS),
    ]
    for key, label in GROUPS:
        group_rows = [r for r in rows if r["group"] == key]
        if not group_rows:
            continue
        lines += ["", f"## {key}. {label}", ""]
        for r in group_rows:
            pos = "" if r["long_nom"] is None else f" at {r['long_nom']:g}°E"
            br = f"BR named FIN ({', '.join(r['br_provisions'])})" if r["br_fin"] else "BR did not name FIN"
            share = "—" if r["stations_share"] is None else f"{r['stations_share']:.0%}"
            gshare = "—" if r["generic_share"] is None else f"{r['generic_share']:.0%}"
            lines.append(
                f"### {r['ntc_id']} {r['sat_name'] or ''} "
                f"({r['adm']}, {r['stage']}, {r['orbit'].upper()}{pos})"
            )
            lines.append("")
            lines.append(
                f"- Stations: worst `{r['stations_worst']}`, max share violating {share}. "
                f"Generic: worst `{r['generic_worst']}`, max share {gshare}. {br}."
            )
            if r["exceeds"]:
                lines.append("- Exceeds: " + "; ".join(r["exceeds"]) + ".")
            if r["near_limit"]:
                lines.append("- Near limit: " + "; ".join(r["near_limit"]) + ".")
            if r["main_beam"]:
                beams = [
                    f"{m.station} ({m.service_class}, {m.band_mhz} MHz, az {m.azimuth_deg:g}°, "
                    f"{m.gain_dbi:g} dBi): satellite at az {m.sat_az_deg:.1f}°, el {m.sat_el_deg:.1f}°, "
                    f"off-axis {m.off_axis_deg:.1f}° "
                    f"of θ3dB {m.hpbw_deg:.1f}°"
                    for m in r["main_beam"][:5]
                ]
                more = len(r["main_beam"]) - 5
                lines.append(
                    "- Main beam: " + "; ".join(beams) + (f"; … {more} more" if more > 0 else "") + "."
                )
            lines.append("- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
