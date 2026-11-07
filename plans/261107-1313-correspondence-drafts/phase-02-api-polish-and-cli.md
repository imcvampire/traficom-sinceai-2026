---
phase: 2
title: "API, polish and CLI"
status: completed
priority: P2
effort: "4h"
dependencies: [1]
---

# Phase 2: API, polish and CLI

## Goal

Expose the draft over the API, add the guarded LLM polish, and add `ific draft` for batch output.

## Files to Create / Modify

- Modify: `backend/src/ific/riia/schemas.py` (`DraftOut`, `DraftAnnexRowOut`, `DraftPolishOut`)
- Modify: `backend/src/ific/api.py` (two routes)
- Modify: `backend/src/ific/riia/draft.py` (`polish_messages()`, `check_polish()`)
- Modify: `backend/src/ific/cli.py` (`draft` command)
- Create: `backend/tests/test_riia_draft_api.py`

## Tasks & Steps

1. **Read route.** `GET /api/risk/issues/{ific_no}/notices/{ntc_id}/draft?as_of=` → `DraftOut`.
   404 when the notice has no stored result in any source; 409 with `detail` = the `NoConcern` reason when there
   is no reading. Uses the per-request cursor (`Db`), read-only.
2. **Polish route.** `POST /api/risk/issues/{ific_no}/notices/{ntc_id}/draft/polish?as_of=` → `DraftPolishOut`
   (`letter_md`, `polished: true`, `model`). No request body: the server rebuilds the draft, so the browser never
   sends text to the LLM.
   - 503 when the chat client is not configured (reuse `_chat_disabled_reason()`); 429 when `try_acquire()` fails;
     `release()` in `finally`.
   - Messages: a system prompt ("Rewrite these paragraphs of a formal letter between administrations for clarity
     and a formal register. Keep every number, date, identifier and RR provision exactly as written. Do not add
     facts. Return only the paragraphs, separated by blank lines.") and the `prose_paragraphs` as user content,
     wrapped as data.
   - Collect `deltas()` into text server-side (no SSE); upstream error → 502.
   - `check_polish(original_tokens, polished)`: every protected token must occur verbatim in the output, and the
     paragraph count must match. On failure return 422 with `{"detail": …, "missing": [...]}`. On success,
     substitute the paragraphs into the template; header, annex and the DRAFT banner are never from the LLM.
   - Log one `ific.draft` line per polish with ific, ntc, token counts, timing and pass/fail — never the text, as
     the chat does.
3. **CLI.** `ific draft ISSUE --as-of YYYY-MM-DD [--ntc N]... [--out DIR]`. Default `--out`:
   `plans/reports/drafts-<ific_no>-<as_of>/`. Writes `<ntc_id>-<kind>.md` per notice with a concern (all notices
   with stored results, or only `--ntc`), skips no-concern notices, prints counts per kind. It opens the DB through
   `_prepare`, like `ific review`, so it needs the API server stopped (DuckDB's file lock blocks a second process
   even read-only). The UI is the route while the server runs. No LLM in the CLI.

## Tests (`backend/tests/test_riia_draft_api.py`, `TestClient` with the fixture issue)

- GET returns 200 with the expected kind for a concern notice, 409 for a no-concern notice, 404 for an unknown
  `ntc_id`; `as_of` moves a CR/C from `comment_9_52`/`inclusion_9_41` to `enquiry` after the window.
- Polish with a fake provider (`httpx2.MockTransport`, as in `test_riia_chat_api.py`) returning faithful prose →
  200 and the annex text is unchanged; returning prose with a changed number → 422 listing it; dropped `ntc_id` →
  422.
- Polish with the LLM off → 503; with the gate held → 429.
- CLI: `ific draft 9999 --as-of …` via `typer.testing.CliRunner` writes the expected files.
- Tests force the LLM off by default, as the chat tests do, so no request reaches Featherless.

## Verification

- `cd backend && uv run pytest tests/test_riia_draft.py tests/test_riia_draft_api.py -q`
- `cd backend && uv run pytest tests/test_riia_chat_api.py -q` (shared gate unaffected)
- `mise run lint`
