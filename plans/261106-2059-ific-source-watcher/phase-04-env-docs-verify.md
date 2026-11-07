---
phase: 4
title: Env example, gitignore, docs, end-to-end verification
status: completed
depends_on: [1, 2, 3]
---

# Phase 04 — Env example, gitignore, docs, end-to-end verification

## Files

| Action | Path |
|---|---|
| create | `.env.example` (repo root) |
| modify | `.gitignore` (add `!.env.example` and `data/ific/`) |
| create or modify | `README.md` or the owning docs page: a "Source watcher" section with env vars, the toggle rule and disk-usage note |

## `.env.example`

```
# ITU Space IFIC source watcher
IFIC_WATCHER_ENABLED=true            # master switch; false locks the UI toggle off
IFIC_WATCHER_INTERVAL_SECONDS=3600   # min 60
IFIC_WATCHER_SOURCE_URL=https://www.itu.int/sns/wic/demowic.html
IFIC_WATCHER_DOWNLOAD_DIR=data/ific
IFIC_WATCHER_HTTP_TIMEOUT_SECONDS=60
IFIC_WATCHER_MAX_DOWNLOAD_BYTES=2000000000
```

Relative paths resolve against `PROJECT_ROOT`; the validator for this is added in phase 01.

## End-to-end verification (one deliberate live run)

1. `mise run lint && mise run test && mise run build`.
2. Run `IFIC_WATCHER_INTERVAL_SECONDS=60 mise run dev` and open the UI. The first run discovers about 25 issues from 2026 and starts downloading them one at a time.
   - **Note:** this run downloads about 475 MB of zips and extracts 3–7 GB of `.mdb` files. Confirm with the user before starting it.
3. After the downloads finish, confirm that `data/ific/3083/ific3083.mdb` exists, that its size matches the local `ific3083.mdb` (112 MB), and that no `*.part` or `*.zip` files remain.
4. Press Check now. The run reports `new_count=0` and makes no zip requests (check the logs).
5. Pause in the UI and restart the API. The UI still shows paused, and the logs show no scheduled run.
6. Set `IFIC_WATCHER_ENABLED=false` and restart. The UI shows "Disabled by environment", the toggle is locked, and `curl -X PATCH` returns 409.
7. Stop the dev servers you started. The process-management rule says to leave no orphans.

## Risk / rollback

The docs and config changes here are additive and easy to roll back. The live run in step 2 is the only step with external side effects (network traffic and disk use).
