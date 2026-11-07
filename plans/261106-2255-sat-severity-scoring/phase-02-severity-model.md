---
phase: 02
title: RIIA engine — receiver populations, hazard inventory, tiers and Monte Carlo (riia-1)
status: completed
depends_on: [01]
---

# Phase 02: RIIA engine

## Context

The method is specified in [`docs/interference-risk-assessment.md`](../../docs/interference-risk-assessment.md). That
doc is the single source for the formulas, tiers, criteria handling and outputs.

This phase builds the engine with the **generic** population. The stations population is a follow-up, and this phase
only keeps the seam clean.

Add `numpy` as a dependency: it is needed for vectorised Monte Carlo and orbit propagation. Do not add SciPy.

## Requirements

### Receiver populations

- `Receiver(id, source, service_class, lat, lon, height_m, f_lo_hz, f_hi_hz, bw_hz, azimuth_deg | None,
  pointing_elev_deg | None, gain_dbi | None, nf_db | None, acs | None, assumptions[], citation[])`.
  - A `None` field is drawn from the class distribution during sampling, and the draw is recorded as an assumption.
- `ReceiverPopulation` is a protocol with `name` and `receivers(con) -> list[Receiver]`.
- `GenericM4Population`:
  - one receiver per protected M4 sub-band × grid cell;
  - grid of 0.25° × 0.5° inside `data/ref/finland_land.geojson`. That file is derived from Natural Earth 1:50m
    (public domain) and records its source in its properties.
  - The service class is matched by an ordered keyword table on `services_in_finland`, and the match is cited.
- `data/ref/receiver_classes.json` holds, for each class, and every value carries a `cite`:
  - criterion points `[{metric, level, time_pct, cite}]`;
  - pattern id;
  - reference gain, noise figure and adjacent-channel selectivity;
  - minimum elevation;
  - distributions for azimuth, height and elevation pointing.

### Hazard inventory (Tier 0)

- For each notice, hazards are listed per (mode, service-class population). The mode set comes from the doc.
- Co-channel and adjacent-band hazards are enumerated by one DuckDB range join between space→Earth `ific.grp` and
  the population bands. Adjacent band means the downlink lies inside the out-of-band or spurious domain of the
  receiver band.
- The earth-station terrestrial path, blocking and intermodulation, and cross-network aggregation modes are always
  listed, with outcome `not_assessed` and a reason.
- `not_applicable` means no overlap, or the satellite is never above the horizon anywhere in the population.

### Tier 1: deterministic worst case

- Each parameter takes its worst value:
  - minimum slant range;
  - receiver main beam toward the satellite;
  - peak satellite gain;
  - maximum `pep_max`.
- If the result is below the lowest criterion level of the service, the outcome is `screened_out`, and
  `worst_case_db` is stored.

### Tier 2: Monte Carlo

- RNG: numpy `PCG64`, seeded from the sha256 of `(model_version, ific_no, ntc_id, hazard_id)`.
- N = max(10⁴, ⌈100/p_min⌉), capped at 10⁶, where p_min is the smallest criterion time percentage of the class.
- Sampling covers receivers in the population, time, and uncertain parameters:
  - **non-GSO time:** circular-orbit Walker-style propagation from `orbit`, with Earth rotation, sampled uniformly
    over the repeat pattern;
  - **GSO:** position within `tol_east`/`tol_west`.
- I sums over all satellites in view for each sample. The pfd uses `c_pfd`/`mask_info` when notified, otherwise
  `pep_max` + S.672 (GSO with boresight) or peak gain (otherwise, marked as an assumption).
- Per receiver: the time-exceedance curve `F_r`. Per criterion percentage *p*: `X_r(p)` and the population risk curve
  `L_p(x)` on the fixed −40…+40 dB grid.
- Outputs per hazard:
  - outcome, `share_violating`;
  - `exceedance_db` per criterion point (median and 95th percentile across the population);
  - risk curves and `worst_case_db`;
  - inputs (source-tagged), citations and assumptions.

### Notice result and sorting

- `NoticeAssessment` has these fields:
  - `ific_no`, `ntc_id`, `sat_name`, `adm`, `prov`, `ntc_type`, `act_code`;
  - `receiver_source` and `model_version`;
  - `hazards[]`;
  - `summary`: worst outcome, services affected, max `share_violating`, max median `exceedance_db`;
  - `regulatory`: stage, `days_left`, `fin_identified` and citations;
  - `as_of`.

  It has **no composite score field**.
- A suppression (`act_code = 'S'`) is still inventoried. Its hazards are `not_applicable` with the reason "suppressed".
- The sort key function follows the doc exactly, and the doc's wording is quoted in its docstring.
- The regulatory context uses `as_of: date` explicitly. There is no hidden `today()`.

## Files

| Action | Path |
|---|---|
| modify | `backend/pyproject.toml`: add `numpy` |
| create | `backend/src/ific/riia/__init__.py` |
| create | `backend/src/ific/riia/geometry.py`: elevation, azimuth, slant range, off-axis angle, haversine, point-in-polygon |
| create | `backend/src/ific/riia/orbits.py`: GSO position, circular-orbit constellation positions (vectorised) |
| create | `backend/src/ific/riia/antenna.py`: F.1245, F.699, BT.419, RA.1631, S.672 and omnidirectional |
| create | `backend/src/ific/riia/emission.py`: SM.1541 out-of-band mask, RR Appendix 3 spurious limit, receiver selectivity |
| create | `backend/src/ific/riia/receivers.py`: `Receiver`, `ReceiverPopulation`, `GenericM4Population` |
| create | `backend/src/ific/riia/hazards.py`: inventory (Tier 0), worst case (Tier 1), Monte Carlo (Tier 2) |
| create | `backend/src/ific/riia/curves.py`: CCDF, quantiles, population risk curve, criterion check |
| create | `backend/src/ific/riia/regulatory.py`: stage, days left, Finland identified |
| create | `backend/src/ific/riia/assess.py`: `assess_issue(con, ific_no, as_of, population, overrides=None, progress=None) -> list[NoticeAssessment]` |
| create | `data/ref/receiver_classes.json`, `data/ref/rr_comment_windows.json`, `data/ref/rr21_pfd_limits.json` (context only), `data/ref/finland_land.geojson` |
| create | `backend/tests/test_riia_geometry.py`, `test_riia_orbits.py`, `test_riia_antenna.py`, `test_riia_emission.py`, `test_riia_curves.py`, `test_riia_hazards.py`, `test_riia_assess.py` |

## Steps

1. Run `ripwire backend --exemplar="pure geometry helper" --legend=compact` to avoid duplicating existing helpers.
2. Write the geometry and orbit tests first:
   - a GSO at 25°E seen from Helsinki has about 21.8° elevation and about 180° azimuth;
   - slant range at 0° elevation is about 41,679 km;
   - a polar circular orbit visits latitude ±89°, and an equatorial one never leaves 0°;
   - positions are identical across runs.
3. Antenna and emission tests:
   - boresight gain equals the reference gain;
   - each pattern decreases monotonically to its floor;
   - values match each Recommendation's formulas at 2–3 hand-checked angles and offsets.
4. Curve tests:
   - the CCDF of a known sample set;
   - `X_r(p)` interpolation;
   - `L_p(x)` on a hand-built population;
   - violation logic at the criterion boundary (equal to the limit is not a violation).
5. Transcribe `receiver_classes.json` from the cited Recommendations, and have a person review it. A test asserts that
   every value has a `cite`, and that every distribution is tagged `assumption`.
6. Implement Tiers 0–2.
   - Test that Tier 1 ≥ Tier 2 max on randomised fixtures, using a fixed seed.
   - Test that the `not_assessed` modes are always present.
   - Test that suppression gives `not_applicable`.
7. Seam test: a fake `ReceiverPopulation` with two hand-built stations goes through `assess_issue` unchanged.
8. Performance:
   - satellite positions are computed once per time sample and broadcast across sites;
   - visibility is cached per (notice, site);
   - `progress(done, total)` is called per notice;
   - the 3074 run time is measured and logged.

## Validation

- `uv run pytest -q tests/test_riia_*.py` passes.
- `ruff check` and `ruff format --check` are clean.
- Running `assess_issue` on 3074 with the generic population stays within the 15-minute budget, and the measured
  time is recorded in the phase 03 report.

## Risks

- **`emi_rcp` semantics** differ between space-station and earth-station notices. Assert the direction mapping using
  one GSO notice and one earth-station notice from the fixtures.
- **Elliptical orbits:** the circular model uses the apogee altitude, and the result carries an assumption.
- **Missing orbit data:** 10 of 110 non-GSO notices in 3074 have none. Their hazards stop at Tier 1. If Tier 1 does
  not screen them out, the outcome is `not_assessed`, with the reason "Tier 2 not possible: orbit missing" and the
  worst-case value shown. A worst case alone is never reported as `exceeds`.
