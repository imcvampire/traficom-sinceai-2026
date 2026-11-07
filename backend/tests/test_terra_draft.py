from pathlib import Path

import pytest
from terra_fixtures import ISSUE_N, ISSUE_N1, assessed

from ific.drafting import BANNER
from ific.terra import draft, store


@pytest.fixture
def stored(tmp_path: Path):
    con, res = assessed(tmp_path)
    for n, rows in res.items():
        store.write_results(con, n, list(rows.values()))
    return con, res


def test_kind_follows_the_stored_findings(stored) -> None:
    _, res = stored
    r = res[ISSUE_N]
    assert draft.choose_kind(r[90000002]) == "coordination_request"  # COORD REQUIRED, meets
    assert draft.choose_kind(r[90000008]) == "coordination_request"  # exceeds, no FIN coordination
    assert draft.choose_kind(r[90000003]) is None  # meets
    fin = [{"adm": "FIN", "coord_prov": "RR6.7", "coord_st": "COORD COMPLETED"}]
    completed = {**r[90000008], "relevance": {**r[90000008]["relevance"], "fin_coordination": fin}}
    assert draft.choose_kind(completed) == "enquiry"


def test_rus_letter_cites_bilateral_and_hides_station_details(stored) -> None:
    con, res = stored
    d = draft.build_draft(con, ISSUE_N, "rus")
    assert isinstance(d, draft.TerraDraft) and d.kind == "coordination_request"
    assert d.letter_md.count(BANNER) == 2
    assert "FIN–RUS bilateral frequency coordination agreement" in d.letter_md and "indicative" in d.letter_md
    assert {a.adm_ref_id for a in d.annex} == {"RUS-002FB26", "RUS-008FB26"}
    for key in (90000002, 90000008):
        assert str(key) not in d.letter_md
        site = res[ISSUE_N][key]["site"]
        assert f"{site['lat']:.4f}" not in d.letter_md
    assert any("90000008" in n for n in d.reviewer_notes)
    assert "+19.1" in d.letter_md  # annex quotes the stored margin


def test_no_concern_and_unknown_administration(stored) -> None:
    con, _ = stored
    assert isinstance(draft.build_draft(con, ISSUE_N, "EST"), draft.NoConcern)
    assert draft.build_draft(con, ISSUE_N, "XYZ") is None
    assert draft.concern_adms(con, ISSUE_N) == {"RUS": 2}


def test_polish_guard_and_reproducibility(stored) -> None:
    con, _ = stored
    d = draft.build_draft(con, ISSUE_N, "RUS")
    assert draft.build_draft(con, ISSUE_N, "RUS") == d
    ok = draft.check_polish(
        d, "\n\n".join(p.replace("may affect", "could affect") for p in d.prose_paragraphs)
    )
    assert ok.paragraphs is not None
    changed = "\n\n".join(d.prose_paragraphs).replace("9997", "9996", 1)
    bad = draft.check_polish(d, changed)
    assert bad.paragraphs is None and "9997" in bad.missing


def test_draft_api_without_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient
    from terra_fixtures import fixture_exporter, fixture_mdb

    from ific import api, ingest
    from ific.config import settings

    issue_dir = settings.terra_download_dir / str(ISSUE_N1)
    issue_dir.mkdir(parents=True)
    fixture_mdb(issue_dir, ISSUE_N1)
    monkeypatch.setattr(ingest, "mdb_export", fixture_exporter)
    monkeypatch.setattr(ingest, "PROJECT_ROOT", tmp_path / "root")
    with TestClient(api.app) as client:
        assert client.post(f"/api/terrestrial/issues/{ISSUE_N1}").status_code == 202
        client.app.state.terra_jobs.wait(ISSUE_N1, 30)
        assert client.get(f"/api/terrestrial/issues/{ISSUE_N1}/drafts").json() == [
            {"adm": "RUS", "adm_name": "Russian Federation", "assignments": 1}
        ]
        letter = client.get(f"/api/terrestrial/issues/{ISSUE_N1}/drafts/RUS").json()
        assert letter["kind"] == "coordination_request" and BANNER in letter["letter_md"]
        assert client.get(f"/api/terrestrial/issues/{ISSUE_N1}/drafts/EST").status_code == 409
        assert client.post(f"/api/terrestrial/issues/{ISSUE_N1}/drafts/RUS/polish").status_code == 503
        tr = client.get(f"/api/terrestrial/issues/{ISSUE_N1}/trends?issues=1,abc").json()
        assert tr["issues"] == [ISSUE_N1] and len(tr["anomalies"]) == 4


def test_polish_that_alters_a_reference_is_rejected(stored) -> None:
    con, _ = stored
    d = draft.build_draft(con, ISSUE_N, "RUS")
    body = "\n\n".join(d.prose_paragraphs)
    bad = draft.check_polish(d, body.replace("RUS-008FB26", "RUS-008FX26"))
    assert bad.paragraphs is None and "RUS-008FB26" in bad.missing


def test_withdrawn_assignment_gets_no_letter(stored) -> None:
    _, res = stored
    w = res[ISSUE_N][90000009]
    rel = {**w["relevance"], "fin_coord_required": True}
    assert draft.choose_kind({**w, "relevance": rel}) is None
