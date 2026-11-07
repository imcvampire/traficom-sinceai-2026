---
title: Risk-informed interference assessment of satellite networks for Finland, with a demo page
status: completed
mode: auto (standard)
created: 2026-11-06
branch: main
source: /ak-plan "build an analytics for IFIC data. First, build a model to score which sat has higher severity score to Finland. Also add a page in UI to demo that scoring"
related:
  - ../reports/brainstorm-261106-2029-ific-interference-analyser.md
  - ../261106-2101-duckdb-startup-m4-reference-load/plan.md
  - ../../docs/interference-risk-assessment.md
---

# Risk-informed interference assessment of satellite networks

## Outcome

For any ingested Space IFIC issue, every satellite-network notice gets a **risk-informed interference assessment**
for Finland, following the FCC TAC / de Vries method:

1. a hazard inventory;
2. a consequence metric;
3. likelihood and consequence, from Monte Carlo over Finnish receiver populations;
4. aggregation against ITU-R protection criteria.

Results are likelihood–consequence curves and readings taken off them, in physical units. There is no composite
score. The regulatory context (stage, comment deadline, BR findings) is shown alongside the technical result and
drives the work queue. A new `/risk` page in the web app lists the notices of a chosen issue and opens a risk chart
for each one.

The demo runs on a **generic receiver population** built from M4 and a grid over Finland. The **stations** receiver
source (the frequencies-of-interest XLSX) is a follow-up plan, and plugs into the same interface.

## Evidence (inspected 2026-11-06)

| Source | Finding |
|---|---|
| Backend | DuckDB with `ref.m4_allocation` (5,917 rows, Hz bounds) is loaded at startup. **No Space IFIC ingest exists yet.** The `.mdb` files are only downloaded by the watcher (`data/ific/<no>/ific<no>.mdb`, 3062–3081). |
| `ific3074.mdb`, `ific3083.mdb` | Both sit in the repo root, outside `data/ific/`. 3074 is the mandatory evaluation issue. |
| 3074 `notice` | 196 notices. `prov`: 9.1/IA 50, 9.6 76, 11.2 65, RS49 5. `ntc_type`: G (GSO) 72, N (non-GSO) 110, S (earth station) 12. `act_code` A/M/S, where S means suppression. |
| 3074 `grp` | 34,365 assignment groups. `freq_min`/`freq_max` are in MHz and always present. `emi_rcp`: E 21,283, R 13,082. |
| 3074 pfd inputs | `emiss.pep_max` (dBW) is present for most G/N groups, and `s_beam.gain` for 2,299 of 2,304 beams. `s_beam` has boresight fields for the S.672 roll-off. A notified `c_pfd` exists for 49 notices, and `mask_info` for 6. |
| 3074 geometry | `geo` (`long_nom`, `tol_east`, `tol_west`) covers all 72 GSO notices. `orbit` (inclination, altitude, planes, right ascension) covers 100 of 110 non-GSO notices. `e_stn` has lat/long for earth stations. |
| 3074 coordination findings | `provn` names FIN under RR provisions in 220 group rows: 9.11 72, 9.14 34, 9.21/C 106, 11.31.1 6, AP30A §7.1 2. `tr_aff_ntw` lists the Finnish networks FIN10300 and FIN10400 (22.8°E) as affected in 8 rows. `coord_agree_ntw` is empty. |
| Frequencies-of-interest XLSX (`data/special_interest/`) | 875 synthetic stations inside Finland. Matching frequency alone, 130 of the 176 3074 notices with downlinks overlap a station. This plan does not read it; the follow-up stations source does. |
| Method sources (primary text read) | FCC TAC *Quick Introduction to RIIA* (2015); de Vries CSMAC handout (2015) and ISART deck (2018); Silicon Flatirons report (2015); Voicu et al., arXiv:1706.02479. The doc lists what each one supports. |
| Tooling | `mdbtools` (`mdb-export`) is installed. `access-parser` is in the dependencies but unused. `numpy` is not yet a dependency. |

## Trade-offs

| Approach | Strength | Fails first when | Verdict |
|---|---|---|---|
| **A. Risk-informed interference assessment (chosen)** | A published spectrum-regulatory method. Consequence is in dB against ITU-R protection criteria, and the protection criteria themselves are the acceptability test, so no invented weights or bands. Seeded Monte Carlo keeps it deterministic. It fits criteria A, D and E. | Compute cost (Monte Carlo over populations and non-GSO time), plus assumptions about the generic population and the satellite beams. Mitigation: tiered screening, cached geometry, background jobs, a sensitivity report, and the stations source for real populations. | Ship |
| B. Weighted 0–100 score | Simple to show and sort | Its weights have no source. de Vries (ISART 2018) warns against reducing results to a single number. | Dropped |
| C. Supervised ML | Learns from cases | No labels exist. | Later, once expert feedback is captured |
| D. LLM judges the risk | Fast to prototype | Breaks the rule that the LLM never decides relevance or limits, and is not reproducible. | Reject |

### Model (`riia-1`)

The full specification is [`docs/interference-risk-assessment.md`](../../docs/interference-risk-assessment.md). It
is the single source, and this plan does not copy it. In summary:

- **Hazards** are pairs of (notice, receiver population) per hazard mode.
  - Quantified: co-channel space→Earth, and adjacent-band unwanted emissions (SM.1541, RR Appendix 3).
  - Inventoried as `not_assessed`: earth-station terrestrial paths, blocking and intermodulation, and aggregation
    across networks.
- **Consequence:** I/N in dB for active services. For passive services, the spectral pfd minus the RA.769 or
  RS.2017 threshold.
- **Likelihood:** each receiver's time-exceedance curve, then the population risk curve for each criterion time
  percentage. Seeded Monte Carlo with N = max(10⁴, ⌈100/p⌉), capped at 10⁶.
- **Tiers:**
  - Tier 0: overlap and visibility.
  - Tier 1: deterministic worst case, which can screen a hazard out.
  - Tier 2: Monte Carlo.
- **Acceptability:** the service's ITU-R criterion points `(level, time %)`.
  - Outcomes: `exceeds`, `meets`, `screened_out`, `not_applicable` or `not_assessed`.
  - Each outcome comes with `share_violating`, `exceedance_db` and the risk curves.
- **Sorting** uses readings off the curves, never a composite score.
- **Regulatory context** (stage, days left, BR identified Finland) sits beside the risk result. The work queue is the
  notices with an `exceeds` hazard or a BR flag whose comment window is open, sorted by days left.
- **Sources:** every input carries a source tag and citation. A sensitivity report lists the outcome-sensitive
  assumptions.

## Extension trace

Two credible variants, both with real data today:

1. **The stations receiver source** (the frequencies-of-interest XLSX).
2. **Terrestrial land-mobile assessment** (IFIC 3076, the side quest).

What stays stable:

- the `Receiver` record and the `ReceiverPopulation` interface;
- the hazard inventory contract: `hazard{mode, population, tier, outcome, share_violating, exceedance_db[],
  risk_curves[], worst_case_db, inputs, citations, assumptions}`;
- the regulatory context;
- the `analytics.risk_*` tables, keyed by `(domain, ific_no, item_id, receiver_source)`.

What changes:

- **Stations:** only a new population provider that maps XLSX rows to `Receiver`, drawing missing values from the
  class distributions.
- **Terrestrial:** a hazard extractor whose consequence is P.1546 field strength against T/R 25-08. The same module
  also closes the earth-station terrestrial-path `not_assessed` mode.

Phase 02 proves the seam with a fake two-station population test. Neither variant is built here, and there is no
plugin registry.

## Phases

| # | Phase | Status | Depends on |
|---|---|---|---|
| 01 | [Space IFIC ingest into DuckDB](phase-01-space-ific-ingest.md) | completed | — |
| 02 | [RIIA engine: populations, hazards, tiers, Monte Carlo](phase-02-severity-model.md) | completed | 01 |
| 03 | [Jobs, API, CLI, consistency checks, sensitivity report](phase-03-api-cli-calibration.md) | completed | 02 |
| 04 | [`/risk` demo page](phase-04-scoring-page.md) | completed | 03 (API contract only, so the UI can start against fixture JSON) |
| 05 | [Docs + whole-flow verification](phase-05-docs-verify.md) | completed | 03, 04 |
| 06 | [Stations receiver source](phase-06-stations-source.md) | completed | 02 |
| 07 | [Concern triage and manual-review export](phase-07-concern-review.md) | completed | 03, 06 |

## Acceptance criteria

1. `uv run ific ingest data/ific/3074/ific3074.mdb` loads the needed space tables into the `ific` schema, tagged
   with `ific_no`. A second run with the same sha256 is a no-op.
2. `uv run ific assess 3074 --as-of 2026-11-06` writes the assessment of every 3074 notice (196). Two runs produce
   byte-identical JSON exports, including the Monte Carlo results.
3. Every notice result carries:
   - `model_version`, `as_of` and `receiver_source`;
   - the full hazard inventory, with every mode listed;
   - for each hazard: tier, outcome, `share_violating`, `exceedance_db` per criterion point, risk curves and
     `worst_case_db`;
   - inputs with source tags and citations, and assumptions;
   - the regulatory context, with its `provn`/`tr_aff_ntw` citations.

   No composite score exists anywhere in the output.
4. Unit tests pin:
   - geometry, including off-axis angles;
   - circular-orbit positions;
   - each antenna pattern and the S.672 roll-off at hand-checked angles;
   - the SM.1541 / Appendix 3 mask;
   - pfd, I and N against hand-checked values;
   - the CCDF and the population risk curve on hand-built samples;
   - criterion-violation logic;
   - seeded reproducibility;
   - the tier rules.
5. Consistency checks on 3074 pass and are reported:
   - Tier 1 ≥ Tier 2 max for every hazard;
   - no `exceeds` for suppressions or never-visible notices;
   - agreement with the BR's Finland findings, with misses listed.
6. The sensitivity report exists and lists the outcome-sensitive assumptions.
7. Assessing 3074 runs as a background job with progress. It finishes in under 15 minutes on a laptop, with the time
   logged. A second request for the same issue while it runs returns 409.
8. `/risk?ific=3074` lists notices in a filterable table, with all filters in URL params:
   - work-queue and technical views;
   - filters for outcome, service, administration, provision and orbit type, plus text search.

   The table shows outcome badges with icon and label, `share_violating`, the worst `exceedance_db`, days left and
   the BR flag. The detail sheet shows:
   - the likelihood–consequence chart, with all hazard curves and the criterion points;
   - the hazard inventory, including the `not_assessed` modes;
   - inputs, source tags, citations and assumptions;
   - the regulatory context.

   A compare view overlays the curves of two or more notices. A receiver-source badge marks the run as a generic
   population. The page works in light and dark mode and at phone width.
9. `mise run lint`, `mise run test` and `mise run build` pass.

## Non-goals

- The stations receiver source and terrestrial assessment. Both are covered by the extension trace and planned as
  follow-ups.
- Quantifying earth-station terrestrial paths, blocking and intermodulation, or aggregation across networks. These
  are inventoried as `not_assessed`.
- AP30/30A/30B plan-notice assessment. 3074 has no such notices.
- The exact ITU examination: EPFD (Art. 22) and ΔT/T (Appendix 5).
- Letter drafting, LLM narration and the submission exports.
- Auto-assessment on watcher download.

## Risks

| Risk | Mitigation |
|---|---|
| Compute: non-GSO constellations with thousands of satellites × about 220 sites × up to 10⁶ samples | Tier 1 screens most hazards out first. Satellite positions are computed once per time sample and shared across sites and bands (numpy, vectorised). Visibility is cached per (notice, site). The job runs in the background with progress. If the 15-minute budget is still missed, the grid gets coarser (0.5° × 1°) and the change is recorded in the result. |
| Transcription of ITU-R protection criteria, patterns and masks | Only the classes M4 needs go into `receiver_classes.json`, each value with a cite. A person reviews it, and patterns and masks are tested at hand-checked points. |
| The generic population overstates exposure | The UI labels it. The stations source follows. The doc lists the generic-vs-stations comparison as validation. |
| Satellite beam assumptions (peak gain for steerable non-GSO beams, full duty cycle) | Tagged as `assumption`, moved in the sensitivity report, and replaced by `c_pfd`/`mask_info` where notified. |
| `provn` / `tr_aff_ntw` semantics are inferred from the data | Phase 01 checks them against the 3074 PDF part for two notices. |
| The result depends on the date | `as_of` is an explicit input stored with every result, and only the regulatory context depends on it. |
| DuckDB single-writer lock | The CLI exits with a clear message while the API runs. The UI path uses the API's connection and the job runner. |
| 3074/3083 sit in the repo root | Phase 01 discovery also scans the repo root for `ific*.mdb`. |

## Unresolved questions

1. Should `ific3074.mdb` and `ific3083.mdb` move into `data/ific/<no>/`, or should discovery also scan the repo root?
   The plan assumes discovery scans the root, so no files are moved.

## Delivery notes (2026-11-07)

- Unresolved question 1 is settled as assumed: discovery scans the watcher download dir, then the project root; no
  files were moved.
- The DuckDB schema is `space`, not `ific`: a schema named `ific` is ambiguous with the `ific.duckdb` catalog.
- The 0.25° × 0.5° grid has 495 cells inside Finland, not about 220; the doc is corrected.
- EESS passive is excluded from the generic population (spaceborne sensors); S.465 was added for earth-station classes.
- The API contract the UI was built against is pinned in [api-contract.md](api-contract.md).
- The provn/tr_aff_ntw semantics could not be checked against the IFIC PDF parts (not downloaded); the note in
  `backend/src/ific/ingest.py` records what the data shows.
- Reports: [consistency](../reports/consistency-261106-riia1-3074.md),
  [sensitivity](../reports/sensitivity-261106-riia1-3074.md),
  [code review](../reports/code-reviewer-261107-0035-riia-backend.md),
  [UI build](../reports/fullstack-developer-261106-2349-risk-page.md).

## Expert feedback (2026-11-07)

The challenge judge defined a concern as: an exceedance of the defined limit; also a close-by exceedance or a
semi-high pfd near the frequency; with the trigger lowered when a Finnish high-gain antenna points in direct line at
the transmitter location given in the IFIC. 3074/3076 should contain several clearly findable cases.

riia-1 covers the first trigger. Phases 06–07 add what the other two need, for Space IFIC 3074; 3076 is terrestrial
and stays with the terrestrial follow-up.

Dry run (3074, as_of 2026-11-06): [review-261107-riia1-3074-concerns.md](../reports/review-261107-riia1-3074-concerns.md)
and its `.csv` (reviewer columns empty). The stations source flags 23 notices (16 networks) as `exceeds`, against 82
with the generic population; 7 of the 23 also carry a BR finding naming Finland, and 2 (CHINASAT-G-33.5E) have a
45 dBi Finnish dish whose main beam contains the GSO position. Station gains above a 4 m aperture were capped
(the dataset's MVV gains reach 77 dB).
