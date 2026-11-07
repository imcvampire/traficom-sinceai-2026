"""Background assessment jobs shared by the space (`riia`) and terrestrial (`terra`) models.

One job per `(ific_no, source)` runs on its own thread and cursor. A second start while one runs returns
False (the API answers 409). A job still marked running when the server starts is marked failed.
"""

import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import duckdb

Job = dict[str, Any]
Progress = Callable[[int, int], None]


class JobCancelled(Exception):
    pass


class JobRunner:
    """Subclasses implement `execute`; persistence goes through `save_job` and `load_jobs`."""

    def __init__(
        self,
        con: duckdb.DuckDBPyConnection,
        source: str,
        save_job: Callable[[duckdb.DuckDBPyConnection, Job], None],
        load_jobs: Callable[[duckdb.DuckDBPyConnection, str], dict[int, Job]],
        source_field: str = "source",
        thread_prefix: str = "job",
        log: logging.Logger | None = None,
    ) -> None:
        self._con = con
        self._source = source
        self._save_job = save_job
        self._source_field = source_field
        self._thread_prefix = thread_prefix
        self._log = log or logging.getLogger("ific.jobs")
        self._locks: dict[tuple[int, str], threading.Lock] = {}
        self._registry = threading.Lock()
        self._jobs: dict[tuple[int, str], Job] = {}
        self._threads: dict[tuple[int, str], threading.Thread] = {}
        self._stop = threading.Event()
        cur = con.cursor()
        try:
            for job in load_jobs(cur, self.source).values():
                if job["status"] == "running":
                    job.update(
                        status="failed",
                        error="interrupted by a server restart",
                        finished_at=datetime.now(UTC),
                    )
                    save_job(cur, job)
                self._jobs[(job["ific_no"], job[source_field])] = job
        finally:
            cur.close()

    @property
    def source(self) -> str:
        return self._source

    def execute(self, cur: duckdb.DuckDBPyConnection, ific_no: int, as_of: date, progress: Progress) -> None:
        raise NotImplementedError

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
            self._source_field: key[1],
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
            target=self._run,
            args=(key, job, as_of, lock),
            name=f"{self._thread_prefix}-{ific_no}",
            daemon=True,
        )
        self._threads[key] = thread
        thread.start()
        return True

    def _run(self, key: tuple[int, str], job: Job, as_of: date, lock: threading.Lock) -> None:
        cur = self._con.cursor()
        try:
            self._save_job(cur, job)

            def progress(done: int, total: int) -> None:
                if self._stop.is_set():
                    raise JobCancelled("server shutting down")
                job["done"], job["total"] = done, total

            self.execute(cur, key[0], as_of, progress)
            job["status"] = "done"
        except Exception as e:
            job["status"], job["error"] = "failed", str(e) or type(e).__name__
            self._log.warning(
                "%s job ific=%d source=%s failed, previous results kept: %s",
                self._thread_prefix,
                key[0],
                key[1],
                job["error"],
            )
        finally:
            job["finished_at"] = datetime.now(UTC)
            try:
                self._save_job(cur, job)
            finally:
                cur.close()
                lock.release()

    def wait(self, ific_no: int, timeout: float | None = None) -> None:
        thread = self._threads.get((ific_no, self.source))
        if thread:
            thread.join(timeout)

    def shutdown(self, timeout: float = 120.0) -> None:
        """Ask running jobs to stop (checked after each item) and wait for them before the DB closes."""
        self._stop.set()
        deadline = time.monotonic() + timeout
        for thread in list(self._threads.values()):
            thread.join(max(0.0, deadline - time.monotonic()))
            if thread.is_alive():
                self._log.warning(
                    "%s job thread %s still running at shutdown", self._thread_prefix, thread.name
                )
