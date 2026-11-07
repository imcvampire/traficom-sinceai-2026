# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Analyser for ITU BR Space IFIC issues: how much interference risk each satellite-network notice poses to Finnish
spectrum use. `backend/` is a Python 3.12 FastAPI service plus the `ific` CLI; `frontend/` is a React 19 + Vite SPA
that only talks to the API through the `/api` proxy. Setup, data locations, CLI and settings are in `README.md`.

## Commands

Tools are pinned in `mise.toml` (Python 3.12, uv, Bun, Node). `mdbtools` (`mdb-export`) is not pinned by mise; `mise run install` installs it through brew/apt-get/dnf if missing.

```sh
mise run install          # mdbtools if missing, uv sync (backend), bun install (frontend)
mise run dev              # API :8000 (reload) + Vite :5173 (strictPort: free the port, don't change it)
mise run lint             # ruff check + ruff format --check (backend), oxlint (frontend)
mise run test             # backend: uv run pytest -q (there are no frontend tests)
mise run build            # frontend: tsc -b && vite build

cd backend && uv run pytest tests/test_riia_assess.py -q            # one file
cd backend && uv run pytest tests/test_riia_assess.py -k work_queue  # one test
cd frontend && bunx tsc -b --noEmit                                  # frontend type-check only
uv run --project backend ruff format backend                         # backend formatter (line length 110)
```

The frontend has no formatter configured; match the surrounding style (single quotes, no semicolons, 2 spaces).

The CLI commands that open DuckDB (`ingest`, `assess`, `review`, `draft`, `assess-sensitivity`) fail while the API is
running, because DuckDB allows one writer. Stop the server first, or trigger an assessment through the API instead
(`POST /api/risk/issues/{ific_no}`).

## Architecture

### Data and storage

One DuckDB file (`var/db/ific.duckdb`) with three schemas, created in `backend/src/ific/db.py`:

- `ref`: reference data loaded at API startup (`m4.ensure_m4`, `special_interest.ensure_special_interest`),
  tracked by sha256 in `ref.source` so unchanged inputs are not reloaded.
- `space`: Space IFIC tables ingested from `.mdb` files via `mdb-export` (`ingest.py`), tagged with `ific_no`. Ingest
  is a no-op when the file's sha256 and the table set (`ingest.TABLES`, recorded in `space.issue.filters`) are
  unchanged, so adding a table re-loads existing issues. The schema is `space`, not `ific`, because `ific` would be
  ambiguous with the catalog name.
- `analytics`: derived `risk_*` tables written by `riia/store.py`, keyed by `(ific_no, receiver_source)`; one
  transaction replaces an issue's whole assessment.

Issue discovery looks in `data/ific/<no>/ific<no>.mdb` (watcher downloads) first, then `ific<no>.mdb` in the repo
root. `brific*.mdb` files are terrestrial issues and are ignored. Hand-curated inputs with citations live in
`data/ref/` (`receiver_classes.json`, `rr_comment_windows.json`, `rr21_pfd_limits.json`, `finland_land.geojson`).

The FastAPI `lifespan` in `api.py` opens the single connection, loads reference data, starts the risk `JobRunner`
and the hourly source watcher (`watcher/`, off with `IFIC_WATCHER_ENABLED=false`). Request handlers get a per-request
`con.cursor()` through `get_db`. Settings come from `IFIC_*` env vars or the root `.env` (`config.py`).

### Risk model (`backend/src/ific/riia/`, model `riia-1`)

The method is specified in `docs/interference-risk-assessment.md`. That doc is the source of truth, and code
docstrings quote it. Read it before changing the model.

- `assess.py` orchestrates: for each notice it builds the hazard inventory (co-channel, adjacent band, plus
  inventoried-only modes reported as `not_assessed`), evaluates the hazards, attaches the regulatory context
  (`regulatory.py`), and derives the summary fields, `in_queue` and the sort keys.
- `hazards.py` runs the tiers: Tier 0 overlap and visibility, Tier 1 deterministic worst case (can screen a hazard
  out), and Tier 2 seeded Monte Carlo. The physics helpers are `geometry.py`, `orbits.py`, `antenna.py`,
  `emission.py` and `curves.py`.
- `receivers.py` defines the `Receiver` record and the `ReceiverPopulation` protocol, with two implementations:
  `generic-m4` (M4 allocations × a grid over Finland) and `stations` (the special-interest station list). Adding a
  receiver source means adding a population, not changing the hazard code.
- `jobs.py` runs one background job per `(ific_no, receiver_source)` on its own thread and cursor; a second request
  while one runs gets 409. `store.py` persists results and serves them to the API.
- `pfd.py` is the RR Table 21-4 check (`pfd_checks`, `pfd_outcome`, `max_pfd_margin_db` on each notice): worst
  pfd on Finnish territory per Table 21-4 row, deterministic, versioned as `pfd_check_version` (not
  `model_version`, which seeds the RNG). Limits are in `data/ref/rr21_pfd_limits.json`, loaded by `pfd_limits.py`;
  every encoded row has a hand-typed cross-check in `tests/test_riia_pfd_limits.py`. It never sets `worst_outcome`.
- `consistency.py`, `sensitivity.py` and `review.py` produce the validation and expert-triage reports from stored
  results.

Invariants to keep:

- **No composite score.** Results are hazard outcomes (`exceeds`, `meets`, `screened_out`, `not_applicable`,
  `not_assessed`) and readings off likelihood–consequence curves. Tests assert that no `score` column exists.
- **Reproducible.** The Monte Carlo random generator is seeded from `(model_version, ific_no, ntc_id, hazard_id)`,
  and two runs must produce byte-identical JSON.
- **`as_of` only affects the regulatory context.** Stored results are re-dated when they are read
  (`assess.apply_as_of` recomputes `days_left`, `window_open` and `in_queue`), so changing the queue rule needs no
  re-assessment.
- Every input carries a source tag and citation, and every assumption an id. The sensitivity report flags the
  assumptions that can change an outcome.

The `/risk` chat context is assembled server-side in `riia/chat.py` from stored results and the method doc, and
streamed by `llm.py`. It must keep the no-score rule: no `score` key, no ranking, and no curve arrays in the context.

Draft letters (`riia/draft.py`) are built on demand and never stored. Their kind comes from the regulatory context,
never from the LLM. The LLM polish rewrites the body paragraphs only, and `check_polish` rejects any change to the
protected tokens. Station ids, coordinates and azimuths go in the reviewer notes, never in the letter.

`propagation/` (ITU-R P.1546 field strength and T/R 25-08 triggers) and `stations.py` serve the `/stations` map. They
are separate from the space risk model.

### Frontend

- `src/router.tsx` defines routes in code. **All page state lives in URL search params**, validated per route in
  `validateSearch`, where invalid values are dropped. A new filter needs its type, its validation and the page wiring.
- `src/lib/api.ts` holds the typed API client and response types, and must be kept in sync with
  `backend/src/ific/riia/schemas.py`. `src/lib/queries.ts` holds the TanStack Query options and mutations.
- `/risk` lives in `pages/risk.tsx`, with its components in `components/risk-*.tsx`, `notice-sheet.tsx` and
  `hazard-inventory.tsx`. Labels, descriptions and formatters shared across these live in `components/risk-meta.ts`.
  `components/term-hint.tsx` is the dotted-underline tooltip used to explain domain terms.
- shadcn/ui components are generated into `src/components/ui/`; add new ones with `bunx --bun shadcn@latest add`.
  Theme tokens are in `src/index.css`. Chart series use `--series-1..5`, and the status tokens are reserved for
  state.

`docs/frontend.md` lists each route's URL params. Update it when params change.

### Tests

The backend tests run against fixtures, not real IFIC files. `tests/riia_fixtures.py` loads a synthetic issue
(`FIXTURE_ISSUE = 9999`) from CSVs in `tests/fixtures/ific/` through a fake `mdb-export`. `conftest.py` points the DB
at a temp directory for every test. API tests use FastAPI's `TestClient`.

## Repository conventions

- Plans go in `plans/<yymmdd-hhmm-slug>/` (`plan.md` plus phase files). Reports go in `plans/reports/` and journals
  in `plans/journals/`. Evergreen documentation goes in `docs/`.
- `.mdb` files, `data/ific/` and `var/` are gitignored.
