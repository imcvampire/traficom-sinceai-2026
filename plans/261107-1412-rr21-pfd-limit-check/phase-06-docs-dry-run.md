---
phase: 06
title: Method doc, dry run on 3074, review
status: completed
depends_on: [01, 05]
effort: 4h
---

# Phase 06: Method doc, dry run on 3074, review

## Step 1 (before phase 03 code): method doc

In `docs/interference-risk-assessment.md`:

- New section "pfd on Finnish territory vs RR Table 21-4": the formula, reference bandwidth rule, GSO grid and NGSO δ
  sweep, `c_pfd` precedence, mask handling, outcome mapping, near-limit margin, and the assumption ids.
- Fix the row "pfd limits (shown for context)" in the sources table: limits are now evaluated.
- Replace "`mask_info` values are not loaded" with the precise statement: mask values are not in the IFIC
  `.mdb`; masked groups are flagged.
- Sorting section: `pfd_outcome` as tie-breaker.
- Known weaknesses: transcription review pending; single-entry (per notice) pfd, no aggregation across
  networks; δ-independent `c_pfd` compared at the lowest δ.

## Step 2 (last): dry run and report

1. Stop the API (DuckDB single writer), re-ingest 3074 so `srv_cls` loads, then `ific assess 3074` for both
   receiver sources and `ific review 3074 --as-of 2026-11-06 --out plans/reports/review-261107-…`.
2. Write `plans/reports/pfd-261107-3074-art21.md`:
   - counts per `pfd_outcome`, and of near-limit notices;
   - each `exceeds` notice: name, adm, provision, group, row, pfd, limit, δ, margin, source;
   - overlap with the 23 stations-source I/N `exceeds` (both / pfd only / I/N only), and the 7 with a BR finding
     naming Finland;
   - 3 notices recomputed by hand from the `.mdb` values as a spot check.
3. If the run shows an implausible pattern (for example, most FSS GSO notices exceeding by 30 dB), stop and check
   the units and the reference-bandwidth rule before reporting. Do not tune limits or margins to change counts.

## Files

| Action | Path |
|---|---|
| modify | `docs/interference-risk-assessment.md` |
| modify | `README.md` only if the re-ingest step or a CLI flag changed |
| create | `plans/reports/pfd-261107-3074-art21.md`, review report and CSV |

## Validation

- Every claim in the doc section points at a function in `riia/pfd.py` or a row in the limits file.
- `mise run lint` and `mise run test` pass.
- Compare with the plan's acceptance criteria; mark phases completed in `plan.md`.
