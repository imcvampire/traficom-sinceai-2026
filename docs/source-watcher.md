# ITU Space IFIC source watcher

The API process runs a background job that checks the ITU Space IFIC download page for newly published
IFIC databases. It downloads each new zip and extracts the `.mdb` file to `data/ific/<ific_no>/`. After that
it fetches the terrestrial BR IFIC extracts into `data/brific/<no>/brific<no>.mdb`. The terrestrial BR IFIC is a
separate publication that uses the same issue numbers and dates, so their numbers come from the Space listing
(see [Terrestrial BR IFIC extracts](#terrestrial-br-ific-extracts)). It does **not** ingest either kind into
DuckDB.

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

5. It then runs the terrestrial check described below.

Pages are fetched with `If-None-Match`. Only one check runs at a time, guarded by an in-process lock plus
`flock` on `var/db/watcher.lock`. A check started while another process holds the lock is recorded as
`skipped`, and the API reports `running: true` and answers Check now with 409 while the CLI holds it.

## Terrestrial BR IFIC extracts

The terrestrial BR IFIC uses the same issue numbers as the Space IFIC, so the watcher derives its list from the
Space issues it already knows. It never scrapes the terrestrial page, which sits behind a web firewall, lists only
10 issues and pages through a JavaScript postback.

1. Every Space issue in the store with a `published_on` within the last 365 days gets a row in `brific_files`
   (same columns as `ific_files`), with its URL from `IFIC_TERRA_SOURCE_URL_TEMPLATE`.
2. Those rows are fetched one at a time, newest first. Each zip holds one `brific<no>.mdb`, extracted with the
   same checks as a Space zip.
3. A row that already has a file is asked again with `If-None-Match` and `If-Modified-Since` from its stored
   ETag and Last-Modified. A 304 leaves it as it is, and a 200 replaces the file.
4. A 404 means "not published yet": the row stays `new`, its `attempts` is not incremented, and the run does not
   count it as failed. Any other failure, such as a bad zip, marks only that row `failed`.

Terrestrial downloads share the lock, the pause switch and the interval with the Space check. A run's
`downloaded_count` and `failed_count` cover both kinds, while `new_count` counts new Space issues only. Set
`IFIC_TERRA_WATCHER_ENABLED=false` to skip the terrestrial check.

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
| `IFIC_TERRA_WATCHER_ENABLED` | `true` | Terrestrial BR IFIC downloads; needs the master switch on too |
| `IFIC_TERRA_DOWNLOAD_DIR` | `data/brific` | Relative paths resolve against the repo root; gitignored |
| `IFIC_TERRA_SOURCE_URL_TEMPLATE` | `https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific{no}.zip` | `{no}` is the issue number |
| `IFIC_TERRA_SOURCE_PAGE_URL` | `https://www.itu.int/en/ITU-R/terrestrial/brific/Pages/default.aspx` | Terrestrial BR IFIC page linked from the watcher panel; never fetched |

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
| `GET` | `/api/watcher` | State: `enabled`, `locked`, `ui_enabled`, `interval_seconds`, `running`, `terrestrial_enabled`, `last_run`, `next_run_at` |
| `PATCH` | `/api/watcher` | Body `{"enabled": bool}`. Returns 409 when locked |
| `POST` | `/api/watcher/check` | Returns 202, or 409 when locked or a check is already running |
| `GET` | `/api/watcher/files?kind=space\|terrestrial` | Discovered issues of that kind (default `space`), newest first. `local_path` is relative, never absolute |

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
- **Schema:** the state DB is at schema v2. Opening a v1 store only adds the `brific_files` table; copy
  `var/db/watcher.sqlite3` to `watcher.sqlite3.bak-<date>` before the first run of a new version anyway.
- **Reset:** stop the API, then delete `var/db/watcher.sqlite3` and, optionally, `data/ific/` and
  `data/brific/`. The next run becomes a first run.
