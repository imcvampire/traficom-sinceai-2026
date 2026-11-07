# LLM provider settings (Featherless)

Added `IFIC_LLM_API_KEY`, `IFIC_LLM_BASE_URL` (default `https://api.featherless.ai/v1`), `IFIC_LLM_MODEL` and
`IFIC_LLM_TIMEOUT_SECONDS` to `backend/src/ific/config.py`, `.env.example` and the README configuration section.

- The key is a `SecretStr`, so it stays masked in reprs and logs. Blank values in `.env` count as unset.
- Featherless serves an OpenAI-compatible API, so a client can be any OpenAI-style SDK or plain `httpx` pointed at the
  base URL. No client code exists yet, because nothing in the app calls an LLM.
- Model chosen: `moonshotai/Kimi-K3.1-Pro`, set in `.env.example` and the local `.env`. It is the top open-weights
  model on Artificial Analysis (Nov 2026). On Featherless it has a 262k context and concurrency cost 4, at $2 in /
  $10 out per 1M tokens. The code default stays `None`, so the choice lives in the env, not in the code.
