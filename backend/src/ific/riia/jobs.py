"""Space assessment jobs: one per (ific_no, receiver_source), on the shared `ific.jobs` runner."""

import logging
import time
from collections.abc import Callable
from datetime import date

import duckdb

from ific import jobs
from ific.jobs import JobCancelled
from ific.riia import store
from ific.riia.assess import assess_issue
from ific.riia.receivers import ReceiverPopulation

log = logging.getLogger("ific.riia")

__all__ = ["JobCancelled", "JobRunner"]


class JobRunner(jobs.JobRunner):
    def __init__(
        self, con: duckdb.DuckDBPyConnection, population_factory: Callable[[], ReceiverPopulation]
    ) -> None:
        self._population_factory = population_factory
        cur = con.cursor()
        try:
            store.ensure_tables(cur)
        finally:
            cur.close()
        super().__init__(
            con,
            population_factory().name,
            store.save_job,
            store.load_jobs,
            source_field="receiver_source",
            thread_prefix="riia",
            log=log,
        )

    @property
    def source(self) -> str:
        return self._population_factory().name

    def execute(
        self, cur: duckdb.DuckDBPyConnection, ific_no: int, as_of: date, progress: jobs.Progress
    ) -> None:
        started = time.perf_counter()
        stats: dict[str, float] = {}
        results = assess_issue(
            cur, ific_no, as_of, self._population_factory(), progress=progress, stats_out=stats
        )
        store.write_results(cur, ific_no, self.source, results)
        log.info(
            "riia job ific=%d source=%s notices=%d hazards=%d tier1_screened=%d tier2=%d duration_ms=%d",
            ific_no,
            self.source,
            stats["notices"],
            stats["hazards"],
            stats.get("tier1_screened", 0),
            stats.get("tier2", 0),
            round((time.perf_counter() - started) * 1000),
        )
