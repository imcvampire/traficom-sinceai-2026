---
title: Terrestrial land-mobile side quest
description: Assess foreign land-mobile notices in terrestrial BR IFIC issues against T/R 25-08 and ECC/REC/(11)04 with deterministic P.1546 field strengths at the Finnish border, on a new /terrestrial page with trends, drafts, exports and a download watcher.
status: completed
mode: auto
priority: P1
effort: 2.5d
branch: main
tags: [backend, api, frontend, cli, watcher, propagation]
blockedBy: []
blocks: []
created: 2026-11-07
source: plans/reports/brainstorm-261107-1401-terrestrial-land-mobile.md (accepted contract, user decisions 2026-11-07)
---

# Terrestrial land-mobile side quest

## Outcome

Each terrestrial BR IFIC issue (`brific<no>.mdb`) is ingested and assessed **on its own**. The assessment
classifies each foreign land-mobile assignment as new, modified or withdrawn, and gives its publication status
(received, recorded with its finding, or returned). It then:

- filters the assignments to those relevant to Finland, using notice data;
- attaches the ITU, GE06, CEPT/ECC and national framework;
- picks the criterion;
- computes the deterministic ITU-R P.1546 field strength at the Finnish border.

Each finding stores the source notice, the field strengths, the model parameters, the assumption ids and the
citations. A new `/terrestrial` page shows the findings, the evidence, a map, neighbour trends and a draft letter
built like the space drafts. CSV, JSON and Markdown exports cover 3076. A second watcher source downloads new
terrestrial issues.

The full contract (evidence, trade-offs, rejected options) is in
[the brainstorm report](../reports/brainstorm-261107-1401-terrestrial-land-mobile.md). This plan does not repeat
it.

## Contract

- **Constraints**
  - **No composite score, and reproducible.** Outcomes are the same five as `riia-1`. Two runs give
    byte-identical JSON. Every input has a source tag and citation, and every assumption an id.
  - **Deterministic only**, with no Monte Carlo.
  - **One issue at a time.** Assessing an issue reads only that issue's rows. Status comes from that file's
    `fxm_pub_hist` and `fxm_fdg`.
  - **`/risk` stays space-only.** Its page, its components, `riia/schemas.py` and the `/api/risk` types are not
    modified. Shared modules may be extracted only if every `riia` test passes unchanged.
  - **RUS criteria are indicative.** Russia's CEPT membership is suspended, so ECC criteria applied to RUS
    notices are `applicability: indicative`, and the FIN–RUS bilateral agreement is the stated basis (an
    assumption id).
  - DuckDB allows one writer: the CLI fails while the API runs, and the API triggers assessments through the job
    runner.
  - The demo is Sunday 8 Nov. Phases are ordered so that a usable vertical slice (phases 1–4) exists first.
- **Non-goals**
  - Chat over terrestrial results.
  - Terrain or DEM data. The model assumes flat terrain, and `tca_not_applied` is flagged per finding.
  - Aggregate interference, and services other than land mobile.
  - Quantifying the space `es_terrestrial` hazard.
  - Verifying the contents of bilateral agreements.
  - Joins or lineage across issues.
  - Auto-ingest after a download.
- **Acceptance criteria:** criteria 1–11 of the brainstorm report, as amended on 2026-11-07. Each phase lists the
  criteria it closes.

## Phases

| # | Phase | Status | Depends on | Closes |
|---|---|---|---|---|
| 1 | [Terrestrial ingest and fixtures](phase-01-terrestrial-ingest.md) | completed | — | AC1 |
| 2 | [Reference data: criteria, frameworks, land mask](phase-02-reference-data.md) | completed | — | (feeds AC4) |
| 3 | [Assessment model `terra-1`](phase-03-assessment-model.md) | completed | 1, 2 | AC2–AC6, AC9 |
| 4 | [Store, job runner, API, CLI, exports](phase-04-store-api-cli.md) | completed | 3 | AC6, AC8 (exports) |
| 5 | [Trends, anomalies and draft letters](phase-05-trends-drafts.md) | completed | 4 | AC10, trends part of AC7 |
| 6 | [Terrestrial watcher source](phase-06-watcher-source.md) | completed | 1 | AC11 |
| 7 | [`/terrestrial` page](phase-07-terrestrial-page.md) | completed | 4, 5 | AC7 |
| 8 | [Docs, real-data verification and 3076 submission](phase-08-docs-verify.md) | completed | all | AC8, final check of all |

Phases 2 and 6 can run in parallel with 1, 3 and 4, because their files do not overlap. Phase 7 can start
against phase 4's API types while phase 5 is in progress.

## Architecture

```
brific<no>.mdb ──ingest──▶ terra.* (tagged ific_no)
                              │
               terra/inventory ─ land-mobile TX/RX, intent class, pub status (own file only)
                              │
               terra/relevance ─ FIN coordination  │  distance ≤ screening range
                              │
               terra/regulatory ─ RR prov · GE06 Art.4 · ECC criterion (+applicability) · M4 row · bilateral
                              │
               terra/hazards  ─ Tier 1 all-sea worst case ─▶ screened_out
                              │ Tier 2 mixed land/sea path, sampled FI border points (p1546.field_strength)
                              ▼
               analytics.terra_* ──▶ /api/terrestrial ──▶ /terrestrial page · exports · drafts · trends
```

Stage mapping to `riia-1`, which the method doc will state: inventory corresponds to the hazard inventory,
relevance to Tier 0, Tier 1 to Tier 1, and Tier 2 to Tier 2, made deterministic. The regulatory context, the
store, the job runner, the review export and the drafts each follow the same pattern as the space side.

**Extension trace.** The shared boundary is the outcome, assumption and citation shape, plus the job runner.
`riia` and `terra` are the two real variants. Under this plan the following stay unchanged:

- the outcome literal;
- the job lifecycle: one job per `(ific_no, source)`, a 409 on a duplicate request, and failed-on-restart;
- canonical JSON;
- the draft polish guard.

Each side owns its own population, physics and criteria. Phase 4 proves the seam: `riia` tests pass unchanged
on the extracted runner, and `terra` uses the same runner. No registry or plugin layer is added.

## Key risks

| Risk | Mitigation |
|---|---|
| Timebox | Phases 1–4 deliver a CLI and API slice that produces the 3076 export. Phases 5 and 7 add the UI value. Phase 6 is independent and can be dropped last. |
| The ECC/REC/(11)04 and T/R 25-08 values are unverified transcriptions | `verified: false` is carried into each finding and shown in the UI and exports. |
| Land-mask resolution near the Gulf of Finland | The Tier 1 all-sea bound is reported next to the mixed-path value, so the sensitivity is visible. |
| Extracting the job runner breaks the space jobs | The space test files run unchanged first (`test_riia_jobs.py`, `test_riia_api.py`). |
| itu.int web firewall rejects page scrapes | The watcher never scrapes the terrestrial page. It builds the zip URL from issue numbers. |

## Decisions (user, 2026-11-07)

1. 3075 and 3077 are downloaded into `data/brific/<no>/`. 3074 and 3078 are optional.
2. ECC/REC/(11)04 is in scope. RUS criteria are indicative, and the bilateral agreement governs.
3. Draft letters are built like the space ones.
4. A terrestrial watcher is in scope, downloading only.
5. Each issue is assessed on its own.
6. `/terrestrial` is a new page, and `/risk` stays space-only.

## Unresolved questions

1. Which publication part should Finland act on, part 1 (received) or part 2 (recorded)? Until the Traficom
   specialists answer, part 1 sorts first. The other questions for them are in the brainstorm conversation.
2. Should ECC/REC/(08)02 (900/1800 MHz) be added? The default is no, and those notices are `not_assessed` with
   the reason `no_criterion_in_registry`.
