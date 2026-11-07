---
phase: 1
title: DB module + M4 loader
status: completed
---

# Phase 01: DB module + M4 loader

## Context

See [plan.md](plan.md) for the evidence and decisions. Read `backend/src/ific/config.py` and `backend/pyproject.toml`.

## Files

| File | Action |
|---|---|
| `backend/src/ific/config.py` | Add a `db_path` property (`db_dir / "ific.duckdb"`), `m4_allocation_json` (`data_dir/api/taajuusjakotaulukko.json`) and `m4_dir` (`data_dir/m4`). |
| `backend/src/ific/db.py` | **New.** `connect(path) -> DuckDBPyConnection`, which creates the parent dir and the `ref` schema and the `ref.source` table. |
| `backend/src/ific/m4.py` | **New.** `parse_freq_hz`, `ensure_m4(con, settings) -> list[SourceStatus]`. |
| `backend/pyproject.toml`, `backend/uv.lock` | Add `pypdf` (pinned through `uv add`). |
| `backend/tests/test_m4.py` | **New.** Tests for the parser and loader. |

## Schema

```sql
CREATE SCHEMA IF NOT EXISTS ref;
CREATE TABLE IF NOT EXISTS ref.source (
  source_id  VARCHAR PRIMARY KEY,   -- 'm4_allocation', 'm4_regulation', 'm4_notes'
  path       VARCHAR NOT NULL,      -- relative to data_dir
  sha256     VARCHAR NOT NULL,
  bytes      BIGINT  NOT NULL,
  edition    VARCHAR,               -- e.g. '4 AG/2026M'
  row_count  BIGINT  NOT NULL,
  loaded_at  TIMESTAMPTZ NOT NULL
);
-- ref.m4_allocation: id BIGINT PK, snake_case copies of all 24 JSON fields,
--   + band_lower_hz, band_upper_hz, duplex_lower_hz, duplex_upper_hz BIGINT (parsed)
--   sub_band_lower_hz / sub_band_upper_hz come straight from the typed *_Hz_ fields.
-- ref.m4_page: doc_id VARCHAR, page_no INTEGER, text VARCHAR, PRIMARY KEY (doc_id, page_no)
```

## Steps

1. `parse_freq_hz(s: str) -> int | None`. An empty string returns `None`. The `^([\d.]+)\s*(Hz|kHz|MHz|GHz)$` pattern
   is evaluated with `Decimal` to avoid float drift (`2173.5 kHz` must give `2173500`). Any other input raises `ValueError`.
2. Allocation loader: read the JSON in Python with `json.load(...)["value"]`, map the fields to snake_case, parse the four
   limit strings, and bulk insert with `executemany` or a DuckDB relation from a list of tuples. Assert
   `sub_band_lower_hz <= sub_band_upper_hz` for every row.
3. Page loader: for each of `m4-radio-frequency-regulation-en` and `m4-explanatory-notes-en`, use the `.txt` split on
   `\f` if the file exists, otherwise use `pypdf.PdfReader(pdf).pages[i].extract_text()`. Pages are numbered from 1.
   Drop trailing empty pages caused by a final `\f`.
4. Edition: take the first regex match of `RADIO FREQUENCY REGULATION (\d+ [A-Z]+/\d{4}M)` in the regulation text, and
   store it on all three M4 source rows.
5. `ensure_m4`: for each source, compute sha256 and compare it with `ref.source`. If it matches and the table exists,
   return `up_to_date`. Otherwise, in `BEGIN … COMMIT`, delete or recreate that source's rows, insert, and upsert
   `ref.source`. Roll back on any exception and re-raise. Log with `logging.getLogger("ific.db")`, including the
   source id, action, rows and ms.
6. A missing source file raises `FileNotFoundError` naming the path and the setting to override (`IFIC_DATA_DIR`).

## Tests (`backend/tests/test_m4.py`)

- `parse_freq_hz`: `"8.3 kHz"→8300`, `"2173.500 kHz"→2173500`, `"1.5 GHz"→1500000000`, `""→None`, `"abc"` raises.
- Loading into a tmp DB with the real `data/` gives 5,917 allocation rows, no NULL `band_lower_hz`, and page counts > 0 for
  both docs, with edition `4 AG/2026M`.
- A second `ensure_m4` call returns `up_to_date` for every source and leaves `loaded_at` unchanged.
- Point the settings at a tmp copy of `data/`, mutate one byte of the JSON, and only `m4_allocation` reloads.
- Corrupt a limit string in the tmp copy: the call raises, and the previous rows are still present (rollback).

## Validation

```bash
uv run --project backend pytest -q backend/tests/test_m4.py
uv run --project backend ruff check backend && uv run --project backend ruff format --check backend
```

## Rollback

Delete `db.py`, `m4.py`, the test and the `pypdf` dependency. Remove `var/db/ific.duckdb`, which is derived and safe to delete.
