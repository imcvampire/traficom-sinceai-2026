# Brainstorm contract: terrestrial land-mobile side quest

Source brief: `Problem.pdf`, "Side quest: Terrestrial land-mobile notices". This contract refines acceptance
criteria 4 and 6 of `brainstorm-261106-2029-ific-interference-analyser.md`. Those criteria were written before
`riia-1`, the P.1546 engine and the station map existed.

## Evidence (inspected 2026-11-07)

| Source | Finding |
|---|---|
| `brific3076.mdb` | **Each issue is a delta, not a snapshot.** All ADD (2905), MODIFY (163) and SUPPRESS (413) rows carry `pub_no` 3076. The 576 RECORDED rows are the *before* state (`pub_no` ≤ 3074), and every one of them is the `fxm_target.target` of a MODIFY or SUPPRESS row. That gives a field-level before/after diff inside one issue. |
| `fxm_coord` | 16 rows name `adm = 'FIN'`. These are RUS FB/ML assignments at 152–153 MHz and 793–795 MHz, some with status `COORD REQUIRED`. This is a direct relevance signal from the notice data. |
| Near Finland (lat 53–72, lon 5–40) | RUS FB 36, ML 13, and POL FB 9. Frequencies span 152–816 MHz, and bandwidths include 11K0, 16K8, 18K0, 5M00 and 7M20. **A large share is LTE800 (790–862 MHz), outside the T/R 25-08 range of 29.7–470 MHz.** |
| `fxm_ant` (FB/ML) | 2325 rows. `pwr_dbw` is present for all of them and `hgt_agl` for 63%, while `azm_max_e` covers 690 and `eff_hgtmax` only 84. Field-strength inputs are mostly present, so the antenna pattern is usually treated as omnidirectional. |
| Geography | Coordinates come from `fxm_geo.lat_dec`/`long_dec` via `geo_key`. |
| `ific.propagation.p1546`, `tr2508` | Validated P.1546-6 port (52/52 reference cases) and the T/R 25-08 trigger table, already built "shared with the side quest". `tr2508` values are marked UNVERIFIED. |
| `data/ref/finland_land.geojson` | Covers Finland only. **There is no neighbouring coastline**, so cross-border mixed land/sea paths cannot be classified yet. The station-map plan lists this as the side quest's first need. |
| `ingest.py` | `brific*.mdb` files are ignored today, and the watcher only follows the Space page. Only `brific3076.mdb` is local. |

## Outcome

`ific ingest brific<no>.mdb` loads one or more terrestrial issues into a `terra` schema. A deterministic
terrestrial assessment then:

- classifies foreign land-mobile assignments as new, modified or withdrawn;
- filters them to those relevant to Finland;
- attaches the ITU, CEPT/ECC and national framework;
- picks the applicable criterion;
- computes the P.1546 field strength at the Finnish border.

Each finding is stored as an outcome with the source notice, the field strengths, the model parameters, the
assumption ids and the citations. A `/terrestrial` page and CSV/JSON/Markdown exports present the findings. A
small trends panel covers neighbouring administrations. For each notifying administration with concerns, a
draft letter is built on demand in the same way as the space drafts. The pipeline stages match `riia-1`
(inventory, tiered screen, deterministic evaluation, outcome, regulatory context, review, draft), with the
simplifications listed below.

## Constraints

- **Same invariants as `riia-1`.** There is no composite score; outcomes are `exceeds`, `meets`,
  `screened_out`, `not_applicable` and `not_assessed`. Two runs must produce byte-identical JSON. Every input
  carries a source tag and citation, and every assumption an id.
- **Deterministic only.** There is no Monte Carlo; this is a deliberate simplification of Tier 2. P.1546 runs at
  each criterion's own time %, location % and receiving height (T/R 25-08: 10% time, 50% locations, 10 m).
- **Reuse, don't fork.** Import `ific.propagation`, extend `ingest.py` rather than adding a second ingester, and
  reuse the outcome, evidence and assumption shapes and the `JobRunner`/store pattern. The `riia` schemas stay
  unchanged, so the space tests and api.ts types remain untouched.
- **Criterion values are indicative.** Bilateral agreements (FIN–RUS, FIN–EST, Nordic) override them. Because
  those agreements are not in the repo, this is a stated assumption, not a looked-up value.
- DuckDB allows one writer. Ingest and assessment must use the API's job path while the server runs.
- Timebox: demo on Sunday 8 Nov, per the earlier contract.

## Non-goals

- Chat over terrestrial findings. The user asked for drafts "like the space one"; the `riia/chat.py` pattern
  could be reused later.
- Terrain profiles and DEM data. The model assumes flat terrain, with `tca_not_applied` flagged per finding.
- Aggregate interference, and services other than land mobile (FX, broadcasting, LF/MF).
- A watcher for the terrestrial BR IFIC page.
- Quantifying the space `es_terrestrial` hazard. The new modules make it feasible, but it is a follow-up.
- Verifying the contents of bilateral agreements.

## Trade-offs

| Approach | Depends most on | Fails first when |
|---|---|---|
| **A. Sibling `ific/terra/` package (recommended).** It shares ingest, `propagation`, the outcome, evidence and assumption contracts, the job/store pattern and the UI shell. It has its own normaliser, relevance filter, criterion registry and evaluator, writes `analytics.terra_*` tables, and serves `/api/terrestrial`. | The shared contracts being small enough to lift into a common module without changing `riia` behaviour. | Reviewers read "same architecture" as literally one code path. Mitigation: move the outcome literal and the evidence/assumption types into a shared module that both packages import, and show the stage-by-stage mapping in the method doc. |
| B. Terrestrial as a `riia` hazard mode or receiver source | `riia`'s `Notice` and hazard schemas tolerating a notice without orbit, pfd or Monte Carlo fields. | Immediately. The Monte Carlo seed, curve outputs, the chat context and the `api.ts` types all change, and the byte-identical space tests are at risk the day before the demo. |
| C. Extract a full shared core first, then two adapters | Time to refactor `riia` and re-prove reproducibility. | On the deadline. It is the most elegant option and the most expensive to abandon partway. |

Evolutionary-design check. Space and terrestrial genuinely share these stages: ingest, the tiered screen, the
outcome vocabulary, evidence, citations and assumptions, the regulatory-context attachment, the review report and
the UI pattern. They vary in the notice normaliser, the relevance test, the physics (pfd versus P.1546) and the
criterion source. Approach A shares the stable part as types and leaves the variable part concrete. That is the
cheapest seam with two real variants.

## Better approaches

1. **Change classification comes from the delta structure, not from diffing snapshots.** The brief reads as
   "diff consecutive issues". The evidence shows that each issue carries only its own publications, and that it
   ships the targeted before-records itself. So:
   - new, modified and withdrawn come from `intent` plus the `fxm_target` link, which gives an exact field-level
     diff (power, height, bandwidth, site) for MODIFY rows;
   - consecutive issues are used to chain lineage (a later MODIFY or SUPPRESS of an earlier ADD) and for
     per-issue trends.

   This is cheaper and more accurate than a set difference, and nothing is lost by switching.
2. **A criterion registry, not just T/R 25-08.** The notices that matter most in the data are RUS LTE800 base
   stations with `COORD REQUIRED` toward Finland. T/R 25-08 does not cover them, so with T/R 25-08 alone they
   would all end as `not_assessed`. Add `data/ref/terrestrial_criteria.json` with T/R 25-08 (29.7–470 MHz) and
   ECC/REC/(11)04 (790–862 MHz). Each entry records its height, time %, reference bandwidth and citation, plus a
   `verified` flag like `tr2508`'s. Bands with no entry give `not_assessed`, with the reason
   `no_criterion_in_registry`. The cost is about one JSON file plus a band lookup.
3. **Worst-case screen before the real path.** This mirrors Tier 1:
   - Tier 1 computes an all-sea path at maximum e.r.p. with an omnidirectional antenna, and screens out a
     notice whose upper bound at its nearest Finnish point is below the trigger.
   - Only the remaining notices get the mixed land/sea path. That needs a public-domain land mask (Natural
     Earth 10m, clipped to the region) in `data/ref/`.

   The screen keeps the expensive path small and makes "screened out" auditable.

## Chosen direction (to plan)

| Stage | Terrestrial implementation |
|---|---|
| Ingest | `ingest.py` accepts `brific*.mdb` into the `terra` schema, loading only the `fxm_*` tables plus `ref_stn_cls*` and `ref_adm`, and tags rows with `ific_no`. Discovery uses `data/brific/<no>/` and the repo root. The skip on unchanged sha256 is kept. |
| Inventory | Land-mobile assignments are selected by station class through the `ref_stn_cls_nat_srv` code table, which is cited; it is not a hard-coded FB/ML list. The selection excludes `adm = 'FIN'`. Each assignment is classified `new`, `modified` (with a before/after field diff from the RECORDED target) or `withdrawn`, and gets a lineage across loaded issues. |
| Relevance (Tier 0) | Any one of three signals: `fxm_coord.adm = 'FIN'`; site distance to Finnish territory ≤ 1000 km (the P.1546 range); or frequency overlap with a Finnish allocation row. Each signal is recorded. |
| Regulatory context | Three layers. ITU: the RR provision from `prov` (11.2, 11.9, …) and the coordination status from `fxm_coord`. CEPT/ECC: the criterion from the registry. National: the matching row of Traficom's frequency allocation table, cited. Bilateral agreements are an assumption id. |
| Tier 1 | All-sea worst case at the nearest Finnish point, which can give `screened_out`. |
| Tier 2 (deterministic) | Field strength at sampled Finnish border points along a mixed land/sea path, at the criterion's time %, location % and height. It uses the antenna azimuth and pattern when present and an omnidirectional antenna otherwise (an assumption). Bandwidth correction follows the criterion. The outcome is `exceeds` or `meets`, with the margin, the worst point and every P.1546 intermediate. |
| Store / API / UI | `analytics.terra_*` keyed by `ific_no`, with each issue replaced in one transaction. `/api/terrestrial/...` runs through `JobRunner`. The `/terrestrial` page keeps its state in URL params, and `api.ts` types are kept in sync. The map reuses the station-map layers. |
| Exports | CSV, JSON and Markdown for 3076. |
| Drafts | Same contract as `riia/draft.py`: built on demand and never stored. The letter kind is a pure function of the stored regulatory context, never chosen by the LLM. For example, `fxm_coord` FIN `COORD REQUIRED` or an exceeded trigger without FIN coordination gives a coordination request, and the other cases give an enquiry. The exact RR and agreement provisions per kind are cited from a `data/ref` file confirmed in the plan. The annex quotes the stored field strength, trigger and margin. The LLM polish rewrites the body paragraphs only, and a `check_polish` equivalent rejects changes to protected tokens. Station ids and coordinates go in the reviewer notes, not the letter. The shared pieces (`load_administrations`, `protected_tokens`, the polish check, `render_letter` scaffolding) are imported from the space module, or moved to a shared module, rather than copied. |
| Trends | Counts per neighbouring administration (RUS, EST, NOR, S, LVA, LTU) by band, distance bin, station class and bandwidth, per issue, plus 3–5 deterministic anomaly rules. Examples: a new band for an administration near the border, a bandwidth atypical for its band, an e.r.p. outlier, and coordination with FIN still `COORD REQUIRED`. |
| Docs | `docs/terrestrial-land-mobile.md` is the method source of truth, mapping each stage to its `riia-1` counterpart. Update `docs/frontend.md` and the README. |

## Acceptance criteria

1. `ific ingest brific3076.mdb` loads the file into `terra`. Re-running it is a no-op, the space ingest and its
   tests are unchanged, and the full backend suite passes.
2. For 3076, every foreign land-mobile assignment has a class (`new`, `modified` or `withdrawn`). MODIFY rows
   show a field diff against their RECORDED target. A fixture with two consecutive synthetic issues proves the
   cross-issue lineage, such as an ADD in issue N that is suppressed in N+1.
3. Every relevant assignment has a recorded relevance reason. The 16 `fxm_coord` FIN rows are all included.
4. Every assessed finding names its criterion and citation, or is `not_assessed` with a reason. The 790–862 MHz
   RUS FB notices are assessed against ECC/REC/(11)04.
5. Every `exceeds` or `meets` finding shows the P.1546 field strength at the worst Finnish point, the trigger,
   the margin, and the full parameter set: f, h1, h2, time %, location %, path segments, e.r.p. and bandwidth
   correction. It also lists its assumption ids and source fields (terrakey, `adm_ref_id`, table and column).
6. Two runs give byte-identical JSON (test). No `score` column or key exists (test). The P.1546 inputs per
   finding reproduce the stored E within 0.001 dB when re-run through `p1546.field_strength` (test).
7. The `/terrestrial` page lists the findings with URL-param filters, opens an evidence sheet and shows a map
   and a trends panel with at least three anomaly rules evaluated on 3076.
8. The exports for 3076 exist. `mise run lint`, `mise run test` and `mise run build` pass.
9. The two adjacent real issues ingest. The live data then shows cross-issue lineage, with a MODIFY or SUPPRESS
   in a later issue linked to its earlier ADD, and per-issue trends.
10. `GET` a terrestrial draft for an administration with concerns returns a letter whose kind follows from the
    regulatory context. The letter carries the draft banner and the annex values. A polish that alters a
    protected token is rejected (test). With no LLM configured, the template letter is returned.

## Risks

- The `tr2508` values and the new REC(11)04 values are unverified transcriptions. Findings carry
  `verified: false` until a person checks them against the PDFs.
- With flat terrain and no clutter, the model overstates reach over hills and into towns. It is conservative for
  screening, and the assumption is flagged per finding.
- The land mask resolution misclassifies short coastal segments near the Gulf of Finland. The sensitivity is
  easy to show by comparing the all-land and all-sea bounds, which are already computed in Tier 1.
- `hgt_agl` is missing for 37% of FB/ML rows. Those assignments are `not_assessed` with the reason
  `missing_antenna_height`. A default height would be invented data, so none is used.

## Decisions (user, 2026-11-07)

1. Adjacent terrestrial issues are available. As of 14:11 only `brific3076.mdb` (plus
   `~/Downloads/brific3076.zip`) is on this machine, so the other files still have to be placed. Expected
   location: `data/brific/<no>/brific<no>.mdb`, or the repo root. The fixture-based lineage test stays in any
   case.
2. ECC/REC/(11)04 for 790–862 MHz is in scope.
3. Draft letters are in scope, built like the space drafts.

## Unresolved questions

1. Which issue numbers are the adjacent terrestrial files, and when will they be in place?
2. Should other ECC recommendations, such as (08)02 for 900/1800 MHz, be added to the criteria file if those
   bands show up in the data? The default is no, and those notices stay `not_assessed` with a reason.
