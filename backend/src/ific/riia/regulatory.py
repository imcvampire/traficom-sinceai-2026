"""Regulatory context of a notice: procedure stage, comment window and the BR's findings on Finland."""

import calendar
import json
from dataclasses import dataclass
from datetime import date, datetime
from functools import cache
from pathlib import Path
from typing import Any

from ific.config import settings

STAGE_BY_PROV = {
    "9.1/IA": "API/A",
    "9.1A": "API/A",
    "9.6": "CR/C",
    "9.7": "CR/C",
    "11.2": "Notification",
    "RS49": "Res49",
}


@cache
def load_windows(path: Path | None = None) -> dict[str, Any]:
    path = path or settings.data_dir / "ref" / "rr_comment_windows.json"
    return json.loads(path.read_text(encoding="utf-8"))


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class Finding:
    source: str
    coord_prov: str
    agree_st: str | None
    grp_id: int | None
    aff_ntc_id: int | None
    network: str | None


def is_technical(coord_prov: str) -> bool:
    return any(coord_prov.startswith(p) for p in load_windows()["technical_findings_prefixes"])


def context(prov: str, d_wic: datetime | date | None, findings: list[Finding], as_of: date) -> dict[str, Any]:
    """Regulatory context at an explicit `as_of`; only `days_left`, `window_open` depend on it."""
    windows = load_windows()
    spec = windows["provisions"].get(prov, {})
    stage = spec.get("stage") or STAGE_BY_PROV.get(prov, "Notification")
    published = d_wic.date() if isinstance(d_wic, datetime) else d_wic
    months = spec.get("window_months")
    window_end = add_months(published, months) if (published and months) else None
    days_left = (window_end - as_of).days if window_end else None
    citations = [spec["cite"]] if spec.get("cite") else []
    if findings:
        citations.append("BR findings in the IFIC: space.provn (adm = FIN) and space.tr_aff_ntw (adm = FIN)")
    else:
        citations.append(windows["inclusion_cite"])
    return {
        "stage": stage,
        "provision": prov,
        "d_wic": published.isoformat() if published else None,
        "window_end": window_end.isoformat() if window_end else None,
        "days_left": days_left,
        "window_open": days_left is not None and days_left >= 0,
        "fin_identified": bool(findings),
        "window_cite": spec.get("cite"),
        "findings": [vars(f) for f in findings],
        "citations": citations,
    }


def with_as_of(regulatory: dict[str, Any], as_of: date) -> dict[str, Any]:
    """Recompute the as_of-dependent fields of a stored context."""
    out = dict(regulatory)
    end = date.fromisoformat(out["window_end"]) if out.get("window_end") else None
    out["days_left"] = (end - as_of).days if end else None
    out["window_open"] = out["days_left"] is not None and out["days_left"] >= 0
    return out
