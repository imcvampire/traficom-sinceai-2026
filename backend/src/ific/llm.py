"""Streaming client for an OpenAI-compatible chat completions API (`IFIC_LLM_*`)."""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx2

from ific import __version__
from ific.config import Settings

_DETAIL_CHARS = 300
_ERROR_BODY_BYTES = 2048


class LlmError(Exception):
    def __init__(self, status: int | None, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int | None
    completion_tokens: int | None


def _describe(e: httpx2.HTTPError) -> str:
    return f"{type(e).__name__}: {e}"[:_DETAIL_CHARS] if str(e) else type(e).__name__


class ChatClient:
    def __init__(self, http: httpx2.AsyncClient, model: str, max_concurrent: int) -> None:
        self.http = http
        self.model = model
        self.max_concurrent = max_concurrent
        self._active = 0

    # Called from async route handlers only, so the counter is touched on the event loop thread alone.
    def try_acquire(self) -> bool:
        if self._active >= self.max_concurrent:
            return False
        self._active += 1
        return True

    def release(self) -> None:
        self._active = max(0, self._active - 1)

    async def aclose(self) -> None:
        await self.http.aclose()

    async def open(self, messages: list[dict[str, str]]) -> httpx2.Response:
        request = self.http.build_request(
            "POST", "chat/completions", json={"model": self.model, "messages": messages, "stream": True}
        )
        try:
            response = await self.http.send(request, stream=True)
        except httpx2.HTTPError as e:
            raise LlmError(None, _describe(e)) from e
        if response.status_code == 200:
            return response
        try:
            body = b""
            async for chunk in response.aiter_bytes():
                body += chunk
                if len(body) >= _ERROR_BODY_BYTES:
                    break
        except httpx2.HTTPError:
            pass
        finally:
            await response.aclose()
        text = body.decode("utf-8", "replace").strip()
        raise LlmError(response.status_code, (text or response.reason_phrase)[:_DETAIL_CHARS])

    async def deltas(self, response: httpx2.Response) -> AsyncIterator[str | Usage]:
        """Content deltas in order, plus `Usage` when a chunk reports it; reasoning deltas are skipped."""
        try:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                try:
                    chunk: dict[str, Any] = json.loads(data)
                except json.JSONDecodeError as e:
                    raise LlmError(None, f"malformed stream chunk: {data[:80]}") from e
                if isinstance(chunk.get("error"), dict | str):
                    err = chunk["error"]
                    raise LlmError(None, str(err.get("message", err) if isinstance(err, dict) else err))
                for choice in chunk.get("choices") or []:
                    text = (choice.get("delta") or {}).get("content")
                    if text:
                        yield text
                if usage := chunk.get("usage"):
                    yield Usage(usage.get("prompt_tokens"), usage.get("completion_tokens"))
        except httpx2.HTTPError as e:
            raise LlmError(None, _describe(e)) from e


def make_chat_client(settings: Settings) -> ChatClient | None:
    if not settings.llm_enabled:
        return None
    assert settings.llm_api_key is not None and settings.llm_model is not None
    http = httpx2.AsyncClient(
        base_url=str(settings.llm_base_url),
        timeout=httpx2.Timeout(settings.llm_timeout_seconds, connect=10),
        headers={
            "Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}",
            "User-Agent": f"ific/{__version__}",
        },
    )
    return ChatClient(http, settings.llm_model, settings.llm_max_concurrent)
