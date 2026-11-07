"""Regulatory context of a terrestrial assignment: RR provision, GE06, the ECC criterion and its
applicability, the matching Finnish M4 rows, and the bilateral basis."""

from __future__ import annotations

from typing import Any

import duckdb

from ific.terra import refdata

FIN_FRAMEWORK_SOURCE = "ref.m4_allocation"


def load_m4(con: duckdb.DuckDBPyConnection) -> tuple[list[dict[str, Any]], str | None]:
    """M4 allocation rows and the regulation edition, or ([], None) when the reference data is not loaded."""
    exists = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'ref' AND table_name = 'm4_allocation'"
    ).fetchone()
    if not exists:
        return [], None
    rows = con.execute(
        "SELECT id, sub_band_lower_hz, sub_band_upper_hz, services_in_finland, sub_band_usage "
        "FROM ref.m4_allocation ORDER BY sub_band_lower_hz, id"
    ).fetchall()
    edition = con.execute("SELECT edition FROM ref.source WHERE source_id = 'm4_regulation'").fetchone()
    return (
        [{"id": r[0], "lower_hz": r[1], "upper_hz": r[2], "services": r[3], "usage": r[4]} for r in rows],
        edition[0] if edition else None,
    )


def m4_rows(m4: list[dict[str, Any]], fmin_mhz: float | None, fmax_mhz: float | None) -> list[dict[str, Any]]:
    if fmin_mhz is None or fmax_mhz is None:
        return []
    lo, hi = fmin_mhz * 1e6, fmax_mhz * 1e6
    return [r for r in m4 if r["lower_hz"] < hi and r["upper_hz"] > lo]


def context(a: dict[str, Any], m4: list[dict[str, Any]], m4_edition: str | None) -> dict[str, Any]:
    fw = refdata.load_frameworks()
    prov = a["prov"] or ""
    spec = fw["rr_provisions"].get(prov)
    ge06 = (a["notice_typ"] or "").startswith("G") or prov.startswith("GE06-")
    criterion = refdata.criterion_for(a["f_mhz"]) if a["f_mhz"] is not None else None
    appl = fw["ecc_applicability"]["by_adm"].get(a["adm"], fw["ecc_applicability"]["default"])
    # T/R 25-08 and ECC/REC/(11)04 are both ECC acts, so the same per-administration applicability holds.
    applicability = appl["status"] if criterion else None
    rows = m4_rows(m4, a["freq_min_mhz"], a["freq_max_mhz"])
    m4_cite = fw["national"]["m4"]["cite"] + (f", edition {m4_edition}" if m4_edition else "")
    citations = [spec["cite"] if spec else f"RR provision {prov or 'not given'} (BR IFIC fxm_terra.prov)"]
    if ge06:
        citations.append(fw["ge06"]["cite"])
    if criterion is not None:
        citations.append(criterion["citation"])
    citations.append(m4_cite)
    citations.append(
        fw["national"]["allocation_table"]["cite"]
        + (f": rows {', '.join(str(r['id']) for r in rows)}" if rows else ": no overlapping row")
    )
    if appl.get("governing"):
        citations.append(appl["governing"])
    citations.append(fw["bilateral"]["cite"])
    return {
        "rr_provision": {"code": prov or None, "label": spec["label"] if spec else None},
        "ge06": {"applies": ge06, "cite": fw["ge06"]["cite"] if ge06 else None},
        "criterion_id": criterion["id"] if criterion else None,
        "criterion_applicability": applicability,
        "applicability_reason": appl["reason"] if criterion else None,
        "governing": appl.get("governing"),
        "m4_rows": [{"id": r["id"], "services": r["services"]} for r in rows],
        "m4_cite": m4_cite,
        "citations": citations,
    }
