---
title: DuckDB bootstrap on API startup with M4 reference data load
status: completed
mode: fast
created: 2026-11-06
branch: main
source: /ak-plan "when BE is started, check DuckDB, and add m4 data (stored in data/) to DB for further work"
related: ../reports/brainstorm-261106-2029-ific-interference-analyser.md
---

# DuckDB bootstrap + M4 reference load

## Outcome

When the FastAPI backend starts, it opens (or creates) the project DuckDB file, verifies that the M4
reference data is present and matches the source files under `data/`, and loads or reloads it when it is
missing or stale. Downstream work (the overlap screen, citations in findings) can then query M4 from SQL.

## Evidence (inspected 2026-11-06)

| Source | Finding |
|---|---|
| `data/api/taajuusjakotaulukko.json` | The M4 Frequency Allocation Table from the Traficom OData API v13: 5,917 rows, unique `ID`, typed BIGINT `Sub_band_*__Hz_`. All 15,010 non-empty band/duplex limit strings match `<number> <Hz\|kHz\|MHz\|GHz>`. |
| `data/api/taajuusjakotaulukko.csv` | The same table as CSV. Redundant with the JSON, which keeps the types, so it is not loaded. |
| `data/m4/m4-radio-frequency-regulation-en.txt` | 41,621 lines and 257 form feeds, so it splits into pages. The table section is badly mangled by PDF extraction, which makes it fine for page-cited text lookups but useless as structured data. Its header carries the edition (`4 AG/2026M`, in force 31.3.2026). |
| `data/m4/m4-explanatory-notes-en.pdf` | There is no `.txt` sibling, and `pdftotext`/`mutool` are not installed, so text extraction needs `pypdf`. |
| `backend/src/ific/config.py` | `db_dir` (`var/db`) and `data_dir` already exist. `var/` and `*.duckdb` are gitignored. |
| `backend/src/ific/api.py` | No lifespan and no DB yet. `/api/health` is static. |

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Structured M4 source | The API JSON, not the parsed PDF text | It is the same table with typed Hz bounds. Parsing the PDF table is unreliable. |
| Text source | `.txt` when present, otherwise `pypdf` on the PDF, stored per page | This gives page-level citations (`M4 p. 10`) without fragile section parsing. |
| Change detection | A `ref.source` manifest with the sha256 of each file; reload when a hash differs or a table is missing | Startup stays idempotent and cheap (about 6 MB to hash), and a refreshed `data/` file is picked up automatically. |
| Reload atomicity | One transaction per reload: drop, create, insert, then upsert the manifest | A failed load leaves the previous good data in place. This meets the backup rule for this derived, re-creatable schema. |
| Schema name | `ref` (tables `ref.source`, `ref.m4_allocation`, `ref.m4_page`) | Leaves room for M15 or CEPT ECO later without renaming. Issue data gets its own schemas later. |
| Failure policy | Fail fast at startup if the DB cannot be opened or an M4 source file is missing | Every downstream feature depends on M4, and a half-up server hides the problem. |
| Connection model | One read-write connection on `app.state`, with a `cursor()` per request through a FastAPI dependency | DuckDB allows one writer process per file, and cursors are the supported way to share it across threads. |

## Extension trace

Next credible variant: the M15 or CEPT ECO reference data, which the brainstorm lists as optional enrichment.
The stable contract is the `ref.source` manifest and a hash-gated `ensure_*` loader per source. Adding a source
means one new loader function and its tables. Phase 01 proves this by keeping the manifest keyed by `source_id`
rather than being M4-specific. No registry or plugin layer is built.

## Phases

| # | Phase | Status | Depends on |
|---|---|---|---|
| 01 | [DB module + M4 loader](phase-01-db-and-m4-loader.md) | completed | — |
| 02 | [Startup wiring, health, tests](phase-02-startup-wiring-and-tests.md) | completed | 01 |

## Acceptance criteria

1. `mise run api` on a clean checkout (no `var/db`) creates `var/db/ific.duckdb` and loads `ref.m4_allocation`
   (5,917 rows) and `ref.m4_page` (one row per page for each M4 document). The log shows one line per source with
   its row count and duration.
2. A second start with unchanged files skips the reload, and the log says `up to date`. Touching or replacing a
   source file triggers a reload of that source only.
3. `ref.m4_allocation` has `band_lower_hz`, `band_upper_hz`, `sub_band_lower_hz`, `sub_band_upper_hz`,
   `duplex_lower_hz` and `duplex_upper_hz` as BIGINT, plus the original text columns. Every non-empty limit string
   parses, and the loader raises if any does not.
4. `GET /api/health` reports the DB path, the M4 edition and the row counts per reference table.
5. A missing source file or an unparseable limit aborts startup with a clear error, and an already-loaded DB is
   left unchanged.
6. `mise run lint` and `mise run test` pass. The tests use a tmp `db_dir` and never touch `var/db`.

## Non-goals

- Ingesting IFIC `.mdb` issues, which is the next plan (`ific ingest`).
- Full-text search. The DuckDB `fts` extension needs a download, so `ILIKE` on `ref.m4_page` is enough for now.
- Parsing the M4 PDF table into structure, or loading the CSV copy.
- A CLI reload command. Startup is the only trigger, as requested.
- Schema migrations framework.

## Risks

- **DuckDB single-writer lock.** A later `ific analyse` CLI run while the API is up will fail to open the file read-write. That plan must open read-only or go through the API. This is recorded here so the ingest plan accounts for it.
- **`uvicorn --reload`** runs the lifespan in the reloaded child process. Each code change re-runs the hash check, which costs well under a second.
- **`pypdf` text quality** for the notes PDF is unverified. Phase 01 checks for non-empty text on every page.

## Unresolved questions

1. Should "M4 data" also cover `data/api/` (assumed yes, because it is the structured M4 table), or only `data/m4/`?
2. Is a manual `ific db reload --force` command wanted for ops, or is startup-only enough?
