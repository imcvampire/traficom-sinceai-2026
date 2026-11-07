---
phase: 05
title: Docs + whole-flow verification
status: completed
depends_on: [03, 04]
---

# Phase 05: Docs and verification

## Steps

1. Update `docs/interference-risk-assessment.md` (written as a proposal before implementation) from proposal to
   implemented.
   - Check the receiver classes, criteria and inputs one for one against `GET /api/risk/model`.
   - Add the outcome-sensitive assumptions and the BR-finding agreement from the phase 03 reports.
   - Add the API table, the CLI, the job behaviour and the measured run time.
   - Explain how to bump `MODEL_VERSION`, and that a bump requires re-assessment.
2. Update `docs/frontend.md` with the `/risk` route and its params. Update `docs/source-watcher.md` with one line
   noting that downloaded issues appear in the risk page's issue picker.
3. Run `ripwire backend --quality-delta --legend=compact`, then `--test-gate --legend=compact`.
4. Run `mise run lint`, `mise run test` and `mise run build`.
5. Do a fresh-DB end-to-end check:
   - back up and then remove `var/db/ific.duckdb`;
   - start `mise run dev`;
   - assess 3074 from the UI;
   - compare the summaries with `fixtures/riia/3074-summary.json`;
   - stop the servers.
6. Walk through acceptance criteria 1–9 in `plan.md`, and mark each phase `completed`.
