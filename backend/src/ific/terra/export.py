"""Exports of one issue's terrestrial findings: canonical JSON, flat CSV and a Markdown report."""

from __future__ import annotations

import csv
import io
from typing import Any

from ific.terra import refdata
from ific.terra.method import ASSUMPTIONS, MODEL_VERSION
from ific.terra.store import OUTCOMES, canonical_json, outcome_counts

CSV_COLUMNS = ("terrakey", "adm", "adm_ref_id", "stn_cls", "notice_typ", "change", "pub_status", "relevant",
               "signals", "f_mhz", "bw_khz", "erp_dbw", "h1_m", "criterion_id", "applicability", "trigger",
               "e_dbuv", "margin_db", "outcome", "reason", "assumptions", "sources")  # fmt: skip


def to_json(results: list[dict[str, Any]]) -> str:
    return canonical_json(results)


def _fmt(v: Any, nd: int = 2) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def _ordered(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(results, key=lambda r: r["sort_key"])


def csv_row(r: dict[str, Any]) -> dict[str, str]:
    ant = r["antenna"] or {}
    crit = r["criterion"] or {}
    return {
        "terrakey": str(r["terrakey"]),
        "adm": r["adm"],
        "adm_ref_id": r["adm_ref_id"] or "",
        "stn_cls": r["stn_cls"],
        "notice_typ": r["notice_typ"] or "",
        "change": r["change"],
        "pub_status": r["pub_status"]["status"],
        "relevant": "true" if r["relevance"]["relevant"] else "false",
        "signals": ";".join(s["id"] for s in r["relevance"]["signals"]),
        "f_mhz": _fmt(r["f_mhz"], 4),
        "bw_khz": _fmt(r["bw_khz"], 1),
        "erp_dbw": _fmt(ant.get("erp_dbw")),
        "h1_m": _fmt(ant.get("hgt_agl_m"), 1),
        "criterion_id": crit.get("id") or "",
        "applicability": crit.get("applicability") or "",
        "trigger": _fmt(r["trigger_dbuv"]),
        "e_dbuv": _fmt(r["e_dbuv"]),
        "margin_db": _fmt(r["margin_db"]),
        "outcome": r["outcome"],
        "reason": r["reason"] or "",
        "assumptions": ";".join(r["assumptions"]),
        "sources": ";".join(r["sources"]),
    }


def to_csv(results: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in _ordered(results):
        w.writerow(csv_row(r))
    return buf.getvalue()


def _evidence(r: dict[str, Any]) -> list[str]:
    h, t2 = r["hazard"], r["hazard"]["tier2"]
    p, trig, wp = h["parameters"], h["trigger"], t2["worst_point"]
    ant, site = r["antenna"], r["site"]
    path = ", ".join(f"{s['kind']} {s['length_km']:.1f} km" for s in t2["path"])
    coord = (
        "; ".join(f"{c['coord_prov']} {c['coord_st']}" for c in r["relevance"]["fin_coordination"]) or "none"
    )
    lines = [
        f"### {r['adm']} {r['adm_ref_id'] or ''} (terrakey {r['terrakey']}): "
        f"{_fmt(r['f_mhz'], 4)} MHz {r['stn_cls']}",
        "",
        f"- Notice: {r['notice_typ']} {r['intent']} ({r['change']}), provision {r['prov']}, publication "
        f"{r['pub_status']['status']} (part {r['pub_status']['part']}, first published in "
        f"{r['pub_status']['first_published_in']}).",
        f"- Site: {site['name']} {site['lat']:.4f}N {site['lon']:.4f}E; "
        f"{r['relevance']['distance_km']:.1f} km to the nearest Finnish point. FIN coordination: {coord}.",
        f"- Criterion: {r['criterion']['citation']} ({r['criterion']['applicability']}, "
        f"verified: {str(r['criterion']['verified']).lower()}). Trigger {trig['e_dbuv_m']:.2f} dB(µV/m) = "
        f"{trig['base_dbuv_m']:g} + {trig['bandwidth_correction_db']:.2f} dB bandwidth correction.",
        f"- P.1546 at the worst Finnish point {wp['lat']:.4f}N {wp['lon']:.4f}E ({wp['distance_km']:.1f} km, "
        f"bearing {wp['bearing_deg']:.0f}°): E = {t2['e_dbuv']:.2f} dB(µV/m), "
        f"margin {t2['margin_db']:+.2f} dB.",
        f"- Parameters: f {p['f_mhz']:g} MHz, h1 {p['h1_m']:g} m, h2 {p['h2_m']:g} m, "
        f"{p['time_pct']:g} % time, "
        f"{p['loc_pct']:g} % locations, e.r.p. {p['erp_dbw']:.2f} dBW ({ant['pwr_eiv']}), bandwidth "
        f"{_fmt(p['bw_khz'], 1)} kHz; path {path}.",
        f"- Bounds: all land {t2['e_all_land_dbuv']:.2f}, all sea {t2['e_all_sea_dbuv']:.2f} dB(µV/m); "
        "Tier 1 "
        f"upper bound {h['tier1']['e_upper_dbuv']:.2f} dB(µV/m).",
        f"- Assumptions: {', '.join(r['assumptions'])}.",
        f"- Sources: {', '.join(r['sources'])}.",
        "",
    ]
    return lines


def to_markdown(ific_no: int, results: list[dict[str, Any]]) -> str:
    counts = outcome_counts(results)
    relevant = [r for r in results if r["relevance"]["relevant"]]
    out = [
        f"# Terrestrial land mobile findings: BR IFIC {ific_no}",
        "",
        f"Model `{MODEL_VERSION}` (docs/terrestrial-land-mobile.md). Deterministic ITU-R P.1546 field "
        "strength at the Finnish border against the ECC criteria. There is no composite score; findings "
        "are ordered by outcome, open FIN coordination, margin, change and publication status.",
        "",
        "## Counts",
        "",
        f"{len(results)} foreign land mobile assignments, {len(relevant)} relevant to Finland.",
        "",
        "| Outcome | Assignments |",
        "|---|---|",
        *(f"| {o} | {counts[o]} |" for o in OUTCOMES),
        "",
        "## Criteria",
        "",
        *(
            f"- `{c['id']}`: {c['citation']} ({c['f_min_mhz']:g}-{c['f_max_mhz']:g} MHz), "
            f"verified: {str(c['verified']).lower()}"
            for c in refdata.criteria()
        ),
        "",
    ]
    for outcome in OUTCOMES:
        rows = [r for r in _ordered(results) if r["outcome"] == outcome and r["relevance"]["relevant"]]
        if not rows:
            continue
        out += [f"## {outcome} ({len(rows)})", ""]
        if outcome == "exceeds":
            for r in rows:
                out += _evidence(r)
            continue
        out += ["| terrakey | adm | adm_ref_id | f (MHz) | class | change | status | margin (dB) | reason |",
                "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
        out += [
            f"| {r['terrakey']} | {r['adm']} | {r['adm_ref_id'] or ''} | {_fmt(r['f_mhz'], 4)} | "
            f"{r['stn_cls']} | "
            f"{r['change']} | {r['pub_status']['status']} | {_fmt(r['margin_db'])} | {r['reason'] or ''} |"
            for r in rows
        ]
        out.append("")
    used = sorted({a for r in results for a in r["assumptions"]})
    out += ["## Assumptions", "", *(f"- `{a}`: {ASSUMPTIONS[a]}" for a in used), ""]
    out += [
        "## Open questions for Traficom",
        "",
        "1. Which publication part should Finland act on: part 1 (received) or part 2 (recorded)? "
        "Part 1 sorts first until answered.",
        "2. Should ECC/REC/(08)02 (900/1800 MHz) be added? Those notices are `not_assessed` with "
        "`no_criterion_in_registry` until then.",
        "3. The ECC/REC/(11)04 and T/R 25-08 trigger values are unverified transcriptions "
        "(`verified: false`).",
        "",
    ]
    return "\n".join(out)
