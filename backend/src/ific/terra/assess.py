"""`terra-1` orchestration: inventory, relevance (Tier 0), regulatory context, the field-strength hazard
(Tier 1 and 2) and the fixed sort keys. A pure function of one issue's `terra` rows and the reference data.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import duckdb

from ific.riia.hazards import OUTCOME_RANK
from ific.riia.store import round_floats
from ific.terra import inventory, refdata, regulatory
from ific.terra.hazards import evaluate, not_evaluated
from ific.terra.method import MODEL_VERSION
from ific.terra.relevance import relevance

log = logging.getLogger("ific.terra")

CHANGE_RANK = {"new": 0, "modified": 0, "withdrawn": 1}
# Part 1 (received) sorts before part 2 (recorded) until Traficom says which part Finland acts on.
PUB_RANK = {"received": 0, "recorded": 1, "returned": 2}
NO_MARGIN = 1e9
_EVALUATED = (
    "A-T-FLAT",
    "A-T-H1-AGL",
    "A-T-LAND-MASK",
    "A-T-BORDER-SAMPLE",
    "A-T-TIER1-3DB",
    "A-T-BW-CHANNEL",
)

Progress = Callable[[int, int], None]


def sort_key(outcome: str, fin_coord_required: bool, margin: float | None, change: str, pub: str, key: int):
    return [
        OUTCOME_RANK[outcome],
        0 if fin_coord_required else 1,
        -margin if margin is not None else NO_MARGIN,
        CHANGE_RANK.get(change, 2),
        PUB_RANK.get(pub, 3),
        key,
    ]


def _hazard(a: dict[str, Any], rel: dict[str, Any], reg: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if not rel["relevant"]:
        return not_evaluated("not_applicable", "not_relevant"), []
    if a["change"] == "withdrawn":
        return not_evaluated("not_applicable", "withdrawn"), []
    if a["role"] == "rx":
        return not_evaluated("not_applicable", "receiving_station"), []
    if a["role"] != "tx":
        return not_evaluated("not_assessed", "unknown_notice_type"), []
    if reg["criterion_id"] is None:
        return not_evaluated("not_assessed", "no_criterion_in_registry"), []
    criterion = next(c for c in refdata.criteria() if c["id"] == reg["criterion_id"])
    hazard, ids = evaluate(a, criterion)
    if hazard["tier"] >= 1:
        ids = [*ids, *_EVALUATED]
    return hazard, ids


def assess_assignment(
    ific_no: int, a: dict[str, Any], ge06_fin: bool, m4: list[dict[str, Any]], m4_edition: str | None
) -> dict[str, Any]:
    reg = regulatory.context(a, m4, m4_edition)
    rel = relevance(a, ge06_fin, bool(reg["m4_rows"]))
    hazard, ids = _hazard(a, rel, reg)
    if reg["criterion_id"] is not None:
        ids.append("A-T-BILATERAL")
        if a["adm"] == "RUS":
            ids.append("A-T-ECC-RUS")
    ids.append("A-T-PUB-PARTS")
    criterion = next((c for c in refdata.criteria() if c["id"] == reg["criterion_id"]), None)
    t2 = hazard.get("tier2")
    margin = t2["margin_db"] if t2 else None
    return round_floats(
        {
            "model_version": MODEL_VERSION,
            "ific_no": ific_no,
            **a,
            "relevance": rel,
            "regulatory": reg,
            "criterion": None
            if criterion is None
            else {
                "id": criterion["id"],
                "title": criterion["title"],
                "citation": criterion["citation"],
                "verified": criterion["verified"],
                "verified_by": criterion["verified_by"],
                "applicability": reg["criterion_applicability"],
            },
            "hazard": hazard,
            "outcome": hazard["outcome"],
            "reason": hazard["reason"],
            "e_dbuv": t2["e_dbuv"] if t2 else None,
            "trigger_dbuv": hazard["trigger"]["e_dbuv_m"] if "trigger" in hazard else None,
            "margin_db": margin,
            "assumptions": sorted(set(ids)),
            "sort_key": sort_key(
                hazard["outcome"],
                rel["fin_coord_required"],
                margin,
                a["change"],
                a["pub_status"]["status"],
                a["terrakey"],
            ),
        },
        6,
    )


def assess_issue(
    con: duckdb.DuckDBPyConnection,
    ific_no: int,
    progress: Progress | None = None,
    stats_out: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    started = time.perf_counter()
    exists = con.execute("SELECT 1 FROM terra.issue WHERE ific_no = ?", [ific_no]).fetchone()
    if not exists:
        raise ValueError(f"BR IFIC {ific_no} is not ingested")
    data = inventory.load_issue(con, ific_no)
    items = inventory.inventory(ific_no, data)
    m4, edition = regulatory.load_m4(con)
    ge06_fin = {r["terrakey"] for r in data["ge06_affected"] if r["adm"] == "FIN"}
    results = []
    for i, a in enumerate(items, 1):
        results.append(assess_assignment(ific_no, a, a["terrakey"] in ge06_fin, m4, edition))
        if progress is not None:
            progress(i, len(items))
    results.sort(key=lambda r: r["terrakey"])
    ms = round((time.perf_counter() - started) * 1000)
    counts: dict[str, int] = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    log.info(
        "terra assess brific=%d assignments=%d outcomes=%s duration_ms=%d", ific_no, len(results), counts, ms
    )
    if stats_out is not None:
        stats_out.update({"assignments": len(results), "duration_ms": ms, **counts})
    return results
