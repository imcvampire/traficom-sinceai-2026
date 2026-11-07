---
phase: 8
title: "Docs, real-data verification and 3076 submission"
status: done
priority: P1
effort: "3h"
dependencies: [1, 2, 3, 4, 5, 6, 7]
---

# Phase 8: Docs, real-data verification and 3076 submission

## Goal

This phase writes the method doc as the source of truth, checks every acceptance criterion against real 3075,
3076 and 3077 data, and produces the 3076 submission files.

## Files

- Create: `docs/terrestrial-land-mobile.md`, the method of `terra-1`. It covers:
  - the stage mapping to `riia-1`;
  - selection, the change and publication-status semantics, and the relevance signals;
  - the framework layers and criteria, with their `verified` state;
  - the tiers, all assumptions with ids, and the outputs;
  - what is not covered;
  - the questions open with Traficom.
- Modify:
  - `docs/propagation.md`: the side quest is now a consumer of the module;
  - `docs/interference-risk-assessment.md`: only its "Not covered" mention of terrestrial notices, linked to
    the new doc;
  - `docs/frontend.md`, already updated in phase 7, so check it;
  - `README.md`: data locations (`data/brific/`), the new CLI commands and settings;
  - `CLAUDE.md`: remove "brific files are ignored", and add the `terra` schema, `terra/` package and
    `/terrestrial` page.
- Create: `plans/reports/verify-<yymmdd-hhmm>-terrestrial-land-mobile.md`, giving each criterion with its
  evidence.
- Create: `plans/journals/<date>-terrestrial-land-mobile-delivered.md`, through the journal step.

## Steps

1. **Real ingest and assessment.** With the API stopped, back up `var/db/ific.duckdb` before the first terrestrial
   write, then run:

   ```sh
   for n in 3075 3076 3077; do (cd backend && uv run ific ingest t$n && uv run ific terra-assess t$n); done
   ```

   Log the time per issue.
2. **Check each criterion against real data** and record the numbers in the verify report:
   - AC3: all 16 FIN-coordination rows in 3076 are relevant, 15 of them TX and 1 RX `not_applicable`, and the CHN
     46°N notices are not relevant.
   - AC4: the RUS G12 793.5/794.74 MHz notices name GE06 Art. 4 and `ecc-rec-11-04` with `indicative`, and every
     finding cites M4.
   - AC5 and AC6: re-run P.1546 for 5 random findings within 0.001 dB, run twice and check the JSON is
     byte-identical, and confirm no `score` key exists.
   - AC9: in 3077, terrakey 93081132 (RUS FB 168.025 MHz, Slantsy, h1 44 m, `pwr_dbw` 10) is `recorded`, REX
     favourable and first published in 3075, using only 3077's rows. Report its E and margin at the worst Finnish
     point, plus the Tier 1 bound.
   - AC2: the counts of `new`, `modified` and `withdrawn` per issue match the raw `intent` counts for the
     land-mobile selection.
3. **Hand cross-check.** For one finding, compute E by hand from the doc's parameters with the reference
   calculator (any independent P.1546 implementation, or the ITU curves at the nominal values), and note the
   agreement.
4. **Submission.** Run `ific terra-export t3076 --out submission/` to produce `terra-3076.{json,csv,md}`. Check
   the `submission` path against the space export location and use the same place. The Markdown report leads
   with the counts, the `exceeds` findings with evidence and the open questions.
5. **Full gates.** `mise run lint`, `mise run test` and `mise run build`.
6. **Close out.** Mark the plan and phase status as completed, and write the journal entry.

## Acceptance

All criteria 1–11 of the brainstorm contract are shown with evidence in the verify report. Any criterion that
cannot be met is reported as such, with the reason, and is not adjusted to pass.
