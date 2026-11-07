# Terrestrial land mobile assessment (`terra-1`)

This document is the source of truth for the terrestrial model. Code docstrings quote it. It covers foreign land
mobile assignments in the BR IFIC (Terrestrial Services) issues, `brific<no>.mdb`, and the field strength they can
cause at the Finnish border.

The model has the same invariants as the space model `riia-1`
([interference-risk-assessment.md](interference-risk-assessment.md)):

- There is no composite score. Each finding has one of the outcomes `exceeds`, `meets`, `screened_out`,
  `not_applicable` and `not_assessed`, plus its margin to a cited trigger.
- It is reproducible. Two runs give byte-identical canonical JSON, and the stored P.1546 inputs reproduce the
  stored field strength.
- Every input carries a source tag (`<ific_no>:<table>:<key>`) and a citation, and every assumption has an id.

The model is deterministic. Unlike `riia-1` it has no Monte Carlo tier.

## Stage mapping to `riia-1`

| `riia-1` stage | `terra-1` stage | Module |
|---|---|---|
| Ingest (`space` schema) | Ingest of `fxm_*` and `ref_*` tables into the `terra` schema | `ingest.ensure_terra_issue` |
| Hazard inventory | Inventory of foreign land mobile assignments, with change class and publication status | `terra/inventory.py` |
| Tier 0 (overlap, visibility) | Relevance to Finland | `terra/relevance.py` |
| Regulatory context | RR provision, GE06, the ECC criterion and its applicability, M4, bilateral basis | `terra/regulatory.py` |
| Tier 1 (deterministic worst case) | Upper bound at the nearest Finnish point: the larger of all-sea and all-land | `terra/hazards.py` |
| Tier 2 (Monte Carlo) | Deterministic mixed land/sea paths to the nearest Finnish points | `terra/hazards.py` |
| Store, jobs | `analytics.terra_*`, one job per issue on the shared runner (`ific/jobs.py`) | `terra/store.py`, `terra/jobs.py` |
| Review export | CSV, JSON and Markdown exports | `terra/export.py` |
| Drafts | One letter per administration, built on demand under the shared polish guard (`ific/drafting.py`) | `terra/draft.py` |
| — | Neighbour trends and anomaly rules | `terra/trends.py` |

## Data: one issue at a time

Each terrestrial issue is a delta, not a snapshot. Its ADD, MODIFY and SUPPRESS rows carry the issue's own
`pub_no`. Its RECORDED rows are the before-states that the MODIFY and SUPPRESS rows target through `fxm_target`.
Each issue is therefore assessed **on its own**, and every query filters on that issue's `ific_no`, so no join
reaches another file. Assessing issues in any order, or with an issue missing, gives the same per-issue results.

`ingest.TERRA_TABLES` lists the loaded tables. They include the issue's own code tables (`ref_stn_cls`,
`ref_notice_typ` and others), because findings cite them. Ingest is a no-op when the file's sha256 and the table set
are unchanged. Column types are fixed per column. A value that does not cast is stored as NULL, with its text kept in a
`<col>_raw` column and a logged count, so one issue's odd value never changes how another issue is read. Rows are
never dropped.

## Inventory

- **Selection.** An assignment is selected when its station class is `FB` (base station, RR No. 1.71) or `ML`
  (land mobile station, RR No. 1.74), and the class is listed in the issue's own `ref_stn_cls` table, which is
  cited per finding. Rows with `adm = 'FIN'` are excluded, and so are `intent = 'RECORDED'` rows, because those
  are before-states. The plan had proposed selecting by `ref_stn_cls_nat_srv`, but that table maps classes to the
  nature of service (CP, OT, IM and so on), not to the land mobile service, so it cannot make the selection.
- **Change.** The `intent` field gives the change: `ADD` is `new`, `MODIFY` is `modified` and `SUPPRESS` is
  `withdrawn`. A `modified` assignment carries a field diff against its RECORDED target, covering the
  `fxm_terra` fields, the `fxm_ant` power, height and pattern fields, and the `fxm_geo` site. When the target is
  missing from the issue, the diff is `null` with the reason `target_not_in_issue`.
- **Publication status.** This comes from the issue's own `fxm_pub_hist` row with `pub_no` equal to the issue:
  part 1 is `received`, part 2 is `recorded` and part 3 is `returned`. `first_published_in` is the smallest part-1
  `pub_no` in the row's history. The finding comes from `fxm_fdg`, preferring the REX row. The part meanings are
  inferred from 3075–3077 and are to be confirmed against the BR IFIC Preface (`A-T-PUB-PARTS`).
- **Role.** The notice type gives the role. `T12`, `G12`, `T14` and `G14` are transmitting (`tx`), `T13` and `G13`
  are receiving (`rx`), and any other type is `unknown`.
- **Antenna.** When an assignment has several `fxm_ant` rows, the one with the highest e.r.p. is assessed
  (`A-T-ANT-MAX`). Power with `pwr_eiv = E` is e.r.p. Power with `pwr_eiv = I` is e.i.r.p. and is converted by
  subtracting 2.15 dB (RR Nos. 1.161–1.162, `A-T-EIRP-ERP`). Any other power type gives `not_assessed` with
  the reason `unsupported_power_type`.

## Relevance (Tier 0)

A notice is relevant when it has a sufficient signal. Non-relevant notices are kept with `not_applicable`
(`not_relevant`), so the trends and the false-positive review can see them.

| Signal | Sufficient | Source |
|---|---|---|
| `fin_coordination` | yes | `fxm_coord.adm = 'FIN'` (any status) |
| `ge06_affected` | yes | FIN in `ge06_adm_affected_broad` through `ge06_notice_group` |
| `within_range` | yes | site within 1000 km (the P.1546 range) of the nearest Finnish border point |
| `freq_overlap_m4` | no | the assignment overlaps a Finnish M4 allocation row. It is recorded but never decides relevance. On its own it would admit, for example, the CHN 586–860 MHz base stations at about 46°N. |

## Regulatory context

| Layer | Content | Source |
|---|---|---|
| ITU | RR provision from `prov`, with label and citation | `data/ref/terrestrial_frameworks.json` `rr_provisions` |
| GE06 | applies when `notice_typ` starts with `G` or `prov` starts with `GE06-`. It cites GE06 Article 4. | `ge06` |
| CEPT/ECC | the criterion from the registry by band, with per-administration applicability: `applicable` for CEPT members near Finland, `indicative` for RUS, `unknown` otherwise | `ecc_applicability` |
| National | Regulation M4 (with the loaded edition) and the overlapping `ref.m4_allocation` rows by id | `national` |
| Bilateral | the FIN–RUS, FIN–EST and Nordic agreements override the indicative criteria. They are named, never quoted (`A-T-BILATERAL`). | `bilateral` |

Russia's CEPT membership is suspended. ECC criteria applied to RUS notices are therefore `indicative`, and the
FIN–RUS bilateral agreement is stated as governing (`A-T-ECC-RUS`, a user decision of 2026-11-07).

## Criteria

The registry is `data/ref/terrestrial_criteria.json`, loaded by `terra/refdata.py`. A band with no criterion gives
`not_assessed` with the reason `no_criterion_in_registry`. ECC/REC/(08)02 (900/1800 MHz) is not in the registry; this
is an open question.

| Id | Band | Trigger at the border | Time / locations / h2 | Bandwidth correction | Verified |
|---|---|---|---|---|---|
| `tr-25-08` | 29.7–470 MHz | 0 / 6 / 12 / 18 / 20 dB(µV/m) per sub-band, within 25 kHz (Annex 1 A1.2.3) | 10 % / 50 % / 10 m | `10 log10(bw/25 kHz)` above 25 kHz | no |
| `ecc-rec-11-04` | 791–821 MHz | 41 dB(µV/m)/5 MHz (Annex 1, non-preferential PCIs, aligned centre frequencies) | 10 % / 50 % / 3 m (Annex 2, Site General model) | `10 log10(bw/5 MHz)`, any size (Annex 1, page 5) | no |

`tr-25-08` is generated at load time from `ific.propagation.tr2508`, which stays its single source of truth. The
`ecc-rec-11-04` values were transcribed on 2026-11-07 from the ECC document database PDF (document 500, edition of
7 November 2025, SHA-256 `660d7571…24c9f2`), and every value is quoted with its page. The 59 dB(µV/m) border level
for non-aligned frequencies or preferential PCIs is reported next to the assessed level as `other_levels`. A
notice does not say whether its PCIs or centre frequencies are aligned, so the most restrictive level is assessed
(`A-T-ECC-NONPREF`). The band 821–862 MHz is the FDD uplink, which has no base-station trigger. Every finding
carries `verified: false` until a person checks the values against the PDFs.

## Field-strength hazard

There is one hazard per relevant transmitting assignment, `field_strength_border`. Receiving assignments are
`not_applicable` (`receiving_station`), and withdrawn assignments are `not_applicable` (`withdrawn`). The inputs
are:

- f, from `freq_assgn` in MHz;
- the bandwidth, from `bdwdth` in kHz, used as the channel spacing or block size (`A-T-BW-CHANNEL`);
- the e.r.p. in dBW;
- h1, the antenna height above ground from `hgt_agl` (`A-T-H1-AGL`). There is no default: a missing height gives
  `not_assessed` (`missing_antenna_height`), and a height outside 0–3000 m gives `antenna_height_out_of_range`;
- the criterion's time %, location % and h2, with a rural receiver;
- flat terrain, so the terrain clearance angle is not applied (`A-T-FLAT`, and `tca_not_applied` in the P.1546
  assumptions).

The Finnish outline in `finland_land.geojson` (Natural Earth 1:50m, land border and coastline) is sampled every
5 km into 798 points (`A-T-BORDER-SAMPLE`).

- **Tier 0.** A frequency outside 30–4000 MHz gives `not_assessed` (`outside_p1546_range`). No Finnish point
  within 1000 km gives `beyond_p1546_distance`.
- **Tier 1.** The tier computes the all-sea and the all-land path at maximum e.r.p. with an omnidirectional antenna
  to the nearest point and takes the larger as the upper bound. A mixed path lies between the two and E falls
  with distance, so the bound covers Tier 2. Above 100 MHz the sea value is always the larger, but below about
  100 MHz the P.1546 land curves can exceed cold sea by up to 8 dB at 30 MHz. When the bound is at least 3 dB
  below the trigger, the hazard is `screened_out` (`A-T-TIER1-3DB`). The bound, its path kind and its margin are
  stored either way.
- **Tier 2.** The tier evaluates the 25 nearest points within 1000 km, ordered by distance, plus the point on the
  main-beam bearing when the antenna has a diagram. Each great-circle path is sampled every 1 km, and each step is
  classified at its midpoint against `region_land.geojson`. That mask is Natural Earth 1:10m land clipped to
  0–45°E, 50–75°N, rasterised at 0.01°, with lakes and everything outside the box counted as land
  (`A-T-LAND-MASK`). Contiguous runs of steps
  become the P.1546 path zones, with sea taken as cold sea (`A-T-SEA-COLD`). Zone lengths are rounded to 1 m before
  the call, so the stored inputs reproduce E exactly. A directional antenna's attenuation at the bearing is
  interpolated from `fxm_ant_diag` (`A-T-ANT-DIAG`); otherwise the antenna is omnidirectional (`A-T-ANT-OMNI`).
  An input P.1546 rejects, such as h1 below 1 m on a path with sea, gives `not_assessed`
  (`p1546_input_out_of_range`) for that assignment only. The worst point gives E, `margin = E − trigger`, and the outcome `exceeds` when the margin is above 0, otherwise
  `meets`. Each finding also stores the worst point, the path zones, every P.1546 intermediate, and the
  all-land and all-sea values at the worst distance as bounds. Those bounds show how sensitive the result is to
  the land mask.

`terra.hazards.reproduce(hazard)` re-runs P.1546 from a stored finding; the tests require agreement within
0.001 dB.

## Ordering

The ordering uses fixed sort keys, with no score:

1. the outcome: `exceeds`, then `not_assessed`, `meets`, `screened_out` and `not_applicable`, the same ranks as
   `riia-1`;
2. FIN coordination `COORD REQUIRED` first;
3. the margin, descending;
4. the change: `new` and `modified` before `withdrawn`;
5. the publication status: `received`, then `recorded`, then `returned`. Part 1 sorts first until Traficom says
   which part Finland acts on;
6. the terrakey.

## Trends and anomaly rules

Trends count the neighbour administrations' notices (RUS, EST, NOR, S, LVA, LTU) that are first published in an
issue (`received`). A notice republished as `recorded` in a later issue is therefore never counted twice, and the
trend over several issues is the sum of the per-issue counts. The counts are broken down by band, distance bin
(< 50, 50–150, 150–300 and 300–1000 km), station class, notice type, bandwidth code and change. The band is the
criterion band, otherwise the first matching M4 row, otherwise `other`.

The anomaly rules run within one issue:

| Rule | Fires on | Threshold |
|---|---|---|
| `A1-new-band-near-border` | a neighbour's new, received notices within 150 km in a band where the issue has no other notice of that administration | per-issue proxy. Without cross-issue joins, "new band" means new within this issue's own notices and before-states, not within the MIFR |
| `A2-atypical-bandwidth` | a bandwidth above 4 × the median for its band and administration | at least 5 notices |
| `A3-erp-outlier` | an e.r.p. above the 95th percentile for its band and administration | at least 10 notices |
| `A4-fin-coord-open` | FIN coordination still `COORD REQUIRED` | — |

## Draft letters

`terra/draft.py` follows the same contract as `riia/draft.py`. A letter is built on demand for each administration
and issue, and is never stored. It covers the administration's assignments that have one of these kinds. The kind
is a pure function of the stored findings:

- FIN `COORD REQUIRED`, or `exceeds` with no FIN coordination row, gives `coordination_request`;
- `exceeds` with FIN coordination recorded gives `enquiry`;
- a withdrawn assignment, or anything else, gives no letter (409 when the administration has none).

The basis paragraphs come from `data/ref/terrestrial_letter_kinds.json` and the stored regulatory context. For
RUS, the bilateral agreement is cited as governing and the ECC criterion as indicative. The letter refers to
assignments by `adm_ref_id`. Terrakeys, site coordinates and worst points go in the reviewer notes. The annex
quotes the stored f, bandwidth, e.r.p., h1, criterion, trigger, E and margin. The LLM polish may only rewrite the
prose paragraphs. The shared guard (`ific.drafting.check_paragraphs`) rejects any change to the numbers,
identifiers, provisions or the bracketed administration code. The terrestrial wrapper also requires every annex
`adm_ref_id` to appear exactly as often as before.

## Outputs

- **API** under `/api/terrestrial`:
  - `GET /issues`, and `POST /issues/{n}` to ingest if needed and assess as a job (409 while one runs);
  - `GET /issues/{n}/assignments` with the filters `outcome`, `adm`, `change`, `pub_status`,
    `relevant=true|false|all`, `criterion` and `q`;
  - `GET /issues/{n}/assignments.csv`, with the same filters and order, as the flat CSV of `terra-export`;
  - `GET /issues/{n}/assignments/{terrakey}`;
  - `GET /issues/{n}/trends?issues=…`;
  - `GET /issues/{n}/drafts`, `GET /issues/{n}/drafts/{adm}` and `POST …/polish`;
  - `GET /model`.
- **CLI**:
  - `ific ingest tNNNN` (or a `brificNNNN.mdb` path);
  - `ific terra-assess tNNNN [--json PATH]`;
  - `ific terra-export tNNNN --out DIR`, which writes `terra-NNNN.{json,csv,md}`;
  - `ific terra-draft tNNNN [--adm RUS] [--out DIR]`.
- **UI.** The `/terrestrial` page ([frontend.md](frontend.md)).

## Not covered

- Terrain and clutter. The model assumes flat terrain, so it overstates reach over hills and into towns. This is
  conservative for screening.
- Aggregate interference, and services other than land mobile (fixed, broadcasting, LF/MF).
- Chat over terrestrial findings.
- Joins and lineage across issues, by design (the user decision of 2026-11-07).
- The contents of bilateral agreements.
- The space `es_terrestrial` hazard. These modules make it feasible, but it is a follow-up.

## Open questions for Traficom

1. What does each publication part mean, and which one should Finland act on: part 1 (received) or part 2
   (recorded)? Part 1 sorts first until they answer.
2. Should ECC/REC/(08)02 (900/1800 MHz) be added to the registry?
3. Is the ECC applicability per administration correct, in particular `indicative` for RUS?
4. The T/R 25-08 and ECC/REC/(11)04 values need a person's check against the PDFs (`verified_by`).
