# Phase 04 `/risk` page: implementation report

Status: completed against the pinned contract. `bun run --cwd frontend lint` and `bun run --cwd frontend build` pass
cleanly. I did not run a browser check, because that was out of scope.

## Files

Modified:

- `frontend/src/lib/api.ts`: the risk types, copied from `api-contract.md` (the contract's `Input` is renamed
  `HazardInput`, because the UI already has an `Input` component), and the clients for `/api/risk/issues`, POST
  assess, notices, notice detail and model.
- `frontend/src/lib/queries.ts`:
  - `riskIssuesQuery` refetches every 3 s while any job is `running`, and every 15 s otherwise.
  - `riskModelQuery`.
  - `riskNoticesQuery` and `riskNoticeQuery`. Their key includes `assessed_at`, so the results refresh after a
    re-assess.
  - `useAssessIssue`: a 409 shows a warning toast and any other error shows an error toast.
- `frontend/src/router.tsx`: `riskRoute`, with `validateSearch` for `ific`, `view`, `outcome`, `service`, `adm`,
  `prov`, `orbit`, `q`, `sort`, `ntc`, `compare` and `as_of`. Invalid values are dropped. `as_of` must be a real
  YYYY-MM-DD date.
- `frontend/src/components/app-shell.tsx`: the "Interference risk" navigation item and page title.
- `frontend/src/index.css`: added the `--series-1..5` categorical chart tokens for light and dark. The existing
  `chart-*` tokens are greys, and the status hues are reserved for state.

Created:

- `frontend/src/pages/risk.tsx`
- `frontend/src/components/risk-table.tsx`
- `frontend/src/components/risk-chart.tsx`
- `frontend/src/components/hazard-inventory.tsx`
- `frontend/src/components/outcome-badge.tsx`
- `frontend/src/components/notice-sheet.tsx`
- `frontend/src/components/risk-compare.tsx`
- `frontend/src/components/risk-header.tsx`
- `frontend/src/components/risk-meta.ts`: outcome and mode metadata, formatters, `likelihoodAt`, `mainCurve` and
  `hasDominantCurve`.
- shadcn `ui/checkbox`, `ui/popover`, `ui/select` and `ui/collapsible`. No npm dependency changed.

## Decisions

- **Chart.** A hand-rolled SVG whose width is measured with a ResizeObserver.
  - It has a minimum width of 520 px and scrolls inside its card.
  - The y axis is log scale from 0.01% to 100%. A curve that falls below the floor drops to the bottom edge and stops.
  - Curves are coloured by hazard mode. A hazard's second and later criterion time % are dotted.
  - Each criterion has a vertical line and an "exceeds criterion" shaded region. Its point marker sits at
    `L_p(level)`, linearly interpolated, and is hollow when the value is below 0.01%.
  - Tier 1 `worst_case_db` values are dashed verticals.
  - Hovering shows the value of every curve at that x.
- **Hazards without curves.** If they have a `worst_case_db`, the chart still draws their criterion lines and dashed
  worst-case line, but no point marker.
- **Compare view.** Each notice's curve is its worst quantified hazard (ranked by outcome order, then share violating,
  then median exceedance) at the criterion time % with the largest share violating. It falls back to the first curve.
  - The "Curves cross" alert appears when no curve is greater than or equal to all the others at every grid point.
  - Notices without a quantified hazard are listed as not drawn.
- **Work queue.** The view uses the API's `view=queue`. The summary row always reads from the technical list.
  - When the queue is empty, the table explains why and offers two buttons: "As of <earliest d_wic>" and "Show all
    notices".
  - `as_of` defaults to today in local time and is kept out of the URL when it equals today.
- **Table order.** With no `sort` in the URL, the table keeps the server's order for the active view. Header sorting
  writes `sort`, and clearing it returns to the server order.
- **Days left.** A null value shows "—" and a past or closed window shows "closed".
- **Outcome-sensitive assumptions.** An assumption is highlighted when `assumption.sensitive` is set or its id is in
  `model.outcome_sensitive`.
- **No composite score.** None is displayed anywhere.

## Not done / notes

- I did not run a browser check (the controller does it) or verify against a live API. The phase file's status was
  left untouched because the file is outside my ownership.
- The `dataviz` skill is not installed in this runtime, so I applied standard chart practice instead: log axis with
  decade ticks, a categorical palette that avoids the status hues, a legend and a tooltip.
- `ak-frontend-design` was read. I took the "preserve existing UI" route and followed the existing tokens and
  components. The render-check script was not run, because a browser check was excluded.
- Vite's chunk-size warning (over 500 kB) is still reported. It is a warning, not an error.

## Unresolved questions

- `Hazard.worst_case_db` is drawn on the same x axis as `level_db`, which treats it as an absolute I/N or pfd-margin
  value. The contract comments are ambiguous: `NoticeSummary.max_worst_case_db` says "relative to the class criterion
  level". If the backend emits relative values, the dashed lines need `+ level_db`.
