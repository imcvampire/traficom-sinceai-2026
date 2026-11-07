from pathlib import Path

from riia_fixtures import FIXTURE_ISSUE, loaded_db
from test_riia_assess import AS_OF, TwoStations

from ific.riia import store
from ific.riia.jobs import JobRunner


class Broken(TwoStations):
    def receivers(self, con):
        raise RuntimeError("population unavailable")


def test_job_runs_and_failure_keeps_previous_results(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    runner = JobRunner(con, TwoStations)
    assert runner.start(FIXTURE_ISSUE, AS_OF)
    runner.wait(FIXTURE_ISSUE, 30)
    job = runner.job(FIXTURE_ISSUE)
    assert job["status"] == "done" and job["done"] == 5
    before = store.list_notices(con, FIXTURE_ISSUE, "stations", AS_OF)[0]

    runner._population_factory = Broken
    assert runner.start(FIXTURE_ISSUE, AS_OF)
    runner.wait(FIXTURE_ISSUE, 30)
    job = runner.job(FIXTURE_ISSUE)
    assert job["status"] == "failed" and "population unavailable" in job["error"]
    assert store.list_notices(con, FIXTURE_ISSUE, "stations", AS_OF)[0] == before
    assert store.load_jobs(con, "stations")[FIXTURE_ISSUE]["status"] == "failed"


def test_interrupted_job_marked_failed_on_restart(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    store.save_job(
        con,
        {
            "ific_no": FIXTURE_ISSUE,
            "receiver_source": "stations",
            "status": "running",
            "done": 1,
            "total": 5,
            "started_at": None,
            "finished_at": None,
            "error": None,
        },
    )
    runner = JobRunner(con, TwoStations)
    assert runner.job(FIXTURE_ISSUE)["status"] == "failed"
    assert runner.running() == 0
