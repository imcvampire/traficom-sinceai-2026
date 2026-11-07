import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from terra_fixtures import ISSUE_N, fixture_exporter, fixture_mdb

from ific import api, ingest
from ific.config import settings
from ific.terra import jobs as terra_jobs

GATE = threading.Event()


@pytest.fixture
def terra_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    issue_dir = settings.terra_download_dir / str(ISSUE_N)
    issue_dir.mkdir(parents=True)
    fixture_mdb(issue_dir, ISSUE_N)
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr(ingest, "PROJECT_ROOT", root)
    monkeypatch.setattr(ingest, "mdb_export", fixture_exporter)
    with TestClient(api.app) as client:
        yield client


def _assess(client: TestClient) -> None:
    assert client.post(f"/api/terrestrial/issues/{ISSUE_N}").status_code == 202
    client.app.state.terra_jobs.wait(ISSUE_N, 30)
    assert client.app.state.terra_jobs.job(ISSUE_N)["status"] == "done"


def test_issue_list_assess_and_assignments(terra_client: TestClient) -> None:
    issues = terra_client.get("/api/terrestrial/issues").json()
    assert [i["ific_no"] for i in issues] == [ISSUE_N] and issues[0]["assessed"] is False
    _assess(terra_client)
    issue = terra_client.get("/api/terrestrial/issues").json()[0]
    assert (
        issue["assessed"] and issue["outcome_counts"]["exceeds"] == 1 and issue["model_version"] == "terra-1"
    )
    body = terra_client.get(f"/api/terrestrial/issues/{ISSUE_N}/assignments").json()
    keys = [a["sort_key"] for a in body["assignments"]]
    assert keys == sorted(keys) and body["assignments"][0]["outcome"] == "exceeds"
    assert all(a["relevance"]["relevant"] for a in body["assignments"])
    every = terra_client.get(f"/api/terrestrial/issues/{ISSUE_N}/assignments?relevant=all").json()
    assert every["count"] == body["count"] + 1
    rus = terra_client.get(f"/api/terrestrial/issues/{ISSUE_N}/assignments?adm=rus&outcome=exceeds").json()
    assert [a["terrakey"] for a in rus["assignments"]] == [90000008]
    assert terra_client.get(f"/api/terrestrial/issues/{ISSUE_N}/assignments?outcome=bogus").status_code == 422


def test_detail_includes_p1546_inputs(terra_client: TestClient) -> None:
    _assess(terra_client)
    detail = terra_client.get(f"/api/terrestrial/issues/{ISSUE_N}/assignments/90000008").json()
    t2 = detail["hazard"]["tier2"]
    assert t2["p1546"]["inputs"]["f_mhz"] == 162.0 and t2["p1546"]["steps"]
    assert detail["hazard"]["parameters"]["erp_dbw"] == 15.0
    assert terra_client.get(f"/api/terrestrial/issues/{ISSUE_N}/assignments/1").status_code == 404


def test_second_post_while_running_is_409(terra_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    original = terra_jobs.assess_issue

    def gated(*args, **kwargs):
        assert GATE.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(terra_jobs, "assess_issue", gated)
    GATE.clear()
    assert terra_client.post(f"/api/terrestrial/issues/{ISSUE_N}").status_code == 202
    assert terra_client.post(f"/api/terrestrial/issues/{ISSUE_N}").status_code == 409
    GATE.set()
    terra_client.app.state.terra_jobs.wait(ISSUE_N, 30)
    assert terra_client.post("/api/terrestrial/issues/1234").status_code == 404


def test_model_lists_criteria_and_assumptions(terra_client: TestClient) -> None:
    model = terra_client.get("/api/terrestrial/model").json()
    assert {c["id"] for c in model["criteria"]} == {"tr-25-08", "ecc-rec-11-04"}
    assert all(c["verified"] is False for c in model["criteria"])
    assert any(a["id"] == "A-T-ECC-RUS" for a in model["assumptions"])


def test_csv_download_follows_the_list_filters(terra_client: TestClient) -> None:
    _assess(terra_client)
    resp = terra_client.get(f"/api/terrestrial/issues/{ISSUE_N}/assignments.csv?adm=RUS&outcome=exceeds")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/csv")
    assert f'filename="terra-{ISSUE_N}.csv"' in resp.headers["content-disposition"]
    lines = resp.text.splitlines()
    assert (
        lines[0].startswith("terrakey,adm,adm_ref_id")
        and len(lines) == 2
        and lines[1].startswith("90000008,")
    )
    listed = terra_client.get(f"/api/terrestrial/issues/{ISSUE_N}/assignments?relevant=all").json()
    full = terra_client.get(
        f"/api/terrestrial/issues/{ISSUE_N}/assignments.csv?relevant=all"
    ).text.splitlines()
    assert [int(line.split(",")[0]) for line in full[1:]] == [a["terrakey"] for a in listed["assignments"]]
    assert terra_client.get("/api/terrestrial/issues/1234/assignments.csv").status_code == 404
