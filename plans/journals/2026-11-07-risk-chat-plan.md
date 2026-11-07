# Risk chat plan

Planned an LLM chat panel for `/risk` in `plans/261107-1208-risk-chat/`. It has not been implemented yet.

- The chosen design builds the context on the server and makes one streamed chat completion per turn, with no
  tools. The user turned down tool calling and an MCP server, wants no auth, and deferred conversation history.
- The browser sends the filtered `ntc_id`s rather than the filter params. Filtering runs client-side in
  `risk-table.tsx`, and copying that logic to the server would drift.
- Payloads measured on IFIC 3083: a notice detail is ~47 KB, the list ~100 KB and the method doc ~32 KB, so
  everything fits Kimi K3.1 Pro's 262k context. The `risk_curves` arrays are dropped from the context because an
  LLM can't read them usefully.
- `backend/tests/conftest.py` must switch the LLM off. Settings load the root `.env`, which holds the real
  Featherless key, so without that the tests would call the paid API.
- The user confirmed three things: the full method doc goes in the context, notice-scope chat is a column in the
  notice sheet, and at most one answer streams at a time.
