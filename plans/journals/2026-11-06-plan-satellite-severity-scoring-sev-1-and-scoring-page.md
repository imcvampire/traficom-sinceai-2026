---
title: "Plan: satellite severity scoring (sev-1) and /scoring page"
date: 2026-11-06
summary: Planned a deterministic per-notice severity model for Finland plus Space IFIC ingest and a demo UI page
---

# Plan: satellite severity scoring (sev-1) and /scoring page

## What happened
Planned the first analytics block in `plans/261106-2255-sat-severity-scoring/`. Profiling IFIC 3074 showed the
inputs a model can use. `emiss.pep_max` and `s_beam.gain` are present for most GSO and non-GSO groups. `c_pfd` is
present for only 49 notices, and `srv_area = FIN` for only 2 groups, so service area alone cannot decide relevance.
There is no Space IFIC ingest yet, so phase 01 adds one, using mdb-export into the `ific` schema with a hash gate.

## Decision
The model is a transparent weighted model, version sev-1: `severity = 100 · V · S · weighted(P, R, C)`.
- V (visibility) and S (M4 spectrum overlap) act as a relevance gate.
- P is an estimated pfd margin against RR Art. 21. It is a screening proxy, not an ITU examination.
- R is the regulatory stage and C is the scale.

ML was rejected because there are no labels. LLM judging was rejected because it breaks reproducibility.

## Next steps
1. Confirm the weights and sensitivity classes with Traficom.
2. Decide where the root-level `ific3074.mdb` and `ific3083.mdb` should live.
3. Run `/ak-cook` on the plan.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
