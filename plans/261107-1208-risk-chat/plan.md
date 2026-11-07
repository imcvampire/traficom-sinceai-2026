---
title: Chat about risk results on /risk
description: An LLM chat panel on /risk that answers questions about the filtered notice view or the open notice, grounded in stored riia-1 results and streamed from the configured OpenAI-compatible provider.
status: completed
mode: auto
priority: P2
effort: 1.5d
branch: main
tags: [frontend, api, llm]
blockedBy: []
blocks: []
created: 2026-11-07
source: /ak-brainstorm "how to ask LLM/AI chat to this system? Should we put it in /risk?outcome=exceeds ..." → option A accepted ("Do option 1. No auth is needed. History is nice-to-have. Skip for now.")
---

# Chat about risk results on /risk

## Outcome

`/risk` gets a chat panel. Its scope follows what the user is looking at:

- **View scope.** No notice is open. The panel answers questions about the notices the table currently shows, after
  all filters and the search (`outcome=exceeds`, `service`, `adm`, `q`, ...), in the table's sort order.
- **Notice scope.** A notice is open (`ntc=`). The chat sits beside the notice details in the same sheet and answers
  about that notice's hazards, assumptions and regulatory context.

The server builds the context from stored results and streams the answer from the provider configured by
`IFIC_LLM_*` (Featherless, `moonshotai/Kimi-K3.1-Pro`). The browser only sends the question, the earlier turns and
notice IDs.

## Contract

- **Constraints:**
  - Read-only. Nothing the LLM says is written to `analytics` or anywhere else.
  - No composite score. The system prompt forbids inventing a score or ranking, and a test asserts that the
    assembled context has no `score` key.
  - No regulatory verdict beyond the stored regulatory context. Answers are labelled "explanation, not
    assessment".
  - The API key stays on the server. No auth on the endpoint (internal tool, user decision 2026-11-07).
  - The open state of the panel lives in the URL (`chat=1`). Messages do not.
- **Non-goals:** persisting or sharing conversations (deferred by the user), tool calling or agents, RAG or
  embeddings, an MCP server, chat on any page other than `/risk`, changing the risk model.
- **Acceptance criteria:**
  1. With `outcome=exceeds`, the request carries only the filtered `ntc_id`s, and the context lists only those
     notices (API test with a fake provider).
  2. With a notice open, the context holds that notice's detail with `sensitive` assumption flags, and an answer
     can cite its `hazard_id`s and assumption ids (API test checks the context; manual smoke checks the answer).
  3. With no key or no model configured, `GET /api/risk/chat` reports `enabled: false`, the POST returns 503 and
     the UI shows the panel disabled with the reason.
  4. A second chat while the concurrency limit is used returns 429. An upstream error before the first token
     returns 502; one after it ends the stream with an `error` event.
  5. The assembled context contains no `score` key and no `risk_curves` or `curve_grid_db` arrays.
  6. `mise run lint`, `mise run test` and `mise run build` pass. `docs/frontend.md` lists `chat`, and the README
     lists `IFIC_LLM_MAX_CONCURRENT`.

## Evidence (inspected 2026-11-07)

| Source | Finding |
|---|---|
| `backend/src/ific/config.py`, `.env.example`, journal `2026-11-07-llm-provider-settings.md` | `llm_api_key` (`SecretStr`), `llm_base_url` (Featherless), `llm_model`, `llm_timeout_seconds` exist. Nothing calls an LLM yet. |
| `backend/pyproject.toml` | `httpx2` is already a dependency and is httpx-compatible (`AsyncClient`, `stream`, `MockTransport`). No OpenAI SDK is needed. |
| Live API, IFIC 3083 (168 notices, 59 `exceeds`) | List ~100 KB; one `exceeds` notice detail ~47 KB, of which `hazards[].inputs` and `assumptions` are most of it and `risk_curves` is ~0.5 KB per hazard; `/api/risk/model` ~14 KB; `docs/interference-risk-assessment.md` ~32 KB. Everything fits a 262k-token context. |
| `frontend/src/components/risk-table.tsx` | Filters, search and sort run client-side in TanStack Table. Rebuilding the view on the server would duplicate that logic. |
| `frontend/src/components/notice-sheet.tsx`, `ui/sheet.tsx` | The notice detail is a modal Radix sheet (`sm:max-w-3xl`). A second modal sheet would cover it. |
| `frontend/package.json` | No markdown renderer, no streaming helper. |
| `frontend/vite.config.ts` | `/api` is proxied to `127.0.0.1:8000`; http-proxy passes SSE through unbuffered. |
| `backend/tests/conftest.py` | Settings load the root `.env`, which holds the real key. Tests must force the LLM off so they never call Featherless. |

## Decisions

| Decision | Choice | Why | Alternative rejected |
|---|---|---|---|
| Architecture | Server-side context assembly, one streamed chat completion per turn, no tools | Fits the window; cheapest to abandon; the context builder can later back tools unchanged | Tool calling (unverified for Kimi on Featherless); MCP (no on-screen context) |
| How the view reaches the server | Client sends the filtered `ntc_id`s in table order plus the active filter values as labels. Server loads the records and drops unknown IDs. | One filter implementation; the server stays the source of record data | Server re-applies URL filters: duplicates `risk-table.tsx` logic, which would drift |
| Provider client | `httpx2.AsyncClient` against `{llm_base_url}/chat/completions` with `stream: true`; parse `data:` lines; use `choices[0].delta.content`, ignore `reasoning_content`; log `usage` when the provider sends it | Existing dependency; the OpenAI wire format is small | OpenAI SDK: new dependency for one call |
| Context contents | System rules; the method doc (`docs/interference-risk-assessment.md`) verbatim; a compact table of the scoped notices (summary fields, columns + rows); for notice scope the full detail minus `risk_curves` and `curve_grid_db` | The doc is the source of truth for terms and outcomes; curve arrays are unreadable to an LLM | `method.describe()` only: lacks the outcome and tier definitions |
| Response transport | SSE (`text/event-stream`): `delta`, `done`, `error` events. Upstream status is checked before the response starts, so pre-stream failures are real HTTP errors | Streaming makes 10–60 s answers usable; status codes stay meaningful | Non-streamed JSON: long waits with no feedback |
| Concurrency | `IFIC_LLM_MAX_CONCURRENT` (default 1) non-blocking gate; over the limit returns 429 | Kimi has concurrency cost 4 on Featherless; queuing hides overload | Unbounded: provider 429s mid-session |
| Chat placement | View scope: a right sheet opened by an "Ask about this view" button. Notice scope: the notice sheet widens and shows the chat as a right column (stacked on narrow screens). Both use one `RiskChat` component. `chat=1` in the URL; closing the notice sheet clears it. | Keeps the data visible while asking; no stacked modals | One shared chat sheet over the notice sheet: hides the details being asked about |
| Conversation state | Page-level map keyed by scope (`ific`, `as_of`, filter values, or `ntc`), in memory only | Survives closing and reopening the panel within a page visit; history persistence is deferred | `sessionStorage`: deferred with history |
| Answer rendering | Plain text with `whitespace-pre-wrap`; the system prompt asks for prose and `-` bullets, no tables or headings | No new dependency | `react-markdown`: a dependency for formatting only |

## Extension trace

The credible next variant is tool calling (option B). The stable contract is the context builder in
`riia/chat.py` (`notice_rows`, `notice_detail`) and the SSE event shape. B would add a tool loop in `llm.py` and
expose the same builder functions as tools; the endpoint, the frontend and the event shape stay unchanged. Phase 1
proves the builder is independent of transport by unit-testing it without HTTP.

## Phases

| # | Phase | Status | Depends on |
|---|---|---|---|
| 1 | [Provider client and context builder](phase-01-llm-client-and-context.md) | completed | — |
| 2 | [Chat API](phase-02-chat-api.md) | completed | 1 |
| 3 | [Chat panel on /risk](phase-03-chat-panel.md) | completed | 2 |
| 4 | [Docs and verification](phase-04-docs-and-verify.md) | completed | 3 |

## Risks

| Risk | Mitigation |
|---|---|
| Kimi K3.1 Pro streams only `reasoning_content` for a long time, or needs a plan with cost-4 concurrency | Ignore reasoning deltas; the UI shows "thinking…" until the first content delta; phase 4 smoke-tests the real model and records latency |
| Large view (all ~200 notices) plus the doc costs ~$0.10 per turn | Compact row format; log prompt tokens; cap `ntc_ids` at 1000 |
| Hallucinated numbers or a made-up score | System rules require citing `ntc_id`/`hazard_id`/assumption ids and quoting stored values; UI label "explanation, not assessment" |
| ITU text fields (satellite or network names) carry instructions | Context is fenced as data; no tools, so nothing can be triggered |
| Tests calling the real provider through `.env` | `conftest.py` autouse fixture sets `llm_api_key` and `llm_model` to `None` |

## Unresolved questions

1. ~~Does the Featherless plan in use allow a cost-4 model at the chosen `IFIC_LLM_MAX_CONCURRENT`?~~ Yes at 1:
   both smoke turns on 2026-11-07 returned 200. Higher values are untested.

## Validation (2026-11-07)

Confirmed by the user: the full method doc goes into the context, notice-scope chat is a column in the notice sheet,
and `IFIC_LLM_MAX_CONCURRENT` defaults to 1.

## Verification (2026-11-07)

- `mise run lint`, `mise run test` (358 passed) and `mise run build` pass.
- Real provider, IFIC 3083: view scope (`outcome=exceeds`, 59 ids) took 43 s with 16.2k prompt and 5.3k completion
  tokens; notice 326500094 took 37 s with 22.1k prompt and 3.7k completion tokens. Every cited `ntc_id` and
  `hazard_id` exists, and neither answer gave a score or ranking. The first answer used Markdown emphasis, so the
  system rules now forbid Markdown; the second answer was plain text.
- A UI turn before the smoke test streamed `reasoning_content` for several minutes (~600 KB) before any content,
  holding the single slot. The per-read timeout does not fire while reasoning chunks arrive. See the journal.
