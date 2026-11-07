import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient
from riia_fixtures import FIXTURE_ISSUE, loaded_db
from test_llm import delta, sse
from test_riia_api import _wait_done, risk_client  # noqa: F401
from test_riia_draft import GenericTwoStations
from typer.testing import CliRunner

from ific import api, cli
from ific.llm import ChatClient
from ific.riia import store
from ific.riia.assess import assess_issue

BASE = f"/api/risk/issues/{FIXTURE_ISSUE}/notices"
AS_OF = "2026-07-01"


@pytest.fixture
def assessed(risk_client: TestClient) -> TestClient:  # noqa: F811
    assert risk_client.post(f"/api/risk/issues/{FIXTURE_ISSUE}?as_of={AS_OF}").status_code == 202
    assert _wait_done(risk_client)["job"]["status"] == "done"
    return risk_client


class Polisher:
    """Fake provider: rewrites the paragraphs it is sent with `edit`."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.edit = lambda text: text.replace("refers to", "wishes to refer to")
        self.status = 200

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        if self.status != 200:
            return httpx2.Response(self.status, text="boom")
        user = body["messages"][1]["content"]
        text = user.removeprefix("<paragraphs>\n").removesuffix("\n</paragraphs>")
        return httpx2.Response(200, content=sse(delta(self.edit(text)), "[DONE]"))


@pytest.fixture
def polisher(assessed: TestClient) -> Iterator[Polisher]:
    fake = Polisher()
    http = httpx2.AsyncClient(base_url="https://llm.test/v1", transport=httpx2.MockTransport(fake))
    api.app.state.chat = ChatClient(http, "fake-model", 1)
    yield fake


def test_get_draft(assessed: TestClient) -> None:
    r = assessed.get(f"{BASE}/1001/draft?as_of={AS_OF}")
    assert r.status_code == 200
    d = r.json()
    assert d["kind"] == "comment_9_52" and d["adm_name"] == "United States of America"
    assert [row["source"] for row in d["annex"]] == ["generic-m4"]
    assert any("`stations` has no stored result" in w for w in d["warnings"])
    assert "score" not in r.text
    late = assessed.get(f"{BASE}/1001/draft?as_of=2026-11-06").json()
    assert late["kind"] == "enquiry" and late["annex"] == d["annex"]


def test_draft_no_concern_and_not_found(assessed: TestClient) -> None:
    r = assessed.get(f"{BASE}/1004/draft?as_of={AS_OF}")
    assert r.status_code == 409 and r.json()["detail"].startswith("no concern to describe: notice 1004")
    assert assessed.get(f"{BASE}/424242/draft?as_of={AS_OF}").status_code == 404


def test_polish_disabled(assessed: TestClient) -> None:
    r = assessed.post(f"{BASE}/1001/draft/polish?as_of={AS_OF}")
    assert r.status_code == 503 and "IFIC_LLM_API_KEY" in r.json()["detail"]


def test_polish_faithful(assessed: TestClient, polisher: Polisher) -> None:
    template = assessed.get(f"{BASE}/1001/draft?as_of={AS_OF}").json()
    r = assessed.post(f"{BASE}/1001/draft/polish?as_of={AS_OF}")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["polished"] and out["model"] == "fake-model"
    assert "wishes to refer to" in out["letter_md"]
    annex = template["letter_md"].split("Yours faithfully,", 1)[1]
    assert out["letter_md"].endswith(annex)
    sent = polisher.requests[0]["messages"]
    assert "| Source |" not in sent[1]["content"] and "Basis (" not in sent[1]["content"]
    assert api.app.state.chat.try_acquire(), "slot released"


@pytest.mark.parametrize(
    ("edit", "missing"),
    [
        (lambda t: t.replace("2026-10-23", "2026-10-30"), ["2026-10-23"]),
        (lambda t: t.replace("(notice 1001)", "(this notice)"), ["1001"]),
    ],
)
def test_polish_rejects_changed_facts(assessed: TestClient, polisher: Polisher, edit, missing) -> None:
    polisher.edit = edit
    r = assessed.post(f"{BASE}/1001/draft/polish?as_of={AS_OF}")
    assert r.status_code == 422
    assert r.json()["missing"] == missing and "template text is kept" in r.json()["detail"]
    assert api.app.state.chat.try_acquire(), "slot released after a rejection"


def test_polish_concurrency_and_upstream_error(assessed: TestClient, polisher: Polisher) -> None:
    assert api.app.state.chat.try_acquire()
    assert assessed.post(f"{BASE}/1001/draft/polish?as_of={AS_OF}").status_code == 429
    api.app.state.chat.release()
    assert assessed.post(f"{BASE}/1004/draft/polish?as_of={AS_OF}").status_code == 409
    assert not polisher.requests
    polisher.status = 500
    r = assessed.post(f"{BASE}/1001/draft/polish?as_of={AS_OF}")
    assert r.status_code == 502 and "boom" in r.json()["detail"]
    assert api.app.state.chat.try_acquire(), "slot released after 409 and 502"


def test_cli_draft_writes_files(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    results = assess_issue(con, FIXTURE_ISSUE, date(2026, 7, 1), GenericTwoStations())
    store.write_results(con, FIXTURE_ISSUE, "generic-m4", results)
    con.close()
    out = tmp_path / "drafts"
    r = CliRunner().invoke(cli.app, ["draft", str(FIXTURE_ISSUE), "--as-of", AS_OF, "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert sorted(p.name for p in out.iterdir()) == ["1001-comment_9_52.md", "1002-enquiry.md"]
    assert "kinds={'comment_9_52': 1, 'enquiry': 1} no_concern=3" in r.output
    text = (out / "1001-comment_9_52.md").read_text(encoding="utf-8")
    assert "Reviewer notes (internal – do not send)" in text
    only = tmp_path / "only"
    r = CliRunner().invoke(
        cli.app, ["draft", str(FIXTURE_ISSUE), "--as-of", "2026-11-06", "--ntc", "1001", "--out", str(only)]
    )
    assert r.exit_code == 0 and [p.name for p in only.iterdir()] == ["1001-enquiry.md"]
