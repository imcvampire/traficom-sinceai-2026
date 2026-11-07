---
title: DuckDB startup bootstrap with M4 reference load
date: 2026-11-06
summary: API startup now opens var/db/ific.duckdb and hash-gates a load of the M4 allocation table and page text into the ref schema.
---

# DuckDB startup bootstrap with M4 reference load

## What happened
Implemented plan `plans/261106-2101-duckdb-startup-m4-reference-load`. New `ific.db.connect` and `ific.m4.ensure_m4`, which load
`ref.m4_allocation` (5,917 rows, BIGINT Hz bounds parsed with Decimal), and `ref.m4_page` (258 regulation pages from the .txt, plus 3 notes pages via pypdf).
A `ref.source` sha256 manifest skips the reload when nothing changed. Each source reloads in its own transaction and rolls back on failure.
The FastAPI lifespan runs it at startup. `/api/health` reports the DB path, edition `4 AG/2026M` and the row counts.

## Findings
- Row-wise `executemany` took 2.4 s for 5,917 rows x 28 columns. Chunked multi-row VALUES took about 0.87 s. A single columnar
  `INSERT ... SELECT unnest(?::T[]), ...` takes about 60 ms and keeps NULLs. A cold start now loads everything in about 170 ms.
- DuckDB 2.0 needs `pytz` to fetch TIMESTAMPTZ values into Python. The tests compare `epoch_us(loaded_at)` instead of adding the dependency.
  Any future Python code that reads `loaded_at` directly will hit the same error.
- The JSON is compact (`"key":"value"`). A byte-replace test needle written with a space silently matched nothing, so the test now asserts that the mutation applied.

## Next steps
- The ingest plan must handle DuckDB's single-writer lock while the API is running.
- The open questions from the plan (scope of `data/api`, a manual reload command) are still unanswered.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
