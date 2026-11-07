"""Sensitivity report: each `assumption` input moved to the low and high end of its range (fixed list)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Any

import duckdb

from ific.riia import MODEL_VERSION
from ific.riia.assess import assess_issue
from ific.riia.hazards import Overrides
from ific.riia.receivers import ReceiverPopulation


@dataclass(frozen=True)
class Perturbation:
    assumption_id: str
    end: str
    label: str
    overrides: Overrides
    classes: tuple[str, ...] = ()


PERTURBATIONS: tuple[Perturbation, ...] = (
    Perturbation(
        "peak_gain",
        "low",
        "Satellite gain −10 dB (beam not pointed at Finland)",
        Overrides(sat_gain_offset_db=-10),
    ),
    Perturbation("full_duty_cycle", "low", "Activity factor 10 % (−10 dB)", Overrides(activity_db=-10)),
    Perturbation(
        "carrier_in_channel",
        "low",
        "Carrier placed uniformly in its group band",
        Overrides(carrier="uniform"),
    ),
    Perturbation("adjacent_extent", "low", "Adjacent range 1.0 × B_n", Overrides(adj_extent_bn=1.0)),
    Perturbation("adjacent_extent", "high", "Adjacent range 5.0 × B_n", Overrides(adj_extent_bn=5.0)),
    Perturbation(
        "dist:fixed:pointing_elev_deg",
        "low",
        "Fixed links point at 0–1°",
        Overrides(distributions=(("fixed", "pointing_elev_deg", 0.0, 1.0),)),
        ("fixed",),
    ),
    Perturbation(
        "dist:fixed:pointing_elev_deg",
        "high",
        "Fixed links point at 0–10°",
        Overrides(distributions=(("fixed", "pointing_elev_deg", 0.0, 10.0),)),
        ("fixed",),
    ),
    Perturbation(
        "dist:radio_astronomy:pointing_elev_deg",
        "low",
        "Telescopes point at 30–90°",
        Overrides(distributions=(("radio_astronomy", "pointing_elev_deg", 30.0, 90.0),)),
        ("radio_astronomy",),
    ),
    Perturbation(
        "dist:fss_es:pointing_elev_deg",
        "high",
        "FSS dishes point at 5–30°",
        Overrides(distributions=(("fss_es", "pointing_elev_deg", 5.0, 30.0),)),
        ("fss_es",),
    ),
    Perturbation(
        "class_values",
        "high",
        "Fixed pattern F.699 (peak envelope) instead of F.1245 (average)",
        Overrides(patterns=(("fixed", "F.699"),)),
        ("fixed",),
    ),
)
NOT_PERTURBED = {
    "grid": "Grid density changes only the number of sites, not any per-receiver level; not re-run for cost.",
    "sample_size": "Fixed by the method (N rule); reproducibility is checked by the determinism test.",
    "circular_orbit": "No alternative orbit model in riia-1.",
    "generic_population": "The alternative is the stations source, a follow-up plan.",
}


def _hazards(results: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    return {(r["ntc_id"], h["hazard_id"]): h for r in results for h in r["hazards"] if h["in_summary"]}


def _median_exceedance(h: dict[str, Any]) -> float | None:
    vals = [e["median_db"] for e in h["exceedance_db"] if e["median_db"] is not None]
    return max(vals) if vals else None


def compare(
    base: list[dict[str, Any]], perturbed: list[dict[str, Any]], classes: tuple[str, ...]
) -> dict[str, Any]:
    a, b = _hazards(base), _hazards(perturbed)
    flips, shifts, share = [], [], []
    for key in sorted(set(a) | set(b)):
        ha, hb = a.get(key), b.get(key)
        if classes and (ha or hb)["service_class"] not in classes:
            continue
        oa, ob = (ha or {}).get("outcome", "not_applicable"), (hb or {}).get("outcome", "not_applicable")
        if (oa == "exceeds") != (ob == "exceeds"):
            flips.append((key, oa, ob))
        if ha and hb:
            ma, mb = _median_exceedance(ha), _median_exceedance(hb)
            if ma is not None and mb is not None:
                shifts.append(mb - ma)
            if ha["share_violating"] is not None and hb["share_violating"] is not None:
                share.append(hb["share_violating"] - ha["share_violating"])
    return {
        "flips": flips,
        "median_shift_db": median(shifts) if shifts else None,
        "max_abs_shift_db": max((abs(s) for s in shifts), default=None),
        "mean_share_change": sum(share) / len(share) if share else None,
        "hazards_compared": len(shifts),
    }


def run(
    con: duckdb.DuckDBPyConnection,
    ific_no: int,
    as_of: date,
    population: ReceiverPopulation,
    base: list[dict[str, Any]] | None = None,
    log: Callable[[str], None] = lambda _: None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    base = base if base is not None else assess_issue(con, ific_no, as_of, population)
    affected = {r["ntc_id"] for r in base if any(h["tier"] >= 1 for h in r["hazards"])}
    rows, flips = [], {}
    for p in PERTURBATIONS:
        log(f"sensitivity {p.assumption_id} ({p.end})")
        only = affected if p.overrides.adj_extent_bn == Overrides().adj_extent_bn else None
        perturbed = assess_issue(
            con, ific_no, as_of, population, overrides=p.overrides, only=only, classes=p.classes
        )
        scope = [r for r in base if only is None or r["ntc_id"] in only]
        c = compare(scope, perturbed, p.classes)
        rows.append({"perturbation": p, **c})
        flips[p.assumption_id] = flips.get(p.assumption_id, 0) + len(c["flips"])
    return rows, flips


def _fmt(x: float | None, unit: str = " dB") -> str:
    return "—" if x is None else f"{x:+.1f}{unit}"


def report(
    ific_no: int, as_of: date, receiver_source: str, rows: list[dict[str, Any]], flips: dict[str, int]
) -> str:
    sensitive = sorted(k for k, v in flips.items() if v > 0)
    lines = [
        f"# Sensitivity report: IFIC {ific_no}, model {MODEL_VERSION}",
        "",
        f"- Receiver source: `{receiver_source}`; `as_of`: {as_of.isoformat()}.",
        "- Each `assumption` input below is moved to one end of its range and the issue is re-assessed."
        " The perturbation list is fixed in `backend/src/ific/riia/sensitivity.py`, so the report is"
        " deterministic.",
        "- A flip is a quantified hazard whose outcome changes to or from `exceeds`. Shifts are in the worst"
        " median `exceedance_db` of each hazard assessed in both runs.",
        "",
        "## Outcome-sensitive assumptions",
        "",
        *(
            [f"- `{s}`: {flips[s]} outcome flips" for s in sensitive]
            or ["- None: no perturbation flipped an outcome."]
        ),
        "",
        "## Perturbations",
        "",
        "| Assumption | End | Change | Flips | Median shift | Max abs shift | Mean Δ share violating |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        p = r["perturbation"]
        share = "—" if r["mean_share_change"] is None else f"{r['mean_share_change'] * 100:+.1f} pp"
        lines.append(
            f"| `{p.assumption_id}` | {p.end} | {p.label} | {len(r['flips'])} | "
            f"{_fmt(r['median_shift_db'])} | "
            f"{_fmt(r['max_abs_shift_db'])} | {share} |"
        )
    lines += ["", "## Flips (first 10 per perturbation)", ""]
    for r in rows:
        if not r["flips"]:
            continue
        p = r["perturbation"]
        lines.append(
            f"- `{p.assumption_id}` ({p.end}): "
            + "; ".join(f"{ntc} {hid} {a} → {b}" for (ntc, hid), a, b in r["flips"][:10])
            + (f"; … {len(r['flips']) - 10} more" if len(r["flips"]) > 10 else "")
        )
    lines += ["", "## Not perturbed", ""] + [f"- `{k}`: {v}" for k, v in NOT_PERTURBED.items()]
    return "\n".join(lines) + "\n"
