---
phase: 3
title: Frontend watcher panel
status: completed
depends_on: [2]
---

# Phase 03 — Frontend watcher panel

## Context

`frontend/src/App.tsx` is a single 28-line component that calls `fetch('/api/health')`. Vite proxies `/api` to `:8000`.
The project has no router, no data library and no UI kit, so this phase does not add any. It uses plain `fetch` and React state, which matches the current code.

## Files

| Action | Path |
|---|---|
| create | `frontend/src/watcher/api.ts` (typed `getWatcher`, `setWatcherEnabled`, `checkNow`, `listFiles`) |
| create | `frontend/src/watcher/WatcherPanel.tsx` |
| modify | `frontend/src/App.tsx` (render `<WatcherPanel />` under the health line) |
| modify | `frontend/src/index.css` (panel, toggle, status badge and table styles) |

## Behaviour

- Poll `GET /api/watcher` and `/api/watcher/files` every 15 s, and right after any action. Pause polling while `document.hidden`.
- The status line shows one of three states:
  - **Active**, with "next check in Xm".
  - **Paused (UI)**.
  - **Disabled by environment** (`locked`), with the hint "set `IFIC_WATCHER_ENABLED=true`".
- The line also shows the interval, the last check time and outcome, and the last error in a muted alert.
- The toggle is a `<input type="checkbox" role="switch">` with a label. It is disabled when `locked`, with a `title` that explains why. The toggle is optimistic and rolls back if the request fails.
- The **Check now** button is disabled while `running` or `locked`. A 409 shows "Check already running".
- The files table has the columns IFIC no., Published, Status (badge: new / downloading / downloaded / failed + error tooltip), Size and Local path, sorted newest first.
- Show empty, loading and API-unreachable states explicitly.

## Validation

```
bun run --cwd frontend lint
bun run --cwd frontend build
```

Then run a manual smoke test against `mise run dev`. Toggle pause and resume and confirm the state persists after an API restart. Press Check now and confirm the status changes to running and then to done.

## Risk / rollback

The UI change is additive. Rollback removes `src/watcher/` and the single `App.tsx` line.
