# Code review: pfd vs RR Table 21-4 check (uncommitted, main)

## Outcome

The change is in good shape and keeps the stated invariants. I found one real correctness bug that can turn an exceedance into `meets`: the notified `c_pfd` rescaling. There are also two medium design gaps (station-class matching of TT&C carriers, and ingest of `.mdb` files without `srv_cls`) and a handful of nits.

- Tests: `uv run pytest tests/test_riia_pfd.py tests/test_riia_pfd_limits.py tests/test_riia_assess.py -q` gave 58 passed. `bunx tsc -b --noEmit` is clean. `ruff check backend` is clean.
- The working tree changed while I was reviewing. `pfd.Emission.of` (the drop of an inconsistent `pwr_ds_max`), `Params.gain_offset_db` and the `pfd_peak_gain` low-end perturbation appeared mid-review. The findings below are against the tree at the end of the review.

## Invariants (verified)

- **No score.** No score or rank key was added. The chat rule was extended, and `pfd_outcome` is a separate summary field that does not feed `worst_outcome`.
- **Model version and seed.** `MODEL_VERSION` and the riia package init are untouched.
- **Hazard inputs.** In `assess._load_notices` the new code only adds `pfd_meta` and `pfd_emissions` before the existing `continue`. The `best`/`Grp`/`cpfd`/`has_mask` inputs to the hazards are unchanged, including the radio-astronomy `c_pfd` rows, which the hazards still use. `Geometry` only gains defaulted fields.
- **Reproducibility.** There is no randomness. All values are cast to Python floats or bools, and the check order is fixed by `sorted(buckets)`.
- **`as_of`.** The pfd fields are not touched by `_stamp`/`apply_as_of`.
- **`api.ts` mirrors `schemas.py`.** `PfdCheck` and `PfdCheckOut` match field for field, and `orbit` is `gso|ngso|es` on both sides. The summary fields are optional or null on both sides.
- **URL params.** `pfd` is validated in `router.tsx` against `PFD_FILTERS`, `RISK_SORT_RE` gained `pfd`, and `docs/frontend.md` is updated.
- **Backward compatibility.** Every reader of old payloads guards for missing pfd fields: `store.get_notice`, `consistency`, `review`, `sensitivity.compare_pfd`, `chat`, `technical_sort_key` (via `.get`, so old results sort last) and the frontend ("re-assess to compute").
- **Ingest manifest.** Ingest runs only on demand (`POST /api/risk/issues/{n}` prepare, and the CLI), not at startup. `manifest_filters()` is deterministic (sorted table list), so an existing DB reloads each issue exactly once, on its next assessment, and is `up_to_date` after that. No schema migration is needed: `space.issue.filters` already exists, and `srv_cls` is created on first load. `assess` guards a missing `space.srv_cls` with an `information_schema` check.
- **Formulas.** The pfd formula, the reference-bandwidth rule (`B_n < B_ref` uses the whole carrier power) and the NGSO slant range `√((R+h)² − R²cos²δ) − R sinδ` are correct. Independent hand checks in `test_riia_pfd.py` (spherical triangle for GSO, S.672 for the boresight, a 0.5° sweep for NGSO) agree to ±0.05 dB.
- **Table 21-4 spot checks.** I checked these rows against the RR from memory: 10.7–11.7 GSO (−150/−140 in 4 kHz), 10.7–11.7 and 11.7–12.5 non-GSO (−126/−116 and −124/−114 in 1 MHz), HEO 10.7–12.5 (−129/−114), 17.7–19.3 GSO (−115/−105), the X(N) of 21.16.6 (continuous at N = 288: 5/119·238 = 1/69·690 = 10), the −115 − X + (10 + X)(δ − 5)/20 encoding, 37.5–40 GSO (−127, then 4/3 per degree to −107 at 20°, −105 at 25°), 40.5–42 GSO (−120/−110 at 15°/−105), 6825–7075 (4 kHz and 1 MHz pairs), 1670–1700 (−133 in 1.5 MHz) and 5150–5216 (−164 in 4 kHz). All are consistent, and every row is continuous by construction (piecewise-linear points).

## Real bugs (ranked)

### 1. High: notified `c_pfd` rescaling ignores the carrier bandwidth and can hide an exceedance

**Where:** `backend/src/ific/riia/pfd.py` in `_evaluate`, the `if usable:` branch, which computes `pfd = c.pfd_dbw_m2 + 10*log10(row.ref_bw_hz / c.bw_hz)`.

**What is wrong:** The calculated path applies the Article 21 convention: when `B_n < B_ref`, the whole carrier counts. The notified path assumes the spectrum is flat over `B_cpfd` whatever the carrier width. The notified value also takes precedence over the calculated one.

**Failure scenario:** A GSO notice in 10.7–11.7 GHz (row reference bandwidth 4 kHz) notifies a pfd of −125 dB(W/m²) in 1 MHz for a 40 kHz carrier.
- The code rescales it to −149 in 4 kHz. The limit at δ ≈ 18° is about −143.5, so the margin is −5.5 dB and the check says `meets`.
- If the power is flat over the 40 kHz carrier, the real value in 4 kHz is −125 − 10 = −135. That is a margin of +8.5 dB, so the check should say `exceeds`.
- The calculated pfd, which may itself exceed, is only kept in `inputs`.

The reverse case (`B_cpfd < B_ref`, a narrow carrier) overstates the pfd by up to 10·log10(B_ref/B_n) and gives a false `exceeds`.

**Fix:** Rescale with `10*log10(min(B_ref, B_n) / min(B_cpfd, B_n))`, using the B_n of the group's strongest emission. When the calculated margin is above 0 but the notified one is not, set a reason such as "calculated pfd exceeds; notified pfd used". Better still, keep the worse of the two and record which one it was. Update the formula in the method doc's "Notified pfd" bullet to match. Add a fixture with `B_cpfd > B_n`.

## Medium

### 2. TT&C-only groups (ED/EK/ER) never match FSS, BSS or other rows

**Where:** `backend/src/ific/riia/pfd_limits.py`, the `SERVICE_CLASSES["so"]` mapping, together with `pfd._matches`.

**What is wrong:** RR No. 1.23 says space operation functions are normally provided within the service in which the space station operates.

**Failure scenario:** An FSS GSO satellite's telemetry beacon in 11.2 GHz, with `stn_cls = ER` only, matches no row, because the 10.7–11.7 rows list only `fss`. The group reports `not_applicable` ("no limit"), when the FSS limit applies.

**Fix:** For a group whose classes are all ED/EK/ER, also match rows of the services held by the notice's other groups. Otherwise, at least report `not_assessed` with the reason "TT&C carrier: service taken from the satellite's other groups". Product decision: see the questions at the end.

### 3. `.mdb` files without a `srv_cls` table can no longer be ingested at all

**Where:** `backend/src/ific/ingest.py`, the `TABLES` entry for `srv_cls`; `ensure_issue` exports every table.

**What is wrong:** `mdb_export` raises `IngestError` on a missing table, and the issue load is rolled back.

**Failure scenario:** An older or variant Space IFIC file that lacks `srv_cls` used to ingest. It now fails with 422 on assessment. Because the manifest changed, this hits on the one-time reload of an already-ingested issue whose file is still present.

**Fix:** Treat `srv_cls` (or any new table) as optional on export failure: log it and load zero rows. The groups then get the existing "No space-station class" `not_assessed`. Confirm whether every 2026 Space IFIC carries the table.

### 4. Sensitivity: the `cpfd_min_delta` perturbation is labelled the wrong end

**Where:** `backend/src/ific/riia/sensitivity.py`, the `PFD_PERTURBATIONS` entry for `cpfd_min_delta`.

**What is wrong:** The entry is labelled `end="high"`. Comparing at the highest δ is the less strict reading for every δ-increasing row, so it is the low or lenient end.

**Fix:** Rename it to `"low"`. The flip counting is unaffected.

### 5. Sensitivity: `pfd_near_db` 3→6 dB is counted as outcome-sensitive

**Where:** `backend/src/ific/riia/sensitivity.py`.

**What is wrong:** Moving `pfd_near_db` from 3 to 6 dB "flips" any notice with a margin in [−6, −3) by definition, so `pfd_near_db` will almost always be flagged outcome-sensitive. `store.get_notice` then marks it on every evaluated check. It is a display threshold, not an input to the outcome.

**Fix:** Count only `exceeds` flips for the pfd perturbations, or report near-limit changes separately. The doc currently states the broader rule, so this is a choice to confirm rather than a contradiction.

## Low

### 6. The doc and the code disagree on how `_collapse` groups checks

**Where:** `pfd._collapse` and the method doc's "Outcomes" paragraph.

**What is wrong:** The doc says checks that share "a row and an outcome" are reported as one. The code buckets all evaluated checks of a row together, `exceeds` and `meets` alike, keeping the worst and counting `n_groups_exceeding`. The code is the better behaviour, but the doc says otherwise. The `reason` of the non-worst evaluated groups (for example "notified pfd without reference bandwidth") is dropped.

**Fix:** Align the doc sentence ("one evaluated check per row, the worst group, with counts").

### 7. `load_limits` is cached for the life of the process

**Where:** `pfd_limits.load_limits`, `@cache`.

**What is wrong:** After an edit to `rr21_pfd_limits.json`, a running API keeps the old rows and the old sha256 until a restart. The other reference data is re-checked by sha at startup only, so this is consistent, but say so in the doc next to the sha256 sentence.

### 8. A bug in the pfd code is recorded as an ordinary `not_assessed`

**Where:** The broad `except Exception` in `assess.pfd_results`.

**What is wrong:** A code bug turns into a quiet `not_assessed` "pfd check failed: …".

**Fix:** Add an assertion in `test_riia_assess` that no fixture notice carries that reason.

### 9. The frontend reading can hide a `not_assessed` behind "near"

**Where:** `risk-meta.pfdReading`.

**What is wrong:** It returns `near` before `not_assessed`. A notice whose `pfd_outcome` is `not_assessed` (one row unencoded) but has a near-limit row shows "near" and hides the gap.

**Fix:** Either check order is defensible; consider showing both.

### 10. The "Has a Table 21-4 limit" filter is mislabelled

**Where:** The `any_limit` filter in `risk-meta`.

**What is wrong:** It matches `max_pfd_margin_db != null`. Notices with a matching but unencoded row are excluded.

**Fix:** Relabel it "Evaluated against a Table 21-4 limit".

### 11. The gain fallback is not recorded as an assumption

**Where:** `assess._load_notices`, the `notice_gain` fallback (`pfd_meta` loop).

**What is wrong:** A group without a beam gain silently takes the notice's maximum gain. This is the existing riia-1 behaviour, but the pfd check reports it as "Satellite peak gain … space.s_beam.gain" with no assumption.

**Fix:** Add an assumption id for the fallback.

### 12. HEO is decided on the selected orbit set only

**Where:** `Geometry.heo` and `min_alt_km` (`assess._load_geometry`).

**What is wrong:** Both are computed from the selected orbit set only (the one with the most satellites). That matches the hazards, but a mixed system with a small HEO set is classed non-HEO. This is acceptable; worth one line in the doc.

## Not issues (checked)

- **GSO tolerance edges.** `dict.fromkeys` removes duplicate edges when the tolerance is 0. `look_angles` indexes correctly for one satellite (`flatnonzero` on shape (N, 1)).
- **NGSO reach.** Reach uses the apogee radius and the range uses the perigee altitude. Both are conservative and named by `pfd_lowest_altitude`.
- **Constellation size limits.** The `n_sats_max` and X(N) range give `not_assessed` correctly, and `N = 999` is still in range.
- **Review ordering.** Group P sorts first, by −`max_pfd_margin_db`. `pfd_lines` only takes evaluated checks, so `margin_db` is never None there.
- **Units.** `c_pfd.bdwdth` is converted from kHz to Hz, `mask_info` from GHz to Hz, and `grp`/`c_pfd` frequencies from MHz to Hz. Radio-astronomy `c_pfd` rows are excluded from `pfd_notified` only.

## Unresolved questions

1. Should TT&C classes inherit the satellite's service (finding 2)? This needs a domain decision.
2. Do all Space IFIC `.mdb` editions carry `srv_cls` (finding 3)?
3. The 13.4–13.65 GHz GSO row has points (0, −159), (25, −149), (80, −149), (84, −151), (90, −151) with no 5° breakpoint. I could not confirm these from memory; they need a check against RR p. 29x at sign-off. The 17.7–19.7 GHz HEO points (3° and 12° breakpoints, 21.16.6B) need the same check.
4. Is "notified takes precedence" still wanted once finding 1 is fixed, or should the check keep the worse of the notified and calculated values?

Status: DONE_WITH_CONCERNS
Summary: The invariants hold, the pfd, bandwidth and slant-range formulas and the Table 21-4 spot checks are right, and the targeted tests and type-check pass. One real bug: the notified `c_pfd` rescaling ignores the carrier bandwidth and can report `meets` for a real exceedance. Medium: TT&C-only groups never match their satellite's service rows, and `.mdb` files without `srv_cls` would now fail to ingest.
