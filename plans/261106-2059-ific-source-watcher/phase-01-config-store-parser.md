---
phase: 1
title: Config, state store, source parser
status: completed
depends_on: []
---

# Phase 01 — Config, state store, source parser

## Context

- `backend/src/ific/config.py` has a `pydantic-settings` `Settings` with the `IFIC_` prefix.
- Evidence and decisions are recorded in [plan.md](plan.md).

## Files

| Action | Path |
|---|---|
| modify | `backend/src/ific/config.py` |
| modify | `backend/pyproject.toml` (move `httpx2` from the `dev` group to `dependencies`; then `uv lock`) |
| create | `backend/src/ific/watcher/__init__.py` |
| create | `backend/src/ific/watcher/source.py` |
| create | `backend/src/ific/watcher/store.py` |
| create | `backend/tests/fixtures/itu/demowic.html`, `demowic26.html`, `demowic25.html` (trimmed real pages) |
| create | `backend/tests/test_watcher_source.py`, `backend/tests/test_watcher_store.py` |

## Steps

1. **Settings.** Set `env_file=PROJECT_ROOT / ".env"` and add the following fields:
   - `watcher_enabled: bool = True`
   - `watcher_interval_seconds: int = Field(3600, ge=60)`
   - `watcher_source_url: HttpUrl = "https://www.itu.int/sns/wic/demowic.html"`
   - `watcher_download_dir: Path = PROJECT_ROOT / "data" / "ific"`
   - `watcher_state_path: Path = PROJECT_ROOT / "var" / "db" / "watcher.sqlite3"`
   - `watcher_http_timeout_seconds: float = 60.0`
   - `watcher_max_download_bytes: int = 2_000_000_000` (guards against an unexpected or huge response)
   - Add a validator that resolves relative `watcher_download_dir` and `watcher_state_path` against `PROJECT_ROOT`, so `IFIC_WATCHER_DOWNLOAD_DIR=data/ific` works from any CWD.
2. **`source.py`.** Keep it pure and free of I/O:
   - `parse_year_links(html, base_url) -> list[YearPage(year, url)]` matches `demowic(\d{2})\.html`, maps `98/99` to the 1900s and the rest to the 2000s, and sorts newest first.
   - `parse_listings(html, page_url) -> list[IficListing(ific_no: int, published_on: date | None, zip_url: str)]` walks `<tr>` rows with `html.parser`. It takes the zip href matching `ific(\d+)\.zip`, resolves it with `urljoin` and the date from `DD.MM.YYYY` in the same row.
   - A page that has year links but **zero** listings raises `SourceLayoutError`, so the run is never reported as a quiet "nothing new".
3. **`store.py`.** Add a thin SQLite wrapper (stdlib `sqlite3`, WAL mode, one connection per call site):
   - `ific_files(ific_no PK, published_on, zip_url, status CHECK IN ('new','downloading','downloaded','failed'), size_bytes, etag, last_modified, sha256, mdb_path, error, attempts, discovered_at, downloaded_at)`
   - `watcher_runs(id PK, started_at, finished_at, trigger CHECK IN ('schedule','manual','cli'), outcome CHECK IN ('ok','error','skipped'), new_count, error)`
   - `kv(key PK, value)` stores `ui_enabled` (`'true'`, `'false'` or absent) and page ETags.
   - Methods: `upsert_listings(listings, *, first_run_page_limit)`, `pending_downloads()`, `mark_*`, `reset_stale_downloading()`, `get/set_ui_enabled()`, `record_run()`, `list_files()`, `last_run()`.
   - New-file rule (see the year-rollover row in plan.md): insert a listing as `new` only if it is not stored and `ific_no > min(stored ific_no)`. When the store is empty, insert everything from the newest page.
   - Create the schema with `CREATE TABLE IF NOT EXISTS`, plus a `PRAGMA user_version` check, so there is no migration framework.

## Tests (no network)

- `test_parse_year_links_newest_first`, run against the `demowic.html` fixture.
- `test_parse_listings_2026_fixture`: the 3083 row has date `2026-10-27` and the absolute URL `https://www.itu.int/sns/ific10/ific3083.zip`.
- `test_parse_listings_raises_on_layout_change` (the fixture has its rows stripped).
- `test_store_first_run_inserts_all_newest_page_rows_as_new`
- `test_store_ignores_older_backlog_after_first_run` (rows from a previous year with lower numbers are not inserted).
- `test_store_ui_override_roundtrip_and_absent_is_none`
- `test_store_reset_stale_downloading_to_failed`

## Validation

```
cd backend && uv run pytest -q tests/test_watcher_source.py tests/test_watcher_store.py
uv run ruff check src tests && uv run ruff format --check src tests
```

## Risk / rollback

The phase is additive. Rollback means deleting `ific/watcher/` and reverting `config.py` and `pyproject.toml`.
