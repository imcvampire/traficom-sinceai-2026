---
phase: 01
title: Space IFIC ingest into DuckDB
status: completed
depends_on: []
---

# Phase 01: Space IFIC ingest

## Context

No IFIC data is in DuckDB yet. The model needs a small, typed subset of the Space `.mdb` per issue, with provenance.
Follow the `m4.py` pattern: a hash-gated loader, one transaction per load, and a manifest row per source.

## Requirements

- Load these tables: `notice`, `com_el`, `grp`, `emiss`, `s_beam`, `geo`, `non_geo`, `orbit`, `c_pfd`, `mask_info`,
  `srv_area`, `e_stn`, `es_ctry`, plus `provn` and `tr_aff_ntw` for Finnish involvement, into schema `ific`. `provn` has about
  760k rows in 3074, so load only the rows where `adm = 'FIN' OR ctry = 'FIN'`, and record the filter in the
  manifest. Each table gets an `ific_no INTEGER NOT NULL` first column.
- Manifest table `ific.issue(ific_no PK, path, sha256, bytes, notice_count, loaded_at)`. If the sha256 is unchanged,
  skip the load. If it changed, delete that issue's rows and reinsert them in one transaction.
- Discovery: `watcher_download_dir/*/ific*.mdb` plus `PROJECT_ROOT/ific*.mdb`. The issue number comes from the file
  name (`ific(\d{4})\.mdb`). Skip `brific*`, which are terrestrial files.
- Export with `mdb-export -D '%Y-%m-%d %H:%M:%S' <file> <table>` into a temp dir, then `read_csv` with an explicit
  `types=` per column for the keys and numerics the model uses (`ntc_id`, `grp_id` BIGINT; `freq_*`, `pep_max`, `gain`,
  `long_nom`, `inclin_ang`, `op_ht_km`, `apog_km`, `perig_km`, `pfd`, `bdwdth`, `tol_east`, `tol_west`, `right_asc`, `bore_long`, `bore_lat` DOUBLE; `nbr_sat_pl`,
  `nbr_plane` INTEGER; `d_wic` TIMESTAMP).
  Leave everything else as VARCHAR.
- A missing `mdb-export` binary or table raises `IngestError` with an actionable message. A table that is legitimately
  empty loads 0 rows without error.

## Files

| Action | Path |
|---|---|
| create | `backend/src/ific/ingest.py`: `discover_issues(settings) -> dict[int, Path]`, `ensure_issue(con, ific_no, path) -> IssueStatus`, `IngestError` |
| modify | `backend/src/ific/db.py`: `CREATE SCHEMA IF NOT EXISTS ific` and `analytics` |
| modify | `backend/src/ific/cli.py`: `ific ingest <path-or-no>` |
| create | `backend/tests/test_ingest.py` |
| create | `backend/tests/fixtures/ific/`: small CSV fixtures per table, plus a fake `mdb-export` shim driven by the test |

## Steps

1. Check `ripwire backend --exemplar="hash-gated source loader" --legend=compact` and reuse the sha256 and timing
   helpers from `m4.py`. Extract them to a shared helper only if both modules need them unchanged.
2. Implement the exporter as a function taking `run: Callable` (subprocess by default) so tests inject the shim.
3. Implement `ensure_issue` with `BEGIN` / `DELETE … WHERE ific_no=?` / inserts / manifest upsert / `COMMIT`, and
   `ROLLBACK` on any error.
4. Log one line per issue: `ific=3074 tables=15 notices=196 duration_ms=…` or `up to date`.
5. Add the CLI command, which exits with code 2 and a clear message when the DB file is locked by a running API.
6. Check the `provn` and `tr_aff_ntw` semantics before phase 02 relies on them: which of `adm` and `ctry` names the
   affected administration, and what `agree_st` codes mean. Compare two 3074 notices that list FIN against the
   IFIC PDF part, and write the finding at the top of `ingest.py` as a short note.

## Validation

- `uv run pytest -q tests/test_ingest.py`: fixture load, the idempotent second call, a changed hash reloads, a
  failure rolls back to the previous rows, and a missing binary raises `IngestError`.
- Manual check: `uv run ific ingest 3074` with the API stopped, then `SELECT count(*) FROM ific.notice WHERE ific_no=3074`
  returns 196.

## Rollback

The schemas are derived and re-creatable. To roll back, drop `ific.*` or delete `var/db/ific.duckdb`, after backing
it up per the DB rule.
