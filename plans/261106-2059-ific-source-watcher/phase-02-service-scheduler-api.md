---
phase: 2
title: Downloader, watcher service, scheduler, API, CLI
status: completed
depends_on: [1]
---

# Phase 02 — Downloader, watcher service, scheduler, API, CLI

## Files

| Action | Path |
|---|---|
| create | `backend/src/ific/watcher/download.py` |
| create | `backend/src/ific/watcher/service.py` |
| modify | `backend/src/ific/api.py` (lifespan + routes) |
| modify | `backend/src/ific/cli.py` (`watch` sub-app with a `check` command) |
| create | `backend/tests/test_watcher_download.py`, `backend/tests/test_watcher_api.py` |

## Steps

1. **`download.py`.** Implement `async download_and_extract(client, listing, dest_dir, max_bytes) -> DownloadResult`:
   - Stream the zip to `dest_dir/<no>/ific<no>.zip.part`, hashing with sha256 and enforcing `max_bytes` as it goes.
   - Check the byte count against `Content-Length` when that header is present, then rename `.part` to `.zip`.
   - Extract only `*.mdb` members. Reject absolute paths, `..` components and symlinks (zip-slip). Write to `ific<no>.mdb.part`, then rename.
   - Delete the zip after the rename succeeds. On any exception, remove the `.part` files and re-raise a `DownloadError(reason)`.
2. **`service.py`.** `WatcherService(settings, store, client_factory)` has these parts:
   - `effective_state() -> WatcherState(enabled, locked, ui_enabled, interval_seconds, running, last_run, next_run_at)`, using the rule in plan.md.
   - `async check(trigger)`: a single-flight `asyncio.Lock` plus a non-blocking `fcntl.flock` on `var/db/watcher.lock`. If the lock is busy, record a `skipped` run. Otherwise:
     1. GET the root page, then the two newest year pages, with `If-None-Match` from `kv`. A 304 reuses the stored listing state.
     2. Run `store.upsert_listings`.
     3. Download every row from `pending_downloads()` one at a time, newest first, updating the status per file.
     4. Record the run with `new_count` and any page-level error.
   - `async run_forever()`: call `reset_stale_downloading()` on start. Then loop: if `effective.enabled`, run `check('schedule')`; then wait with `asyncio.wait_for(self._wake.wait(), interval)`.
   - `set_ui_enabled(bool)` persists the value and sets `_wake` so that resuming checks immediately. `request_check()` sets `_wake` with a manual trigger flag.
   - The HTTP client is `httpx2.AsyncClient(timeout=…, follow_redirects=True, headers={"User-Agent": "ific-watcher/<version> (+Traficom hackathon)"})`.
   - Logging: write one structured `logger.info` line per run (`trigger`, `pages`, `new`, `downloaded`, `failed`, `duration_ms`) and a `logger.warning` per failed file.
3. **`api.py`.** In the `lifespan` context, build the service. If `settings.watcher_enabled`, start `run_forever()` as a task. Cancel the task on shutdown and await it, so `--reload` leaves no orphan.
   - `GET /api/watcher` returns `WatcherState`.
   - `PATCH /api/watcher {"enabled": bool}` returns 409 if `locked`. Otherwise it persists the value and returns the new state.
   - `POST /api/watcher/check` returns 202 `{"accepted": true}`, or 409 when `locked` or already running. A UI pause only stops the schedule, so a manual check still works while paused.
   - `GET /api/watcher/files` returns the rows newest first. It exposes `mdb_path` relative to the project root and never absolute paths.
4. **`cli.py`.** `ific watch check` runs `asyncio.run(service.check('cli'))`, prints a summary, and exits non-zero if the run errored.

## Tests (no network)

Use `httpx2.MockTransport` as the client factory, a `tmp_path` store and a `tmp_path` download dir.

- `test_check_downloads_new_and_is_idempotent`: two calls, and the second makes no download request.
- `test_size_mismatch_marks_failed_and_leaves_no_part_file`
- `test_zip_slip_member_rejected`
- `test_one_failure_does_not_block_other_files`
- `test_page_304_uses_etag`
- API tests with `TestClient` and the service patched to the mock transport:
  - `test_env_disabled_locks_patch_409`
  - `test_patch_pause_persists_across_new_service_instance`
  - `test_check_now_409_while_running`

## Validation

```
cd backend && uv run pytest -q tests/test_watcher_download.py tests/test_watcher_api.py
uv run pytest -q   # the backend suite is still small; shared api.py changed
```

## Risk / rollback

`api.py` gets a lifespan, so the existing `test_health` must still pass. Tests that do not exercise the watcher set
`IFIC_WATCHER_ENABLED=false` through a fixture, so they never start the loop.
