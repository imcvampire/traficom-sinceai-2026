---
phase: 3
title: "Assessment model terra-1"
status: done
priority: P1
effort: "6h"
dependencies: [1, 2]
---

# Phase 3: Assessment model `terra-1`

## Goal

`assess_issue(con, ific_no) -> list[dict]` is a pure function of one issue's `terra` rows and the reference data.
It produces one result per foreign land-mobile assignment, with deterministic outcomes, readings, assumptions and
citations, and no score.

## Files

- Create: `backend/src/ific/terra/inventory.py`, `relevance.py`, `regulatory.py`, `hazards.py`, `assess.py`,
  `method.py` (`MODEL_VERSION = "terra-1"` and the assumption ids)
- Read only: `backend/src/ific/propagation/p1546.py`, `tr2508.py`, `riia/schemas.py` (the outcome literal),
  `riia/assess.py` (sort-key and assumption idioms)
- Create: `backend/tests/test_terra_inventory.py`, `test_terra_relevance.py`, `test_terra_hazards.py`,
  `test_terra_assess.py`

## Steps

1. **Outcome type.** Import the outcome literal from `riia.schemas`. If importing it would pull in space-only
   modules, move only the literal into `ific/outcomes.py` and re-export it from `riia.schemas`; the
   `riia.schemas` public names stay identical.
2. **Inventory** (`inventory.py`).
   - **Selection.** Land mobile means a station class whose `ref_stn_cls_nat_srv` row maps to the land mobile
     service, joined from this issue's own code table and cited as `"<ific_no>:ref_stn_cls_nat_srv"`. Exclude
     `adm = 'FIN'` and `intent = 'RECORDED'`; RECORDED rows are before-states, not assignments.
   - **`change`.** `intent` gives `ADD` → `new`, `MODIFY` → `modified` and `SUPPRESS` → `withdrawn`. A
     `modified` row gets a `diff` listing every changed field against its `fxm_target` RECORDED row, covering the
     `fxm_terra` fields, `fxm_ant` power and height, and `fxm_geo` site. A missing target gives `diff: null` with
     the reason `target_not_in_issue`.
   - **`pub_status`.** This comes from this issue's own `fxm_pub_hist` row: part 1 → `received`, part 2 →
     `recorded`, part 3 → `returned`. It carries `first_published_in`, the minimum earlier `pub_no` with part 1,
     and the finding from `fxm_fdg` (`fdg_type`, `fdg_status`, `is_favorbl`).
   - **`role`.** Notice types `T12`, `G12` and `T14` are `tx`; `T13` and `G13` are `rx`; anything else is
     `unknown`, which gives `not_assessed`.
3. **Relevance** (`relevance.py`). The result is `relevant: bool` plus `signals[]`.
   - `fin_coordination` comes from `fxm_coord.adm = 'FIN'`, with its `coord_st`, and is sufficient on its own.
   - `ge06_affected` is FIN in the `ge06_*` tables, and is also sufficient on its own.
   - `within_range` is a site distance ≤ 1000 km to the nearest Finland border point (haversine).
   - `freq_overlap_m4` is recorded as an attribute and never gates relevance.

   A notice is relevant when it has a sufficient signal or `within_range`. Non-relevant rows are kept with
   `relevant: false`, because trends and the false-positive check need them.
4. **Regulatory context** (`regulatory.py`). The output fields are `rr_provision`, `ge06` (bool and cite),
   `criterion_id`, `criterion_applicability` (`applicable`, `indicative` or `unknown`), `governing` (bilateral
   text or null), `m4_rows[]` (`ref.m4_allocation` rows overlapping `[freq_min, freq_max]`) and `citations[]`.
   The criterion is picked by band from `terrestrial_criteria.json`. If no band matches, the result is
   `criterion_id: null` with `not_assessed` and the reason `no_criterion_in_registry`.
5. **Hazard** (`hazards.py`). There is one hazard per TX assignment, `field_strength_border`. RX assignments get
   `not_applicable` with the reason `receiving_station`.
   - **Inputs.**
     - e.r.p. in dBW, from `pwr_dbw` where `pwr_eiv = 'E'`. Otherwise use `not_assessed` with
       `unsupported_power_type`, or flag the conversion as an assumption, whichever the BR Preface supports.
       Record the choice.
     - h1, from `hgt_agl`. If it is missing, use `not_assessed` with `missing_antenna_height`, with no default.
     - f, from `freq_assgn`, and the bandwidth, from `bdwdth` in kHz.
     - The criterion's time %, location % and h2.
     - The antenna is non-directional unless `azm_max_e` and `fxm_ant_diag` are present, in which case the
       attenuation at the bearing is applied. Assumption `A-T-ANT-OMNI` applies when the antenna is
       non-directional.
   - **Tier 0.** `outside_p1546_range` → `not_assessed`. If the h1 limit is exceeded, record the assumption and
     clamp, matching the `stations.py` behaviour.
   - **Tier 1.** Compute an all-sea path at the nearest border point. If E plus the bandwidth correction is at
     least 3 dB below the trigger, the result is `screened_out`. Store `e_upper_dbuv`. The 3 dB margin is an
     assumption id, so the sensitivity can be shown.
   - **Tier 2.** For each border point within 1000 km, ordered by distance, compute the great-circle path, sample
     it every 1 km, and classify each sample by `region_land`. Contiguous runs of the same kind become the
     `path` for `p1546.field_strength` (land, or `sea_cold` for the Baltic, which is assumption `A-T-SEA-COLD`).
     Evaluate up to N = 25 nearest points, plus the point on the main-beam bearing if the antenna is directional.
     The worst point gives `e_dbuv`, `margin_db = e - trigger` and the outcome `exceeds` or `meets`. Store the
     worst point (lat, lon, distance, bearing), the path segments, every `FieldResult` intermediate and
     `e_all_land` / `e_all_sea` as bounds.
6. **Orchestration** (`assess.py`). Results are sorted by `terrakey`. Each result carries `model_version`, the
   `source` tags (`<ific_no>:<table>:<terrakey>`), the `assumptions` ids, `criterion.verified` and the sort keys:

   ```
   (outcome_rank, fin_coord_required, -margin_db or +inf, change_rank, pub_status_rank, terrakey)
   ```

   `pub_status_rank` puts `received` before `recorded`, an open question noted in the plan. Floats are rounded
   through `riia.store.round_floats`.

## Tests

- **Inventory.**
  - The FIN FX notice is excluded and RECORDED rows are not assignments.
  - The MODIFY diff names the power change.
  - In 9998, the RUS 168 MHz notice is `recorded`, first published in 9997, REX favourable, using 9998's rows
    only (assert no query touches 9997).
  - The part-3 notice is `returned`.
- **Relevance.**
  - The FIN-coordination row is relevant, and so is the Slantsy FB.
  - The CHN 46°N FB is not relevant, despite its M4 overlap.
  - `freq_overlap_m4` is recorded but never decides.
- **Hazards.**
  - Re-running `p1546.field_strength` with the stored inputs reproduces E within 0.001 dB.
  - A missing height gives `not_assessed` and the RX notice gives `not_applicable`.
  - The 450 MHz EST notice uses `tr-25-08`. The 793.5 MHz G12 notice uses `ecc-rec-11-04` (or `not_assessed` if
     the entry was left out), carries `ge06: true` and, for RUS, `criterion_applicability: indicative`.
  - A far notice is `screened_out`.
- **Assessment.**
  - Two runs give byte-identical canonical JSON.
  - No `score` key exists anywhere in the output (recursive check).

## Validation

```sh
cd backend && uv run pytest tests/test_terra_*.py -q
```

## Risks

- Tier 2 cost: about 100 relevant TX notices × 25 points × about 200 path samples is fine in Python. The land
  lookup must be one vectorised `refdata.is_land` call per path. Measure on 3077, which has the most rows, and log the time per issue.
- Cold or warm sea: assume cold sea for the Baltic, and state it.
