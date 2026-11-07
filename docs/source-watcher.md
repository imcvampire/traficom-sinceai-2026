# ITU Space IFIC source watcher

The API process runs a background job that checks the ITU Space IFIC download page for newly published
IFIC databases. It downloads each new zip and extracts the `.mdb` file to `data/ific/<ific_no>/`. It does
**not** ingest the files into DuckDB.

## How a check works

1. It fetches `IFIC_WATCHER_SOURCE_URL` (`demowic.html`). That page lists only year links, so the job follows
   it to the two newest year pages (`demowicYY.html`).
2. It parses each `ificNNNN.zip` row, taking the IFIC number from the href and the publication date
   (`DD.MM.YYYY`) from the same row. A year page with no zip rows is skipped, which covers the case of a new
   year page in early January before its first issue is posted. If neither page has rows, the run fails
   with `SourceLayoutError` instead of quietly reporting "nothing new".
3. It records new issues in `var/db/watcher.sqlite3`.
   - **First run** (the store is empty): every issue on the newest year page counts as new, which is about
     25 files and 3–7 GB of `.mdb` once extracted.
   - **Later runs:** an issue counts as new only if its number is higher than the lowest stored number, so
     an older year's backlog is never pulled in.
4. It downloads `new` and `failed` issues one at a time, newest first. Each zip is streamed to a `.part`
   file, checked against `Content-Length`, extracted (zip-slip and symlink members are rejected; a single
   `.mdb` member is saved as `ific<no>.mdb`), and then deleted. Any failure, including a corrupt or encrypted
   zip, marks only that issue `failed`, and the next run retries it. Stored error text never contains
   absolute paths.

Pages are fetched with `If-None-Match`. Only one check runs at a time, guarded by an in-process lock plus
`flock` on `var/db/watcher.lock`. A check started while another process holds the lock is recorded as
`skipped`, and the API reports `running: true` and answers Check now with 409 while the CLI holds it.

## Configuration

Copy `.env.example` to `.env` in the repository root. Both the API and the CLI read it, whatever the working
directory.

| Variable | Default | Notes |
|---|---|---|
| `IFIC_WATCHER_ENABLED` | `true` | Master switch, see below |
| `IFIC_WATCHER_INTERVAL_SECONDS` | `3600` | Minimum `60` |
| `IFIC_WATCHER_SOURCE_URL` | `https://www.itu.int/sns/wic/demowic.html` | |
| `IFIC_WATCHER_DOWNLOAD_DIR` | `data/ific` | Relative paths resolve against the repo root; gitignored |
| `IFIC_WATCHER_STATE_PATH` | `var/db/watcher.sqlite3` | |
| `IFIC_WATCHER_HTTP_TIMEOUT_SECONDS` | `60` | |
| `IFIC_WATCHER_MAX_DOWNLOAD_BYTES` | `2000000000` | Cap for one zip and for its extracted `.mdb` files |

## Enable, pause and lock

```
effective = IFIC_WATCHER_ENABLED and (ui_override is unset or ui_override)
locked    = not IFIC_WATCHER_ENABLED
```

- **`IFIC_WATCHER_ENABLED=false`:** the scheduler does not start, the UI shows "Disabled by environment"
  with the toggle locked, `PATCH /api/watcher` and `POST /api/watcher/check` return 409, and
  `ific watch check` exits with code 2.
- **`IFIC_WATCHER_ENABLED=true`:** the UI toggle pauses or resumes scheduled checks, and the choice is
  stored in the state DB so it survives restarts. Resuming a paused watcher triggers a check straight away.
  Pausing mid-run lets the file in flight finish and starts no new downloads. Check now and
  `ific watch check` still work while paused.

Run the API as a single process (`uvicorn` without `--workers`). A second process would not double-download
because of the file lock, but it would run its own scheduler.

## API

| Method | Path | Result |
|---|---|---|
| `GET` | `/api/watcher` | State: `enabled`, `locked`, `ui_enabled`, `interval_seconds`, `running`, `last_run`, `next_run_at` |
| `PATCH` | `/api/watcher` | Body `{"enabled": bool}`. Returns 409 when locked |
| `POST` | `/api/watcher/check` | Returns 202, or 409 when locked or a check is already running |
| `GET` | `/api/watcher/files` | Discovered issues, newest first. `local_path` is relative, never absolute |

## CLI

```
cd backend && uv run ific watch check
```

Runs one check and prints `outcome: new=… downloaded=… failed=…`. It exits with 1 if the run errored or any
download failed, and with 2 if the env switch is off.

## Operations

- **Logs** (`ific.watcher` logger): one line per run with `trigger`, `outcome`, counts and `duration_ms`,
  plus one warning for each failed file.
- **Restarts:** rows left in `downloading` by a killed process (an API `--reload` or a killed CLI) are reset
  to `failed` at the start of the next check, while it holds the lock, and are then retried.
- **Scheduler errors:** an unexpected error in one loop iteration (for example `database is locked`) is
  logged with its traceback and the loop carries on at the next interval.
- **Risk page:** every downloaded `data/ific/<no>/ific<no>.mdb` (and any `ific*.mdb` in the project root) appears in the
  issue picker of `/risk`; it is ingested into DuckDB when it is first assessed, not on download.
- **Reset:** stop the API, then delete `var/db/watcher.sqlite3` and, optionally, `data/ific/`. The next run
  becomes a first run.
