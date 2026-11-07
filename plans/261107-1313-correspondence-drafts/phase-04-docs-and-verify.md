---
phase: 4
title: "Docs and verification"
status: completed
priority: P2
effort: "1.5h"
dependencies: [3]
---

# Phase 4: Docs and verification

## Goal

Document the draft feature where its users and maintainers look, and run the release gates.

## Files to Create / Modify

- Modify: `docs/interference-risk-assessment.md` (new section "Draft correspondence" after "Concern triage for
  manual review")
- Modify: `docs/frontend.md` (`draft` param on `/risk`)
- Modify: `README.md` (CLI table: `ific draft`; API mention of the two routes if the README lists routes)
- Modify: `CLAUDE.md` only if a new invariant needs stating (the LLM-polish guard and "no station data in the
  letter" are candidates)

## Tasks & Steps

1. Method doc: the four kinds and the rule that picks them (a table quoting the `rr_comment_windows.json` cites),
   what the annex contains and where its numbers come from, what stays in reviewer notes and why, the polish
   guard, and that drafts are not stored. Note the non-goals (AP30 plan letters, no-objection replies).
2. Frontend doc: `draft` (`1` or absent), opened from the notice sheet, cleared with `ntc`.
3. README: `ific draft ISSUE --as-of YYYY-MM-DD [--ntc N] [--out DIR]` with its purpose, and whether it needs the
   server stopped.
4. Generate drafts for a real issue (`ific draft 3074 --as-of 2026-11-06`) and read two of each kind that occurs,
   checking provisions and numbers against the notice in the UI. Record any wording problems as plan follow-ups;
   do not commit the generated drafts.

## Verification

- `mise run lint`
- `mise run test`
- `mise run build`
- Links in the edited docs resolve; every claim in the new method-doc section matches `draft.py`.
- Compare the result with the plan's acceptance criteria 1–8 before marking the plan completed.
