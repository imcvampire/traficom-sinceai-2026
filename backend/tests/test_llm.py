import asyncio
import json

import httpx2
import pytest
from pydantic import SecretStr

from ific.config import Settings
from ific.llm import ChatClient, LlmError, Usage, make_chat_client


def sse(*chunks: dict | str) -> bytes:
    lines = [f"data: {c if isinstance(c, str) else json.dumps(c)}\n\n" for c in chunks]
    return ("".join(lines)).encode()


def delta(text: str | None = None, reasoning: str | None = None) -> dict:
    d = {k: v for k, v in (("content", text), ("reasoning_content", reasoning)) if v is not None}
    return {"choices": [{"index": 0, "delta": d}]}


def client_for(handler, max_concurrent: int = 1) -> ChatClient:
    http = httpx2.AsyncClient(base_url="https://llm.test/v1", transport=httpx2.MockTransport(handler))
    return ChatClient(http, "test-model", max_concurrent)


async def collect(client: ChatClient) -> list[str | Usage]:
    response = await client.open([{"role": "user", "content": "hi"}])
    try:
        return [x async for x in client.deltas(response)]
    finally:
        await response.aclose()


def test_stream_joins_content_and_skips_reasoning() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        body = b": keep-alive\n\n" + sse(
            delta(reasoning="let me think"),
            delta("Hello"),
            delta(""),
            delta(", world"),
            {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 3}},
            "[DONE]",
            delta("after done"),
        )
        return httpx2.Response(200, content=body, headers={"content-type": "text/event-stream"})

    out = asyncio.run(collect(client_for(handler)))
    assert out == ["Hello", ", world", Usage(12, 3)]
    assert str(seen[0].url) == "https://llm.test/v1/chat/completions"
    sent = json.loads(seen[0].content)
    assert sent == {"model": "test-model", "messages": [{"role": "user", "content": "hi"}], "stream": True}


def test_non_200_raises_with_status_and_truncated_body() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, content=b'{"error": "invalid key"}' + b"x" * 5000)

    with pytest.raises(LlmError) as e:
        asyncio.run(collect(client_for(handler)))
    assert e.value.status == 401 and e.value.detail.startswith('{"error": "invalid key"}')
    assert len(e.value.detail) == 300


def test_malformed_chunk_and_transport_error() -> None:
    def bad(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=sse(delta("ok")) + b"data: {not json\n\n")

    with pytest.raises(LlmError, match="malformed"):
        asyncio.run(collect(client_for(bad)))

    def down(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused")

    with pytest.raises(LlmError) as e:
        asyncio.run(collect(client_for(down)))
    assert e.value.status is None and "ConnectError" in e.value.detail


def test_concurrency_gate() -> None:
    client = client_for(lambda r: httpx2.Response(200), max_concurrent=2)
    assert client.try_acquire() and client.try_acquire()
    assert not client.try_acquire()
    client.release()
    assert client.try_acquire()


def test_make_chat_client_needs_key_and_model() -> None:
    assert make_chat_client(Settings(llm_api_key=None, llm_model="m")) is None
    assert make_chat_client(Settings(llm_api_key=SecretStr("k"), llm_model=None)) is None
    client = make_chat_client(Settings(llm_api_key=SecretStr("sk-test"), llm_model="m", llm_max_concurrent=3))
    assert client is not None
    try:
        assert client.http.headers["Authorization"] == "Bearer sk-test"
        assert client.model == "m" and client.max_concurrent == 3
        assert str(client.http.base_url) == "https://api.featherless.ai/v1/"
    finally:
        asyncio.run(client.aclose())
