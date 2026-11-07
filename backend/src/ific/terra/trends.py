"""Neighbour trends and anomaly rules, computed from stored `terra-1` results of one issue at a time.

Counts cover the neighbouring administrations' notices first published in the issue (`received`, part 1),
so a notice republished as `recorded` in a later issue is never counted twice; a multi-issue trend is the sum
of per-issue counts. Anomaly rules are evaluated within one issue's assignments (no join across issues).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from ific.terra import refdata
from ific.terra.method import NEIGHBOURS

DISTANCE_BINS = ((0.0, 50.0, "<50 km"), (50.0, 150.0, "50-150 km"), (150.0, 300.0, "150-300 km"),
                 (300.0, 1000.0, "300-1000 km"))  # fmt: skip
DIMENSIONS = ("band", "distance", "stn_cls", "notice_typ", "bw_code", "change")
RULE_CITE = "docs/terrestrial-land-mobile.md, Trends and anomaly rules"

NEAR_KM = 150.0
A2_FACTOR, A2_MIN = 4.0, 5
A3_PCT, A3_MIN = 95.0, 10


def band(r: dict[str, Any]) -> str:
    """The criterion band (e.g. `tr-25-08 108-380 MHz`), else the first matching M4 row, else `other`."""
    crit = r["criterion"]
    f = r["f_mhz"]
    if crit and f is not None:
        c = next((c for c in refdata.criteria() if c["id"] == crit["id"]), None)
        b = next((b for b in c["bands"] if b["f_min_mhz"] <= f <= b["f_max_mhz"]), None) if c else None
        if b is not None:
            return f"{c['id']} {b['f_min_mhz']:g}-{b['f_max_mhz']:g} MHz"
    rows = r["regulatory"]["m4_rows"]
    return f"M4 row {rows[0]['id']}" if rows else "other"


def distance_bin(d: float | None) -> str:
    if d is None:
        return "unknown"
    return next((label for lo, hi, label in DISTANCE_BINS if lo <= d < hi), "≥1000 km")


def _dims(r: dict[str, Any]) -> dict[str, str]:
    return {
        "band": band(r),
        "distance": distance_bin(r["relevance"]["distance_km"]),
        "stn_cls": r["stn_cls"],
        "notice_typ": r["notice_typ"] or "unknown",
        "bw_code": r["bw_code"] or (f"{r['bw_khz']:g} kHz" if r["bw_khz"] is not None else "unknown"),
        "change": r["change"],
    }


def population(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in results if r["adm"] in NEIGHBOURS and r["pub_status"]["status"] == "received"]


def counts(results: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, int]]]:
    """dimension -> adm -> value -> count, over the neighbour population of one issue."""
    out: dict[str, dict[str, Counter]] = {d: {} for d in DIMENSIONS}
    for r in population(results):
        for dim, value in _dims(r).items():
            out[dim].setdefault(r["adm"], Counter())[value] += 1
    return {d: {adm: dict(sorted(c.items())) for adm, c in sorted(v.items())} for d, v in out.items()}


def _match(r: dict[str, Any], detail: str) -> dict[str, Any]:
    return {"terrakey": r["terrakey"], "adm": r["adm"], "adm_ref_id": r["adm_ref_id"], "detail": detail}


def anomalies(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in results:
        by_group.setdefault((r["adm"], band(r)), []).append(r)

    a1, a2, a3, a4 = [], [], [], []
    for (adm, b), rows in sorted(by_group.items()):
        if adm in NEIGHBOURS:
            near = [
                r for r in rows
                if r["pub_status"]["status"] == "received" and r["change"] == "new"
                and r["relevance"]["distance_km"] is not None and r["relevance"]["distance_km"] < NEAR_KM
            ]  # fmt: skip
            if near and len(near) == len(rows):
                a1 += [_match(r, f"{adm} has no other notice in {b} in this issue") for r in near]
        bws = [r["bw_khz"] for r in rows if r["bw_khz"] is not None]
        if len(bws) >= A2_MIN:
            med = float(np.median(bws))
            a2 += [
                _match(r, f"bandwidth {r['bw_khz']:g} kHz > {A2_FACTOR:g} × median {med:g} kHz ({b})")
                for r in rows
                if r["bw_khz"] is not None and r["bw_khz"] > A2_FACTOR * med
            ]
        erps = [r["antenna"]["erp_dbw"] for r in rows if r["antenna"] and r["antenna"]["erp_dbw"] is not None]
        if len(erps) >= A3_MIN:
            p = float(np.percentile(erps, A3_PCT))
            a3 += [
                _match(r, f"e.r.p. {r['antenna']['erp_dbw']:.1f} dBW > p{A3_PCT:g} {p:.1f} dBW ({b})")
                for r in rows
                if r["antenna"] and r["antenna"]["erp_dbw"] is not None and r["antenna"]["erp_dbw"] > p
            ]
    for r in results:
        if r["relevance"]["fin_coord_required"]:
            provs = ", ".join(
                c["coord_prov"]
                for c in r["relevance"]["fin_coordination"]
                if c["coord_st"] == "COORD REQUIRED"
            )
            a4.append(_match(r, f"FIN coordination COORD REQUIRED ({provs})"))

    def rule(rid: str, description: str, threshold: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
        return {"id": rid, "description": description, "threshold": threshold, "citation": RULE_CITE,
                "matches": sorted(matches, key=lambda m: m["terrakey"])}  # fmt: skip

    return [
        rule("A1-new-band-near-border",
             "A neighbour's new notices near the border in a band where this issue has no other notice of it",
             f"received, new, < {NEAR_KM:g} km; no other notice of the administration in the band", a1),
        rule("A2-atypical-bandwidth", "Bandwidth far above the typical one for the band and administration",
             f"> {A2_FACTOR:g} × median, at least {A2_MIN} notices", a2),
        rule("A3-erp-outlier", "e.r.p. above the 95th percentile for the band and administration",
             f"> p{A3_PCT:g}, at least {A3_MIN} notices", a3),
        rule("A4-fin-coord-open", "Coordination with Finland still required on a notice in this issue",
             "fxm_coord adm = FIN, coord_st = COORD REQUIRED", a4),
    ]  # fmt: skip


def _add(acc: dict, c: dict) -> None:
    for dim, by_adm in c.items():
        for adm, values in by_adm.items():
            tgt = acc.setdefault(dim, {}).setdefault(adm, {})
            for v, n in values.items():
                tgt[v] = tgt.get(v, 0) + n


def trends(ific_no: int, by_issue: dict[int, list[dict[str, Any]]]) -> dict[str, Any]:
    """Trends for `ific_no` plus the sum over `by_issue` (which includes `ific_no`)."""
    per_issue = {}
    total: dict[str, Any] = {}
    for n in sorted(by_issue):
        c = counts(by_issue[n])
        _add(total, c)
        per_issue[n] = {
            "received": len(population(by_issue[n])),
            "by_adm": dict(sorted(Counter(r["adm"] for r in population(by_issue[n])).items())),
        }
    return {
        "ific_no": ific_no,
        "issues": sorted(by_issue),
        "neighbours": list(NEIGHBOURS),
        "dimensions": list(DIMENSIONS),
        "per_issue": per_issue,
        "counts": {
            d: {a: dict(sorted(v.items())) for a, v in sorted(total.get(d, {}).items())} for d in DIMENSIONS
        },
        "anomalies": anomalies(by_issue[ific_no]),
    }
