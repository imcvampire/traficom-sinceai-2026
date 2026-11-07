---
phase: 6
title: "Terrestrial watcher source"
status: done
priority: P3
effort: "3h"
dependencies: [1]
---

# Phase 6: Terrestrial watcher source

## Goal

The existing watcher also downloads terrestrial MDB extracts into `data/brific/<no>/brific<no>.mdb`. It derives
the issue numbers from the Space listing it already parses, and it never scrapes the terrestrial SharePoint page.
It downloads only and does not ingest.

## Evidence

- Asking for `https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific<no>.zip` with the watcher
  User-Agent gave 200 and a zip with ETag and Last-Modified headers. This held for 3074 (2.8 MB), 3077 (3.1 MB)
  and 3078 (3.5 MB). Each zip holds one `brific<no>.mdb`.
- A plain `curl` of the terrestrial HTML page was rejected by the web firewall. The page lists only 10 issues and
  pages through a JavaScript postback.

## Files

- Modify: `backend/src/ific/watcher/store.py`. Add the `brific_files` table, with the same columns as
  `ific_files`. Parameterise the file methods by a `kind: Literal["space", "terrestrial"]` that selects the
  table. `SCHEMA_VERSION` goes to 2, and the migration only creates the new table. **Back up
  `var/db/watcher.sqlite3` before the first run** (copy it to `watcher.sqlite3.bak-<date>`).
- Modify: `backend/src/ific/watcher/download.py`. Make the zip, extracted-name prefix and destination dir
  parameters (`"ific"`/`watcher_download_dir` or `"brific"`/`terra_download_dir`). Add an `If-None-Match` and
  `If-Modified-Since` request from the stored ETag and Last-Modified. A 304 means unchanged, and a 404 means "not
  published yet": status stays `new`, `attempts` is not incremented, and it is not an error.
- Modify: `backend/src/ific/watcher/service.py`. After the space check, run `_check_terrestrial()`: for every
  space issue number the store knows with `published_on` within the last 12 months, upsert a `brific_files`
  listing with the derived URL, then download pending rows one at a time. The interval floor and the lock are
  shared.
- Modify: `backend/src/ific/config.py`: `terra_watcher_enabled: bool = True`, and
  `terra_source_url_template: str = "https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific{no}.zip"`.
- Modify: `backend/src/ific/api.py`. `GET /api/watcher/files?kind=terrestrial` defaults to `space`, so the
  existing behaviour is unchanged.
- Modify: `frontend/src/components/watcher-controls.tsx`, `frontend/src/pages/sources.tsx` and
  `frontend/src/lib/api.ts`. Add a terrestrial files section that reuses `files-table.tsx`.
- Create or modify: `backend/tests/test_watcher_terra.py`, extending `watcher_fakes.py` with a 404 issue and a
  304 issue.

## Tests

- A run with fakes downloads two terrestrial issues to `.../brific/<no>/brific<no>.mdb`.
- A second run sends conditional headers, gets 304 and downloads nothing.
- A 404 issue stays `new` with `attempts` at 0.
- A bad zip marks only that file `failed`.
- The space watcher tests pass unchanged.
- No test touches itu.int.

## Validation

```sh
cd backend && uv run pytest tests/test_watcher_*.py -q
```

Live check, with the user's go-ahead: one manual check through `POST /api/watcher/check` fetches the 2026
terrestrial issues, about 22 × 3 MB.

## Risks

The issue numbers are shared with the Space IFIC, which holds for 3074–3083 by date. If a terrestrial issue is
ever skipped, its 404 stays pending and harms nothing.
