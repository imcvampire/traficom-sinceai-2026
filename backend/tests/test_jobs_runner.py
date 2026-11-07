import threading
from datetime import date
from pathlib import Path

from ific import db, jobs

GATE = threading.Event()


class MemoryStore:
    def __init__(self) -> None:
        self.jobs: dict[int, dict] = {}

    def save(self, con, job: dict) -> None:
        self.jobs[job["ific_no"]] = dict(job)

    def load(self, con, source: str) -> dict[int, dict]:
        return {k: dict(v) for k, v in self.jobs.items() if v["source"] == source}


class Gated(jobs.JobRunner):
    def execute(self, cur, ific_no: int, as_of: date, progress) -> None:
        assert GATE.wait(10)
        progress(1, 1)


class Failing(jobs.JobRunner):
    def execute(self, cur, ific_no: int, as_of: date, progress) -> None:
        raise RuntimeError("boom")


def _con(tmp_path: Path):
    return db.connect(tmp_path / "db" / "ific.duckdb", "v1.5.0")


def test_second_start_while_running_is_refused(tmp_path: Path) -> None:
    mem = MemoryStore()
    runner = Gated(_con(tmp_path), "fake", mem.save, mem.load)
    GATE.clear()
    assert runner.start(1, date(2026, 11, 7))
    assert not runner.start(1, date(2026, 11, 7))
    assert runner.running() == 1
    GATE.set()
    runner.wait(1, 10)
    assert runner.job(1)["status"] == "done" and runner.job(1)["done"] == 1
    assert runner.start(1, date(2026, 11, 7))
    runner.wait(1, 10)


def test_failure_is_recorded_and_running_job_fails_on_restart(tmp_path: Path) -> None:
    mem = MemoryStore()
    con = _con(tmp_path)
    runner = Failing(con, "fake", mem.save, mem.load)
    assert runner.start(2, date(2026, 11, 7))
    runner.wait(2, 10)
    assert runner.job(2)["status"] == "failed" and runner.job(2)["error"] == "boom"
    mem.jobs[3] = {"ific_no": 3, "source": "fake", "status": "running", "done": 0, "total": 0,
                   "started_at": None, "finished_at": None, "error": None}  # fmt: skip
    restarted = Failing(con, "fake", mem.save, mem.load)
    assert restarted.job(3)["status"] == "failed" and "restart" in restarted.job(3)["error"]
    assert mem.jobs[3]["status"] == "failed" and restarted.running() == 0
