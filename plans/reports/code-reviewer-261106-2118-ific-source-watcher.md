# Code review: ITU Space IFIC source watcher

## Code Review Summary

### Scope
- Files reviewed: `backend/src/ific/{config,api,cli}.py`, `backend/src/ific/watcher/{source,store,download,service}.py`, `backend/tests/{conftest,watcher_fakes,test_watcher_source,test_watcher_store,test_watcher_download,test_watcher_api}.py`, `frontend/src/watcher/{api.ts,WatcherPanel.tsx}`, `frontend/src/App.tsx`, `.env.example`, `.gitignore`, `docs/source-watcher.md`
- Lines analysed: about 2,000
- Review focus: the uncommitted watcher feature, checked against `plans/261106-2059-ific-source-watcher/plan.md` and phases 02–03
- Updated plans: none. The caller asked for a read-only review, so plan statuses (all still `pending`) were not changed.

### Overall Assessment
The implementation is solid. The zip-slip, symlink and zip-bomb defences are correct (CPython's `ZipExtFile` truncates output to the declared `file_size`, so the sum check at `download.py:51` really does bound the output). The single-flight lock, flock and `.part` handling work for the common paths. `uv run pytest -q` gives 50 passed, and `bun run --cwd frontend lint` (oxlint) is clean.

There are two real correctness gaps:
1. A corrupt or encrypted zip aborts the whole check. This breaks acceptance criterion 4, and I reproduced the exceptions.
2. The scheduler task has no error boundary. One SQLite or OS error stops scheduling for good, with no visible signal.

The rest are Medium or Low.

### Critical Issues
None.

### High Priority Findings

**H1. A corrupt or encrypted zip aborts the whole run and hides the real reason (breaks AC4).**
- Where: `backend/src/ific/watcher/download.py:62-63` and `backend/src/ific/watcher/service.py:215-217`
- What goes wrong: `_extract_mdbs` converts only `zipfile.BadZipFile`. I reproduced the other cases in a scratch script:
  - A damaged deflate stream raises `zlib.error` ("Error -3 while decompressing data: invalid block type").
  - An encrypted member raises `RuntimeError` ("password required").
  - An unsupported method such as Deflate64 raises `NotImplementedError`.
  - A truncated member raises `EOFError`.
- Failure scenario: none of these is a `DownloadError`, so they fall through to `except BaseException` in `download.py:119`. Cleanup still runs there, which is good. They then reach `service.py:215`, which marks the file `failed` with the misleading error `"interrupted"` and re-raises. `check()` then records the whole run as `error`, and the remaining pending files in that run are never attempted. The same thing happens for any unexpected `Exception` in `download_and_extract`, such as a `ValueError` from a malformed URL.
- Fix:
  - In `_extract_mdbs`, use `except (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError) as e: raise DownloadError(f"bad zip: {e}") from e`.
  - In `_check`, split the handlers: `except Exception as e:` → `mark_failed(row.ific_no, f"{type(e).__name__}: {e}")`, `failed += 1`, `continue`. Keep `except BaseException:` only for cancellation and `KeyboardInterrupt` (mark `interrupted`, then re-raise).
  - Add a parametrised case with a corrupted deflate payload to `test_one_failure_does_not_block_other_files`.

**H2. The scheduler loop has no error boundary, so one error kills it silently. Shutdown then re-raises and skips closing DuckDB.**
- Where: `backend/src/ific/watcher/service.py:130-143` and `backend/src/ific/api.py:28-35`
- What goes wrong: several calls in `run_forever` sit outside `check()`'s `try`:
  - `reset_stale_downloading()`
  - `is_enabled()`, which hits SQLite
  - `_process_lock`'s `os.open`, e.g. on a permission error or a read-only `var/db`
  - `_finish()` → `record_run()`
  - `mark_failed()` inside an except block
  
  Any of them can raise, for example `sqlite3.OperationalError: database is locked` after the 30 s busy timeout while the CLI holds a write lock.
- Failure scenario:
  - The task dies, and nothing observes it.
  - The API keeps serving. `running` is false, and `next_run_at` is stuck at the last value, so the UI shows "Next check now" forever.
  - If `_manual_requested` was set, `running` stays `true` permanently and every `POST /api/watcher/check` returns 409.
  - At shutdown, `await watcher_task` re-raises the original exception, which `suppress(CancelledError)` does not catch, so `con.close()` at `api.py:35` never runs.
- Fix:
  - Wrap each loop iteration in `try: ... except Exception: log.exception("watcher loop iteration failed")`, so the loop survives and keeps waiting on the interval.
  - In the lifespan, use `with suppress(asyncio.CancelledError, Exception):` around the await, or close `con` in a nested `finally`.
  - Optionally add `watcher_task.add_done_callback(...)` to log an unexpected exit.

### Medium Priority Improvements

**M1. Cancelling during `asyncio.to_thread` extraction does not stop the thread, and cleanup races it.**
- Where: `backend/src/ific/watcher/download.py:103` and `download.py:119-121`
- What goes wrong: when shutdown or `--reload` cancels the task during extraction, the `await` returns at once but the worker thread keeps writing up to 273 MB. `_cleanup` then deletes `*.part` and the zip while the thread still holds them open.
- Failure scenarios:
  - If cleanup runs before the thread opens its `.part`, the thread creates and renames a complete `.mdb` after the row was marked `failed: interrupted`. That leaves an untracked file that the next run downloads again and overwrites.
  - If cleanup unlinks an open `.part`, the thread's `part.replace()` fails with an exception nobody sees.
  - In both cases uvicorn shutdown blocks until the thread finishes, because the default executor is joined.
- Fix: run the extraction as a task and, on cancel, wait for it before cleaning up:
  ```python
  fut = asyncio.ensure_future(asyncio.to_thread(_extract_mdbs, zip_path, dest, max_bytes))
  try:
      mdb_paths = await asyncio.shield(fut)
  except asyncio.CancelledError:
      with suppress(Exception):
          await fut
      raise
  ```
  Alternatively, pass a `threading.Event` that the copy loop checks between chunks. That also makes shutdown faster.

**M2. Stale `downloading` rows are reset only when the API starts, and the reset does not take the flock.**
- Where: `backend/src/ific/watcher/service.py:131` and `backend/src/ific/watcher/store.py:212-217`
- Failure scenarios:
  - (a) The CLI `ific watch check` is killed with SIGKILL, or the machine sleeps or crashes during a CLI run, while the API keeps running. The row stays `downloading`. `pending_downloads()` excludes that status, so the file is never retried until the API restarts, and the UI shows it as downloading forever.
  - (b) The API starts while a CLI check is mid-download. The API resets the CLI's live row to `failed: interrupted by restart`, so the UI shows wrong status until the CLI finishes.
- Fix: call `reset_stale_downloading()` at the start of `_check`, after the flock is acquired. Holding the flock proves no other process is downloading. Then drop it from `run_forever`.

**M3. Error strings can leak absolute server paths through the API.**
- Where: `backend/src/ific/watcher/download.py:118`, `service.py:158` and `service.py:212`. They are exposed through `api.py:184` (`WatcherFileOut.error`) and `WatcherRunOut.error`.
- Failure scenario: an `OSError` message embeds the filename. For example, `OSError: [Errno 28] No space left on device: '/Users/qa/Projects/.../data/ific/3083/ific3083.zip.part'`, or a permission error on `var/db/watcher.lock`. The message is stored and served verbatim, and the UI displays it. This contradicts the plan's "never absolute paths" rule, which `_display_path` enforces only for `local_path`. The UI is localhost-only, so the impact is low, but it is a contract gap.
- Fix: route stored error text through a small sanitiser that replaces `str(PROJECT_ROOT)` and `str(settings.watcher_download_dir)` with relative forms. Or, for `OSError`, store `f"{type(e).__name__}: {e.strerror}"`.

**M4. The 409 "already running" check and the `running` flag do not see checks run by another process.**
- Where: `backend/src/ific/watcher/service.py:97-99` and `service.py:122-128`
- Failure scenario: while `ific watch check` is downloading 25 files, `GET /api/watcher` reports `running: false`, and `POST /api/watcher/check` returns 202. The API run then records a `skipped` run with the error "another process is running a check". That run becomes `last_run`, so the panel shows "Last error: another process…" and an outcome of `skipped`. The scheduled tick does the same once an hour.
- AC7 says 409 "while one is already running". That is met in-process only.
- Fix: add a cheap non-blocking flock probe, `_process_lock` acquire-and-release, to `running`/`request_check`. Also consider not recording `skipped` runs as `last_run`, or excluding them from the "Last error" display.

### Low Priority Suggestions

- **L1.** `service.py:118-120`: `set_ui_enabled(True)` always wakes the loop, so every `PATCH {"enabled": true}` runs a full check (three page requests to itu.int), even when the watcher was already enabled. Wake only on a transition from disabled to enabled.
- **L2.** `download.py:39` and `download.py:55`: the `.mdb` keeps the zip member's name. AC3 and phase 02 require `ific<no>.mdb`. That matches only if ITU names the member that way. A member like `IFIC3083.MDB` or `SRS_3083.mdb` would miss the contract. Also, only `mdb_paths[0]` is stored (`service.py:223`), while `size_bytes` sums all members. Either rename a single member to `ific<no>.mdb` or document the behaviour.
- **L3.** `download.py:66-69`: on failure, `.mdb` files already extracted in a multi-member zip are kept, and an empty `data/ific/<no>/` directory is left behind. This is harmless but untidy.
- **L4.** `source.py:109`: `zip_url` is taken from the scraped page with no scheme or host check, and it is then fetched and rendered as an `<a href>`. React 19 blocks `javascript:` URLs, and httpx rejects non-HTTP schemes, so the risk is low. Still, restricting the URL to `https` on the source host is cheap.
- **L5.** `WatcherPanel.tsx:79-90` and `WatcherPanel.tsx:112-126`:
  - Overlapping `refresh()` calls (interval, visibility change and post-action) are not sequenced, so an older response can overwrite a newer one.
  - A poll that is in flight when the user toggles can briefly flip the switch back after the optimistic update.
  
  A request counter or `AbortController` that ignores stale responses fixes both.
- **L6.** Sync `sqlite3` calls with `timeout=30` run on the event loop: in `state()`, `is_enabled()` and all `mark_*` calls. A write lock held by the CLI could stall every API request for up to 30 s. In practice writes are tiny, so this is acceptable. If it shows up, move them to `asyncio.to_thread` or lower the timeout.
- **L7.** In January, a new `demowicYY.html` with no rows yet raises `SourceLayoutError` on every run until the first issue is posted. The plan intends this, but it will look like an outage. See the questions below.

### Positive Observations
- The zip handling is careful:
  - Names are flattened to the basename, and duplicate basenames are rejected.
  - Symlinks are rejected via `external_attr`.
  - The declared-size cap bounds decompression.
  - Writes go through `.part`, then `replace`.
  - Size is checked against `Content-Length`, with a correct exception for `content-encoding`.
- `check()` is single-flight in-process, and the flock correctly records `skipped` across processes. The lock fd is always closed.
- The effective-enabled and locked rules exactly match the plan. PATCH and check return 409 while locked, and the CLI exits with code 2.
- The tests are hermetic (`MockTransport`, `tmp_path`, env disabled by default in `conftest.py`). They cover idempotency, retry, zip-slip, size mismatch, ETag, pause mid-run, cross-process skip and persistence across restarts.
- `_display_path` keeps `local_path` relative. `.gitignore` correctly adds `!.env.example` and `data/ific/`.

### Recommended Actions
1. Fix H1: widen the extraction exception mapping, and make the per-file handler catch `Exception`. Add a corrupt-deflate test.
2. Fix H2: add a per-iteration `try/except` in `run_forever`, and make the lifespan's `con.close()` unconditional.
3. Fix M2: move `reset_stale_downloading()` inside the flock at the start of `_check`.
4. Fix M1: wait for the extraction thread on cancellation.
5. Fix M3: sanitise stored error text.
6. Fix M4: probe the flock for `running` and for the 409 check.
7. Then address L1, L2 and L5. Mark phases 01–03 done in the plan once H1 and H2 land.

### Metrics
- Type coverage: fully annotated Python and TS. mypy/pyright was not run separately, beyond what `mise run lint` covers.
- Tests: `uv run pytest -q` gives 50 passed in 4.4 s, with no network.
- Linting: oxlint reports 0 issues.

### Unresolved Questions
1. If the newest year page exists but is still empty (early January), should the run fall back to the next page instead of failing with `SourceLayoutError`?
2. Should `ific watch check` respect the UI pause, or is it meant to override it like "Check now"? It currently ignores the pause.
3. Is the real member name inside the ITU zips always `ific<no>.mdb`? AC3 depends on it (L2).
