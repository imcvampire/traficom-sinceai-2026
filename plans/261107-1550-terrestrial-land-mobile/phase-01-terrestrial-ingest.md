---
phase: 1
title: "Terrestrial ingest and fixtures"
status: done
priority: P1
effort: "4h"
dependencies: []
---

# Phase 1: Terrestrial ingest and fixtures

## Goal

`ific ingest brific<no>.mdb` loads a terrestrial issue into the DuckDB `terra` schema, tagged with `ific_no`. It
is a no-op when the file and its table set are unchanged. The space ingest behaves exactly as before.

## Files

- Modify: `backend/src/ific/ingest.py`, adding a terrestrial path beside the space one with shared helpers.
- Modify: `backend/src/ific/config.py`: `terra_download_dir: Path = PROJECT_ROOT / "data" / "brific"`, with the
  same validator as `watcher_download_dir`.
- Modify: `backend/src/ific/cli.py`: `_resolve_issue` / `_ingest` accept a `brific<no>.mdb` path or `t<no>`.
- Create: `backend/tests/fixtures/brific/9997/*.csv` and `backend/tests/fixtures/brific/9998/*.csv`.
- Create: `backend/tests/terra_fixtures.py`, a fake `mdb-export` for the brific fixtures, like
  `riia_fixtures.py`.
- Create: `backend/tests/test_terra_ingest.py`.
- Modify: `.gitignore` if `data/brific/` is not already covered. `*.mdb` already is; add `data/brific/` for the
  watcher's zip and `.part` files.

## Steps

1. **Shared helpers.** `mdb_export`, `_load_table`, `_column_type` and the sha256 manifest check gain a `schema`
   parameter, and the space callers pass `"space"`. Do not change the space column-type maps. Add a
   `_TERRA_TYPES` map for terrestrial columns:
   - `terrakey`, `geo_key`, `target`, `ant_key`: BIGINT;
   - `freq_assgn`, `freq_min`, `freq_max`, `bdwdth`, `lat_dec`, `long_dec`, `radius`, `pwr_dbw`, `gain_max`,
     `hgt_agl`, `eff_hgtmax`, `azm_max_e`, `bmwdth`, `site_alt`: DOUBLE;
   - `pub_no`: INTEGER;
   - `d_*` fields: TIMESTAMP, parsed from the `MM/DD/YY HH:MM:SS` format.

   A column that fails to cast stays VARCHAR and is logged once. Rows are never dropped.
2. **Terrestrial table set.** `TERRA_TABLES = ("fxm_terra", "fxm_tx", "fxm_ant", "fxm_ant_diag", "fxm_geo",
   "fxm_geo_pt", "fxm_coord", "fxm_target", "fxm_pub_hist", "fxm_fdg", "fxm_rmks", "ge06_adm_affected_broad",
   "ge06_affected_os", "ref_stn_cls", "ref_stn_cls_nat_srv", "ref_nat_srv", "ref_notice_typ", "ref_adm")`. The
   `ref_*` tables are loaded per issue too, because they are the issue's own code tables and get cited from it.
3. **Manifest.** `terra.issue(ific_no PK, path, sha256, bytes, assignment_count, filters, loaded_at)`, with the
   same no-op rule as `space.issue`. Changing `TERRA_TABLES` re-loads existing issues.
4. **Discovery.** `discover_terra_issues(settings)` looks in `terra_download_dir/*/brific*.mdb` first, then
   `PROJECT_ROOT/brific*.mdb`, with the regex `^brific(\d{4})\.mdb$`. `discover_issues` (space) keeps ignoring
   `brific*`.
5. **Fixtures.** These are two synthetic issues, written as hand-made CSVs with the real column headers copied
   from 3076. Their rows cover every case the later phases test:
   - **9997:** an RUS FB T12 ADD at 168 MHz near Slantsy, in part 1. An RUS FB G12 GE06-4.2 ADD at 793.5 MHz with
     an `fxm_coord` FIN `COORD REQUIRED` row. An EST FB T12 ADD at 450 MHz. An RUS ML T13 receiving notice. A CHN FB
     at 46°N. An FB with missing `hgt_agl`. A FIN FX notice, which must be excluded. A MODIFY plus its RECORDED
     target with a power change. A SUPPRESS plus its target.
   - **9998:** the 9997 RUS 168 MHz notice again with the same `terrakey`, now in part 2 with an `fxm_fdg` REX
     favourable row. A part-3 returned notice. A notice whose bandwidth is atypical for its band, for the anomaly
     rules.
6. **CLI.** `ific ingest data/brific/3076/brific3076.mdb` prints the table counts. A bare `t3076` resolves through
   discovery.

## Tests

- `test_terra_ingest.py`:
  - The fixture ingest gives the expected row counts per table, and re-ingest is a no-op.
  - A changed file replaces that issue's rows atomically, and the other issue's rows are untouched.
  - A cast failure keeps the column as VARCHAR.
  - Discovery prefers `data/brific` over the repo root.
- `test_ingest.py` must pass unchanged.

## Validation

```sh
cd backend && uv run pytest tests/test_terra_ingest.py tests/test_ingest.py -q
uv run --project backend ruff check backend && uv run --project backend ruff format --check backend
# real data, API stopped:
cd backend && uv run ific ingest ../data/brific/3076/brific3076.mdb   # second run prints "unchanged"
```

## Risks

The `d_*` date format with two-digit years needs care: `03/10/26` means 2026, while `01/25/79` means 1979. Use a
pivot year of 70 and test both.
