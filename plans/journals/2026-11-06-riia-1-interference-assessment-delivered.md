---
title: riia-1 interference assessment delivered
date: 2026-11-06
summary: "Space IFIC ingest, RIIA engine, API/CLI/jobs and /risk page for plan 261106-2255; review caught three result-changing bugs"
---

# riia-1 interference assessment delivered

## What happened
Implemented plan `plans/261106-2255-sat-severity-scoring` end to end: `space` schema ingest of Space IFIC `.mdb`
files, the riia-1 engine (`backend/src/ific/riia/`), background jobs, `/api/risk/*`, CLI (`ingest`, `assess`,
`assess-sensitivity`) and the `/risk` page (built by a subagent against `api-contract.md`).

IFIC 3074 (generic population, as_of 2026-11-06): about 220 s, two runs byte-identical; worst outcomes exceeds 82,
not assessed 9, meets 36, screened out 5, not applicable 64. Tier 1 bounds Tier 2 everywhere; 9 of 15 BR Finland
findings agree, the 6 misses are explained (below horizon, or no protected-band overlap).

## Lessons
- A schema named `ific` is ambiguous inside `ific.duckdb` (catalog name = file stem); renamed to `space`.
- `mdb-export -D` does not format datetime columns; `-T` is needed.
- DuckDB needs `pytz` to fetch TIMESTAMPTZ into Python; read `epoch_us(...)` instead.
- Code review found three result-changing bugs after the first "green" run: `c_pfd.bdwdth` is kHz (was read as Hz,
  +30 dB), the Tier 2 candidate cut used the lowest orbit radius (dropped higher satellites), and receiver heights
  were never drawn. All fixed with regression tests; every report was regenerated afterwards.
- A same-size edit within the same second made Python reuse a stale `.pyc`, so a regression test looked like it failed
  on fixed code. Bump mtime when toggling code to prove a test.

## Decision
Kept absolute RA.1631 gain in the radio-astronomy spfd margin (RA.769 0 dBi basis); the EPFD peak-normalised
convention is an open review question in the doc.

## Next steps
- Person review of `data/ref/receiver_classes.json`.
- Stations receiver source; terrestrial module for earth-station paths.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
