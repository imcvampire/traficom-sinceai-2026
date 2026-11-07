"""Terrestrial assessment jobs (one per issue) on the shared `ific.jobs` runner."""

import logging
from datetime import date

import duckdb

from ific import jobs
from ific.terra import store
from ific.terra.assess import assess_issue
from ific.terra.method import MODEL_VERSION

log = logging.getLogger("ific.terra")


class TerraJobRunner(jobs.JobRunner):
    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        super().__init__(con, MODEL_VERSION, store.save_job, store.load_jobs, thread_prefix="terra", log=log)

    def execute(
        self, cur: duckdb.DuckDBPyConnection, ific_no: int, as_of: date, progress: jobs.Progress
    ) -> None:
        stats: dict[str, float] = {}
        results = assess_issue(cur, ific_no, progress=progress, stats_out=stats)
        store.write_results(cur, ific_no, results)
        log.info(
            "terra job brific=%d assignments=%d duration_ms=%d",
            ific_no,
            stats["assignments"],
            stats["duration_ms"],
        )
