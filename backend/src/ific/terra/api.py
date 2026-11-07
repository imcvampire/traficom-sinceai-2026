"""`/api/terrestrial`: terrestrial land mobile issues, assessments, trends and draft letters."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from dataclasses import asdict
from datetime import date
from pathlib import Path as FsPath
from typing import Annotated, Literal

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from ific import ingest
from ific.config import PROJECT_ROOT, settings
from ific.drafting import load_administrations
from ific.llm import ChatClient, LlmError
from ific.propagation import p1546
from ific.riia.schemas import JobOut, Outcome
from ific.terra import draft, export, refdata, store, trends
from ific.terra.jobs import TerraJobRunner
from ific.terra.method import ASSUMPTIONS, MODEL_VERSION, NEIGHBOURS
from ific.terra.schemas import (
    AssignmentListOut,
    AssignmentOut,
    AssumptionOut,
    Change,
    CriterionOut,
    DraftAdmOut,
    PubStatus,
    TerraAcceptedOut,
    TerraDraftOut,
    TerraDraftPolishOut,
    TerraIssueOut,
    TerraModelOut,
    TrendsOut,
)

log = logging.getLogger("ific.terra")
draft_log = logging.getLogger("ific.draft")

router = APIRouter(prefix="/api/terrestrial", tags=["terrestrial"])


def get_db(request: Request) -> Iterator[duckdb.DuckDBPyConnection]:
    cursor = request.app.state.db.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


def get_jobs(request: Request) -> TerraJobRunner:
    return request.app.state.terra_jobs


Db = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]
Jobs = Annotated[TerraJobRunner, Depends(get_jobs)]


def _display(path: FsPath) -> str:
    for base in (settings.terra_download_dir, PROJECT_ROOT):
        if path.is_relative_to(base):
            return path.relative_to(base).as_posix()
    return path.name


def _paths(con: duckdb.DuckDBPyConnection) -> tuple[dict[int, FsPath], dict[int, tuple[str, int]]]:
    return ingest.discover_terra_issues(settings), ingest.ingested_terra_issues(con)


@router.get("/issues")
def issues(con: Db, jobs: Jobs) -> list[TerraIssueOut]:
    found, ingested = _paths(con)
    summaries = store.issue_summaries(con)
    out = []
    for no in sorted(set(found) | set(ingested) | set(summaries), reverse=True):
        s = summaries.get(no)
        out.append(
            TerraIssueOut(
                ific_no=no,
                path=_display(found[no]) if no in found else ingested.get(no, ("", 0))[0],
                ingested=no in ingested,
                assessed=s is not None,
                model_version=s["model_version"] if s else None,
                assignment_count=s["assignments"] if s else None,
                relevant_count=s["relevant"] if s else None,
                outcome_counts=s["outcome_counts"] if s else None,
                assessed_at=s["assessed_at"] if s else None,
                job=JobOut(**jobs.job(no)),
            )
        )
    return out


@router.post("/issues/{ific_no}", status_code=status.HTTP_202_ACCEPTED)
def assess(ific_no: int, con: Db, jobs: Jobs) -> TerraAcceptedOut:
    found, ingested = _paths(con)
    if ific_no not in found and ific_no not in ingested:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"BR IFIC {ific_no} not found")

    def prepare() -> None:
        if ific_no in found:
            ingest.ensure_terra_issue(con, ific_no, found[ific_no])

    try:
        started = jobs.start(ific_no, date.today(), prepare)
    except ingest.IngestError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    if not started:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"an assessment of BR IFIC {ific_no} is already running"
        )
    return TerraAcceptedOut(accepted=True, job=JobOut(**jobs.job(ific_no)))


def _summary(con: duckdb.DuckDBPyConnection, ific_no: int) -> dict:
    s = store.issue_summaries(con).get(ific_no)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"BR IFIC {ific_no} has not been assessed")
    return s


def _filtered(
    con: duckdb.DuckDBPyConnection,
    ific_no: int,
    outcome: list[Outcome] | None,
    adm: list[str] | None,
    change: list[Change] | None,
    pub_status: list[PubStatus] | None,
    relevant: str,
    criterion: str | None,
    q: str | None,
    slim: bool = True,
) -> list[dict]:
    return store.list_assignments(
        con,
        ific_no,
        outcome=list(outcome or []),
        adm=[a.upper() for a in adm or []],
        change=list(change or []),
        pub_status=list(pub_status or []),
        relevant=None if relevant == "all" else relevant == "true",
        criterion=criterion,
        q=q.strip() if q else None,
        slim=slim,
    )


@router.get("/issues/{ific_no}/assignments")
def assignments(
    ific_no: int,
    con: Db,
    outcome: Annotated[list[Outcome] | None, Query()] = None,
    adm: Annotated[list[str] | None, Query(max_length=8)] = None,
    change: Annotated[list[Change] | None, Query()] = None,
    pub_status: Annotated[list[PubStatus] | None, Query()] = None,
    relevant: Literal["true", "false", "all"] = "true",
    criterion: Annotated[str | None, Query(max_length=40)] = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
) -> AssignmentListOut:
    s = _summary(con, ific_no)
    rows = _filtered(con, ific_no, outcome, adm, change, pub_status, relevant, criterion, q)
    return AssignmentListOut(
        ific_no=ific_no,
        model_version=s["model_version"],
        assessed_at=s["assessed_at"],
        count=len(rows),
        assignments=rows,
    )


@router.get("/issues/{ific_no}/assignments.csv", response_class=Response)
def assignments_csv(
    ific_no: int,
    con: Db,
    outcome: Annotated[list[Outcome] | None, Query()] = None,
    adm: Annotated[list[str] | None, Query(max_length=8)] = None,
    change: Annotated[list[Change] | None, Query()] = None,
    pub_status: Annotated[list[PubStatus] | None, Query()] = None,
    relevant: Literal["true", "false", "all"] = "true",
    criterion: Annotated[str | None, Query(max_length=40)] = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
) -> Response:
    """The same rows and order as `/assignments`, as the flat CSV of `ific terra-export`."""
    _summary(con, ific_no)
    rows = _filtered(con, ific_no, outcome, adm, change, pub_status, relevant, criterion, q)
    return Response(
        export.to_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="terra-{ific_no}.csv"'},
    )


@router.get("/issues/{ific_no}/assignments/{terrakey}")
def assignment(ific_no: int, terrakey: int, con: Db) -> AssignmentOut:
    row = store.get_assignment(con, ific_no, terrakey)
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"assignment {terrakey} of BR IFIC {ific_no} not assessed"
        )
    return AssignmentOut(**row)


@router.get("/model")
def model() -> TerraModelOut:
    fw = refdata.load_frameworks()
    return TerraModelOut(
        model_version=MODEL_VERSION,
        p1546_version=p1546.VERSION,
        criteria=[CriterionOut(**c) for c in refdata.criteria()],
        assumptions=[AssumptionOut(id=k, text=v) for k, v in sorted(ASSUMPTIONS.items())],
        frameworks=[
            fw["ge06"]["cite"],
            fw["national"]["m4"]["cite"],
            fw["national"]["allocation_table"]["cite"],
            fw["bilateral"]["cite"],
        ],  # fmt: skip
        neighbours=list(NEIGHBOURS),
        method_doc="docs/terrestrial-land-mobile.md",
    )


@router.get("/issues/{ific_no}/trends")
def issue_trends(
    ific_no: int,
    con: Db,
    issues: Annotated[str | None, Query(max_length=200, description="Comma-separated issues to sum")] = None,
) -> TrendsOut:
    _summary(con, ific_no)
    assessed = store.issue_summaries(con)
    wanted = {ific_no}
    for part in (issues or "").split(","):
        if part.strip().isdecimal() and part.strip().isascii() and int(part) in assessed:
            wanted.add(int(part))
    return TrendsOut(**trends.trends(ific_no, {n: store.all_results(con, n) for n in sorted(wanted)}))


@router.get("/issues/{ific_no}/drafts")
def draft_adms(ific_no: int, con: Db) -> list[DraftAdmOut]:
    _summary(con, ific_no)
    names = load_administrations()["admins"]
    return [
        DraftAdmOut(adm=a, adm_name=names.get(a), assignments=n)
        for a, n in draft.concern_adms(con, ific_no).items()
    ]


def _build_draft(con: duckdb.DuckDBPyConnection, ific_no: int, adm: str) -> draft.TerraDraft:
    out = draft.build_draft(con, ific_no, adm)
    if out is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"no assessed assignment of {adm.upper()} in BR IFIC {ific_no}"
        )
    if isinstance(out, draft.NoConcern):
        raise HTTPException(status.HTTP_409_CONFLICT, f"no concern to describe: {out.reason}")
    return out


AdmPath = Annotated[str, Path(pattern=r"^[A-Za-z]{1,3}$")]


@router.get("/issues/{ific_no}/drafts/{adm}")
def get_draft(ific_no: int, adm: AdmPath, con: Db) -> TerraDraftOut:
    return TerraDraftOut.model_validate(asdict(_build_draft(con, ific_no, adm)))


def get_chat(request: Request) -> ChatClient | None:
    return request.app.state.chat


@router.post("/issues/{ific_no}/drafts/{adm}/polish", response_model=TerraDraftPolishOut)
async def polish_draft(
    ific_no: int, adm: AdmPath, con: Db, client: Annotated[ChatClient | None, Depends(get_chat)]
) -> TerraDraftPolishOut | JSONResponse:
    """Rewrite the prose paragraphs of the server-built letter; the header, annex and basis never change."""
    if client is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "polish is disabled: no LLM is configured")
    if not client.try_acquire():
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "an LLM answer is already being generated")
    started, outcome = time.monotonic(), "error"
    try:
        d = await run_in_threadpool(_build_draft, con, ific_no, adm)
        try:
            upstream = await client.open(draft.polish_messages(d))
            try:
                text = "".join([item async for item in client.deltas(upstream) if isinstance(item, str)])
            finally:
                await upstream.aclose()
        except LlmError as e:
            outcome = "upstream_error"
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM provider error: {e.detail}") from e
        check = draft.check_polish(d, text)
        if check.paragraphs is None:
            outcome = "rejected"
            return JSONResponse(
                {
                    "detail": f"polish rejected, the template text is kept: {check.reason}",
                    "missing": check.missing,
                    "added": check.added,
                },
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        outcome = "ok"
        return TerraDraftPolishOut(
            letter_md=draft.render_letter(d, check.paragraphs), polished=True, model=client.model
        )
    finally:
        client.release()
        draft_log.info(
            "terra polish brific=%s adm=%s elapsed_s=%.1f outcome=%s",
            ific_no,
            adm,
            time.monotonic() - started,
            outcome,
        )
