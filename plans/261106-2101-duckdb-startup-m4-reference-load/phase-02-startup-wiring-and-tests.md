---
phase: 2
title: Startup wiring, health, tests
status: completed
depends_on: [1]
---

# Phase 02: Startup wiring, health, tests

## Context

Phase 01 provides `ific.db.connect` and `ific.m4.ensure_m4`. Read `backend/src/ific/api.py` and `backend/tests/test_api.py`.

## Files

| File | Action |
|---|---|
| `backend/src/ific/api.py` | Add a lifespan that opens the DB, runs `ensure_m4`, stores the connection on `app.state.db` and closes it on shutdown. Add a `get_db` dependency that yields `app.state.db.cursor()`. Extend `/api/health`. |
| `backend/src/ific/cli.py` | Configure `logging.basicConfig(level=INFO)` in `serve` so the loader lines show up next to uvicorn's. |
| `backend/tests/conftest.py` | **New.** A fixture that points `settings.db_dir` at `tmp_path` and yields a `TestClient` used as a context manager, so the lifespan runs. |
| `backend/tests/test_api.py` | Update to use the fixture. Assert the health payload. |

## Steps

1. In the lifespan: `con = db.connect(settings.db_path)`, then `statuses = m4.ensure_m4(con, settings)`, then `app.state.db = con`
   and `app.state.ref_status = statuses`, then `yield`, then `con.close()` in a `finally` block. Any exception propagates, so
   uvicorn exits non-zero with the error.
2. `/api/health` returns `{"status": "ok", "version", "db": {"path", "m4_edition", "tables": {"m4_allocation": n,
   "m4_page": n}}}`. The counts come from `ref.source` and not from `COUNT(*)`, so health stays O(1). The existing
   `status` and `version` keys stay unchanged.
3. Tests must never create `var/db` in the repo. The fixture overrides `db_dir` before the app starts.

## Tests

- Health on a fresh tmp DB returns 200, `db.tables.m4_allocation == 5917` and `m4_edition == "4 AG/2026M"`.
- Restarting the app on the same tmp DB (two `TestClient` contexts) gives `ref_status` all `up_to_date` the second time.
- When `data_dir` points at an empty tmp dir, entering the `TestClient` context raises `FileNotFoundError`.

## Validation

```bash
mise run lint
mise run test
rm -rf var/db && mise run api   # manual: watch the load log, curl localhost:8000/api/health, restart → "up to date"
```

## Rollback

Revert `api.py`, `cli.py` and the tests. Phase 01 modules stay unused, which does no harm.
