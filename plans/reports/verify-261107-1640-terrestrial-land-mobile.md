# Verification: terrestrial land mobile side quest (`terra-1`)

Plan: [261107-1550-terrestrial-land-mobile](../261107-1550-terrestrial-land-mobile/plan.md). Contract:
[brainstorm-261107-1401](brainstorm-261107-1401-terrestrial-land-mobile.md), criteria 1–11 as amended 2026-11-07.

**Data.** Real `brific3075/3076/3077.mdb` from `data/brific/<no>/`. The user's API server was running and held the
DuckDB lock, so the stored assessment was produced through `POST /api/terrestrial/issues/{n}`, as CLAUDE.md
prescribes. `var/db/ific.duckdb` was backed up first to `var/db/backup/ific.duckdb.bak-20261107-terra`. The
numbers below come from a scratch DuckDB built from the same files and the same code. Its results match the API's
stored results exactly: outcome, margin and sort key for all 8,017 assignments, with 0 mismatches.

**Timing.** Through the API, including the first ingest, 3075 took 2.0 s, 3076 1.9 s and 3077 4.5 s. The
assessment step alone takes 0.4–1.0 s per issue.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Ingest into `terra`; re-run is a no-op; space ingest unchanged; full suite passes | met | `ific ingest` loads 18 tables (19 with `ge06_notice_group`): 3076 has 4,057 `fxm_terra` rows in 601 ms, and a re-run is `up_to_date` in 10 ms. `test_ingest.py` is unchanged and passes. `test_terra_ingest.py` covers atomic replace, the cast-failure fallback to VARCHAR and discovery order. |
| 2 | Every assignment has a change class; MODIFY shows a field diff; fixture lineage across two issues | met | The change counts equal the raw `intent` counts for the selection: 3075 ADD 1,657 / MODIFY 4; 3076 ADD 1,847 / MODIFY 11; 3077 ADD 4,498. Every MODIFY has a diff (4/4, 11/11). Fixture 9997 ADDs EST 90000003, and 9998 withdraws it from 9998's own RECORDED copy (`test_cross_issue_lineage_from_each_issue_alone`). |
| 3 | Relevance reason for every relevant assignment; the 16 FIN rows; CHN at about 46°N not relevant | met, count differs | 3076 has 16 `fxm_coord` FIN rows. 15 belong to assignments, all relevant: 14 rows on TX assignments, and 1 on the RX assignment (ML 152.9 MHz T13, `not_applicable` / `receiving_station`). The 16th row belongs to 92326149, a RECORDED before-state (the target of MODIFY 93082392), so it is not an assignment. The contract's "15 TX" counted that row. All 194 CHN assignments are not relevant; the nearest is 3,644 km away. |
| 4 | Criterion and citation, or `not_assessed` with a reason; RUS 790–862 MHz FB under ECC/REC/(11)04 with GE06 Art. 4; every finding cites M4 | met | 3076 has 22 RUS FB assignments in 790–862 MHz: all on `ecc-rec-11-04`, `indicative`, `ge06.applies`, G12 (7 under GE06-4.2, 15 under RR11.2). Every finding (8,017 of 8,017) cites Regulation M4. No `exceeds` or `meets` finding lacks a criterion. |
| 5 | E at the worst point, trigger, margin, full parameter set, assumptions and source fields | met | Each Tier 2 finding stores `parameters` (f, h1, h2, time %, location %, e.r.p., bandwidth correction), the path zones, the worst point, every P.1546 step, `assumptions[]` and `sources[]` (`<ific_no>:<table>:<key>`). See the evidence blocks in `terra-3076.md`. |
| 6 | Byte-identical JSON; no `score`; P.1546 re-run within 0.001 dB | met | Two runs are byte-identical for 3075, 3076 and 3077, and no key contains `score`. All 21 Tier 2 findings reproduce exactly through `hazards.reproduce`, including the five sampled with seed 7. A hand calculation for 3076 terrakey 93082383, using log interpolation over the P.1546 tables (h1 20/37.5 m, d 30/35 km, f 100/600 MHz) outside `field_strength`, gives 24.85 dB(µV/m); the code gives 24.85. This check shares the curve tables but not the code path. |
| 7 | `/terrestrial` page; filters in the URL; evidence sheet; map; trends with at least 3 anomaly rules on 3076 | met | Four rules are evaluated on 3076: A1 0 matches, A2 4, A3 6, A4 3. A headless Playwright run of the page against real 3076, on the running dev servers, passed with no console errors: invalid params are dropped (`outcome=bogus,exceeds` became `exceeds`); filters round-trip through the URL; the sheet shows the P.1546 parameters and intermediates; the map draws the worst-point line; the trends and anomalies render; the RUS draft opens; `/risk` still renders. |
| 8 | 3076 exports; lint, test and build pass | met, with one rerun gap | `plans/reports/terra-3076/terra-3076.{json,csv,md}`. `mise run lint` is clean. `mise run test` passes 491 tests. `bunx tsc -b --noEmit` passes. `mise run build` passed in the frontend run. After that I only added one optional field to `api.ts` (type-checked); a local hook blocks commands containing "build", so I did not rerun it myself. |
| 9 | Issues assessed independently; 93081132 in 3077 `recorded`, REX favourable, first published in 3075; re-assessing one leaves the others byte-identical; part-1 sums match | met | 93081132: `recorded` (part 2), REX FINAL favourable, `first_published_in` 3075, all from 3077's rows. Its outcome is `screened_out`: the Tier 1 all-sea bound at the nearest Finnish point (60.468N 27.452E, 156.6 km) is 2.50 dB(µV/m) against the 12 dB(µV/m) trigger (−9.5 dB), with h1 44 m and 10 dBW e.r.p. Re-assessing 3076 left 3075 and 3077 byte-identical. Neighbour part-1 counts are 34 + 78 + 62 = 174, matching a direct count of 174. |
| 10 | Draft for an administration with concerns; kind from the context; banner and annex; polish guard; template without LLM | met | 3076 has one letter administration, RUS, with 9 assignments of kind `coordination_request` (3 COORD REQUIRED, 6 `exceeds`). See `plans/reports/terra-drafts-3076/RUS-coordination_request.md`. The FIN–RUS bilateral agreement is cited as governing, and the letter contains no terrakeys or coordinates. `test_terra_draft.py` covers the kinds, the guard rejecting an altered number, the 503 without an LLM and determinism. |
| 11 | Watcher downloads the 2026 terrestrial issues; a second run downloads nothing (304); a 404 stays pending | met | The live watcher in the user's reloading dev server downloaded 3062–3083 (22 issues, 25–113 MB each) between 16:01 and 16:03, and the next scheduled run downloaded none. No issue was 404. `test_watcher_terra.py` covers 404, 304 and a bad zip with fakes. |

## 3076 findings

There are 1,858 foreign land mobile assignments, 57 of them relevant. Outcomes: `exceeds` 6, `meets` 3,
`screened_out` 39, `not_applicable` 1,810 (1,801 not relevant, 9 receiving stations), `not_assessed` 0. The six
`exceeds` are all RUS 152–153 MHz base stations 30–42 km from Finland: two at Kostomuksha (+12.9 and +12.6 dB),
three at Vyborg Gruzovoi (+8.2 dB) and one at Lyaskelya (+9.0 dB). Five carry FIN coordination COORD COMPLETED
under RR 6.7. The Lyaskelya notice (93075637) has no FIN coordination row. The three RUS 793.5/794.74 MHz G12
notices with GE06 4.2.2.2 COORD REQUIRED are `meets` (−27.8 dB) or `screened_out`.

## Deviations from the plan

- **Selection.** Land mobile is selected by station class FB/ML in the issue's own `ref_stn_cls`, not through
  `ref_stn_cls_nat_srv`, because that table maps class to nature of service, not to the service (method doc,
  Inventory).
- **ECC/REC/(11)04.** The registry covers 791–821 MHz (base stations; 821–862 MHz is the FDD uplink). It assesses
  the most restrictive 41 dB(µV/m)/5 MHz border level and reports 59 dB(µV/m) beside it, at h2 3 m.
- **Height out of range.** h1 above 3000 m gives `not_assessed` (`antenna_height_out_of_range`), as `stations.py`
  does, rather than a clamp.
- **Withdrawn and non-relevant assignments** get `not_applicable` with the reasons `withdrawn` and
  `not_relevant`.
- **Land mask.** The mask is rasterised once at 0.01° by an exact even-odd fill of each cell centre, instead of a
  per-path polygon test. The polygon test was about 100 ms per path, and the raster makes a path one index
  lookup.
- **Provenance.** Provenance is in the JSON `cite` and `review` blocks, the `region_land.geojson` properties and the
  method doc, not in a `data/ref/SOURCES.md`. The repository rule keeps Markdown out of `data/`.
- **Submission files.** These are in `plans/reports/terra-3076/`, next to the space review and draft outputs. No
  `submission/` directory exists.
- **Real-data CLI runs.** These were replaced by the API job path, because the user's server held the DB lock.

## Observations for review

- The RUS 790–800 MHz G12 notices have `pwr_dbw` 0 with `pwr_eiv = I`, which gives −2.15 dBW e.r.p. That is
  plausible for a per-carrier value but worth checking against the notice.
- On 3077, all 4,498 assignments are ADD, and the relevant ones are `screened_out` (38) or `meets` (2).

## Independent review and fixes

A code review of the backend changes found no critical issues. It confirmed determinism and reproducibility on 15
real issues (3062–3083). These findings were fixed, each with a regression test where one applies:

- **Tier 1 upper bound below 100 MHz.** The all-sea value is not an upper bound there, because P.1546 land
  exceeds cold sea by up to 8 dB at 30 MHz. Tier 1 now takes the larger of the all-sea and all-land values, and
  the method doc and `A-T-TIER1-3DB` say so. No real 3075–3077 result changed, because no relevant notice is
  below 100 MHz.
- **Issue-wide type fallback.** A bad value in one issue no longer changes a column's type for every issue. It is
  stored as NULL, with the text in `<col>_raw`. This replaces the plan's "column stays VARCHAR" rule, which broke
  the one-issue-at-a-time isolation at the type level.
- **One bad assignment failing a whole job.** A P.1546 input error now gives that assignment `not_assessed`
  (`p1546_input_out_of_range`). Path zone rounding can no longer push the total above 1000 km.
- **The polish guard and references.** The guard now protects each annex `adm_ref_id` verbatim.
- **Low items:**
  - "(None)" in the prose;
  - a None crash in the Markdown export;
  - a 500 from non-ASCII digits in `issues=`;
  - LIKE wildcards in `q`;
  - a crash on a removed criterion id;
  - a letter for a withdrawn notice;
  - a transient watcher re-check marking a good file failed;
  - the land mask outside its clip box, which is now documented.

The 3076 outputs above were regenerated after the fixes, and the API's stored results match them, with 0
mismatches.

## Unresolved questions

1. Which publication part should Finland act on, part 1 (received) or part 2 (recorded)? Part 1 sorts first for
   now.
2. Should ECC/REC/(08)02 (900/1800 MHz) be added?
3. Is the ECC applicability per administration correct, in particular `indicative` for RUS?
4. The criterion values need a person's check against the PDFs (`verified_by`).
