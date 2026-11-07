import json
from collections.abc import Callable, Iterator

import httpx2
import pytest
from fastapi.testclient import TestClient
from riia_fixtures import FIXTURE_ISSUE
from test_llm import delta, sse
from test_riia_api import _wait_done, risk_client  # noqa: F401

from ific import api
from ific.llm import ChatClient

URL = f"/api/risk/issues/{FIXTURE_ISSUE}/chat?as_of=2026-07-01"
ASK = [{"role": "user", "content": "Which services are affected?"}]

Handler = Callable[[httpx2.Request], httpx2.Response]


class FakeProvider:
    def __init__(self) -> None:
        self.requests: list[dict] = []
        usage = {"choices": [], "usage": {"prompt_tokens": 9}}
        body = sse(delta("Fixed "), delta("links."), usage, "[DONE]")
        self.reply: Handler = lambda r: httpx2.Response(200, content=body)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        return self.reply(request)

    def data(self, i: int = -1) -> dict:
        system = self.requests[i]["messages"][0]["content"]
        return json.loads(system.split("<data>\n", 1)[1].rsplit("\n</data>", 1)[0])


@pytest.fixture
def assessed(risk_client: TestClient) -> TestClient:  # noqa: F811
    assert risk_client.post(f"/api/risk/issues/{FIXTURE_ISSUE}?as_of=2026-07-01").status_code == 202
    assert _wait_done(risk_client)["job"]["status"] == "done"
    return risk_client


@pytest.fixture
def provider(assessed: TestClient) -> Iterator[FakeProvider]:
    fake = FakeProvider()
    http = httpx2.AsyncClient(base_url="https://llm.test/v1", transport=httpx2.MockTransport(fake))
    api.app.state.chat = ChatClient(http, "fake-model", 1)
    yield fake


def events(body: str) -> list[tuple[str, dict]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_status_disabled_by_default(assessed: TestClient) -> None:
    status = assessed.get("/api/risk/chat").json()
    assert status == {
        "enabled": False,
        "model": None,
        "reason": "IFIC_LLM_API_KEY and IFIC_LLM_MODEL are not set",
    }
    r = assessed.post(URL, json={"messages": ASK})
    assert r.status_code == 503 and "IFIC_LLM_API_KEY" in r.json()["detail"]


def test_status_enabled(assessed: TestClient, provider: FakeProvider) -> None:
    assert assessed.get("/api/risk/chat").json() == {"enabled": True, "model": "fake-model", "reason": None}


def test_view_scope_streams_answer(assessed: TestClient, provider: FakeProvider) -> None:
    r = assessed.post(URL, json={"messages": ASK, "ntc_ids": [1001], "filters": {"outcome": "Exceeds"}})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    ev = events(r.text)
    assert "".join(d["text"] for e, d in ev if e == "delta") == "Fixed links."
    assert ev[-1] == ("done", {"usage": {"prompt_tokens": 9, "completion_tokens": None}})
    data = provider.data()
    assert data["scope"] == "view" and data["filters"] == {"outcome": "Exceeds"}
    assert [row[0] for row in data["notices"]["rows"]] == [1001]
    assert provider.requests[0]["model"] == "fake-model" and provider.requests[0]["messages"][1:] == ASK
    assert api.app.state.chat.try_acquire(), "slot released after the stream"


def test_notice_scope(assessed: TestClient, provider: FakeProvider) -> None:
    r = assessed.post(URL, json={"messages": ASK, "ntc_id": 1001})
    assert r.status_code == 200
    data = provider.data()
    assert data["scope"] == "notice" and data["notice"]["ntc_id"] == 1001 and data["notice"]["hazards"]


def test_not_found_and_validation(assessed: TestClient, provider: FakeProvider) -> None:
    assert assessed.post(URL, json={"messages": ASK, "ntc_id": 424242}).status_code == 404
    assert assessed.post("/api/risk/issues/1234/chat", json={"messages": ASK}).status_code == 404
    last_assistant = [*ASK, {"role": "assistant", "content": "ok"}]
    assert assessed.post(URL, json={"messages": last_assistant}).status_code == 422
    assert not provider.requests
    assert api.app.state.chat.try_acquire(), "slot released after 404"


def test_concurrency_limit(assessed: TestClient, provider: FakeProvider) -> None:
    assert api.app.state.chat.try_acquire()
    r = assessed.post(URL, json={"messages": ASK})
    assert r.status_code == 429 and not provider.requests


def test_upstream_error_before_stream(assessed: TestClient, provider: FakeProvider) -> None:
    provider.reply = lambda r: httpx2.Response(401, json={"error": "invalid api key"})
    r = assessed.post(URL, json={"messages": ASK})
    assert r.status_code == 502 and "invalid api key" in r.json()["detail"]
    assert api.app.state.chat.try_acquire(), "slot released after 502"


def test_upstream_error_mid_stream(assessed: TestClient, provider: FakeProvider) -> None:
    provider.reply = lambda r: httpx2.Response(200, content=sse(delta("Partial")) + b"data: {broken\n\n")
    r = assessed.post(URL, json={"messages": ASK})
    assert r.status_code == 200
    ev = events(r.text)
    assert ev[0] == ("delta", {"text": "Partial"})
    assert ev[-1][0] == "error" and "malformed" in ev[-1][1]["detail"]
    assert api.app.state.chat.try_acquire(), "slot released after a stream error"
