"""Inventory of foreign land mobile assignments in one terrestrial issue, from that issue's rows only.

Every query filters on `ific_no = ?` with the issue being assessed: no join reaches another issue.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import duckdb

from ific.terra.method import EIRP_TO_ERP_DB, LAND_MOBILE_CLASSES, RX_NOTICE_TYPES, TX_NOTICE_TYPES

CHANGE_BY_INTENT = {"ADD": "new", "MODIFY": "modified", "SUPPRESS": "withdrawn"}
PUB_STATUS_BY_PART = {"1": "received", "2": "recorded", "3": "returned"}

_TERRA_DIFF = ("freq_assgn", "freq_min", "freq_max", "bdwdth", "bdwdth_cde", "emi_cls", "stn_cls",
               "notice_typ", "prov", "op_hh_fr", "op_hh_to", "geo_key")  # fmt: skip
_ANT_DIFF = ("pwr_dbw", "pwr_eiv", "hgt_agl", "ant_dir", "azm_max_e", "gain_max")
_GEO_DIFF = ("site_name", "lat_dec", "long_dec")

_TERRA_COLS = ("terrakey", "adm", "adm_ref_id", "intent", "stage", "d_rcv", *_TERRA_DIFF)


def _rows(con: duckdb.DuckDBPyConnection, sql: str, ific_no: int) -> list[dict[str, Any]]:
    cur = con.execute(sql, [ific_no])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def _iso(v: Any) -> Any:
    return v.isoformat() if hasattr(v, "isoformat") else v


def load_issue(con: duckdb.DuckDBPyConnection, ific_no: int) -> dict[str, Any]:
    """All rows the assessment reads, keyed by table; each query is limited to `ific_no`."""
    classes = ", ".join(f"'{c}'" for c in LAND_MOBILE_CLASSES)
    terra_cols = ", ".join(f't."{c}"' for c in _TERRA_COLS)
    selected = (
        f"SELECT {terra_cols}, c.description AS stn_cls_description, n.description AS notice_typ_description "
        "FROM terra.fxm_terra t "
        "JOIN terra.ref_stn_cls c ON c.ific_no = t.ific_no AND c.stn_cls = t.stn_cls "
        "LEFT JOIN terra.ref_notice_typ n ON n.ific_no = t.ific_no AND n.notice_typ = t.notice_typ "
        f"WHERE t.ific_no = ? AND t.stn_cls IN ({classes}) AND t.adm <> 'FIN' AND t.intent <> 'RECORDED'"
    )
    assignments = _rows(con, selected + " ORDER BY t.terrakey", ific_no)
    targets = _rows(
        con,
        f"SELECT x.terrakey AS source_terrakey, x.action, {terra_cols} FROM terra.fxm_target x "
        "JOIN terra.fxm_terra t ON t.ific_no = x.ific_no AND t.terrakey = x.target "
        "WHERE x.ific_no = ? ORDER BY x.terrakey, t.terrakey",
        ific_no,
    )
    target_links = _rows(
        con,
        "SELECT terrakey, target, action FROM terra.fxm_target WHERE ific_no = ? ORDER BY terrakey",
        ific_no,
    )
    ant_cols = ", ".join(f'"{c}"' for c in ("terrakey", "ant_key", "pwr_xyz", *_ANT_DIFF))
    return {
        "assignments": assignments,
        "targets": targets,
        "target_links": target_links,
        "geo": _rows(
            con,
            "SELECT geo_key, geo_type, ctry, site_name, lat_dec, long_dec, site_alt FROM terra.fxm_geo "
            "WHERE ific_no = ?",
            ific_no,
        ),
        "ant": _rows(
            con, f"SELECT {ant_cols} FROM terra.fxm_ant WHERE ific_no = ? ORDER BY terrakey, ant_key", ific_no
        ),
        "ant_diag": _rows(
            con,
            "SELECT terrakey, ant_key, polar, azm, attn FROM terra.fxm_ant_diag WHERE ific_no = ? "
            "ORDER BY terrakey, ant_key, azm",
            ific_no,
        ),
        "coord": _rows(
            con,
            "SELECT terrakey, coord_prov, adm, coord_st, d_coord_st FROM terra.fxm_coord WHERE ific_no = ? "
            "ORDER BY terrakey, adm, coord_prov, coord_st",
            ific_no,
        ),
        "pub_hist": _rows(
            con,
            "SELECT terrakey, pub_no, pub_part FROM terra.fxm_pub_hist WHERE ific_no = ? "
            "ORDER BY terrakey, pub_no, pub_part",
            ific_no,
        ),
        "fdg": _rows(
            con,
            "SELECT terrakey, fdg_type, fdg_status, is_favorbl FROM terra.fxm_fdg WHERE ific_no = ? "
            "ORDER BY terrakey, fdg_type, fdg_status",
            ific_no,
        ),
        "ge06_affected": _rows(
            con,
            "SELECT g.terrakey, a.adm FROM terra.ge06_notice_group g JOIN terra.ge06_adm_affected_broad a "
            "ON a.ific_no = g.ific_no AND a.groupkey = g.groupkey WHERE g.ific_no = ? "
            "ORDER BY g.terrakey, a.adm",
            ific_no,
        ),
    }


def _by_key(rows: list[dict[str, Any]], key: str = "terrakey") -> dict[Any, list[dict[str, Any]]]:
    out: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        out[r[key]].append(r)
    return out


def _erp(ant: dict[str, Any]) -> float | None:
    if ant.get("pwr_dbw") is None:
        return None
    if ant.get("pwr_eiv") == "E":
        return float(ant["pwr_dbw"])
    if ant.get("pwr_eiv") == "I":
        return float(ant["pwr_dbw"]) - EIRP_TO_ERP_DB
    return None


def _antenna(ants: list[dict[str, Any]], diag: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The antenna row with the highest e.r.p. (first by ant_key on ties)."""
    if not ants:
        return None
    best = max(ants, key=lambda a: (-1e9 if _erp(a) is None else _erp(a), -a["ant_key"]))
    pattern = [{"azm": d["azm"], "attn": d["attn"]} for d in diag if d["ant_key"] == best["ant_key"]]
    return {
        "ant_key": best["ant_key"],
        "pwr_dbw": best["pwr_dbw"],
        "pwr_eiv": best["pwr_eiv"],
        "pwr_xyz": best["pwr_xyz"],
        "erp_dbw": _erp(best),
        "hgt_agl_m": best["hgt_agl"],
        "ant_dir": best["ant_dir"],
        "azm_max_e": best["azm_max_e"],
        "gain_max": best["gain_max"],
        "diagram": pattern,
        "rows": len(ants),
    }


def _site(g: dict[str, Any] | None) -> dict[str, Any] | None:
    if g is None or g["lat_dec"] is None or g["long_dec"] is None:
        return None
    return {
        "geo_key": g["geo_key"],
        "geo_type": g["geo_type"],
        "ctry": g["ctry"],
        "name": g["site_name"],
        "lat": g["lat_dec"],
        "lon": g["long_dec"],
        "alt_m": g["site_alt"],
    }


def _diff(
    new: dict[str, Any], old: dict[str, Any], ant_new: list, ant_old: list, geo: dict[Any, dict[str, Any]]
) -> list[dict[str, Any]]:
    out = []
    for f in _TERRA_DIFF:
        if new.get(f) != old.get(f):
            out.append(
                {"table": "fxm_terra", "field": f, "before": _iso(old.get(f)), "after": _iso(new.get(f))}
            )
    a_new = {a["ant_key"]: a for a in ant_new}
    a_old = {a["ant_key"]: a for a in ant_old}
    for k in sorted(set(a_new) | set(a_old)):
        for f in _ANT_DIFF:
            b, a = a_old.get(k, {}).get(f), a_new.get(k, {}).get(f)
            if a != b:
                out.append({"table": "fxm_ant", "field": f, "ant_key": k, "before": b, "after": a})
    g_new, g_old = geo.get(new.get("geo_key")) or {}, geo.get(old.get("geo_key")) or {}
    for f in _GEO_DIFF:
        if g_new.get(f) != g_old.get(f):
            out.append({"table": "fxm_geo", "field": f, "before": g_old.get(f), "after": g_new.get(f)})
    return out


def _pub_status(ific_no: int, hist: list[dict[str, Any]], fdg: list[dict[str, Any]]) -> dict[str, Any]:
    here = sorted((h for h in hist if h["pub_no"] == ific_no), key=lambda h: str(h["pub_part"]))
    part = str(here[0]["pub_part"]) if here else None
    part1 = [h["pub_no"] for h in hist if str(h["pub_part"]) == "1" and h["pub_no"] is not None]
    earlier = [n for n in part1 if n <= ific_no]
    findings = [
        {"fdg_type": f["fdg_type"], "fdg_status": f["fdg_status"], "is_favorbl": f["is_favorbl"] == "TRUE"}
        for f in fdg
    ]
    main = next((f for f in findings if f["fdg_type"] == "REX"), findings[0] if findings else None)
    return {
        "status": PUB_STATUS_BY_PART.get(part or "", "unknown"),
        "part": part,
        "pub_no": ific_no if here else None,
        "first_published_in": min(earlier) if earlier else None,
        "history": [{"pub_no": h["pub_no"], "part": str(h["pub_part"])} for h in hist],
        "finding": main,
        "findings": findings,
    }


def role(notice_typ: str | None) -> str:
    if notice_typ in TX_NOTICE_TYPES:
        return "tx"
    if notice_typ in RX_NOTICE_TYPES:
        return "rx"
    return "unknown"


def inventory(ific_no: int, data: dict[str, Any]) -> list[dict[str, Any]]:
    geo = {g["geo_key"]: g for g in data["geo"]}
    ant = _by_key(data["ant"])
    diag = _by_key(data["ant_diag"])
    hist = _by_key(data["pub_hist"])
    fdg = _by_key(data["fdg"])
    targets = _by_key(data["targets"], "source_terrakey")
    links = _by_key(data["target_links"])
    coord = _by_key(data["coord"])
    out = []
    for t in data["assignments"]:
        key = t["terrakey"]
        change = CHANGE_BY_INTENT.get(t["intent"], "unknown")
        sources = [f"{ific_no}:fxm_terra:{key}", f"{ific_no}:ref_stn_cls:{t['stn_cls']}"]
        target_rows, diff, diff_reason = targets.get(key, []), None, None
        target = None
        if change in ("modified", "withdrawn"):
            link = links.get(key, [])
            if target_rows:
                old = target_rows[0]
                target = {"terrakey": old["terrakey"], "action": old["action"], "intent": old["intent"]}
                sources.append(f"{ific_no}:fxm_target:{key}")
                if change == "modified":
                    diff = _diff(t, old, ant.get(key, []), ant.get(old["terrakey"], []), geo)
            else:
                diff_reason = "target_not_in_issue"
                if link:
                    target = {"terrakey": link[0]["target"], "action": link[0]["action"], "intent": None}
        a = _antenna(ant.get(key, []), diag.get(key, []))
        if a is not None:
            sources.append(f"{ific_no}:fxm_ant:{key}:{a['ant_key']}")
            if a["diagram"]:
                sources.append(f"{ific_no}:fxm_ant_diag:{key}:{a['ant_key']}")
        g = geo.get(t["geo_key"])
        if g is not None:
            sources.append(f"{ific_no}:fxm_geo:{g['geo_key']}")
        if hist.get(key):
            sources.append(f"{ific_no}:fxm_pub_hist:{key}")
        if fdg.get(key):
            sources.append(f"{ific_no}:fxm_fdg:{key}")
        out.append(
            {
                "terrakey": key,
                "adm": t["adm"],
                "adm_ref_id": t["adm_ref_id"],
                "stn_cls": t["stn_cls"],
                "stn_cls_description": t["stn_cls_description"],
                "notice_typ": t["notice_typ"],
                "notice_typ_description": (t["notice_typ_description"] or "").strip() or None,
                "role": role(t["notice_typ"]),
                "intent": t["intent"],
                "prov": t["prov"],
                "f_mhz": t["freq_assgn"],
                "freq_min_mhz": t["freq_min"],
                "freq_max_mhz": t["freq_max"],
                "bw_khz": t["bdwdth"],
                "bw_code": t["bdwdth_cde"],
                "emi_cls": t["emi_cls"],
                "d_rcv": _iso(t["d_rcv"]),
                "site": _site(g),
                "antenna": a,
                "change": change,
                "target": target,
                "diff": diff,
                "diff_reason": diff_reason,
                "pub_status": _pub_status(ific_no, hist.get(key, []), fdg.get(key, [])),
                "coordination": [
                    {"adm": c["adm"], "coord_prov": c["coord_prov"], "coord_st": c["coord_st"]}
                    for c in coord.get(key, [])
                ],
                "sources": sources,
            }
        )
    return out
