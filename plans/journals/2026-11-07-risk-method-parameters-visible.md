# Risk page: assumptions and model parameters made visible

Date: 2026-11-07 15:17 (Europe/Helsinki)

## Check

The question was whether `/risk` shows its assumptions and model parameters. For a single notice it did. The notice
sheet lists each hazard's assumptions, with outcome-sensitive ones flagged, along with its inputs (value, unit,
source tag, citation), protection criteria, receiver and sample counts, and the pfd-check assumptions.

The model-wide view did not. `/api/risk/model` already returned the receiver classes (gain, noise figure, bandwidth,
pattern, criteria, Monte Carlo distributions), the input list with its 27 named assumptions, the outcome-sensitive ids
and the curve grid. The Method popover rendered only the method steps and references. The page used
`receiver_classes` for service labels and nothing else. Adjacent-channel selectivity, minimum elevation and the
citation for each characteristic were held in `ReceiverClass` but the API did not return them.

## Change

- `ReceiverClassOut` and `method.describe` now include `acs_db`, `min_elev_deg` and `cites`. `test_model_endpoint`
  asserts them.
- The Method popover is replaced by a "Method & parameters" sheet (`components/risk-method.tsx`). It shows the method
  steps, the model settings (version and RNG seed role, population, curve grid), every assumption with the
  outcome-sensitive ones highlighted, each receiver class with cited characteristics, criteria and distributions,
  then the input sources and references.
- `docs/frontend.md` is updated.

## Notes

- The sheet's open state is local, as the popover's was, and is not a URL param.
- On the current DB `outcome_sensitive` is empty, so no assumption is highlighted. The highlight only appears after a
  sensitivity run has stored results.
