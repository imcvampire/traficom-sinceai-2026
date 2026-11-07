# Risk-informed interference assessment of satellite networks for Finland

> **Status: implemented (model `riia-1`), receiver-class values pending review.** Code:
> `backend/src/ific/riia/`. Plan: [`plans/261106-2255-sat-severity-scoring/`](../plans/261106-2255-sat-severity-scoring/plan.md).
> This page explains the method, where each part comes from, and what is still unvalidated. Where the
> implementation differs from the original proposal, see [Implementation (riia-1)](#implementation-riia-1).

## Purpose

Each Space IFIC issue lists 150–200 satellite-network notices; issue 3074 has 196. Most of them cannot affect
Finland. For every notice, this tool answers the questions of the **risk triplet**:

- What can go wrong for Finnish receivers?
- How likely is it?
- What are the consequences?

The answers are expressed in physical units and compared with the ITU-R protection criteria of the affected Finnish
services. The expert can then see which notices put Finnish use at risk, and why.

The tool is **risk-informed, not risk-based**. The technical result is one input to the expert's decision, alongside
the regulatory context (procedure stage, comment deadline, coordination findings). It does not replace the ITU
examination or expert judgement.

Design constraints, inherited from the challenge brief and the project brainstorm:

- **Deterministic.** Monte Carlo sampling uses fixed seeds and fixed sample sizes, so the same input gives a
  byte-identical output.
- **Auditable.** Every number traces back to one of the following:
  - a notice field;
  - an M4 table row;
  - a receiver record;
  - a Radio Regulations (RR) provision;
  - an ITU-R Recommendation;
  - a stated assumption.
- **No LLM in the decision.** An LLM may explain results or draft letters, but it never decides relevance or a limit.

## Method

The method is **risk-informed interference assessment**, as defined by the FCC Technological Advisory Council (TAC,
2015) and de Vries (2015, 2017, 2018). The TAC abbreviates it as RIA; this repo spells it RIIA, hence the `riia`
package and the model id `riia-1`. It follows the TAC steps, and adds the aggregation step that de Vries describes
in his 2018 presentation:

| Step | Source wording | What this tool does |
|---|---|---|
| 1 | "Make an inventory of all significant harmful interference hazard modes" | It lists every hazard mode for each notice and Finnish receiver population, including the modes it cannot yet quantify. |
| 2 | "Define a consequence metric to characterize the severity of hazards" | For active services, I/N in dB at the receiver. For passive services, the received spectral pfd relative to the ITU-R detrimental-interference threshold, in dB. |
| 3 | "Assess the likelihood and consequence of each hazard mode" | It runs Monte Carlo over the receiver population, over time, and over uncertain parameters. Likelihood is the probability of exceeding a consequence value. |
| 4 | "Aggregate results" | For each notice, it overlays all hazard curves on one likelihood–consequence chart, and compares them with the protection criteria of the affected services. |

Some points carry over directly from the sources:

- **No single number.** de Vries (ISART 2018) lists "boil answers down to a single (binary) number" as a common but
  misleading response, because "the world isn't like this". Results stay as curves and as readings off those curves.
- **Quantitative scales, no qualitative bins.** TAC (2015) advises "using a quantitative scale and omitting
  qualitative categories", and notes that "rough estimates of severity and likelihood, even just orders of
  magnitude, will often be sufficient".
- **Tiered analysis.** A cheap deterministic worst-case screen runs first. Probabilistic analysis runs only where
  the screen cannot rule out harm. This is the US EPA's tiered approach, as reported in the Silicon Flatirons 2015
  report.

## Receiver populations

Likelihood in this method is "the probability of occurrence of a hazard in a population of devices" (TAC, 2015).
Each hazard is therefore evaluated over a **population** of Finnish receivers. The model reads receivers through
one interface, implemented by two sources:

| Source | Status | Population |
|---|---|---|
| **Generic** (`generic-m4`) | Used for the demo | For each protected Finnish service in each M4 sub-band, one receiver per cell of a 0.25° × 0.5° grid inside Finland's land boundary (495 sites). Each receiver uses the ITU-R reference characteristics of its service class. Parameters that vary between real stations, such as antenna azimuth and height, are drawn from stated distributions. |
| **Stations** (`stations`) | Planned, for the real analytics | The stations in the frequencies-of-interest dataset (`data/special_interest/`), with their real location, receive channel, bandwidth, antenna height, azimuth, directivity and, where present, gain. Missing values are drawn from the same class distributions and marked as assumptions. |

Every result records its receiver source. A generic result means "if this Finnish service were deployed across
Finland with typical characteristics". A stations result means "for the stations actually listed".

## Step 1: hazard inventory

For each notice, the hazard modes are:

| Mode | Applies when | Status in `riia-1` |
|---|---|---|
| **Co-channel, space→Earth** | A downlink assignment group overlaps the receiver's band | Quantified. The interference is the sum over all satellites of the system in view. |
| **Adjacent-band unwanted emissions, space→Earth** | A downlink lies within the out-of-band or spurious domain of the receiver's band | Quantified. The emission mask follows Rec. ITU-R SM.1541 in the out-of-band domain and RR Appendix 3 in the spurious domain. Receiver selectivity comes from the service class. |
| **Earth-station emissions over a terrestrial path** | An Earth→space notice has earth stations near Finland | Inventoried, quantified later. It needs the terrestrial propagation module that the terrestrial side quest builds. Until then it is listed as *not assessed*, with the earth-station distance shown. |
| **Receiver blocking and intermodulation** | Strong downlinks near the receiver's band | Inventoried, *not assessed*. There is no receiver blocking data. |
| **Aggregate across different networks** | Several notices in the same band | Inventoried, *not assessed*. The scope is one notice at a time. |

Listing what is not assessed is deliberate. The TAC values a full inventory because it "increase[s] the chances of
identifying unexpected harmful interference mechanisms".

## Step 2: consequence metric

| Service type | Consequence metric | Basis |
|---|---|---|
| Active services: fixed, mobile, broadcasting, radionavigation, MetSat earth stations | I/N in dB at the receiver input | TAC (2015) lists I/N among the RF consequence metrics. ITU-R protection criteria for these services are expressed as I/N, or as interference power, together with a time percentage. |
| Passive services: radio astronomy | Received spectral pfd minus the detrimental-interference threshold, in dB | Rec. ITU-R RA.769 expresses protection as spectral pfd thresholds. EESS passive sensors (Rec. ITU-R RS.2017) are spaceborne, so they are not a Finnish ground population and riia-1 excludes them. |

The I/N calculation for an active receiver:

```
pfd_s    = P_s + G_s(φ_s) − 10·log10(4π·d_s²) − 10·log10(B_s)          per satellite s in view, dBW/m²/Hz
I        = 10·log10( Σ_s 10^((pfd_s + 10·log10(B_overlap,s) + G_r(θ_s) + 10·log10(λ²/4π) − M_s)/10) )   dBW
N        = 10·log10(k·T₀·B_r) + NF_r                                     dBW
I/N      = I − N
```

| Term | Meaning |
|---|---|
| `P_s` | Peak carrier power, from `emiss.pep_max`. |
| `G_s(φ_s)` | Satellite antenna gain toward the receiver. For a geostationary satellite, Rec. ITU-R S.672 is applied around the beam boresight (`s_beam`). With no boresight, or for a steerable non-geostationary beam, the peak gain is used and marked as an assumption. |
| `B_overlap,s` | The part of the carrier inside the receiver's channel. |
| `M_s` | The unwanted-emission attenuation. It is 0 for co-channel, and follows the SM.1541 / Appendix 3 mask plus the receiver's selectivity for adjacent band. |
| `G_r(θ_s)` | Receiver gain toward satellite *s*, from the service class's ITU-R reference pattern: F.1245 for fixed and radiolocation (F.699 in the sensitivity run), BT.419 for broadcasting, S.465 for FSS/BSS and MetSat earth stations, omnidirectional for mobile, radionavigation, MSS and RNSS terminals, RA.1631 for radio astronomy. |
| `NF_r` | Receiver noise figure, from the service class. |
| `B_r` | Receiver channel bandwidth. |

When the notice carries a notified pfd (`c_pfd`) or a pfd mask (`mask_info`), that value replaces the calculated
`pfd_s`.

## Step 3: likelihood and consequence

### Sampling

For each hazard, the model draws a fixed number of samples over three things:

- **Receivers in the population:** the grid cells or stations, with distributed parameters.
- **Time:**
  - for non-geostationary systems, a time instant over the constellation's repeat pattern, from a circular-orbit
    model (inclination, altitude, planes, satellites per plane, right ascension);
  - for geostationary satellites, the position within the station-keeping tolerance (`geo.tol_east`, `tol_west`).
- **Uncertain parameters:** each has a distribution in the service-class file, for example the azimuth of a
  directional fixed link (uniform over 0°–360° in the generic population).

The sample size depends on the smallest time percentage *p* among the relevant criteria:
N = max(10,000, ⌈100 / p⌉), capped at 1,000,000. This follows the MetSat/LTE study, which used 10,000 to 1 million
samples "depending on time %". The random generator is seeded from `(model_version, ific_no, ntc_id, hazard_id)`.

### Tiered screening

| Tier | What it does | Outcome |
|---|---|---|
| **Tier 0: inventory** | Frequency overlap and visibility (above the horizon anywhere in Finland). | A hazard with no overlap, or never visible, is *not applicable* and is recorded as such. |
| **Tier 1: deterministic worst case** | Each parameter at its worst value: closest geometry, receiver main beam toward the satellite, peak satellite gain. | If even the worst-case consequence stays below every protection level of the service, the hazard is *screened out*, and the worst-case value is shown. |
| **Tier 2: probabilistic** | Monte Carlo as above. | Gives the likelihood–consequence curves. If Tier 2 cannot run (for example, the orbit data is missing), the hazard is `not_assessed`, and its worst-case value is shown. A worst case alone is never reported as `exceeds`. |

### Likelihood

ITU-R protection criteria are stated per receiver, as a level not to be exceeded for more than *p*% of the time. The
model therefore computes likelihood at two levels, matching the TAC's two likelihood framings: % of time and % of
locations or devices.

1. **Per receiver:** a time-exceedance curve, `F_r(x) = P_time(consequence > x)`. "Exceeds" is strict throughout: a value equal to a criterion level does not exceed it.
2. **Across the population**, for each criterion time percentage *p*: the consequence a receiver exceeds for *p*% of
   the time is `X_r(p) = F_r⁻¹(p)`. The **risk curve** is then `L_p(x) = share of receivers with X_r(p) > x`.

A geostationary satellite's geometry is fixed, so each receiver's time curve is essentially a step, and the
likelihood comes from the receiver population. A non-geostationary system contributes both a time component and a
population component.

## Step 4: aggregation and acceptability

### The acceptability boundary is the protection criterion

In the MetSat/LTE case, the acceptable-risk test was the ITU-R protection criterion itself: "Long-term interference
may not exceed −116 dBm more than 20% of the time", plus a short-term criterion at 0.0125% of the time (de Vries,
ISART 2018). This tool applies the same test. Each Finnish service class has its criterion points `(level_k, p_k)`
from its ITU-R Recommendation, for example a long-term point and a short-term point.

A receiver **violates** its criterion if `F_r(level_k) > p_k` for any point *k*.

### Results per hazard

| Field | Meaning |
|---|---|
| `outcome` | One of `exceeds` (at least one receiver in the population violates), `meets`, `screened_out`, `not_applicable` or `not_assessed`. |
| `share_violating` | The share of the receiver population that violates the criterion. With the stations source, this is also given as a count. |
| `exceedance_db` | For each criterion point, the consequence at that point's time percentage minus the criterion level. It is read at the population median and at the 95th percentile. |
| `risk_curves` | `L_p(x)` for each criterion percentage *p*, on a fixed grid from x = −40 dB to +40 dB in 1 dB steps. |
| `worst_case_db` | The Tier 1 value. |

### Results per notice

- **Every hazard curve is shown on one likelihood–consequence chart**, with the criterion points of each affected
  service. This follows Fig. 7(b) of the TAC introduction: risk curves "for different interference modes … would
  help prioritize which failure modes to focus on".
- **The notice outcome is the set of hazard outcomes**, not a combined score. For example: "exceeds: fixed (2025–2110
  MHz), 18% of receivers, +6 dB at 20% of time; meets: broadcasting; not assessed: earth-station terrestrial path".

### Sorting a list of notices

The issue table needs a default order. It sorts by readings off the curves, never by a composite score:

1. Outcome: `exceeds`, then `not_assessed` only, then `meets`, then `screened_out`.
2. Largest `share_violating`.
3. Largest median `exceedance_db`.
4. `ntc_id`.

The expert can re-sort by any reported quantity. Two curves can cross, so one notice is "riskier" than another only
when its curve lies above the other's everywhere. The comparison view overlays the curves of selected notices so this
can be seen.

## Regulatory context and the work queue

The technical risk is not multiplied by deadlines. The regulatory context is shown next to it, and drives the work
queue as a filter and sort order.

| Field | How it is computed |
|---|---|
| **Stage** | RR No. 9.6 coordination request (CR/C), RR No. 11.2 notification, RR No. 9.1 advance publication (API/A), Resolution 49. |
| **Days left** | Days left in the comment window, counted from the IFIC publication date (`notice.d_wic`). For a CR/C, the window is the four months of RR No. 9.52. Under No. 9.52C, an administration that does not reply in time can be treated as not affected. Window lengths per provision live in a reference file that cites the RR edition. |
| **BR identified Finland** | Finland is listed under a coordination provision in `provn` (for example 9.11, 9.14, 9.21 or AP30A §7.1), or a Finnish network is listed as affected in `tr_aff_ntw`. Otherwise, Finland may request inclusion under RR No. 9.41. |

**Work queue:** the notices with at least one `exceeds` hazard whose comment window has not closed: the window is
still open, or the notice is at a stage without one (Notification, Resolution 49). They are sorted by days left, with
the notices that have no window after those that do, then by the technical sort above. BR findings are shown beside
each notice and can be filtered on, but do not put a notice in the queue on their own. The evaluation date is an explicit `as_of`
input recorded with every result, and only the UI defaults it to today.

## Data availability (IFIC 3074)

| Input | Coverage |
|---|---|
| Assignment bands (`grp.freq_min/max`, MHz) | All 34,365 groups |
| Transmit power (`emiss.pep_max`) | Most geostationary and non-geostationary groups |
| Satellite antenna gain (`s_beam.gain`) | 2,299 of 2,304 beams |
| Geostationary position and tolerance (`geo`) | All 72 geostationary notices |
| Non-geostationary orbit (`orbit`) | 100 of 110 non-geostationary notices |
| Notified pfd (`c_pfd`) and masks (`mask_info`) | 49 notices; 6 notices |
| BR coordination findings naming Finland (`provn`) | 220 group rows (9.11: 72, 9.14: 34, 9.21/C: 106, 11.31.1: 6, AP30A §7.1: 2) |
| Finnish networks listed as affected (`tr_aff_ntw`) | 8 rows (FIN10300 and FIN10400 at 22.8°E) |

**Frequencies-of-interest dataset (stations source).** It has 875 synthetic stations, all inside Finland:

| Licence class | Stations |
|---|---|
| FX | 320 |
| Unclassified | 294 |
| BC | 117 |
| MVV | 63 |
| BT | 58 |
| MUUT | 22 |

Matching frequency alone, 130 of the 176 3074 notices with downlinks overlap at least one station, so likelihood and
consequence are needed to separate them. Receiver gain is present for 85 stations.

## Inputs and their sources

Every input carries a source tag (`physics`, `rr`, `itu-r`, `data` or `assumption`) and a citation. The UI shows the
tag next to each value.

### Method references

These were read in the primary text while writing this page:

| Reference | What it supports |
|---|---|
| FCC TAC Spectrum and Receiver Performance Working Group, [*A Quick Introduction to Risk-Informed Interference Assessment*](https://transition.fcc.gov/bureaus/oet/tac/tacdocs/meeting4115/Intro-to-RIA-v100.pdf), v1.00, 1 April 2015 | The steps, likelihood as a probability in a population, quantitative scales, risk curves per interference mode and harm threshold, and "risk-informed, not risk-based". |
| J. P. de Vries, [*Risk-informed interference assessment*](https://www.ntia.gov/sites/default/files/publications/15-05-12_csmac_risk_hand-out_0.pdf), CSMAC handout, 12 May 2015 | The risk triplet, I/N as a consequence metric, Monte Carlo likelihood–consequence profiles, and aggregation. |
| J. P. de Vries, [*Modeling Interference Risk: Propagation and Other Uncertainties*](https://its.ntia.gov/media/66520/devries_isart2018.pdf), ISART, 26 July 2018 | The four-step method including "aggregate results", protection criteria as the acceptability test, the sample size by time %, sensitivity analysis, and the warning against single numbers. |
| Silicon Flatirons Center, [*Risk Assessment in Spectrum Policy*](https://siliconflatirons.org/documents/publications/report/201512RiskAssessmentReport.pdf), 2015 report | Tiered analysis (deterministic screen first), and the observation that worst-case assumptions compound. |
| Voicu, Simić, de Vries, Petrova and Mähönen, "Risk-Informed Interference Assessment for Shared Spectrum Bands: A Wi-Fi/LTE Coexistence Case Study", [arXiv:1706.02479](https://arxiv.org/abs/1706.02479) | A worked application: likelihood as a CCDF, likelihood–consequence charts, and curves that cross. |

These were cited by the documents above but not read directly:

- de Vries, "Risk-informed interference assessment: A quantitative basis for spectrum allocation decisions",
  *Telecommunications Policy* 41(5), 2017,
  [doi:10.1016/j.telpol.2016.12.007](https://doi.org/10.1016/j.telpol.2016.12.007). An earlier conference version
  (TPRC 2015) is on [SSRN](https://ssrn.com/abstract=2574459).
- De Vries, Livnat and Tonkin, "A Risk-Informed Interference Assessment of MetSat/LTE Coexistence", *IEEE Access*
  5, 2017, [doi:10.1109/ACCESS.2017.2685592](https://doi.org/10.1109/ACCESS.2017.2685592).

### Technical references

Each ITU-R Recommendation link opens its landing page, which lists all versions. The version used for each value is
recorded in `data/ref/receiver_classes.json`.

| Input | Source |
|---|---|
| Link budget, thermal noise and geometry | `physics` |
| Protection criteria `(level, time %)` per service | Rec. ITU-R [F.758](https://www.itu.int/rec/R-REC-F.758/en) (fixed), [SA.1026](https://www.itu.int/rec/R-REC-SA.1026/en) (MetSat), [RA.769](https://www.itu.int/rec/R-REC-RA.769/en) with [RA.1513](https://www.itu.int/rec/R-REC-RA.1513/en) (radio astronomy), [RS.2017](https://www.itu.int/rec/R-REC-RS.2017/en) (EESS passive), and the relevant M-series and BT-series Recommendations for mobile, radionavigation and broadcasting. They are transcribed into `data/ref/receiver_classes.json`, each with a citation, and reviewed by a person. |
| Receiver antenna patterns | Rec. ITU-R [F.1245](https://www.itu.int/rec/R-REC-F.1245/en) / [F.699](https://www.itu.int/rec/R-REC-F.699/en), [BT.419](https://www.itu.int/rec/R-REC-BT.419/en), [RA.1631](https://www.itu.int/rec/R-REC-RA.1631/en); omnidirectional for mobile and radionavigation. |
| Satellite antenna roll-off | Rec. ITU-R [S.672](https://www.itu.int/rec/R-REC-S.672/en). |
| Unwanted emission masks | Rec. ITU-R [SM.1541](https://www.itu.int/rec/R-REC-SM.1541/en); [RR](https://www.itu.int/pub/R-REG-RR) Appendix 3. |
| pfd limits (shown for context) | [RR](https://www.itu.int/pub/R-REG-RR) Article 21, Table 21-4. |
| Finland land boundary (generic grid) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m, public domain. |
| Regulatory context | [RR](https://www.itu.int/pub/R-REG-RR) No. 9.1, 9.6, 9.41, 9.52, 9.52C and 11.2; Resolution 49; the BR findings in the IFIC. |

### Assumptions, tagged `assumption`

- **Generic population:**
  - it is built from the M4 sub-bands on a grid over Finland, so each protected service is assumed to be deployed
    everywhere in Finland;
  - each service class has distributions for antenna azimuth, height and elevation pointing.
- **Missing receiver data:** gain, noise figure and selectivity default to the class values from ITU-R
  Recommendations; how those defaults spread across stations is an assumption.
- **Satellite antennas:**
  - steerable non-geostationary beams, and beams with no boresight, use peak gain;
  - carriers transmit at `pep_max` all the time, with no duty cycle.
- **Orbit model:** circular orbits only. Highly elliptical orbits use the apogee altitude, and the result is marked.
- **Grid density** (0.25° × 0.5°) and **sample sizes.**

## Sensitivity analysis

de Vries (ISART 2018) stresses that results can be very sensitive to the assumed inputs. In the MetSat/LTE case, a
change of propagation model alone moved aggregate interference by more than 20 dB. Each run therefore includes a
sensitivity report. Every `assumption` input is moved to the low and high end of its stated range, and the report
gives:

- the shift in median `exceedance_db`;
- the number of hazard outcomes that change (for example from `meets` to `exceeds`);
- the change in `share_violating`.

Inputs whose change flips outcomes are listed in the result as **outcome-sensitive**.

## Implementation (riia-1)

Code lives in `backend/src/ific/riia/`; the receiver classes, comment windows, RR Article 21 context rows and the
Finland boundary are in `data/ref/`. Bumping `MODEL_VERSION` (`riia/__init__.py`) changes every Monte Carlo seed, so
every issue must be re-assessed after a bump; stored results keep the version they were made with.

### Differences from the proposal above

- **Schema.** Space IFIC tables are loaded into the DuckDB schema `space` (a schema named `ific` is ambiguous with the
  `ific.duckdb` catalog). `provn` keeps only rows with `adm = 'FIN' OR ctry = 'FIN'`, `tr_aff_ntw` only `adm = 'FIN'`.
- **Service classes.** `receiver_classes.json` defines ten classes, matched by an ordered keyword table on the
  **primary** (upper-case) services of M4: fixed, mobile, broadcasting, radiolocation, radionavigation, radio
  astronomy, FSS/BSS earth station, MSS terminal, MetSat earth station and RNSS receiver. Every value carries a
  citation; the file is marked *review pending* until a person checks it against the cited Recommendation versions.
- **Population size.** 588 merged class bands × 495 grid cells. Receiver azimuth, pointing elevation and height are
  drawn per site and hazard from the class distributions.
- **Sample plan.** For a hazard with S sites, `N = max(10⁴, ⌈100/p⌉)` samples are split as at least `⌈100/p⌉` time
  samples per site; if that exceeds 10⁶ samples, sites are subsampled evenly and the result says so.
- **One beam per satellite.** Per satellite, the strongest assignment group counts (maximum, not sum); satellites in
  view are summed. A group with a notified pfd (`c_pfd`, reference bandwidth in kHz) uses it instead of the
  calculated pfd. `mask_info` values are not loaded, so masked notices use the calculated pfd.
- **Notice summary.** The worst outcome of a notice is taken over the co-channel and adjacent-band hazards, plus the
  earth-station terrestrial hazard of an earth-station notice within 1 000 km of Finland (an assumption). The other
  inventory modes are always listed but do not set the worst outcome, otherwise every notice would be `not_assessed`.
- **Radio astronomy.** The consequence is `spfd + G_r(θ) − RA.769 threshold`, with `G_r` the absolute RA.1631 gain,
  so main-beam coupling counts in full. The ITU EPFD convention normalises by the peak gain instead; which one to use
  is an open review question.

### Interfaces

| Interface | Behaviour |
|---|---|
| `uv run ific ingest <no or path>` | Loads one issue; an unchanged sha256 is a no-op. Exits 2 if the DB is locked by the API. |
| `uv run ific assess <no> [--as-of] [--json] [--consistency] [--summary]` | Foreground run with progress; stores results and writes the canonical export and reports. |
| `uv run ific assess-sensitivity <no> --as-of …` | Runs the fixed perturbation list and writes `plans/reports/sensitivity-…md`; flags outcome-sensitive assumptions for the UI. |
| `GET /api/risk/issues` | Discovered and ingested issues, outcome counts and job progress. |
| `POST /api/risk/issues/{no}?as_of=` | Ingests if needed (under the job lock), then starts a background job: 202, 404, 409 while running, 422 on ingest errors. |
| `GET /api/risk/issues/{no}/notices?as_of=&view=` | Technical order, or `view=queue` for the work queue. `as_of` only changes the regulatory fields. |
| `GET /api/risk/issues/{no}/notices/{ntc_id}?as_of=` | Full hazard inventory with curves, inputs, citations, assumptions and regulatory context. |
| `GET /api/risk/model` | Method steps, references, receiver classes and input sources. |
| `GET /api/risk/issues/{no}/notices/{ntc_id}/draft?as_of=` | Draft letter to the notifying administration (see [Draft correspondence](#draft-correspondence)): 404 when not assessed, 409 with the reason when there is no concern. |
| `POST /api/risk/issues/{no}/notices/{ntc_id}/draft/polish?as_of=` | LLM rewrite of the letter's prose under the protected-token guard: 422 with `missing` and `added` tokens when rejected, 503 when the LLM is off, 429 when busy. |
| `uv run ific draft <no> --as-of … [--ntc N] [--out DIR]` | One Markdown draft per notice with a concern; needs the API stopped. |

Results go to `analytics.risk_notice`, `risk_hazard`, `risk_job` and `risk_sensitivity`; one transaction replaces an
issue's rows, and a failed job keeps the previous results. Jobs run on their own thread and DuckDB cursor, one per
issue at a time; a job left `running` by a restart is marked failed.

### Results on IFIC 3074 (generic population, `as_of` 2026-11-06)

- **Run time:** about 220 s on a laptop (Tier 1 4 s, Tier 2 213 s for 579 Monte Carlo hazards; 149 hazards screened
  out at Tier 1). Two runs give byte-identical exports.
- **Notice worst outcome:** exceeds 82, not assessed 9, meets 36, screened out 5, not applicable 64.
- **Consistency:** Tier 1 bounds Tier 2 for every hazard; no suppression or never-visible notice exceeds. The BR named
  Finland under a technical provision for 15 notices; 9 have a live hazard. The 6 misses are a GSO at 52.5°W that is
  below Finland's horizon (9.11) and two NGSO networks whose downlinks touch no protected band of a riia-1 class
  (9.21/C), each notified twice. See `plans/reports/consistency-261106-riia1-3074.md`.
- **Outcome-sensitive assumptions:** peak satellite gain and full duty cycle (117 flips each at −10 dB), the
  adjacent-band extent (33), fixed-link pointing elevation (25), the F.699 instead of F.1245 pattern (8), carrier
  placement (5) and FSS dish pointing (1). See `plans/reports/sensitivity-261106-riia1-3074.md`.
- **Work queue:** empty at this `as_of`, because every four-month window of 3074 (published 2026-06-23) closed on
  2026-10-23. Set `as_of` before that date to see it.

### Concern triage for manual review

Expert guidance (2026-11-07): a concern is an exceedance of the defined limit, a close-by exceedance or a semi-high
pfd near the frequency, with the trigger lowered when a Finnish high-gain antenna points in direct line at the IFIC
transmitter location. `ific review <no> --as-of …` turns this into three readings over the stored results of both
receiver sources (definitions in `backend/src/ific/riia/review.py`), never a score:

| Reading | Rule |
|---|---|
| `exceeds` | A receiver violates a criterion point. |
| `near_limit` | No violation, but the 95th-percentile exceedance is within 6 dB of a criterion level (assumption). |
| `main_beam` | A directional, high-gain station whose half-power beam (θ3dB ≈ 70·λ/D) contains the notified GSO position. |

The stations source (`ific assess <no> --source stations`) uses the frequencies-of-interest stations: real location,
receive band, height, azimuth and gain. Broadcast transmitter licences are excluded; station gains above a 4 m, 60 %
aperture are capped as data errors; directional stations in an omnidirectional class use the F.1245 envelope.

### Draft correspondence

Step 9 of the brief: name the counterparty and draft correspondence for expert review. `backend/src/ific/riia/draft.py`
builds a letter from the Administration of Finland to the notifying administration (`space.notice.adm`) for a notice
that has at least one triage reading (`exceeds`, `near_limit` or `main_beam`) in the stored `stations` or
`generic-m4` results. A notice without a reading gets no draft. Drafts are built on demand and never stored.

The letter kind is a pure function of the stored regulatory context, quoting the cites in
`data/ref/rr_comment_windows.json`:

| Kind | Rule | Basis |
|---|---|---|
| `comment_9_52` | Stage CR/C, window open, the BR identified Finland | RR No. 9.52 (with No. 9.52C) |
| `inclusion_9_41` | Stage CR/C, window open, the BR did not identify Finland | RR No. 9.41, and comments under No. 9.52 |
| `comment_9_3` | Stage API/A, window open | RR No. 9.3 |
| `enquiry` | Any other case: Notification, Resolution 49, or a closed window | None; an informal technical enquiry, with a warning |

`as_of` only moves a notice between kinds through the comment window, as everywhere else.

- **Counterparty.** The administration name comes from `data/ref/itu_administrations.json` (symbol → name, cited to
  the IFIC Preface, review status pending). An unknown code is shown as the code with a warning, never a guessed name.
- **Annex.** One row per receiver source, hazard and reading, with the stored share of receivers violating, worst
  95th-percentile exceedance, Tier 1 worst case, bands and the criterion (metric, level, time %, cite) behind the
  worst exceedance. Values are copied from the stored hazard; only display rounding is applied. A `Basis` line quotes
  the RR cite verbatim. The annex reads off outcomes and never combines them.
- **Reviewer notes** (internal, never part of the letter): the deadline, the receiver sources used and skipped, the
  outcome-sensitive assumptions of each cited hazard, the radio astronomy weakness (item 8 below), the review status
  of the reference tables, and station-level details of `main_beam` readings. Station ids, coordinates, azimuths and
  gains come from an internal dataset, so they stay out of the letter, which only names the band and service.
- **LLM polish.** Only the body paragraphs are sent to the LLM; the header, annex and Basis line never are. Every fact
  in the prose is written in digits so that a guard can check it: the rewrite must keep exactly the same protected
  tokens (numbers, dates, provisions, hazard ids, the bracketed administration code) and the same number of
  paragraphs, or it is rejected and the template text is kept. The LLM picks nothing: not the kind, the provision or
  the hazards.
- **Not covered:** AP30/AP30A/AP30B plan-procedure letters, "no objection" replies, French or Spanish letters,
  letter addresses and signatories (placeholders), and storing or tracking drafts.

## Known weaknesses

1. **The generic population overstates exposure.** It assumes every protected M4 service is deployed everywhere in
   Finland. The stations source removes this assumption.
2. **The satellite emits all the time at full power.** The worst-case beam assumption for steerable non-geostationary
   beams also overestimates interference where the notice carries no pfd mask.
3. **Three hazard modes are inventoried but not assessed:** earth-station terrestrial paths, blocking and
   intermodulation, and aggregation across networks. Results show them as `not_assessed`, never as safe.
4. **There is no measured accuracy yet.** The checks below are internal consistency checks and agreement with the
   BR's findings. They are not a comparison with expert-labelled cases.
5. **Service classes are matched by keyword** on the M4 service text. The matched keyword is shown so that a reviewer
   can catch a wrong match.
6. **Receiver-class values are unreviewed.** They were transcribed for riia-1 without the primary texts open.
7. **IFIC 3074 carries no beam boresight data**, so every beam uses peak gain toward every receiver; S.672 is
   implemented and tested but never applies to 3074.
8. **Radio astronomy adjacent-band hazards are extreme** (tens of dB over the RA.769 thresholds) because the worst
   carrier placement puts the carrier edge at the band edge, where the SM.1541 mask is 0 dB.

## Not covered

- Scoring of AP30, AP30A and AP30B plan notices. The 3074 `.mdb` has no such notices. It has only AP30A coordination
  references naming Finnish networks, which appear in the regulatory context.
- The ITU EPFD (Art. 22) and ΔT/T (Appendix 5) examinations. This tool complements them; it does not reproduce them.
- Terrestrial notices. The receiver interface, hazard inventory and risk-curve output are designed so that the
  terrestrial side quest can reuse them, with P.1546 field strength against T/R 25-08 as the consequence.

## How the model is checked

Automated checks on IFIC 3074, using the generic population and a fixed `as_of`:

| Check | What it shows |
|---|---|
| Tier 1 worst case is always at least the Tier 2 maximum, for every hazard | The tiers are consistent. |
| Suppressions and notices never visible from Finland have no `exceeds` hazards | Tier 0 works. |
| Notices for which the BR identified Finland under a technical provision (9.11, 9.14, 9.21, AP30A §7.1) have at least one hazard that is not `screened_out` or `not_applicable`. Misses are listed with their worst-case values. | Agreement with an independent, authoritative signal. The BR findings are not used as an input. |
| Sensitivity report as above | Which conclusions depend on assumptions. |
| Two runs with the same `as_of` produce byte-identical exports | Reproducibility, including the seeded Monte Carlo. |

Future validation:

| Step | What it would show |
|---|---|
| A stations-source run compared with the generic run on 3074 | How much the generic population overstates exposure |
| Expert review by Traficom of about 20 notices from 3074 | Whether the outcomes match expert judgement |
| Concerns Traficom raised on 3074, if shared | Hit rate of `exceeds` against real concerns |
