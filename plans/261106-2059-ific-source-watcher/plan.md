---
title: ITU Space IFIC source watcher (scheduled check + download, UI/env toggle)
status: completed
created: 2026-11-06
mode: auto (standard)
branch: main
blockedBy: []
---

# ITU Space IFIC source watcher

## Outcome

A background job inside the FastAPI process checks the ITU Space IFIC portal on a configurable interval
(default 1 h) for newly published IFIC databases. It downloads each new zip and extracts the `.mdb` into
`data/ific/<ific_no>/`. A UI panel shows watcher status, a toggle, a "check now" action and the discovered
files. The env flag is the master switch, and the UI can pause or resume the watcher only while env allows it.

## Scope change vs. accepted brainstorm

`plans/reports/brainstorm-261106-2029-ific-interference-analyser.md` listed "automatic fetching or scraping of
IFICs from the ITU portal" as a **non-goal**. The user explicitly requested this feature on 2026-11-06, so that
non-goal no longer applies to the Space IFIC source page. The terrestrial BR IFIC source and auto-ingest stay out of scope.

## Evidence (fetched 2026-11-06)

| Fact | Consequence |
|---|---|
| `https://www.itu.int/sns/wic/demowic.html` lists only **year links** (`demowic98.html` … `demowic26.html`). The page's `Last-Modified` is 23 Dec 2025. | Watching the root page alone never sees a new IFIC. The watcher must follow the root page to the newest year page and then read that page's rows. |
| `demowic26.html` has one row per issue: `<b>27.10.2026</b>` + `<a href="../ific10/ific3083.zip">3083</a>`. It lists 25 rows for 2025. | Parse with stdlib `html.parser` and key each row on the IFIC number, taken from the zip href. The publication date is `DD.MM.YYYY`. |
| `ific3083.zip`: 19 MB, with `ETag`, `Last-Modified` and `Content-Length` headers. Year pages send `ETag` too. | Use conditional GET (`If-None-Match`) on the pages and check the downloaded size against `Content-Length`. |
| Extracted Space `.mdb` files are 112–273 MB. | Treating every current-year issue as new on the first run means about 25 files, or **3–7 GB** in `data/ific/`. Disk has 328 GB free. Zips are deleted after a verified extraction. |
| Dev dependency `httpx2==2.16.0` (import `httpx2`, has `AsyncClient`) is already locked. | Promote it to a runtime dependency. There is no new HTTP library. |
| `Settings` uses `env_file=".env"` relative to the CWD. `mise run api` runs in `backend/`. | Point `env_file` at `PROJECT_ROOT / ".env"` so a single root `.env` works for both the CLI and the API. |
| `.gitignore` has `.env.*`, which would also ignore `.env.example`, and it has no rule for `data/ific/`. | Add `!.env.example` and `data/ific/`. |

## User decisions (2026-11-06)

1. **On a new file:** detect it, download it into this repo under `data/ific/`, and extract the `.mdb`. Do not auto-ingest.
2. **Toggle rule:** `IFIC_WATCHER_ENABLED` is the master switch. When it is `false`, the watcher is off and the UI toggle is locked. When it is `true`, the UI can pause or resume the watcher, and that choice is persisted across restarts.
3. **First run:** treat every issue on the newest year page as new and download all of them.

## Effective-enabled rule

```
effective = env.IFIC_WATCHER_ENABLED and (ui_override is None or ui_override)
locked    = not env.IFIC_WATCHER_ENABLED
```

`PATCH /api/watcher` returns **409** while `locked`.

## Architecture

```
FastAPI lifespan ──► WatcherService.run_forever()  (asyncio task, single-flight lock + cross-process flock)
                          │ every IFIC_WATCHER_INTERVAL_SECONDS, or woken by toggle/"check now"
                          ▼
   source.py: fetch root ─► newest demowicYY.html ─► parse rows → [IficListing(no, published_on, zip_url)]
                          ▼
   store.py (SQLite var/db/watcher.sqlite3): upsert listings; new|failed → download queue
                          ▼
   download.py: stream → data/ific/<no>/ific<no>.zip.part → verify size → unzip .mdb (zip-slip safe) → delete zip
                          ▼
   api.py: GET/PATCH /api/watcher · POST /api/watcher/check · GET /api/watcher/files
                          ▼
   frontend WatcherPanel: status, toggle (locked state), check now, files table (polls 15 s)
```

**Why SQLite for watcher state, not DuckDB:** the state is small OLTP rows written by the API process and
read by the CLI (`ific watch check`). DuckDB takes an exclusive file lock per writer process, which would
conflict with the analysis databases' access pattern. SQLite is stdlib and safe across processes.

**Why an asyncio loop, not APScheduler:** there is one job on a fixed interval. The loop is about 20 lines and adds no
dependency. Run it single-process (`uvicorn` without `--workers`). A `fcntl.flock` on `var/db/watcher.lock` makes
a second process skip the run instead of duplicating downloads.

## Phases

| # | Phase | Status | Depends on |
|---|---|---|---|
| 01 | [Config, state store, source parser](phase-01-config-store-parser.md) | completed | — |
| 02 | [Downloader, watcher service, scheduler, API, CLI](phase-02-service-scheduler-api.md) | completed | 01 |
| 03 | [Frontend watcher panel](phase-03-frontend-panel.md) | completed | 02 (API contract) |
| 04 | [Env example, gitignore, docs, end-to-end verification](phase-04-env-docs-verify.md) | completed | 01–03 |

## Acceptance criteria

1. With `IFIC_WATCHER_ENABLED=true`, starting the API schedules a check immediately and then every `IFIC_WATCHER_INTERVAL_SECONDS` (default `3600`, minimum `60`).
2. A check follows the root page to the newest year page and records every listed IFIC (number, publication date, URL). Parser tests run against saved fixtures of `demowic.html` and `demowic26.html`.
3. Each issue with status `new` or `failed` is downloaded one at a time. The `.mdb` ends up at `data/ific/<no>/ific<no>.mdb` and the zip is deleted. A re-run downloads nothing (idempotent).
4. Each failure (HTTP error, size mismatch, bad zip, zip-slip path) marks only that file as `failed` with an error message. The other files continue, and the next run retries it. A partial `.part` file never counts as downloaded.
5. With `IFIC_WATCHER_ENABLED=false`, no check runs, `GET /api/watcher` reports `locked: true`, and `PATCH` returns 409.
6. With env `true`, the UI toggle pauses and resumes the watcher. The choice survives an API restart. Resuming triggers a check without waiting for the full interval.
7. `POST /api/watcher/check` starts a check (202), or returns 409 while one is already running or the watcher is locked.
8. The UI panel shows: effective state with its source (env-locked, UI-paused or active), interval, last/next check, last error, and the files table with status, size and date.
9. `ific watch check` runs one check from the CLI and shares state with the API.
10. `mise run lint`, `mise run test` and `mise run build` pass. The tests never reach the network.

## Risks

| Risk | Mitigation |
|---|---|
| ITU changes the HTML layout | Rows are parsed on the `ificNNNN.zip` href only, which is a stable artefact. If the newest year page has zero parsed rows, the run fails with a parser error instead of reporting "nothing new". |
| Year rollover: an issue posted on last year's page after the new year page appears | Always scan the **two** newest year pages. A listing counts as new only if it is not in the store **and** its IFIC number is above the lowest number already stored. IFIC numbers increase monotonically, so last year's backlog is never pulled in. On the first run (empty store), only the newest page's rows count, per decision 3. |
| `--reload` restarts the process mid-download | Downloads write `.part` files first and the status goes back to `failed`. Stale `downloading` rows are reset to `failed` on startup. |
| Disk usage (3–7 GB on the first run) | Zips are deleted after extraction. Sizes are shown in the UI. `data/ific/` is gitignored. |
| Politeness toward itu.int | One request at a time, conditional GET on pages, a descriptive `User-Agent`, and the interval floor of 60 s. |

## Focus note (2026-11-06)

The watcher focuses on the Space IFIC source (`demowic.html`) for now. Watching the terrestrial BR IFIC page is
deferred and not part of this plan. If it is picked up later, a second source parser can feed the same store.

## Delivery notes (2026-11-06)

- The live run downloaded 3 of the 22 issues for 2026 (3083, 3082 and 3081) into a scratch directory, and then the watcher was paused through the API. `ific3083.mdb` is byte-identical to the local reference copy. The full 3–7 GB first run into `data/ific/` was not started, because it needs the user's go-ahead.
- Review fixes that changed behaviour:
  - Any per-file exception now marks only that file as failed.
  - The scheduler loop survives errors in a single iteration.
  - Stale `downloading` rows are reset under the file lock at the start of each check.
  - `running` and the 409 response from Check now also detect a check run by another process.
  - A single `.mdb` member is saved as `ific<no>.mdb`.
  - An empty newest year page falls back to the year before it.
- The UI panel passes lint and build. It has not been checked visually in a browser.
