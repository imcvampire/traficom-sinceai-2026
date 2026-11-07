---
phase: 05
title: /risk UI
status: completed
depends_on: [04]
effort: 3h
---

# Phase 05: `/risk` UI

## Requirements

- **api.ts**: mirror `PfdCheckOut` and the new summary/detail fields from `schemas.py`.
- **Table (`risk-table.tsx`)**: column "pfd vs Art. 21" showing `max_pfd_margin_db` with sign and unit
  (`+4.2 dB`), coloured by `pfd_outcome` using the status tokens (exceeds / near / meets); `not_applicable` shows
  "no limit" muted; `null` shows "re-assess". Sortable. Include it in the CSV export (`lib/csv.ts`, the
  uncommitted CSV work), as `pfd_outcome` and `max_pfd_margin_db`.
- **Filter**: URL search param `pfd` ∈ `exceeds | near | any_limit`, validated in `router.tsx` `validateSearch`
  (invalid values dropped), wired in `pages/risk.tsx`.
- **Notice sheet (`notice-sheet.tsx`)**: section "pfd limits (RR Art. 21, Table 21-4)" above the hazard inventory: a
  table with group, band, service, row, B_ref, pfd, limit, δ, margin, source, outcome; expandable inputs,
  citations and assumptions like `hazard-inventory.tsx`. A banner "Table 21-4 transcription: review pending" while
  the file's review status is pending.
- **risk-meta.ts**: labels and `TermHint` texts for pfd, reference bandwidth, δ (angle of arrival), margin.
- **risk-chart.tsx**: axis label → "Consequence x (dB): I/N, or spfd margin for radio astronomy", so nobody reads
  this chart as the Article 21 check.
- **docs/frontend.md**: add `pfd` to the `/risk` params.

## Files

| Action | Path |
|---|---|
| modify | `frontend/src/lib/api.ts`, `frontend/src/router.tsx`, `frontend/src/pages/risk.tsx` |
| modify | `frontend/src/components/risk-table.tsx`, `notice-sheet.tsx`, `risk-meta.ts`, `risk-chart.tsx` |
| modify | `frontend/src/lib/csv.ts` |
| modify | `docs/frontend.md` |

## Validation

- `cd frontend && bunx tsc -b --noEmit` and `mise run lint`.
- `mise run build`.
- Manual check with `mise run dev` (stop any stale server on :8000/:5173 first): 3074 table sorts and filters by
  pfd; `?pfd=bogus` is dropped; notice sheet shows the section for a notice with checks and "re-assess" for an
  old payload.
