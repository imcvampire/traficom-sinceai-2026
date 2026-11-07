"""Scheduled ITU Space IFIC check: discover new issues, then download them one at a time."""

import asyncio
import fcntl
import logging
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import httpx2

from ific import __version__
from ific.config import Settings
from ific.watcher.download import DownloadError, describe_error, download_and_extract
from ific.watcher.source import IficListing, SourceLayoutError, parse_listings, parse_year_links
from ific.watcher.store import CachedPage, RunOutcome, RunRow, RunTrigger, WatcherStore, utcnow

log = logging.getLogger("ific.watcher")

USER_AGENT = f"ific-watcher/{__version__} (+Traficom hackathon)"
YEAR_PAGES_SCANNED = 2

ClientFactory = Callable[[], httpx2.AsyncClient]


def make_client(settings: Settings) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        timeout=settings.watcher_http_timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )


@dataclass(frozen=True)
class WatcherState:
    enabled: bool
    locked: bool
    ui_enabled: bool | None
    interval_seconds: int
    running: bool
    source_url: str
    last_run: RunRow | None
    next_run_at: datetime | None


@dataclass(frozen=True)
class CheckResult:
    outcome: RunOutcome
    new_count: int = 0
    downloaded_count: int = 0
    failed_count: int = 0
    error: str | None = None


@contextmanager
def _process_lock(path: Path) -> Iterator[bool]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class WatcherService:
    def __init__(
        self,
        settings: Settings,
        store: WatcherStore | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.settings = settings
        self.store = store or WatcherStore(settings.watcher_state_path)
        self._client_factory = client_factory or (lambda: make_client(settings))
        self._lock_path = settings.watcher_state_path.with_name("watcher.lock")
        self._run_lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._manual_requested = False
        self._next_run_at: datetime | None = None

    @property
    def locked(self) -> bool:
        return not self.settings.watcher_enabled

    @property
    def running(self) -> bool:
        return self._run_lock.locked() or self._manual_requested or self._other_process_running()

    def _other_process_running(self) -> bool:
        with _process_lock(self._lock_path) as acquired:
            return not acquired

    def is_enabled(self) -> bool:
        return not self.locked and self.store.get_ui_enabled() is not False

    def state(self) -> WatcherState:
        ui_enabled = self.store.get_ui_enabled()
        enabled = not self.locked and ui_enabled is not False
        return WatcherState(
            enabled=enabled,
            locked=self.locked,
            ui_enabled=ui_enabled,
            interval_seconds=self.settings.watcher_interval_seconds,
            running=self.running,
            source_url=str(self.settings.watcher_source_url),
            last_run=self.store.last_run(),
            next_run_at=self._next_run_at if enabled and not self.running else None,
        )

    def set_ui_enabled(self, enabled: bool) -> None:
        was_enabled = self.is_enabled()
        self.store.set_ui_enabled(enabled)
        if enabled != was_enabled:
            self._wake.set()

    def request_check(self) -> bool:
        """Queue a manual check for the scheduler loop; False when one is already queued or running."""
        if self.running:
            return False
        self._manual_requested = True
        self._wake.set()
        return True

    async def run_forever(self) -> None:
        interval = self.settings.watcher_interval_seconds
        while True:
            self._wake.clear()
            manual, self._manual_requested = self._manual_requested, False
            try:
                if manual or self.is_enabled():
                    self._next_run_at = None
                    await self.check("manual" if manual else "schedule")
            except Exception:
                log.exception("watcher loop iteration failed; retrying after the interval")
            self._next_run_at = utcnow() + timedelta(seconds=interval)
            with suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), interval)

    async def check(self, trigger: RunTrigger) -> CheckResult:
        started_at = utcnow()
        if self._run_lock.locked():
            return self._finish(trigger, started_at, CheckResult("skipped", error="check already running"))
        async with self._run_lock:
            with _process_lock(self._lock_path) as acquired:
                if not acquired:
                    result = CheckResult("skipped", error="another process is running a check")
                    return self._finish(trigger, started_at, result)
                try:
                    result = await self._check(trigger)
                except Exception as e:
                    log.exception("watcher check failed")
                    result = CheckResult("error", error=describe_error(e))
                return self._finish(trigger, started_at, result)

    def _finish(self, trigger: RunTrigger, started_at: datetime, result: CheckResult) -> CheckResult:
        finished_at = utcnow()
        self.store.record_run(
            RunRow(
                started_at=started_at,
                finished_at=finished_at,
                trigger=trigger,
                outcome=result.outcome,
                new_count=result.new_count,
                downloaded_count=result.downloaded_count,
                failed_count=result.failed_count,
                error=result.error,
            )
        )
        log.info(
            "watcher run trigger=%s outcome=%s new=%d downloaded=%d failed=%d duration_ms=%d%s",
            trigger,
            result.outcome,
            result.new_count,
            result.downloaded_count,
            result.failed_count,
            (finished_at - started_at) / timedelta(milliseconds=1),
            f" error={result.error!r}" if result.error else "",
        )
        return result

    async def _check(self, trigger: RunTrigger) -> CheckResult:
        # Holding the cross-process lock proves no other process is mid-download.
        reset = self.store.reset_stale_downloading()
        if reset:
            log.warning("watcher reset %d interrupted download(s) to failed", reset)
        root_url = str(self.settings.watcher_source_url)
        async with self._client_factory() as client:
            year_pages = parse_year_links(await self._fetch_page(client, root_url), root_url)
            pages: list[list[IficListing]] = []
            layout_errors: list[SourceLayoutError] = []
            for page in year_pages[:YEAR_PAGES_SCANNED]:
                try:
                    pages.append(parse_listings(await self._fetch_page(client, page.url), page.url))
                except SourceLayoutError as e:
                    # A freshly opened year page (early January) has no rows yet.
                    log.warning("watcher year page has no listings: %s", e)
                    layout_errors.append(e)
            if not pages:
                raise layout_errors[0]
            new_count = self.store.upsert_listings(pages[0], [x for xs in pages[1:] for x in xs])

            downloaded = failed = 0
            for row in self.store.pending_downloads():
                if trigger == "schedule" and not self.is_enabled():
                    log.info("watcher paused; remaining downloads wait for the next run")
                    break
                self.store.mark_downloading(row.ific_no)
                started = time.monotonic()
                try:
                    result = await download_and_extract(
                        client,
                        IficListing(row.ific_no, row.published_on, row.zip_url),
                        self.settings.watcher_download_dir,
                        self.settings.watcher_max_download_bytes,
                    )
                except Exception as e:
                    failed += 1
                    error = str(e) if isinstance(e, DownloadError) else describe_error(e)
                    self.store.mark_failed(row.ific_no, error)
                    log.warning("watcher download failed ific=%d error=%s", row.ific_no, error)
                    continue
                except BaseException:
                    self.store.mark_failed(row.ific_no, "interrupted")
                    raise
                downloaded += 1
                self.store.mark_downloaded(
                    row.ific_no,
                    size_bytes=result.mdb_bytes,
                    sha256=result.sha256,
                    mdb_path=result.mdb_paths[0],
                    etag=result.etag,
                    last_modified=result.last_modified,
                )
                log.info(
                    "watcher downloaded ific=%d zip_bytes=%d mdb_bytes=%d duration_ms=%d",
                    row.ific_no,
                    result.zip_bytes,
                    result.mdb_bytes,
                    (time.monotonic() - started) * 1000,
                )
        return CheckResult(
            "ok",
            new_count=new_count,
            downloaded_count=downloaded,
            failed_count=failed,
            error=f"{failed} download(s) failed" if failed else None,
        )

    async def _fetch_page(self, client: httpx2.AsyncClient, url: str) -> str:
        cached = self.store.get_page(url)
        headers = {"If-None-Match": cached.etag} if cached and cached.etag else {}
        response = await client.get(url, headers=headers)
        if response.status_code == 304 and cached:
            return cached.body
        response.raise_for_status()
        self.store.set_page(url, CachedPage(response.headers.get("etag"), response.text))
        return response.text
