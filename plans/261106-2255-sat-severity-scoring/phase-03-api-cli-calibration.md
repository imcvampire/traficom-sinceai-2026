---
phase: 03
title: Assessment jobs, API, CLI, consistency checks and sensitivity report
status: completed
depends_on: [02]
---

# Phase 03: Jobs, API, CLI, checks, sensitivity

## Requirements

### Storage

These are derived tables. Writing an issue replaces its rows in one transaction.

- `analytics.risk_notice` holds one row per notice.
  - Columns:
    - `domain`, `ific_no`, `item_id`, `receiver_source`;
    - `model_version`, `as_of`;
    - `worst_outcome`, `max_share_violating`, `max_median_exceedance_db`;
    - `days_left`, `fin_identified`;
    - `payload JSON`, `assessed_at`.
  - Primary key: `(domain, ific_no, item_id, receiver_source)`.
  - There is no composite score column.
- `analytics.risk_hazard` holds one row per hazard. It stores the outcome, the tier, and the curves as JSON arrays on
  the fixed dB grid. It is keyed by the notice key plus `hazard_id`.
- `analytics.risk_job` holds `(ific_no, receiver_source, status, done, total, started_at, finished_at, error)`.

### Jobs

- An assessment runs in a background thread with its own DuckDB cursor.
- There is one job per `(ific_no, receiver_source)` at a time, guarded by a non-blocking `threading.Lock` per key.
- Progress comes from the `progress` callback. A failed job keeps the previous results and records its error.
- The days-left values depend only on `as_of`. `GET` requests with a different `as_of` recompute them from the stored
  payload. That is cheap, and needs no new Monte Carlo run.

### API

The routes use Pydantic models.

| Method | Path | Result |
|---|---|---|
| `GET` | `/api/risk/issues` | Discovered and ingested issues: `ific_no`, `ingested`, `assessed`, `model_version`, `notice_count`, counts per outcome, and job status/progress |
| `POST` | `/api/risk/issues/{ific_no}` | Ingest if needed, then start the job. Returns 202, 404 if the issue is unknown, 409 if a job is running, 422 on `IngestError` |
| `GET` | `/api/risk/issues/{ific_no}/notices?as_of=` | The notice list, with summary fields and regulatory context, in the doc's technical sort order. A `view=queue` parameter applies the work-queue filter and order |
| `GET` | `/api/risk/issues/{ific_no}/notices/{ntc_id}?as_of=` | The full assessment: hazards, curves, criterion points, inputs, citations, assumptions and regulatory context |
| `GET` | `/api/risk/model` | `model_version`, the method steps with their source quotes, the receiver classes (criteria, patterns, distributions), and the source tag and cite for every input |

### CLI

- `ific assess <ific_no> [--as-of YYYY-MM-DD] [--json PATH]` runs in the foreground and shows progress. `--json`
  writes a canonical export: sorted keys, stable order, floats rounded to 4 decimals. The determinism test uses it.
- `ific assess-sensitivity <ific_no> --as-of … [--out PATH]` runs the sensitivity report:
  - each `assumption` input is moved to the low and high end of its range;
  - it reports the shift in median `exceedance_db`, the outcome flips and the change in `share_violating`;
  - it lists the outcome-sensitive assumptions;
  - the perturbation list is fixed, so the report is deterministic.

  It writes to `plans/reports/sensitivity-261106-riia1-3074.md`.

### Consistency report

`plans/reports/consistency-261106-riia1-3074.md` contains:

- the outcome distribution per service class;
- Tier 1 ≥ Tier 2 max for every hazard, with any violation listed;
- that suppressions and never-visible notices have no `exceeds`;
- agreement with the BR's Finland findings, with misses listed by worst-case value;
- the run time per tier.

## Files

| Action | Path |
|---|---|
| create | `backend/src/ific/riia/store.py`: writes, reads, summaries |
| create | `backend/src/ific/riia/jobs.py`: job runner, per-key locks, progress |
| create | `backend/src/ific/riia/sensitivity.py`: perturbation list and report writer |
| modify | `backend/src/ific/api.py`: the routes above, with the job runner on `app.state` and cancellation at shutdown |
| modify | `backend/src/ific/cli.py`: `assess` and `assess-sensitivity` |
| create | `backend/tests/test_riia_api.py`, `test_riia_store.py`, `test_riia_jobs.py` |
| create | `backend/tests/fixtures/riia/3074-summary.json`: a reviewable snapshot of the per-notice summaries at a fixed `as_of` |

## Validation

- Determinism: assess the fixture issue twice and compare the exports byte for byte.
- Regulatory fields at two `as_of` dates differ only in `days_left`. The hazards are identical.
- API tests:
  - 202, then progress, then done;
  - 409 while running;
  - 404;
  - 422 on a broken export;
  - the response shapes contain no score field.
- A job failure keeps the previous results.
- Manual checks:
  - `uv run ific assess 3074 --as-of 2026-11-06 --json …` succeeds within budget;
  - both reports exist and meet plan acceptance criteria 5 and 6.

## Operational notes

- Log `riia job ific=… source=… notices=… hazards=… tier1_screened=… tier2=… duration_ms=…` once per job, plus one
  warning per failed notice.
- `/api/health` gains `risk: {issues_assessed, model_version, running_jobs}`.
- Stop the API before a CLI run. The CLI exits with a clear message if the DB is locked.
