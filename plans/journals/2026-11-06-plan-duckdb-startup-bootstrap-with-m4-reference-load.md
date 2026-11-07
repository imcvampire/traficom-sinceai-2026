---
title: "Plan: DuckDB startup bootstrap with M4 reference load"
date: 2026-11-06
summary: "Planned hash-gated, transactional M4 load into DuckDB ref schema on FastAPI startup"
---

# Plan: DuckDB startup bootstrap with M4 reference load

## What happened
Planned how the backend opens DuckDB at startup and loads M4 reference data. Plan: `plans/261106-2101-duckdb-startup-m4-reference-load/`.

## Decision
- The structured M4 table comes from `data/api/taajuusjakotaulukko.json` (5,917 rows, typed Hz). The PDF-extracted table text is too mangled to parse.
- The M4 regulation and explanatory notes are stored per page in `ref.m4_page` for citations. The notes PDF needs `pypdf`.
- A `ref.source` sha256 manifest gates reloads. Each reload runs in one transaction, and startup fails fast on missing files.

## Next steps
Run `/ak-cook` on the plan. The later ingest plan must handle DuckDB's single-writer lock while the API is running.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
