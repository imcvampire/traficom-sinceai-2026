---
phase: 4
title: "Store, job runner, API, CLI, exports"
status: done
priority: P1
effort: "4h"
dependencies: [3]
---

# Phase 4: Store, job runner, API, CLI, exports

## Goal

Terrestrial results are persisted per issue and served from `/api/terrestrial`. They are assessed through the
same job lifecycle as space (one job per issue, a 409 on a duplicate request, failed-on-restart), and exported as
CSV, JSON and Markdown.

## Files

- Create: `backend/src/ific/jobs.py`, the generic runner extracted from `riia/jobs.py`
- Modify: `backend/src/ific/riia/jobs.py`, reduced to a thin space binding with the same public `JobRunner`
  name and constructor
- Create: `backend/src/ific/terra/store.py`, `terra/schemas.py`, `terra/export.py`
- Create: `backend/src/ific/terra/api.py`, an `APIRouter(prefix="/api/terrestrial")` included from `api.py`
- Modify: `backend/src/ific/api.py`, adding the lifespan wiring for the terrestrial runner and including the
  router
- Modify: `backend/src/ific/cli.py`: `terra-assess`, `terra-export`
- Create: `backend/tests/test_terra_store.py`, `test_terra_api.py`, `test_jobs_runner.py`

## Steps

1. **Generic runner.** `ific.jobs.JobRunner(con, source, run: Callable[[cursor, ific_no, as_of, progress],
   list[dict]], write: Callable[[cursor, ific_no, source, results], None], save_job, load_jobs)`. The body comes
   from `riia/jobs.py`: locks, the registry, the stop event and failed-on-restart. `riia.jobs.JobRunner(con,
   population_factory)` keeps its signature and builds the generic runner. `test_riia_jobs.py` and
   `test_riia_api.py` must pass **unchanged**; run them before touching anything else.
2. **Store.** `analytics.terra_assessment(ific_no, terrakey, payload JSON, sort keys…)`,
   `analytics.terra_issue(ific_no PK, model_version, assessed_at, counts…)` and `analytics.terra_jobs`. One
   transaction replaces an issue. Use canonical JSON through `riia.store.canonical_json`, with no score column.
   The tables are keyed by `ific_no` only; there is no receiver source.
3. **API.** All endpoints are under `/api/terrestrial`. Response models live in `terra/schemas.py`.
   - `GET /issues` lists the discovered and ingested issues with their assessment status and counts.
   - `POST /issues/{n}` returns 202 and runs ingest-if-needed plus assess as a job. A running job gives 409.
   - `GET /issues/{n}/assignments` takes the filters `outcome`, `adm`, `change`, `pub_status`, `relevant`
     (default true), `criterion` and `q`. It returns rows sorted by the stored sort keys, without the bulky
     `p1546_steps`.
   - `GET /issues/{n}/assignments/{terrakey}` returns the full detail.
   - `GET /model` returns the model version, criteria with `verified`, the assumptions and the frameworks
     citations.
4. **Exports** (`terra/export.py`). `to_json` writes the canonical JSON. `to_csv` writes one row per assignment
   with flat columns: `terrakey`, `adm`, `adm_ref_id`, `stn_cls`, `notice_typ`, `change`, `pub_status`,
   `relevant`, `signals`, `f_mhz`, `bw_khz`, `erp_dbw`, `h1_m`, `criterion_id`, `applicability`, `trigger`,
   `e_dbuv`, `margin_db`, `outcome`, `reason`, `assumptions` and `sources`. `to_markdown` writes a report grouped
   by outcome, with an evidence block per `exceeds` finding.
5. **CLI.** `ific terra-assess t3076 [--json PATH]` and `ific terra-export t3076 --out DIR` write
   `terra-3076.{json,csv,md}`.

## Tests

- **Store.** Re-assessing issue 9998 leaves 9997's stored payload byte-identical. No `score` column exists in
  `information_schema`.
- **API** (TestClient):
  - POST gives 202 and a second POST gives 409.
  - The list is sorted and filters drop invalid values.
  - The detail includes the P.1546 inputs.
  - The `/api/risk/*` responses are unchanged, checked by the existing tests.
- **Runner.** The generic runner, given a fake run function, reproduces failed-on-restart and the 409 behaviour.

## Validation

```sh
cd backend && uv run pytest tests/test_riia_jobs.py tests/test_riia_api.py -q   # first, unchanged
cd backend && uv run pytest tests/test_jobs_runner.py tests/test_terra_store.py tests/test_terra_api.py -q
cd backend && uv run pytest -q
```

## Risks

Extracting the job runner is the only change in this plan that touches space code. If the unchanged space tests
cannot be kept green within about 1 h, fall back to a separate `terra/jobs.py` copy and record the duplication as
debt in the journal.
