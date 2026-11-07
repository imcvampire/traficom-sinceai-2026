---
title: IFIC source watcher
date: 2026-11-06
summary: An asyncio watcher in the FastAPI lifespan polls the ITU IFIC demo pages, records issues in SQLite and downloads and extracts .mdb files one at a time.
---

# IFIC source watcher

**Date**: 2026-11-06 21:32 (Europe/Helsinki)
**Component**: backend watcher, CLI, UI panel

## What happened
Implemented plan `plans/261106-2059-ific-source-watcher` (all 4 phases). An asyncio loop in the FastAPI lifespan polls
`https://www.itu.int/sns/wic/demowic.html` and follows the 2 newest year pages. It records issues in `var/db/watcher.sqlite3`
and downloads and extracts the `.mdb` files to `data/ific/<no>/` one at a time. Also shipped: a UI panel (toggle, Check now,
files table), `ific watch check`, `.env.example` entries and `docs/source-watcher.md`.

## Decisions
- Watcher state lives in SQLite, not DuckDB. DuckDB allows one writer per process, and the watcher and CLI would compete for that lock.
- A plain asyncio loop instead of APScheduler. One periodic job did not justify adding a dependency.
- `fcntl.flock` provides single-flight across processes, so an API run and a CLI check cannot download at the same time.
- `IFIC_WATCHER_ENABLED` in the environment is the master switch. The UI pause is stored separately in SQLite. The CLI also
  respects the env switch and exits with code 2 when it is off.

## Findings
Code review found two real bugs, and we should have caught both earlier:
- H1: a corrupt or encrypted zip raised `zlib.error`/`RuntimeError` and aborted the whole run, not just that one issue.
- H2: the scheduler task had no error boundary. One exception would kill it silently, and the watcher would stop with no log line.

Smaller problems: cancellation raced the `to_thread` extraction, the stale-row reset ran outside the lock, `OSError` text
leaked absolute paths to the client, and `running` did not reflect checks started from the CLI. All of these were fixed with
regression tests, and the 57 tests pass. The lesson: any background task needs a top-level try/except and a log line from the first commit.

Live smoke test: 3 real issues downloaded, and `ific3083.mdb` is byte-identical to the reference. Pausing mid-run worked, and
the pause survived a restart with zero ITU requests.

## Next steps
- The full first run (3–7 GB) has not been run, so disk use, duration and resume behaviour at that size are unproven.
- Nobody has looked at the UI panel in a browser yet.
- Synchronous sqlite calls on the event loop are accepted for now. Move them to `to_thread` if latency shows up.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

**Status**: Implemented and tested. Full first run and the visual UI check are still pending.
