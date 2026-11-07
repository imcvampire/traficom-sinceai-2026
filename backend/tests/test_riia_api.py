import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from riia_fixtures import FIXTURE_ISSUE, fixture_exporter, fixture_mdb
from test_riia_assess import TwoStations

from ific import api, ingest
from ific.config import settings

GATE = threading.Event()


class GenericFake(TwoStations):
    name = "generic-m4"


class GatedFake(GenericFake):
    def receivers(self, con):
        assert GATE.wait(10)
        return super().receivers(con)


@pytest.fixture
def risk_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    issue_dir = settings.watcher_download_dir / str(FIXTURE_ISSUE)
    issue_dir.mkdir(parents=True)
    fixture_mdb(issue_dir)
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr(ingest, "PROJECT_ROOT", root)
    monkeypatch.setattr(ingest, "mdb_export", fixture_exporter)
    monkeypatch.setattr(api, "GenericM4Population", GenericFake)
    with TestClient(api.app) as client:
        yield client


def _wait_done(client: TestClient) -> dict:
    for _ in range(200):
        issue = client.get("/api/risk/issues").json()[0]
        if issue["job"]["status"] != "running":
            return issue
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_issues_before_assessment(risk_client: TestClient) -> None:
    issues = risk_client.get("/api/risk/issues").json()
    assert [i["ific_no"] for i in issues] == [FIXTURE_ISSUE]
    assert issues[0]["path"] == f"{FIXTURE_ISSUE}/ific{FIXTURE_ISSUE}.mdb"
    assert issues[0]["assessed"] is False and issues[0]["job"]["status"] == "idle"
    assert risk_client.get(f"/api/risk/issues/{FIXTURE_ISSUE}/notices").status_code == 404


def test_assess_then_read(risk_client: TestClient) -> None:
    r = risk_client.post(f"/api/risk/issues/{FIXTURE_ISSUE}?as_of=2026-07-01")
    assert r.status_code == 202 and r.json()["accepted"]
    issue = _wait_done(risk_client)
    assert issue["job"]["status"] == "done" and issue["job"]["done"] == issue["job"]["total"] == 5
    assert issue["assessed"] and issue["notice_count"] == 5 and issue["model_version"] == "riia-1"
    assert sum(issue["outcome_counts"].values()) == 5

    listing = risk_client.get(f"/api/risk/issues/{FIXTURE_ISSUE}/notices?as_of=2026-07-01").json()
    assert len(listing["notices"]) == 5 and listing["view"] == "technical"
    assert listing["notices"][0]["worst_outcome"] == "exceeds"
    queue = risk_client.get(f"/api/risk/issues/{FIXTURE_ISSUE}/notices?as_of=2026-07-01&view=queue").json()
    # 1002 is a Notification (no comment window), so it follows 1001's open window.
    assert [n["ntc_id"] for n in queue["notices"]] == [1001, 1002]
    late = risk_client.get(f"/api/risk/issues/{FIXTURE_ISSUE}/notices?as_of=2026-11-06&view=queue").json()
    # 1001's window has closed by then; 1002 has none to close.
    assert [n["ntc_id"] for n in late["notices"]] == [1002]

    detail = risk_client.get(f"/api/risk/issues/{FIXTURE_ISSUE}/notices/1001?as_of=2026-07-01").json()
    assert detail["regulatory"]["days_left"] == 114 and detail["regulatory"]["findings"]
    assert {h["mode"] for h in detail["hazards"]} >= {"cochannel", "es_terrestrial", "blocking_im"}
    assert detail["curve_grid_db"] == {"start": -40.0, "stop": 40.0, "step": 1.0}
    assert detail["pfd_outcome"] == "meets" and detail["pfd_limits_review"] == "pending"
    assert detail["pfd_checks"][0]["row_id"] == "t21-4-10700-11700-fss-gso"
    assert {n["ntc_id"]: n["pfd_outcome"] for n in listing["notices"]}[1002] == "exceeds"
    later = risk_client.get(f"/api/risk/issues/{FIXTURE_ISSUE}/notices/1001?as_of=2026-11-06").json()
    assert later["hazards"] == detail["hazards"] and later["regulatory"]["days_left"] == -14
    assert risk_client.get(f"/api/risk/issues/{FIXTURE_ISSUE}/notices/42").status_code == 404

    body = r.text + str(listing) + str(detail)
    assert "score" not in body

    health = risk_client.get("/api/health").json()["risk"]
    assert health == {"issues_assessed": 1, "model_version": "riia-1", "running_jobs": 0}


def test_model_endpoint(risk_client: TestClient) -> None:
    model = risk_client.get("/api/risk/model").json()
    assert [s["step"] for s in model["method_steps"]] == [1, 2, 3, 4]
    assert {c["id"] for c in model["receiver_classes"]} >= {"fixed", "radio_astronomy", "metsat_es"}
    assert all(i["cite"] for i in model["inputs"])
    fixed = next(c for c in model["receiver_classes"] if c["id"] == "fixed")
    assert set(fixed["cites"]) == {"pattern", "gain_dbi", "nf_db", "bw_hz", "acs_db", "min_elev_deg"}
    assert all(fixed["cites"].values())
    assert fixed["acs_db"] == 45.0
    assert {d["param"] for d in fixed["distributions"]} == {"azimuth_deg", "pointing_elev_deg", "height_m"}
    assert model["doc_path"] == "docs/interference-risk-assessment.md"


def test_unknown_issue_404(risk_client: TestClient) -> None:
    assert risk_client.post("/api/risk/issues/1234").status_code == 404


def test_conflict_while_running(risk_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = risk_client.app.state.risk_jobs
    monkeypatch.setattr(runner, "_population_factory", GatedFake)
    GATE.clear()
    try:
        assert risk_client.post(f"/api/risk/issues/{FIXTURE_ISSUE}").status_code == 202
        assert risk_client.post(f"/api/risk/issues/{FIXTURE_ISSUE}").status_code == 409
        assert risk_client.get("/api/health").json()["risk"]["running_jobs"] == 1
    finally:
        GATE.set()
    assert _wait_done(risk_client)["job"]["status"] == "done"


def test_broken_export_422(risk_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(mdb: Path, table: str, out: Path) -> None:
        raise ingest.IngestError(f"mdb-export {mdb.name} {table} failed: corrupt file")

    monkeypatch.setattr(ingest, "mdb_export", broken)
    r = risk_client.post(f"/api/risk/issues/{FIXTURE_ISSUE}")
    assert r.status_code == 422 and "corrupt file" in r.json()["detail"]
