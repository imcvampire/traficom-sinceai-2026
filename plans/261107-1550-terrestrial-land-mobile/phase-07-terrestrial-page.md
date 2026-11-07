---
phase: 7
title: "/terrestrial page"
status: done
priority: P1
effort: "6h"
dependencies: [4, 5]
---

# Phase 7: `/terrestrial` page

## Goal

This phase adds a new route for expert review of one terrestrial issue. It has a findings table, an evidence
sheet, a map, a trends panel and the draft letter. `/risk` and its components are not modified.

## Files

- Modify: `frontend/src/router.tsx`. Add `terrestrialRoute` with `validateSearch`, a nav entry in
  `app-shell.tsx` and an overview card if the overview lists the pages.
- Modify: `frontend/src/lib/api.ts`. Add the `Terra*` types, mirrored from `backend/src/ific/terra/schemas.py`.
- Modify: `frontend/src/lib/queries.ts`. Add the terrestrial query options and mutations (assess, polish).
- Create: `frontend/src/pages/terrestrial.tsx`
- Create: `frontend/src/components/terra-table.tsx`, `terra-sheet.tsx`, `terra-map.tsx`, `terra-trends.tsx`,
  `terra-draft.tsx`, `terra-meta.ts`
- Read or import only: `term-hint.tsx`, `outcome-badge.tsx`, `status-badge.tsx`, `station-map.tsx` (its layers and
  basemap; extend it by composition, not by editing it), `notice-draft.tsx` (its layout idiom), `ui/*`
- Modify: `docs/frontend.md`, documenting the `/terrestrial` URL params

## URL params (validated, invalid values dropped)

| Param | Type | Notes |
|---|---|---|
| `issue` | int | default: the latest assessed issue |
| `outcome` | `exceeds`, `meets`, `screened_out`, `not_applicable` or `not_assessed`, as a list | |
| `adm` | string list | |
| `change` | `new`, `modified` or `withdrawn` | |
| `status` | `received`, `recorded` or `returned` | |
| `relevant` | `true` (default) or `all` | `all` shows the non-relevant rows for false-positive review |
| `criterion` | criterion id | |
| `q` | string | matches `adm_ref_id`, site name or frequency |
| `ntc` | terrakey | opens the sheet |
| `tab` | `findings`, `map` or `trends` | |
| `trend_issues` | int list | the issues summed in the trends panel |
| `draft` | adm code | opens the draft panel |

## Steps

1. **Header.** An issue picker, the assessment status and an "Assess" button (POST, poll the job, 409-aware). The
   model version and a criteria list with an "unverified" badge come from `/model`.
2. **Table.** This uses the server's sort order and adds no client-side ranking. Its columns are:
   - outcome badge and margin (dB);
   - administration and `adm_ref_id`;
   - class, notice type, change and publication status;
   - f (MHz), bandwidth, e.r.p. and h1;
   - criterion, with the `indicative` chip for RUS;
   - FIN coordination status and distance to Finland.
3. **Sheet**, for one assignment:
   - the source notice fields with source tags, and the MODIFY diff;
   - the relevance signals;
   - the regulatory context with citations (RR, GE06, ECC, M4, bilateral);
   - the Tier 1 bound;
   - the Tier 2 worst point, the path segments, the parameters table and the P.1546 intermediates (collapsible);
   - the assumptions, with their ids and text.
4. **Map.** Relevant TX sites are coloured by outcome. Selecting one draws a line to its worst Finnish point with
   E labelled. An `exceeds` site also shows its border point.
5. **Trends.** Small multiples by band, distance bin, class and bandwidth for the neighbour administrations, plus
   the anomaly list with links to the rows. They use the `--series-1..5` tokens, and the status tokens are kept
   for outcomes only.
6. **Draft.** A per-administration letter view with the banner, a polish button and the rejection reason when the
   polish guard trips.

## Validation

```sh
cd frontend && bunx tsc -b --noEmit && bunx oxlint
mise run build
```

Then a manual run in the browser against real 3076 data (the `run` skill):

- the filters round-trip through the URL;
- an invalid param is dropped;
- the sheet shows the P.1546 parameters;
- the RUS draft opens;
- `/risk` still renders as before.
