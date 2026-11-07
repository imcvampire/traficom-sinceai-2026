import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import duckdb
import httpx2
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.types import Receive, Scope, Send

from ific import __version__, db, ingest, m4, special_interest, stations
from ific.config import PROJECT_ROOT, settings
from ific.llm import ChatClient, LlmError, Usage, make_chat_client
from ific.riia import MODEL_VERSION, chat, method
from ific.riia import store as risk_store
from ific.riia.jobs import JobRunner
from ific.riia.receivers import GenericM4Population
from ific.riia.schemas import (
    AcceptedOut,
    ChatIn,
    ChatStatusOut,
    IssueOut,
    JobOut,
    ModelOut,
    NoticeDetailOut,
    NoticeListOut,
)
from ific.watcher.service import WatcherService, WatcherState
from ific.watcher.store import FileStatus, RunRow

chat_log = logging.getLogger("ific.chat")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    con = db.connect(settings.db_path, settings.db_storage_version)
    watcher_task: asyncio.Task[None] | None = None
    chat_client = make_chat_client(settings)
    app.state.chat = chat_client
    try:
        app.state.ref_status = [
            *m4.ensure_m4(con, settings),
            special_interest.ensure_special_interest(con, settings),
        ]
        app.state.db = con
        app.state.risk_jobs = JobRunner(con, GenericM4Population)
        app.state.watcher = WatcherService(settings)
        if settings.watcher_enabled:
            watcher_task = asyncio.create_task(app.state.watcher.run_forever(), name="ific-watcher")
        yield
    finally:
        try:
            if watcher_task is not None:
                watcher_task.cancel()
                with suppress(asyncio.CancelledError):
                    await watcher_task
        finally:
            if hasattr(app.state, "risk_jobs"):
                app.state.risk_jobs.shutdown()
            con.close()
            if chat_client is not None:
                await chat_client.aclose()


app = FastAPI(title="IFIC interference analyser", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(stations.router)


def get_db(request: Request) -> Iterator[duckdb.DuckDBPyConnection]:
    cursor = request.app.state.db.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


Db = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]


def get_jobs(request: Request) -> JobRunner:
    return request.app.state.risk_jobs


Jobs = Annotated[JobRunner, Depends(get_jobs)]


@app.get("/api/health")
def health(con: Db, jobs: Jobs) -> dict[str, Any]:
    sources = {
        source_id: (edition, row_count)
        for source_id, edition, row_count in con.execute(
            "SELECT source_id, edition, row_count FROM ref.source"
        ).fetchall()
    }
    return {
        "status": "ok",
        "version": __version__,
        "db": {
            "path": str(settings.db_path),
            "m4_edition": sources["m4_regulation"][0],
            "tables": {
                "m4_allocation": sources["m4_allocation"][1],
                "m4_page": sources["m4_regulation"][1] + sources["m4_notes"][1],
                "special_interest_station": sources[special_interest.SOURCE_ID][1],
            },
        },
        "risk": {
            "issues_assessed": len(risk_store.issue_summaries(con, jobs.source)),
            "model_version": MODEL_VERSION,
            "running_jobs": jobs.running(),
        },
    }


class WatcherRunOut(BaseModel):
    started_at: datetime
    finished_at: datetime
    trigger: str
    outcome: str
    new_count: int
    downloaded_count: int
    failed_count: int
    error: str | None


class WatcherStateOut(BaseModel):
    enabled: bool
    locked: bool
    ui_enabled: bool | None
    interval_seconds: int
    running: bool
    source_url: str
    last_run: WatcherRunOut | None
    next_run_at: datetime | None

    @classmethod
    def of(cls, state: WatcherState) -> "WatcherStateOut":
        run: RunRow | None = state.last_run
        return cls(
            enabled=state.enabled,
            locked=state.locked,
            ui_enabled=state.ui_enabled,
            interval_seconds=state.interval_seconds,
            running=state.running,
            source_url=state.source_url,
            last_run=WatcherRunOut(**vars(run)) if run else None,
            next_run_at=state.next_run_at,
        )


class WatcherPatch(BaseModel):
    enabled: bool


class WatcherFileOut(BaseModel):
    ific_no: int
    published_on: date | None
    zip_url: str
    status: FileStatus
    size_bytes: int | None
    local_path: str | None
    error: str | None
    attempts: int
    discovered_at: datetime
    downloaded_at: datetime | None


def get_watcher(request: Request) -> WatcherService:
    return request.app.state.watcher


Watcher = Annotated[WatcherService, Depends(get_watcher)]


def _display_path(path: str | None) -> str | None:
    """Never expose absolute server paths: show them relative to the project or download dir."""
    if path is None:
        return None
    p = Path(path)
    for base in (PROJECT_ROOT, settings.watcher_download_dir):
        if p.is_relative_to(base):
            return p.relative_to(base).as_posix()
    return p.name


# Watcher routes are async on purpose: they signal the scheduler's asyncio.Event, which is not thread-safe.
@app.get("/api/watcher")
async def watcher_state(watcher: Watcher) -> WatcherStateOut:
    return WatcherStateOut.of(watcher.state())


@app.patch("/api/watcher")
async def watcher_update(body: WatcherPatch, watcher: Watcher) -> WatcherStateOut:
    if watcher.locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "watcher is disabled by IFIC_WATCHER_ENABLED=false")
    watcher.set_ui_enabled(body.enabled)
    return WatcherStateOut.of(watcher.state())


@app.post("/api/watcher/check", status_code=status.HTTP_202_ACCEPTED)
async def watcher_check(watcher: Watcher) -> dict[str, bool]:
    if watcher.locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "watcher is disabled by IFIC_WATCHER_ENABLED=false")
    if not watcher.request_check():
        raise HTTPException(status.HTTP_409_CONFLICT, "check already running")
    return {"accepted": True}


@app.get("/api/watcher/files")
async def watcher_files(watcher: Watcher) -> list[WatcherFileOut]:
    return [
        WatcherFileOut(
            ific_no=f.ific_no,
            published_on=f.published_on,
            zip_url=f.zip_url,
            status=f.status,
            size_bytes=f.size_bytes,
            local_path=_display_path(f.mdb_path),
            error=f.error,
            attempts=f.attempts,
            discovered_at=f.discovered_at,
            downloaded_at=f.downloaded_at,
        )
        for f in watcher.store.list_files()
    ]


AsOf = Annotated[date | None, Query(description="Evaluation date (YYYY-MM-DD); defaults to today")]


def _issue_paths(con: duckdb.DuckDBPyConnection) -> tuple[dict[int, Path], dict[int, tuple[str, int]]]:
    return ingest.discover_issues(settings), ingest.ingested_issues(con)


@app.get("/api/risk/issues")
def risk_issues(con: Db, jobs: Jobs) -> list[IssueOut]:
    found, ingested = _issue_paths(con)
    summaries = risk_store.issue_summaries(con, jobs.source)
    out = []
    for no in sorted(set(found) | set(ingested), reverse=True):
        s = summaries.get(no)
        path = _display_path(str(found[no])) if no in found else ingested[no][0]
        out.append(
            IssueOut(
                ific_no=no,
                path=path or "",
                ingested=no in ingested,
                assessed=s is not None,
                model_version=s["model_version"] if s else None,
                receiver_source=jobs.source,
                notice_count=ingested[no][1] if no in ingested else None,
                outcome_counts=s["outcome_counts"] if s else None,
                assessed_at=s["assessed_at"] if s else None,
                as_of=s["as_of"].isoformat() if s else None,
                job=JobOut(**jobs.job(no)),
            )
        )
    return out


@app.post("/api/risk/issues/{ific_no}", status_code=status.HTTP_202_ACCEPTED)
def risk_assess(ific_no: int, con: Db, jobs: Jobs, as_of: AsOf = None) -> AcceptedOut:
    found, ingested = _issue_paths(con)
    if ific_no not in found and ific_no not in ingested:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"IFIC {ific_no} not found")

    def prepare() -> None:
        if ific_no in found:
            ingest.ensure_issue(con, ific_no, found[ific_no])

    try:
        started = jobs.start(ific_no, as_of or date.today(), prepare)
    except ingest.IngestError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    if not started:
        raise HTTPException(status.HTTP_409_CONFLICT, f"an assessment of IFIC {ific_no} is already running")
    return AcceptedOut(accepted=True, job=JobOut(**jobs.job(ific_no)))


@app.get("/api/risk/issues/{ific_no}/notices")
def risk_notices(
    ific_no: int, con: Db, jobs: Jobs, as_of: AsOf = None, view: Literal["technical", "queue"] = "technical"
) -> NoticeListOut:
    day = as_of or date.today()
    notices, assessed_at = risk_store.list_notices(con, ific_no, jobs.source, day, view)
    if assessed_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"IFIC {ific_no} has not been assessed")
    model = risk_store.issue_summaries(con, jobs.source)[ific_no]["model_version"]
    return NoticeListOut(
        ific_no=ific_no,
        model_version=model,
        receiver_source=jobs.source,
        as_of=day.isoformat(),
        assessed_at=assessed_at,
        view=view,
        notices=notices,
    )


@app.get("/api/risk/issues/{ific_no}/notices/{ntc_id}")
def risk_notice(ific_no: int, ntc_id: int, con: Db, jobs: Jobs, as_of: AsOf = None) -> NoticeDetailOut:
    sensitive = risk_store.sensitive_assumptions(con, ific_no, jobs.source)
    notice = risk_store.get_notice(con, ific_no, jobs.source, ntc_id, as_of or date.today(), sensitive)
    if notice is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"notice {ntc_id} of IFIC {ific_no} has not been assessed"
        )
    return NoticeDetailOut(**notice)


@app.get("/api/risk/model")
def risk_model(con: Db, jobs: Jobs) -> ModelOut:
    return ModelOut(**method.describe(sorted(risk_store.sensitive_assumptions(con, None, jobs.source))))


def get_chat(request: Request) -> ChatClient | None:
    return request.app.state.chat


Chat = Annotated[ChatClient | None, Depends(get_chat)]


def _chat_disabled_reason() -> str:
    required = (("IFIC_LLM_API_KEY", settings.llm_api_key), ("IFIC_LLM_MODEL", settings.llm_model))
    missing = [name for name, value in required if value is None]
    return f"{' and '.join(missing) or 'the LLM client'} {'is' if len(missing) < 2 else 'are'} not set"


@app.get("/api/risk/chat")
async def risk_chat_status(client: Chat) -> ChatStatusOut:
    if client is None:
        return ChatStatusOut(enabled=False, model=None, reason=_chat_disabled_reason())
    return ChatStatusOut(enabled=True, model=client.model, reason=None)


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


@dataclass
class _ChatTurn:
    ific_no: int
    scope: str
    notice_count: int
    history: int
    started: float
    first_token_s: float | None = None
    usage: Usage | None = None
    outcome: str = "cancelled"


class _ChatStream(StreamingResponse):
    """Streams one answer. Cleanup is in `__call__`, so a disconnect before the first chunk frees the slot."""

    def __init__(self, client: ChatClient, upstream: httpx2.Response, turn: _ChatTurn) -> None:
        self.client = client
        self.upstream = upstream
        self.turn = turn
        super().__init__(
            self._events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def _events(self) -> AsyncIterator[bytes]:
        turn = self.turn
        try:
            async for item in self.client.deltas(self.upstream):
                if isinstance(item, Usage):
                    turn.usage = item
                    continue
                if turn.first_token_s is None:
                    turn.first_token_s = time.monotonic() - turn.started
                yield _sse("delta", {"text": item})
        except LlmError as e:
            turn.outcome = "upstream_error"
            yield _sse("error", {"detail": e.detail})
            return
        turn.outcome = "ok"
        yield _sse("done", {"usage": vars(turn.usage) if turn.usage else None})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            try:
                await self.upstream.aclose()
            finally:
                self.client.release()
                self._log()

    def _log(self) -> None:
        t, u = self.turn, self.turn.usage
        chat_log.info(
            "chat ific_no=%s scope=%s notices=%s history=%s prompt_tokens=%s completion_tokens=%s "
            "first_token_s=%s elapsed_s=%.1f outcome=%s",
            t.ific_no,
            t.scope,
            t.notice_count,
            t.history,
            u.prompt_tokens if u else None,
            u.completion_tokens if u else None,
            f"{t.first_token_s:.1f}" if t.first_token_s is not None else None,
            time.monotonic() - t.started,
            t.outcome,
        )


@app.post("/api/risk/issues/{ific_no}/chat")
async def risk_chat(
    ific_no: int, body: ChatIn, con: Db, jobs: Jobs, client: Chat, as_of: AsOf = None
) -> StreamingResponse:
    if client is None:
        detail = f"chat is disabled: {_chat_disabled_reason()}"
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail)
    if not client.try_acquire():
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "a chat answer is already being generated")
    scope = "view" if body.ntc_id is None else "notice"
    turn = _ChatTurn(ific_no, scope, 0, len(body.messages), time.monotonic())
    try:
        data = await run_in_threadpool(
            chat.build_context,
            con,
            ific_no=ific_no,
            receiver_source=jobs.source,
            as_of=as_of or date.today(),
            ntc_ids=body.ntc_ids,
            ntc_id=body.ntc_id,
            filters=body.filters,
        )
        if data is None:
            what = f"notice {body.ntc_id} of IFIC {ific_no}" if body.ntc_id is not None else f"IFIC {ific_no}"
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what} has not been assessed")
        turn.notice_count = len(data["notices"]["rows"])
        try:
            upstream = await client.open(chat.messages_for(data, [m.model_dump() for m in body.messages]))
        except LlmError as e:
            chat_log.warning("chat ific_no=%s upstream status=%s detail=%s", ific_no, e.status, e.detail)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM provider error: {e.detail}") from e
    except BaseException:
        client.release()
        raise
    return _ChatStream(client, upstream, turn)
