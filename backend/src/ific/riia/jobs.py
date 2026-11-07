"""Background assessment jobs: one per (ific_no, receiver_source), each on its own thread and cursor."""

import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import duckdb

from ific.riia import store
from ific.riia.assess import assess_issue
from ific.riia.receivers import ReceiverPopulation

log = logging.getLogger("ific.riia")


class JobCancelled(Exception):
    pass


class JobRunner:
    def __init__(
        self, con: duckdb.DuckDBPyConnection, population_factory: Callable[[], ReceiverPopulation]
    ) -> None:
        self._con = con
        self._population_factory = population_factory
        self._locks: dict[tuple[int, str], threading.Lock] = {}
        self._registry = threading.Lock()
        self._jobs: dict[tuple[int, str], dict[str, Any]] = {}
        self._threads: dict[tuple[int, str], threading.Thread] = {}
        self._stop = threading.Event()
        cur = con.cursor()
        try:
            store.ensure_tables(cur)
            for job in store.load_jobs(cur, population_factory().name).values():
                if job["status"] == "running":
                    job.update(
                        status="failed",
                        error="interrupted by a server restart",
                        finished_at=datetime.now(UTC),
                    )
                    store.save_job(cur, job)
                self._jobs[(job["ific_no"], job["receiver_source"])] = job
        finally:
            cur.close()

    @property
    def source(self) -> str:
        return self._population_factory().name

    def _lock(self, key: tuple[int, str]) -> threading.Lock:
        with self._registry:
            return self._locks.setdefault(key, threading.Lock())

    def job(self, ific_no: int) -> dict[str, Any]:
        job = self._jobs.get((ific_no, self.source))
        if job is None:
            return {
                "status": "idle",
                "done": 0,
                "total": 0,
                "started_at": None,
                "finished_at": None,
                "error": None,
            }
        return {k: job[k] for k in ("status", "done", "total", "started_at", "finished_at", "error")}

    def running(self) -> int:
        with self._registry:
            return sum(1 for j in self._jobs.values() if j["status"] == "running")

    def start(self, ific_no: int, as_of: date, prepare: Callable[[], None] | None = None) -> bool:
        """Start an assessment in the background; False if one is already running for this key.

        `prepare` (e.g. the ingest) runs synchronously while the key's lock is held, so a second request
        cannot re-ingest an issue a running job is reading. Its exception propagates and nothing starts.
        """
        key = (ific_no, self.source)
        lock = self._lock(key)
        if not lock.acquire(blocking=False):
            return False
        try:
            if prepare is not None:
                prepare()
        except BaseException:
            lock.release()
            raise
        job = {
            "ific_no": ific_no,
            "receiver_source": key[1],
            "status": "running",
            "done": 0,
            "total": 0,
            "started_at": datetime.now(UTC),
            "finished_at": None,
            "error": None,
        }
        with self._registry:
            self._jobs[key] = job
        thread = threading.Thread(
            target=self._run, args=(key, job, as_of, lock), name=f"riia-{ific_no}", daemon=True
        )
        self._threads[key] = thread
        thread.start()
        return True

    def _run(self, key: tuple[int, str], job: dict[str, Any], as_of: date, lock: threading.Lock) -> None:
        cur = self._con.cursor()
        started = time.perf_counter()
        try:
            store.save_job(cur, job)

            def progress(done: int, total: int) -> None:
                if self._stop.is_set():
                    raise JobCancelled("server shutting down")
                job["done"], job["total"] = done, total

            stats: dict[str, float] = {}
            results = assess_issue(
                cur, key[0], as_of, self._population_factory(), progress=progress, stats_out=stats
            )
            store.write_results(cur, key[0], key[1], results)
            job["status"] = "done"
            log.info(
                "riia job ific=%d source=%s notices=%d hazards=%d tier1_screened=%d tier2=%d duration_ms=%d",
                key[0],
                key[1],
                stats["notices"],
                stats["hazards"],
                stats.get("tier1_screened", 0),
                stats.get("tier2", 0),
                round((time.perf_counter() - started) * 1000),
            )
        except Exception as e:
            job["status"], job["error"] = "failed", str(e) or type(e).__name__
            log.warning(
                "riia job ific=%d source=%s failed, previous results kept: %s", key[0], key[1], job["error"]
            )
        finally:
            job["finished_at"] = datetime.now(UTC)
            try:
                store.save_job(cur, job)
            finally:
                cur.close()
                lock.release()

    def wait(self, ific_no: int, timeout: float | None = None) -> None:
        thread = self._threads.get((ific_no, self.source))
        if thread:
            thread.join(timeout)

    def shutdown(self, timeout: float = 120.0) -> None:
        """Ask running jobs to stop (checked after each notice) and wait for them before the DB closes."""
        self._stop.set()
        deadline = time.monotonic() + timeout
        for thread in list(self._threads.values()):
            thread.join(max(0.0, deadline - time.monotonic()))
            if thread.is_alive():
                log.warning("riia job thread %s still running at shutdown", thread.name)
