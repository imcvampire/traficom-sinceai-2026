---
phase: 2
title: Chat API
status: completed
depends_on: [1]
---

# Phase 02: Chat API

## Context

See [plan.md](plan.md) and [phase 01](phase-01-llm-client-and-context.md). Read `backend/src/ific/api.py` (lifespan,
`get_db`, the risk routes), `backend/tests/conftest.py` and `backend/tests/test_riia_api.py` (`risk_client`).

## Files

| File | Action |
|---|---|
| `backend/src/ific/riia/schemas.py` | `ChatMessageIn`, `ChatIn`, `ChatStatusOut`. |
| `backend/src/ific/api.py` | Lifespan creates and closes the `ChatClient`; `get_chat` dependency; two routes. |
| `backend/tests/conftest.py` | Autouse: `settings.llm_api_key = None`, `settings.llm_model = None`. |
| `backend/tests/test_riia_chat_api.py` | **New.** |

## Schemas

- `ChatMessageIn`: `role: Literal["user", "assistant"]`, `content: str` (1–8000 chars).
- `ChatIn`: `messages` (1–40, last one must be `user`, validated), `ntc_ids: list[int] | None` (max 1000),
  `ntc_id: int | None`, `filters: dict[str, str]` (max 12 entries, values max 200 chars, default `{}`).
- `ChatStatusOut`: `enabled: bool`, `model: str | None`, `reason: str | None` (e.g. "IFIC_LLM_API_KEY is not set").

## Routes

- `GET /api/risk/chat` → `ChatStatusOut`. Never exposes the key or the base URL.
- `POST /api/risk/issues/{ific_no}/chat?as_of=` (`async def`):
  1. No client → 503 with the reason.
  2. `try_acquire()` fails → 429 "a chat answer is already being generated".
  3. Build messages with `run_in_threadpool(chat.build_messages, con, ...)`; `None` → 404 (release first).
  4. `await client.open(messages)`; `LlmError` → 502 with its detail (release first).
  5. Return `StreamingResponse(media_type="text/event-stream", headers={"Cache-Control": "no-cache",
     "X-Accel-Buffering": "no"})` over a generator that emits `event: delta` with `{"text": ...}` per content
     chunk, `event: done` with `{"usage": ... | null}` at the end, and `event: error` with `{"detail": ...}` on an
     `LlmError` mid-stream. Its `finally` closes the upstream response and calls `release()`, so a client
     disconnect frees the slot and cancels the upstream call.
- Log one line per turn on `ific.chat`: `ific_no`, scope, notice count, history length, prompt/completion tokens
  when known, elapsed seconds, outcome (`ok`, `upstream_error`, `cancelled`). Never log message text.

The DB cursor from `get_db` is only used before the response starts.

## Tests (`test_riia_chat_api.py`)

Assess the fixture issue, then install a `ChatClient` built on `httpx2.MockTransport` into `api.app.state.chat`.
The transport records the request body and replies with a canned SSE stream.

- status: disabled by default (conftest), enabled with the fake client;
- view scope: posted `ntc_ids=[1001]` → recorded system message's `<data>` rows contain only 1001; SSE body has
  `delta` events whose text joins to the canned answer, then `done`;
- notice scope: `ntc_id=1001` → context has `notice.hazards`;
- 503 when disabled; 404 for an unknown notice and an unassessed issue; 422 when the last message is from
  `assistant`;
- 429: hold the slot with `try_acquire()` before posting;
- 502: transport answers 401 → 502 with the provider detail, and the slot is released;
- mid-stream malformed chunk → `error` event, slot released.

## Validation

```sh
cd backend && uv run pytest tests/test_riia_chat_api.py tests/test_riia_api.py -q
```

## Rollback

Remove the two routes, the schemas and the lifespan lines.
