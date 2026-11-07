# Solution overview: inputs, processing and outputs

This page describes the IFIC interference analyser end to end: which data goes in, what the tool does with it, and
which files come out. It is written to be read on its own, next to the submission for Space IFIC 3074 and
Terrestrial BR IFIC 3076. The detailed method specifications are `docs/interference-risk-assessment.md` (space,
model `riia-1`) and `docs/terrestrial-land-mobile.md` (terrestrial, model `terra-1`) in the repository; this page
summarises them and does not replace them.

## What the tool answers

Each IFIC issue publishes foreign radio stations and satellite networks that may affect other countries. Traficom
has to decide, within the comment window, which of them need a reaction from Finland. The tool answers, for every
notice or assignment in one issue:

- Can it cause harmful interference to Finnish spectrum use, and under which hazard mode?
- How likely is that, and how large is the excess over the protection criterion or trigger?
- What is the regulatory situation: procedure stage, comment deadline, whether the BR already named Finland?

It is **risk-informed, not risk-based**. It gives findings for an expert to judge, never a decision.

Three rules hold for every result:

- **No composite score.** Each finding is one of `exceeds`, `meets`, `screened_out`, `not_applicable` or
  `not_assessed`, together with the physical value behind it (I/N in dB, pfd margin in dB, or field strength
  margin in dB). Lists are ordered by fixed sort keys on those values, not by a weighted number.
- **Reproducible.** The same input files and the same code give byte-identical JSON. The space Monte Carlo is
  seeded from `(model_version, ific_no, ntc_id, hazard_id)`; the terrestrial model is fully deterministic.
- **Traceable.** Every input value carries a source tag (an IFIC table and key, an RR provision, an ITU-R
  Recommendation, a reference file, or an assumption id) and a citation. No LLM takes part in any finding.

## The pipeline at a glance

```
 ITU BR Space IFIC  ificNNNN.mdb ──┐                      ┌── riia-1: hazards, pfd check, regulatory context
                                   ├─ ingest ─► DuckDB ───┤                     │
 ITU BR IFIC (Terr.) brificNNNN.mdb┘   (mdb-export)       └── terra-1: inventory, relevance, P.1546
                                                                                │
 Reference data (data/ref, M4, frequencies-of-interest) ──────────────────────► │
                                                                                ▼
                                          stored results (analytics schema) ─► exports, reports, UI, draft letters
```

1. **Ingest.** `mdb-export` reads the needed tables of an `.mdb` file into DuckDB, tagged with the issue number.
   Ingest is a no-op when the file's SHA-256 and the table set are unchanged.
2. **Assess.** The model for the issue type runs over every notice or assignment and stores the full result in one
   transaction.
3. **Report.** Exports, the concern triage, the consistency and sensitivity reports, the web UI and the draft
   letters are all built from the stored results. None of them recomputes or changes a finding.

## Inputs

### ITU issue files

| Input | File used for the submission | SHA-256 |
|---|---|---|
| Space IFIC 3074 | `data/ific/3074/ific3074.mdb` (273 MB) | `a9755213b6cdb7a26a1ca1dcf95ba69a362d3bcc2cb088e91b6b8e01e4790e31` |
| Terrestrial BR IFIC 3076 | `data/brific/3076/brific3076.mdb` (24 MB) | `7358853076caab70e2a18c1d86cc1d22be40a28d0a17202aa6ad35729fce234d` |

The files are the ITU downloads, unchanged. A copy in the repository root has the same hash.

**Space tables read** (`ingest.TABLES`): `notice`, `com_el`, `grp`, `emiss`, `s_beam`, `geo`, `non_geo`, `orbit`,
`c_pfd`, `mask_info`, `srv_cls`, `srv_area`, `e_stn`, `es_ctry`, and the Finland-related rows of `provn` and
`tr_aff_ntw`.

| What the model needs | Space table | Coverage in 3074 |
|---|---|---|
| Assignment bands | `grp.freq_min/max` | all 34,365 groups |
| Transmit power | `emiss.pep_max` | most GSO and non-GSO groups |
| Satellite antenna gain | `s_beam.gain` | 2,299 of 2,304 beams |
| GSO position and tolerance | `geo` | all 72 GSO notices |
| Non-GSO orbit | `orbit` | 100 of 110 non-GSO notices |
| Notified pfd, pfd masks | `c_pfd`, `mask_info` | 49 notices, 6 notices |
| BR findings naming Finland | `provn` | 220 group rows |
| Finnish networks listed as affected | `tr_aff_ntw` | 8 rows |

**Terrestrial tables read** (`ingest.TERRA_TABLES`): `fxm_terra`, `fxm_tx`, `fxm_ant`, `fxm_ant_diag`, `fxm_geo`,
`fxm_geo_pt`, `fxm_coord`, `fxm_target`, `fxm_pub_hist`, `fxm_fdg`, `fxm_rmks`, the GE06 tables
`ge06_notice_group`, `ge06_adm_affected_broad` and `ge06_affected_os`, and the issue's own code tables `ref_stn_cls`,
`ref_stn_cls_nat_srv`, `ref_nat_srv`, `ref_notice_typ` and `ref_adm`. Each terrestrial issue is a delta, so it is
assessed on its own: every query filters on that issue's number. A value that does not cast to its column type is
stored as NULL with its original text kept beside it; no row is dropped.

### Finnish data

| Input | File | SHA-256 | Used for |
|---|---|---|---|
| Frequencies-of-interest dataset (synthetic, 875 stations in Finland) | `data/special_interest/Frequencies_of_interest_v05112026.csv` | `7a314bb39ce9c92c37e52751315a5b649a04fe5daef2bb40d6c9cd1226c5b1e1` | The `stations` receiver population: real location, receive band, height, azimuth, gain |
| Regulation M4 (Finnish frequency allocation table) | `data/m4/m4-radio-frequency-regulation-en.txt` (text of the PDF beside it) | `0da79e50322d3d88e61ac4675468c94fc5f5f1bb867f83ae2993c13ce64f01e5` | The `generic-m4` receiver population, and the national layer of the terrestrial regulatory context |

### Hand-curated reference data (`data/ref/`)

Each file carries its own citations. Values that still need a person's sign-off are marked as pending in the file,
and the reports repeat that.

| File | Contents | SHA-256 |
|---|---|---|
| `receiver_classes.json` | ITU-R reference characteristics and protection criteria per Finnish service class | `09cfc2bf5575a1fde001a6d3766e2545811bc33af988385ba08aeef2a2aa0f30` |
| `rr21_pfd_limits.json` | RR Article 21, Table 21-4 (Edition of 2024) pfd limits that can apply in Finland | `f49fa1cb48424669ac1f561e0deb03300bdb95a6aa082af2fe0d1c1d50e41a5b` |
| `rr_comment_windows.json` | Comment-window length per RR provision | `90a7ba67b7e20b8efd83c69096fcb663a5babc1fd2f575775d70a5b9c40a263e` |
| `finland_land.geojson` | Finnish land border and coastline (Natural Earth 1:50m) | `d7973ed15f2d4a207011ffe7090104eb6db8a07cc354f4be51f8af47d7b7b53b` |
| `region_land.geojson` | Land mask for mixed land/sea paths (Natural Earth 1:10m, 0–45°E, 50–75°N) | `521a4df40b31e96a277c190da810524d8b66c431596dd8835b6bc1797a8e43a4` |
| `terrestrial_criteria.json` | ECC trigger levels at the border (T/R 25-08, ECC/REC/(11)04) | `612639cf2561bdd3edc619e1b3a7813d2ba525091a926bd82bd24851ddbd8d0d` |
| `terrestrial_frameworks.json` | RR provisions, GE06, ECC applicability per administration, bilateral agreements | `da459794b97b33c740329ec6fa4be348e3df4293f8a41ad84dc464a8a4b3ca71` |
| `terrestrial_letter_kinds.json` | Letter types for terrestrial draft correspondence | `27af17266c4206db2fd6f275656583ea029a8212add375769301cef1470569ea` |
| `itu_administrations.json` | ITU administration codes and names | `56f3a2b95e9c7935a22ace5dd380a2124ffc6bd6c8158990bcb643905ab17e83` |

### Explicit run parameters

| Parameter | Value in the submission | Effect |
|---|---|---|
| `as_of` | 2026-11-07 | The evaluation date. It changes only the regulatory fields (days left, window open, work queue), never a technical finding. |
| Space receiver source | `stations` and `generic-m4`, run separately | Which Finnish receiver population the hazards are evaluated over |
| Model versions | `riia-1`, `terra-1`, pfd check `art21-1` | Recorded in every result |
| Code | commit `8b88761` (2026-11-07) | Uncommitted changes at export time were in the frontend only and do not affect any output file |

## Processing: Space IFIC (`riia-1`)

The method follows the risk-informed interference assessment of the FCC Technological Advisory Council (2015) and
de Vries (2015–2018). For each of the 196 notices in issue 3074:

1. **Hazard inventory.** It lists every way the notice could harm a Finnish receiver: co-channel space-to-Earth,
   adjacent-band unwanted emissions, and three modes that are listed but not yet quantified (earth-station emissions
   over a terrestrial path, receiver blocking, aggregation across networks). The unquantified modes are reported as
   `not_assessed` so that nothing is hidden.
2. **Receiver population.** Each hazard is evaluated over Finnish receivers:
   - `stations`: the frequencies-of-interest stations. This is the finding.
   - `generic-m4`: every protected service in M4 placed on a 0.25° × 0.5° grid over Finland (495 sites). It
     overstates exposure, because it assumes every service is deployed everywhere, and is used to check coverage.
3. **Consequence metric.** I/N in dB at the receiver for active services; spectral pfd against the RA.769
   threshold for radio astronomy. Inputs are the notice's power, antenna gain and pattern (S.672), orbit or GSO
   position, bandwidth overlap and emission mask (SM.1541, RR Appendix 3), and the receiver class's pattern, noise
   figure and bandwidth.
4. **Tiers.**
   - Tier 0: no frequency overlap, or never above the horizon in Finland, gives `not_applicable`.
   - Tier 1: a deterministic worst case. If even that stays below every criterion, the hazard is `screened_out`.
   - Tier 2: a seeded Monte Carlo over receivers, time (orbit position or GSO station-keeping) and uncertain
     parameters, with 10,000 to 1,000,000 samples depending on the criterion's time percentage. It gives
     likelihood–consequence curves. Missing data that blocks Tier 2 gives `not_assessed`; a worst case alone is
     never reported as `exceeds`.
5. **Acceptability.** The boundary is the ITU-R protection criterion of the affected service, as level and time
   percentage. A hazard `exceeds` when at least one receiver violates a criterion point. Results include the share
   of receivers violating, the exceedance in dB at the median and 95th percentile, and the curves.
6. **pfd check (RR Table 21-4).** Separately from the hazards, the worst pfd on Finnish territory is compared with
   every applicable Table 21-4 limit. It is a regulatory limit on the transmitter, so it is reported beside the
   hazards and does not set the notice's worst outcome.
7. **Regulatory context.** Procedure stage, days left in the comment window counted from the IFIC publication date,
   and whether the BR named Finland (`provn`, `tr_aff_ntw`). The work queue holds notices with an `exceeds` hazard
   whose window has not closed, ordered by days left.
8. **Concern triage.** `ific review` reads the stored results of both populations and puts each notice in a group:
   P (pfd exceeds Table 21-4), A (a station's criterion is exceeded), B (a GSO position lies in a Finnish station's
   main beam), C (within 6 dB of a criterion at a station), D (exceeded only in the generic population).

## Processing: Terrestrial BR IFIC (`terra-1`)

For each foreign land mobile assignment in issue 3076:

1. **Inventory.** It selects station classes FB (base station) and ML (land mobile), excludes Finland's own rows
   and before-state rows, and records the change (`new`, `modified` with a field diff, or `withdrawn`), the
   publication status (`received`, `recorded`, `returned`), the role (transmit or receive) and the antenna with the
   highest e.r.p.
2. **Relevance (Tier 0).** An assignment is relevant to Finland when Finland is named in `fxm_coord`, Finland is
   affected under GE06, or the site is within 1000 km (the P.1546 range) of the Finnish border. The rest are kept
   as `not_applicable` so they stay visible.
3. **Regulatory context.** The RR provision, GE06, the ECC criterion for the band and its applicability per
   administration (`indicative` for Russia, whose CEPT membership is suspended, with the FIN–RUS bilateral
   agreement stated as governing), the overlapping M4 rows, and the bilateral basis.
4. **Field strength at the border.** The Finnish outline is sampled every 5 km (798 points).
   - Tier 1: the larger of the all-sea and all-land P.1546 values at the nearest point is an upper bound. When it is
     at least 3 dB below the trigger, the hazard is `screened_out`.
   - Tier 2: ITU-R P.1546 over real mixed land/sea paths to the 25 nearest points (plus the main-beam bearing when
     the antenna has a diagram), with the antenna attenuation from `fxm_ant_diag`. The worst point gives E;
     `margin = E − trigger`, and the outcome is `exceeds` when the margin is above 0.
   - Every P.1546 input and intermediate is stored, so E can be recomputed exactly from the stored finding.

## Outputs

All outputs come from the CLI with no hand edits. The submission folder has this layout:

### Space IFIC 3074 (`space-3074/`)

| File | Contents | Produced by |
|---|---|---|
| `concerns-3074.md`, `concerns-3074.csv` | Concern triage in groups P, A, B, C, D. The CSV adds empty `reviewer_verdict` and `reviewer_note` columns for recording a judgement. **Start here.** | `ific review` |
| `summary-stations.json`, `summary-generic-m4.json` | One row per notice: worst outcome, hazard counts, worst exceedance, BR findings on Finland | `ific assess --summary` |
| `assessment-stations.json`, `assessment-generic-m4.json` | The full canonical result per notice: every hazard, its tier, curves, inputs with citations, assumptions, pfd checks, regulatory context | `ific assess --json` |
| `consistency-stations.md`, `consistency-generic-m4.md` | Internal checks on the results (for example Tier 1 ≥ Tier 2 maximum) and agreement with the BR's own findings on Finland | `ific assess --consistency` |
| `sensitivity-3074.md` | Which assumptions can flip an outcome when moved to the end of their range (generic population) | `ific assess-sensitivity` |

### Terrestrial BR IFIC 3076 (`terra-3076/`)

| File | Contents | Produced by |
|---|---|---|
| `terra-3076.md` | Readable findings per relevant assignment: change, criterion, trigger, E at the worst Finnish point, margin, model parameters, assumptions. **Start here.** | `ific terra-export` |
| `terra-3076.csv` | One row per assignment (all 1858); filter `relevant=true` for the 57 relevant ones | `ific terra-export` |
| `terra-3076.json` | The full canonical result per assignment, with the stored P.1546 inputs | `ific terra-export` |
| `assessment-3076.json` | The same content as `terra-3076.json`, written directly by the assessment run | `ific terra-assess --json` |

### Headline results

| Issue | Result |
|---|---|
| Space 3074, `stations` | 196 notices: 23 exceed, 66 meet, 5 screened out, 95 not applicable, 7 not assessed |
| Space 3074, `generic-m4` | 82 exceed, 36 meet, 5 screened out, 64 not applicable, 9 not assessed |
| Space 3074, triage | P 47, A 8, B 0, C 1, D 35 notices |
| Space 3074, BR agreement | For 9 of the 15 notices where the BR named Finland under a technical provision, the tool also finds a live hazard; the 6 others are listed with their values in the consistency reports |
| Terrestrial 3076 | 1858 assignments, 57 relevant: 6 exceed, 3 meet, 39 screened out, 1810 not applicable, 0 not assessed. All 6 exceedances are new Russian base stations at 152–153 MHz, 30–42 km from the border (Kostomuksha, Lyaskelya, Vyborg) |

### Other outputs not in the submission folder

- **Web UI**: `/risk` for space issues (work queue, likelihood–consequence charts, hazard inventory per notice) and
  `/terrestrial` for terrestrial issues (assignment list, border map, trends).
- **Draft letters** to the notifying administration (`ific draft`, `ific terra-draft`). Their type comes from the
  regulatory context. An optional LLM polish may rewrite the prose only, and is rejected if it changes any number,
  provision or identifier.
- **API** under `/api/risk` and `/api/terrestrial`, which serves the same stored results.

## Reproducing the submission

Prerequisites: Python 3.12 with `uv`, and `mdbtools` (`mdb-export`); `mise run install` sets them up. Place the two
`.mdb` files at the paths in [Inputs](#inputs), or in the repository root. Stop the API server first, because
DuckDB allows only one writer.

```sh
cd backend
OUT=../plans/reports/submission-261107-ific-3074-3076
DAY=2026-11-07

# Space IFIC 3074
uv run ific ingest 3074
for SRC in stations generic-m4; do
  uv run ific assess 3074 --as-of $DAY --source $SRC \
    --json $OUT/space-3074/assessment-$SRC.json \
    --consistency $OUT/space-3074/consistency-$SRC.md \
    --summary $OUT/space-3074/summary-$SRC.json
done
uv run ific review 3074 --as-of $DAY --out $OUT/space-3074/concerns-3074.md   # also writes the .csv
uv run ific assess-sensitivity 3074 --as-of $DAY --out $OUT/space-3074/sensitivity-3074.md

# Terrestrial BR IFIC 3076
uv run ific ingest t3076
uv run ific terra-assess t3076 --json $OUT/terra-3076/assessment-3076.json
uv run ific terra-export t3076 --out $OUT/terra-3076
```

With the same input hashes and the same code, the JSON files are byte-identical to the submitted ones.

## How the results are checked

- **Consistency reports** for each space run: Tier 1 worst case is never below the Tier 2 maximum, no suppressed or
  never-visible notice exceeds, and agreement with the BR's findings on Finland is listed notice by notice. All
  checks pass in the submission.
- **Sensitivity report**: names the assumptions that can change an outcome. In 3074 these are `adjacent_extent`
  (33 flips), `carrier_in_channel` (5) and `class_values` (8).
- **Reproduction**: the terrestrial tests recompute P.1546 from each stored finding and require agreement within
  0.001 dB; the space tests require two runs to give byte-identical JSON.
- **Hand cross-checks**: every encoded RR Table 21-4 row has a hand-typed check in the test suite.

## Known limits

- The receiver-class values, the RR Table 21-4 transcription and the ECC criteria are cited but still await a
  person's sign-off. Findings say so (`review.status: pending`, `verified: false`).
- Earth-station emissions over terrestrial paths, receiver blocking and aggregation across networks are listed but
  not quantified in `riia-1`.
- The frequencies-of-interest dataset is synthetic. The `stations` results show what the tool does with real station
  data; they are not a statement about real Finnish stations.
- Terrestrial paths assume flat terrain. The stored all-land and all-sea bounds show how much the land mask
  matters for each finding.
- Bilateral agreements (FIN–RUS, FIN–EST, Nordic) are named as governing but not quoted, because their texts are not
  in the inputs.
