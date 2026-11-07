# Risk chat implemented

Implemented `plans/261107-1208-risk-chat/`: a chat panel on `/risk` that answers about the filtered view or the open
notice, grounded in stored riia-1 results and streamed from Featherless (`moonshotai/Kimi-K3.1-Pro`).

- `backend/src/ific/llm.py` is a small `httpx2` streaming client. `riia/chat.py` builds the `<data>` context, and
  the endpoint in `api.py` streams SSE `delta` / `done` / `error` events.
- The concurrency slot is released in `_ChatStream.__call__`, not in the body generator. A generator that never
  started never runs its `finally`, so a client that disconnects before the first chunk would otherwise hold the
  only slot until restart.
- The JSON in `<data>` escapes `</` as `<\/`, so an ITU text field cannot close the fence. JSON readers still see the
  same string.
- The first real answer used Markdown bold and backticks, which the plain-text panel showed literally. The system
  rules now forbid Markdown, and the next answer was plain text.
- Real-provider timings on IFIC 3083: 37–43 s per turn, 16–22k prompt tokens, 4–5k completion tokens (most of it
  reasoning). Featherless accepted one cost-4 request at a time.
- Open risk: a UI turn streamed `reasoning_content` for several minutes (~600 KB) before any content. The
  per-read timeout (`IFIC_LLM_TIMEOUT_SECONDS`) does not fire while chunks keep arriving, and nothing caps a turn's
  wall-clock time, so one long answer blocks every other user (429) until it ends or the user presses Stop.
- While this work was in progress, someone else's concurrent edit removed the "Risk-informed screening" badge from
  the notice sheet header. It was left as found.
