"""Draft letters to a notifying administration from stored `terra-1` findings, built on demand, never stored.

One letter per administration and issue covers its `exceeds` and FIN `COORD REQUIRED` assignments. The kind
is a pure function of the stored findings. The letter names assignments by `adm_ref_id`; terrakeys, site
coordinates and worst points go in the reviewer notes. Only `prose_paragraphs` may be polished, under the
shared `ific.drafting` guard.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from functools import cache
from typing import Any, Literal

import duckdb

from ific.config import settings
from ific.drafting import BANNER, PolishCheck, check_paragraphs, load_administrations
from ific.drafting import polish_messages as _polish_messages
from ific.terra import store
from ific.terra.method import MODEL_VERSION

LetterKind = Literal["coordination_request", "enquiry"]
_ASKS: dict[str, str] = {"coordination_request": "coordination", "enquiry": "confirmation"}


@cache
def load_letter_kinds() -> dict[str, Any]:
    return json.loads(
        (settings.data_dir / "ref" / "terrestrial_letter_kinds.json").read_text(encoding="utf-8")
    )


def choose_kind(assignment: dict[str, Any]) -> LetterKind | None:
    """`COORD REQUIRED`, or `exceeds` with no FIN coordination: request; `exceeds` with FIN coordination
    recorded (completed): enquiry; a withdrawn assignment or anything else: no letter."""
    rel = assignment["relevance"]
    if not rel["relevant"] or assignment["change"] == "withdrawn":
        return None
    if rel["fin_coord_required"]:
        return "coordination_request"
    if assignment["outcome"] == "exceeds":
        return "enquiry" if rel["fin_coordination"] else "coordination_request"
    return None


@dataclass(frozen=True)
class AnnexRow:
    adm_ref_id: str | None
    kind: LetterKind
    f_mhz: float | None
    bw_khz: float | None
    erp_dbw: float | None
    h1_m: float | None
    criterion_id: str | None
    applicability: str | None
    trigger_dbuv: float | None
    e_dbuv: float | None
    margin_db: float | None
    fin_coord: str | None
    outcome: str


@dataclass(frozen=True)
class NoConcern:
    reason: str


@dataclass(frozen=True)
class TerraDraft:
    kind: LetterKind
    ific_no: int
    adm: str
    adm_name: str | None
    annex: list[AnnexRow]
    basis: list[str]
    warnings: list[str]
    reviewer_notes: list[str]
    prose_paragraphs: list[str]
    model_version: str
    letter_md: str = field(default="")


def _f(x: float | None, spec: str) -> str:
    return "—" if x is None else format(x, spec)


def _row(r: dict[str, Any], kind: LetterKind) -> AnnexRow:
    ant = r["antenna"] or {}
    crit = r["criterion"] or {}
    fin = "; ".join(sorted({c["coord_st"] for c in r["relevance"]["fin_coordination"]})) or None
    return AnnexRow(
        adm_ref_id=r["adm_ref_id"],
        kind=kind,
        f_mhz=r["f_mhz"],
        bw_khz=r["bw_khz"],
        erp_dbw=ant.get("erp_dbw"),
        h1_m=ant.get("hgt_agl_m"),
        criterion_id=crit.get("id"),
        applicability=crit.get("applicability"),
        trigger_dbuv=r["trigger_dbuv"],
        e_dbuv=r["e_dbuv"],
        margin_db=r["margin_db"],
        fin_coord=fin,
        outcome=r["outcome"],
    )


def _basis(concerns: list[dict[str, Any]], kind: LetterKind) -> list[str]:
    lk = load_letter_kinds()
    out = [f"Basis ({lk['rr_edition']}): " + "; ".join(lk["kinds"][kind]["provisions"]) + "."]
    for c in sorted(
        {(r["criterion"]["citation"], r["criterion"]["applicability"]) for r in concerns if r["criterion"]}
    ):
        out.append(lk["basis"]["ecc"].format(criterion=c[0], applicability=c[1]))
    governing = sorted({r["regulatory"]["governing"] for r in concerns if r["regulatory"]["governing"]})
    out += [lk["basis"]["governing"].format(governing=g) for g in governing]
    if any(r["regulatory"]["ge06"]["applies"] for r in concerns):
        out.append(lk["basis"]["ge06"])
    return out


def _paragraphs(d: TerraDraft) -> list[str]:
    lk = load_letter_kinds()
    n = len(d.annex)
    required = sum(1 for a in d.annex if a.fin_coord and "COORD REQUIRED" in a.fin_coord)
    exceeds = [a for a in d.annex if a.outcome == "exceeds"]
    refs = ", ".join(a.adm_ref_id or "(no reference)" for a in d.annex)
    first = (
        f"The Administration of Finland has examined the land mobile assignments of the Administration of "
        f"{d.adm_name or d.adm} ({d.adm}) published in BR IFIC (Terrestrial Services) {d.ific_no}. "
        f"{n} assignment{'s' if n != 1 else ''} ({refs}) may affect radio services in Finland."
    )
    detail = []
    if exceeds:
        worst = max(exceeds, key=lambda a: a.margin_db or 0)
        detail.append(
            f"For {len(exceeds)} of them the predicted field strength at the Finnish border exceeds the "
            f"coordination trigger, by up to {worst.margin_db:.1f} dB ({worst.adm_ref_id or 'no reference'})."
        )
    if required:
        detail.append(f"For {required} of them the coordination status with Finland is COORD REQUIRED.")
    second = " ".join(detail) + " The values are given in the annex."
    return [first, second, lk["kinds"][d.kind]["ask"]]


def _annex_md(annex: list[AnnexRow]) -> list[str]:
    lines = [
        "| Reference | f (MHz) | Bandwidth (kHz) | e.r.p. (dBW) | h1 (m) | Criterion | Trigger (dB(µV/m)) "
        "| E at border (dB(µV/m)) | Margin (dB) | Coordination with FIN | Asks for |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for a in annex:
        crit = f"{a.criterion_id} ({a.applicability})" if a.criterion_id else "—"
        lines.append(
            f"| {a.adm_ref_id or '—'} | {_f(a.f_mhz, 'g')} | {_f(a.bw_khz, 'g')} | {_f(a.erp_dbw, '.1f')} | "
            f"{_f(a.h1_m, 'g')} | {crit} | {_f(a.trigger_dbuv, '.1f')} | "
            f"{_f(a.e_dbuv, '.1f') if a.e_dbuv is not None else a.outcome.replace('_', ' ')} | "
            f"{_f(a.margin_db, '+.1f')} | {a.fin_coord or 'none recorded'} | {_ASKS[a.kind]} |"
        )
    return lines


def render_letter(d: TerraDraft, paragraphs: list[str]) -> str:
    to = f"Administration of {d.adm_name} ({d.adm})" if d.adm_name else f"Administration ({d.adm})"
    subject = f"BR IFIC (Terrestrial Services) {d.ific_no}: {load_letter_kinds()['kinds'][d.kind]['subject']}"
    lines = [
        f"**{BANNER}**",
        "",
        "From: Administration of Finland",
        f"To: {to}",
        "Date: [Date]",
        "Reference: [Reference]",
        f"Subject: {subject}",
        "",
        "Dear Sir or Madam,",
        "",
    ]
    for p in paragraphs:
        lines += [p, ""]
    lines += [
        "Yours faithfully,",
        "",
        "[Name, title]",
        "Administration of Finland",
        "[e-mail]",
        "",
        f"## Annex: field strength at the Finnish border (model {d.model_version})",
        "",
        "Deterministic ITU-R P.1546 predictions over flat terrain at the criterion's time and location "
        "percentages and receiving height. Each row is one assignment and the trigger it is read against.",
        "",
        *_annex_md(d.annex),
        "",
        *d.basis,
        "",
        f"**{BANNER}**",
    ]
    return "\n".join(lines) + "\n"


def to_markdown(d: TerraDraft) -> str:
    notes = [f"- Warning: {w}" for w in d.warnings] + [f"- {n}" for n in d.reviewer_notes]
    return d.letter_md + "\n---\n\n## Reviewer notes (internal – do not send)\n\n" + "\n".join(notes) + "\n"


def _notes(r: dict[str, Any]) -> str:
    site = r["site"] or {}
    t2 = r["hazard"].get("tier2")
    worst = (
        f"; worst Finnish point {t2['worst_point']['lat']:.4f}N {t2['worst_point']['lon']:.4f}E "
        f"({t2['worst_point']['distance_km']:.1f} km)"
        if t2
        else ""
    )
    return (
        f"{r['adm_ref_id']}: terrakey {r['terrakey']}, site {site.get('name')} {site.get('lat', 0):.4f}N "
        f"{site.get('lon', 0):.4f}E{worst}; sources {', '.join(r['sources'][:3])}"
    )


def build_draft(con: duckdb.DuckDBPyConnection, ific_no: int, adm: str) -> TerraDraft | NoConcern | None:
    """None when the issue is not assessed or has no assignment of `adm`."""
    adm = adm.upper()
    rows = [r for r in store.all_results(con, ific_no) if r["adm"] == adm]
    if not rows:
        return None
    concerns = [
        (r, k) for r in sorted(rows, key=lambda r: r["sort_key"]) if (k := choose_kind(r)) is not None
    ]
    if not concerns:
        return NoConcern(f"no exceeds or COORD REQUIRED assignment of {adm} in BR IFIC {ific_no}")
    kind: LetterKind = (
        "coordination_request" if any(k == "coordination_request" for _, k in concerns) else "enquiry"
    )
    warnings = []
    if any(r["criterion"] and not r["criterion"]["verified"] for r, _ in concerns):
        warnings.append("criterion values are unverified transcriptions (verified: false)")
    if any(r["criterion"] and r["criterion"]["applicability"] != "applicable" for r, _ in concerns):
        warnings.append("the ECC criterion is not applicable as such to this administration; see the basis")
    draft = TerraDraft(
        kind=kind,
        ific_no=ific_no,
        adm=adm,
        adm_name=load_administrations()["admins"].get(adm),
        annex=[_row(r, k) for r, k in concerns],
        basis=_basis([r for r, _ in concerns], kind),
        warnings=warnings,
        reviewer_notes=[_notes(r) for r, _ in concerns],
        prose_paragraphs=[],
        model_version=MODEL_VERSION,
    )
    paragraphs = _paragraphs(draft)
    return replace(draft, prose_paragraphs=paragraphs, letter_md=render_letter(draft, paragraphs))


def concern_adms(con: duckdb.DuckDBPyConnection, ific_no: int) -> dict[str, int]:
    """Administrations with at least one assignment that would be in a letter, with the count."""
    out: dict[str, int] = {}
    for r in store.all_results(con, ific_no):
        if choose_kind(r) is not None:
            out[r["adm"]] = out.get(r["adm"], 0) + 1
    return dict(sorted(out.items()))


def check_polish(d: TerraDraft, polished: str) -> PolishCheck:
    """The shared guard, plus every annex reference kept verbatim: the letter names assignments only by it."""
    check = check_paragraphs(d.prose_paragraphs, d.adm, polished)
    if check.paragraphs is None:
        return check
    body = "\n\n".join(d.prose_paragraphs)
    text = "\n\n".join(check.paragraphs)
    refs = sorted({a.adm_ref_id for a in d.annex if a.adm_ref_id})
    missing = [r for r in refs if body.count(r) != text.count(r)]
    if missing:
        return PolishCheck(None, missing, [], "the rewrite changed an assignment reference")
    return check


def polish_messages(d: TerraDraft) -> list[dict[str, str]]:
    return _polish_messages(d.prose_paragraphs)
