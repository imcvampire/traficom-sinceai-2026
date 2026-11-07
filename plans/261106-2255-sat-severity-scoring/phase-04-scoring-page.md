---
phase: 04
title: /risk demo page
status: completed
depends_on: [03]
---

# Phase 04: `/risk` page

## Context

Follow `docs/frontend.md`:

- shadcn/ui components;
- TanStack Query (`src/lib/queries.ts`);
- code-based TanStack Router, with filters in URL search params;
- TanStack Table, with memoised state;
- status tokens always paired with an icon and a label.

Load the `dataviz` skill before writing the likelihood–consequence chart. Load `ak-frontend-design` for the layout
pass.

## Requirements

### Route and navigation

- Route `/risk` with `validateSearch` for these params. Invalid values are dropped, as in `sourcesRoute`.
  - `ific` (int);
  - `view` (`queue|technical`, default `queue`);
  - `outcome` (`exceeds|meets|screened_out|not_applicable|not_assessed`);
  - `service`, `adm`, `prov`, `orbit` (`gso|ngso|es`), `q`, `sort`;
  - `ntc` (opens the detail sheet);
  - `compare` (a comma-separated `ntc_id` list).
- Sidebar navigation entry: "Interference risk", in `app-shell.tsx`.

### Header

- An issue picker showing each issue's assessed state and job progress, with an **Assess** or **Re-assess** button.
  - The button is disabled while a job runs, and a progress bar polls the job every 3 seconds.
  - A 409 response shows a toast.
- The model version and `as_of`.
- A receiver-source badge: "Generic population (M4 × grid over Finland)".
- A "Method" popover. It shows the four steps with their source quotes and the reference list, both from
  `/api/risk/model`, and links to `docs/interference-risk-assessment.md`.

### Summary row

- Notice counts per worst outcome.
- Notices in the work queue.
- Notices for which the BR identified Finland.
- The Finnish services with at least one `exceeds` hazard.

### Notice table

The table follows the active view's order.

- Columns:
  - outcome badge (icon and label);
  - satellite network, administration, provision (API/CR/N) and orbit type;
  - services affected;
  - `share_violating` (percentage);
  - worst `exceedance_db`;
  - days left in the comment window (`closed` once past);
  - a "BR: FIN identified" badge.
- Checkboxes select notices for the compare view.
- The table never shows a composite score.

### Detail sheet

The detail sheet opens from `ntc` in the URL, so it can be shared.

- **Likelihood–consequence chart.**
  - Consequence (dB) on the x axis, likelihood on the y axis (a log scale is allowed, from 0.01% to 100%).
  - One curve per hazard and criterion percentage, coloured by hazard mode.
  - The criterion points `(level, time %)` are drawn as markers, and the region beyond each point is shaded as
    "exceeds criterion".
  - Tier 1 worst-case values are drawn as dashed vertical lines.
- **Hazard inventory table.**
  - It lists every mode, including the `not_assessed` and `screened_out` ones, each with its reason.
  - Columns: mode, service, band, tier, outcome, `share_violating`, `exceedance_db` (median and 95th percentile),
    `worst_case_db`.
- **Expandable inputs per hazard:** values with source tags, citations (M4 rows, ITU-R Recommendations, RR
  provisions) and assumptions. Outcome-sensitive assumptions from the sensitivity report are highlighted.
- **Regulatory context:** stage, days left with the RR No. 9.52 citation, and the `provn`/`tr_aff_ntw` rows.
- The label "Risk-informed screening, not an ITU examination".

### Compare view

- It overlays the main curve of each selected notice on one chart.
- It shows a "curves cross" note whenever no curve lies above all the others everywhere.

### States and layout

- Empty, loading (skeleton) and error states.
- Light and dark mode.
- Phone width: the table and the chart scroll inside their cards, and the page does not scroll sideways.

## Files

| Action | Path |
|---|---|
| modify | `frontend/src/lib/api.ts`: types and client for `/api/risk/*` |
| modify | `frontend/src/lib/queries.ts`: query options, the assess mutation, and job polling |
| modify | `frontend/src/router.tsx`: `riskRoute` |
| modify | `frontend/src/components/app-shell.tsx`: navigation item |
| create | `frontend/src/pages/risk.tsx` |
| create | `frontend/src/components/risk-table.tsx`, `risk-chart.tsx`, `hazard-inventory.tsx`, `outcome-badge.tsx` |
| modify | `frontend/src/index.css`, only if a token is missing. Reuse the `status-*` tokens: `exceeds` = critical, `not_assessed` = warning, `meets` = good, `screened_out` and `not_applicable` = neutral. |

## Validation

- `bun run --cwd frontend lint` and `bun run --cwd frontend build` are clean.
- Browser check (the `run` skill or `ak-agent-browser`), with the API running and 3074 assessed:
  - Assess shows progress and then the results;
  - a second click returns 409 and shows the toast;
  - URL filters round-trip on reload;
  - a deep link opens the detail sheet;
  - the chart shows the curves and criterion markers;
  - compare works;
  - dark mode works;
  - a 390 px width has no horizontal scroll.
- Stop the dev servers started for the check.
