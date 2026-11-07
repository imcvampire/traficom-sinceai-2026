---
phase: 4
title: Docs and verification
status: completed
depends_on: [3]
---

# Phase 04: Docs and verification

## Files

| File | Action |
|---|---|
| `docs/frontend.md` | `/risk` param table: `chat` (opens the chat panel; scope is the open notice, else the filtered view). A short paragraph on the panel and the "explanation, not assessment" label. |
| `README.md` | Configuration: `IFIC_LLM_MAX_CONCURRENT`, and that chat is disabled until key and model are set. API list: `GET /api/risk/chat`, `POST /api/risk/issues/{ific_no}/chat`. |
| `.env.example` | `IFIC_LLM_MAX_CONCURRENT=1` with a comment on Featherless concurrency cost. |
| `CLAUDE.md` | One line under Architecture: chat context is assembled server-side in `riia/chat.py` and must keep the no-score rule. |

## Verification

1. `mise run lint`, `mise run test`, `mise run build`.
2. Real-provider smoke test (needs the key in `.env`; costs a few cents): restart the API, open
   `/risk?ific=3083&outcome=exceeds&chat=1`, ask "Which Finnish services are most affected?"; open notice
   326500094, ask "Which assumptions could change the outcome?". Check that the answers cite ids that exist, give
   no combined score, and that the `ific.chat` log line shows token counts or `null`. Record first-token latency
   and whether Featherless accepted the concurrency setting.
3. Compare against the acceptance criteria in [plan.md](plan.md) and mark phases completed.

## Rollback

Docs only.
