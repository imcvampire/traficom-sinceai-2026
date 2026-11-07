"""Consistency checks of one assessed issue (doc: 'How the model is checked')."""

from collections import Counter, defaultdict
from typing import Any

from ific.riia import MODEL_VERSION, regulatory
from ific.riia.hazards import OUTCOME_RANK, QUANTIFIED_MODES

SUMMARY_FIELDS = (
    "ntc_id",
    "sat_name",
    "adm",
    "prov",
    "orbit",
    "act_code",
    "worst_outcome",
    "hazard_counts",
    "services_exceeding",
    "max_share_violating",
    "max_median_exceedance_db",
    "max_worst_case_db",
    "in_queue",
)


def _why(quantified: list[dict[str, Any]]) -> str:
    if any("never above the horizon" in (h["reason"] or "") for h in quantified):
        return "never above the horizon in Finland"
    if all(h["outcome"] == "not_applicable" for h in quantified):
        return "no downlink overlaps or adjoins a protected Finnish band of a riia-1 class"
    live = [h for h in quantified if h["outcome"] not in ("screened_out", "not_applicable")]
    return (
        ", ".join(sorted({h["hazard_id"] for h in live})[:4])
        or "all overlapping hazards screened out at Tier 1"
    )


def summary_snapshot(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reviewable per-notice summaries (fixtures/riia/3074-summary.json)."""
    out = []
    for r in sorted(results, key=lambda r: r["ntc_id"]):
        s = {k: r[k] for k in SUMMARY_FIELDS}
        s["fin_identified"] = r["regulatory"]["fin_identified"]
        s["days_left"] = r["regulatory"]["days_left"]
        out.append(s)
    return out


def checks(results: list[dict[str, Any]]) -> dict[str, Any]:
    per_class: dict[str, Counter] = defaultdict(Counter)
    tier_violations, bad_exceeds, br_rows, pfd_violations = [], [], [], []
    pfd_counts: Counter = Counter()
    for r in results:
        if r.get("pfd_outcome") is not None:
            pfd_counts[r["pfd_outcome"]] += 1
            exceeding = any((c["margin_db"] or 0) > 0 for c in r["pfd_checks"])
            if (r["pfd_outcome"] == "exceeds") != exceeding:
                pfd_violations.append(r["ntc_id"])
        quantified = [h for h in r["hazards"] if h["mode"] in QUANTIFIED_MODES]
        for h in quantified:
            per_class[h["service_class"]][h["outcome"]] += 1
            if (
                h["tier"] == 2
                and h["tier2_max_db"] is not None
                and h["worst_case_db"] < h["tier2_max_db"] - 1e-9
            ):
                tier_violations.append((r["ntc_id"], h["hazard_id"], h["worst_case_db"], h["tier2_max_db"]))
        never_visible = any("never above the horizon" in (h["reason"] or "") for h in quantified)
        if (r["act_code"] == "S" or never_visible) and any(h["outcome"] == "exceeds" for h in quantified):
            bad_exceeds.append(r["ntc_id"])
        technical = [f for f in r["regulatory"]["findings"] if regulatory.is_technical(f["coord_prov"])]
        if technical:
            live = [h for h in quantified if h["outcome"] not in ("screened_out", "not_applicable")]
            worst = max(
                (h["worst_case_db"] for h in quantified if h["worst_case_db"] is not None), default=None
            )
            br_rows.append(
                {
                    "ntc_id": r["ntc_id"],
                    "sat_name": r["sat_name"],
                    "provisions": sorted({f["coord_prov"] for f in technical}),
                    "agrees": bool(live),
                    "worst_outcome": r["worst_outcome"],
                    "max_worst_case_db": worst,
                    "why": _why(quantified),
                }
            )
    return {
        "per_class": per_class,
        "tier_violations": tier_violations,
        "bad_exceeds": bad_exceeds,
        "br": br_rows,
        "pfd_counts": pfd_counts,
        "pfd_violations": pfd_violations,
    }


def _db(x: float | None) -> str:
    return "—" if x is None else f"{x:.1f} dB"


def report(ific_no: int, as_of: str, results: list[dict[str, Any]], stats: dict[str, float]) -> str:
    c = checks(results)
    outcomes = list(OUTCOME_RANK)
    br = c["br"]
    agree = [b for b in br if b["agrees"]]
    misses = sorted((b for b in br if not b["agrees"]), key=lambda b: -(b["max_worst_case_db"] or -999))
    worst_counts = Counter(r["worst_outcome"] for r in results)
    lines = [
        f"# Consistency report: IFIC {ific_no}, model {MODEL_VERSION}",
        "",
        f"- Receiver source: `{results[0]['receiver_source'] if results else '—'}`; `as_of`: {as_of}.",
        f"- Notices: {len(results)}; hazards: {sum(len(r['hazards']) for r in results)}.",
        "- Notice worst outcome: " + ", ".join(f"{o} {worst_counts.get(o, 0)}" for o in outcomes) + ".",
        "",
        "## Checks",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Tier 1 worst case ≥ Tier 2 maximum, every Tier 2 hazard | "
        f"{'pass' if not c['tier_violations'] else 'FAIL'} ({len(c['tier_violations'])} violations) |",
        f"| No `exceeds` for suppressions or never-visible notices | "
        f"{'pass' if not c['bad_exceeds'] else 'FAIL'} ({len(c['bad_exceeds'])} notices) |",
        f"| BR identified Finland under a technical provision → at least one live hazard | "
        f"{len(agree)} of {len(br)} agree, {len(misses)} misses |",
        f"| pfd `exceeds` ⇔ some Table 21-4 check has a positive margin | "
        f"{'pass' if not c['pfd_violations'] else 'FAIL'} ({len(c['pfd_violations'])} notices) |",
        "",
        "- pfd vs RR Table 21-4: " + ", ".join(f"{o} {c['pfd_counts'].get(o, 0)}" for o in outcomes) + ".",
        "",
        "## Outcomes per service class (quantified modes)",
        "",
        "| Class | " + " | ".join(outcomes) + " |",
        "|---|" + "---|" * len(outcomes),
    ]
    for cls in sorted(c["per_class"]):
        lines.append(f"| {cls} | " + " | ".join(str(c["per_class"][cls].get(o, 0)) for o in outcomes) + " |")
    lines += ["", "## BR findings naming Finland (technical provisions)", ""]
    lines += [
        "| ntc_id | Network | Provisions | Worst outcome | Max Tier 1 (dB) | Agrees | Why |",
        "|---|---|---|---|---|---|---|",
    ]
    for b in sorted(br, key=lambda b: b["ntc_id"]):
        wc = "—" if b["max_worst_case_db"] is None else f"{b['max_worst_case_db']:.1f}"
        lines.append(
            f"| {b['ntc_id']} | {b['sat_name']} | {', '.join(b['provisions'])} | {b['worst_outcome']} | "
            f"{wc} | "
            f"{'yes' if b['agrees'] else '**miss**'} | {b['why']} |"
        )
    if misses:
        lines += [
            "",
            "Misses, by worst-case value: "
            + ", ".join(f"{m['ntc_id']} ({_db(m['max_worst_case_db'])})" for m in misses)
            + ".",
        ]
    if c["tier_violations"]:
        lines += ["", "## Tier violations", ""] + [f"- {v}" for v in c["tier_violations"]]
    if stats:
        lines += [
            "",
            "## Run time",
            "",
            f"- Total: {stats.get('duration_ms', 0) / 1000:.1f} s.",
            f"- Tier 1: {stats.get('tier1_s', 0):.1f} s; "
            f"{int(stats.get('tier1_screened', 0))} hazards screened out.",
            f"- Tier 2: {stats.get('tier2_s', 0):.1f} s for "
            f"{int(stats.get('tier2', 0))} Monte Carlo hazards.",
        ]
    return "\n".join(lines) + "\n"
