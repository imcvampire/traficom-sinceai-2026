---
title: Space pfd over Finland vs RR Article 21, Table 21-4
description: For every space-to-Earth group of a Space IFIC notice, compute the worst-case pfd on Finnish territory and compare it with the applicable RR Table 21-4 limit, reported as a margin with its own outcome, next to the receiver I/N hazards.
status: completed
mode: auto
priority: P1
effort: 3d
branch: main
tags: [feature, backend, frontend, docs]
blockedBy: []
blocks: []
created: 2026-11-07
source: /ak-plan "do a planning for it. Focus on space, pfd, and table21-4"
---

# Space pfd over Finland vs RR Table 21-4

## Outcome

The challenge judge said pfd is the main issue. Today the pfd is only an intermediate value: riia-1 computes it
(`hazards.pair_terms`, `assess._load_notices`), then turns it into I/N at a modelled receiver. No pfd number is
ever shown, and `data/ref/rr21_pfd_limits.json` (3 rows, "context only") is not read by any code.

After this plan, every Space IFIC notice that has space-to-Earth groups gets a **pfd check**. For each group and
each Table 21-4 row that applies to it (band, service, orbit), the check reports:

- the worst-case pfd on Finnish territory, in dB(W/m²) in the reference bandwidth of the row (4 kHz, 1 MHz…);
- the limit at the angle of arrival δ where the margin is worst, and that δ;
- `margin_db = pfd − limit`;
- an outcome: `exceeds` / `meets` / `not_applicable` (no Table 21-4 row) / `not_assessed` (data missing or row
  not encoded), plus a `near_limit` reading;
- source (calculated or notified `c_pfd`), inputs, citation (RR edition, table row, footnote) and assumption ids.

The check is visible in the API, the `/risk` table (column and filter), the notice sheet, the review report and
CSV, and the chat context. It is deterministic: no Monte Carlo and no receiver population.

## Acceptance criteria

1. `data/ref/rr21_pfd_limits.json` holds every Table 21-4 row that applies in Region 1 (Finland), whatever the
   band (3074 downlinks span 137 MHz to 240 GHz), structured so code can evaluate it, with
   row-level citations, and `review.status` stays `pending` until a person signs it off. Rows the encoding cannot
   express are present with `encoded: false` and a reason, never dropped.
2. `riia/pfd.py` computes the checks; unit tests reproduce at least three hand-calculated cases (GSO with
   boresight, GSO without boresight, NGSO at minimum altitude) to ±0.05 dB, and limit interpolation at the δ
   breakpoints of every encoded row.
3. Notice payloads carry `pfd_checks` and the summary fields `pfd_outcome` and `max_pfd_margin_db`. Two runs give
   byte-identical JSON. No `score` key anywhere (existing test still passes).
4. The Monte Carlo numbers of riia-1 do not change: the RNG seed and `model_version` stay as they are.
5. `/risk` shows a "pfd vs Art. 21" column and a `pfd` URL filter; the notice sheet has a "pfd limits (RR Art. 21)"
   section. `docs/frontend.md` lists the new param.
6. `ific review 3074` gains a group "pfd exceeds a Table 21-4 limit" and CSV columns for it.
7. `docs/interference-risk-assessment.md` specifies the method before the code lands (source of truth).
8. A dry run on 3074 produces `plans/reports/pfd-261107-3074-art21.md`: counts per outcome, the exceeding
   notices, and the overlap with the 23 stations-source I/N `exceeds`.

## Non-goals

- EPFD (Article 22) and Appendix 5 ΔT/T or coordination pfd thresholds (9.11A, Annex 1 of AP5). Table 21-4 only.
  The data model leaves room for a second limit table, but none is built.
- pfd masks (`mask_info` with `f_mask = 'P'`): the mask values are not in the IFIC `.mdb` (only `mask_lnk*` ids).
  Masked groups are flagged as a data gap, not evaluated against the mask.
- Terrestrial IFIC 3076 and the `/stations` map.
- Draft letters: their kind still comes from the regulatory context only. Citing a pfd exceedance in the letter
  body is a later change.
- Changing the likelihood–consequence chart's model. Only its axis label is corrected.

## Decisions (defaults taken; change before cooking if wrong)

| Decision | Default | Why | Alternative |
|---|---|---|---|
| Where the result lives | A separate `pfd_checks` list on the notice, not a new hazard mode | A Table 21-4 limit is a regulatory limit on the transmitter, not a receiver protection criterion; it has no likelihood, curves or receiver count. Keeping it apart avoids mixing the two in `worst_outcome`. | New hazard mode `pfd_limit` in `hazards`: reuses UI plumbing but every hazard field (`n_receivers`, `risk_curves`, `share_violating`) would be meaningless |
| Effect on `worst_outcome` and sort | None. `pfd_outcome` is its own summary field, a table column and a filter; the queue sort adds it as a tie-breaker after outcome | No composite score; the two readings stay side by side | Fold pfd `exceeds` into `worst_outcome` |
| Versioning | Keep `model_version = "riia-1"` (it seeds the RNG); add `pfd_check_version = "art21-1"` and the limits file sha256 to each notice | Bumping the model version would change every Monte Carlo number | Bump to `riia-2` |
| Where the pfd is evaluated | Finnish land grid (`receivers.finland_grid`, same cells as generic-m4) for GSO; δ sweep 0–90° at 0.5° for NGSO, limited to δ reachable from Finland | Article 21 limits apply on the Earth's surface in the territory; worst case over the grid is easy to audit | Single centroid point |
| Satellite gain | S.672 around the notified boresight when present, otherwise peak gain (assumption `pfd_peak_gain`) | Same rule as riia-1 | Peak gain always |
| Notified `c_pfd` | Takes precedence over the calculated value for overlapping groups; no δ in the data, so it is compared with the limit at the lowest δ seen from Finland (assumption `cpfd_min_delta`) | Conservative and explicit | Compare at every δ |
| Reference bandwidth | pfd in B_ref = peak density + 10·log10(min(B_ref, B_n)); for B_n < B_ref the whole carrier power counts | Standard Article 21 convention for carriers narrower than the reference bandwidth | Average density |
| Near-limit margin | 3 dB, assumption `pfd_near_db`, shown in the sensitivity output | pfd is deterministic, so it needs less slack than the 6 dB I/N margin | Reuse 6 dB |
| Service matching | Group's `srv_cls.stn_cls` (space-station class) mapped to the Table 21-4 service column; unknown class → `not_assessed` with reason | Rows are per service; band alone over-applies them | Band only |
| Limits storage | JSON file in `data/ref/`, read at assessment like `receiver_classes.json`, sha256 recorded | Same pattern as the other hand-curated inputs | `ref` schema table |

## Phases

| # | Phase | Depends on | Effort | Status |
|---|---|---|---|---|
| 01 | [Table 21-4 reference data](phase-01-table-21-4-data.md) | — | 6h | completed |
| 02 | [Ingest space-station class (`srv_cls`)](phase-02-ingest-srv-cls.md) | — | 1h | completed |
| 03 | [pfd engine (`riia/pfd.py`)](phase-03-pfd-engine.md) | 01, 02 | 6h | completed |
| 04 | [Assessment, store, API, review, chat](phase-04-integration.md) | 03 | 4h | completed |
| 05 | [`/risk` UI](phase-05-risk-ui.md) | 04 | 3h | completed |
| 06 | [Method doc, dry run on 3074, review](phase-06-docs-dry-run.md) | 01 (doc first), 05 | 4h | completed |

The method section in phase 06 is written **before** phase 03 is coded (the doc is the source of truth); the dry
run and report come last.

## Data flow

```text
space.grp (E) ─┬─ emiss (pep_max / pwr_ds_max) ─┐
               ├─ s_beam (gain, boresight)      ├─► per group: density, B_n, gain pattern
               ├─ srv_cls (stn_cls)  [new] ─────┤
               └─ c_pfd (notified pfd) ─────────┘
geo / non_geo / orbit ─► Geometry (GSO lon + tolerance, NGSO altitudes, inclination)
data/ref/rr21_pfd_limits.json ─► Limit rows (band, service, orbit, B_ref, limit(δ), N-formula)

riia/pfd.py: for group × applicable row → worst over Finland of pfd(δ) − limit(δ)
          ─► pfd_checks[] + pfd_outcome + max_pfd_margin_db on the notice payload
          ─► store (same transaction) ─► API ─► /risk column, filter, notice sheet; review; chat
```

## Risks

| Risk | Mitigation |
|---|---|
| A transcription error in Table 21-4 produces a false `exceeds` that the judge spots | Row-level citation (edition, page, row, footnote); a test asserts every encoded row at δ = 0, 5, 25, 90 against a second hand-entered list; `review.status: pending` shown in the UI and the report until signed off |
| Rows with conditions the encoding cannot express (constellation-size formulas, per-Region footnotes, "for each space station" vs aggregate) | `encoded: false` + reason → outcome `not_assessed`, never `meets` |
| Many notice bands have no Table 21-4 row (most MSS L/S band, adjacent cases) | Outcome `not_applicable` with reason "no Table 21-4 limit in this band for this service"; the UI shows it greyed, not green |
| `c_pfd` units: `bdwdth` in kHz, and empty in 14 of 119 rows of 3074 (e.g. `-131` at 1164–1215 MHz) | An empty bandwidth falls back to the calculated pfd, and the check carries the reason "notified pfd without reference bandwidth"; a fixture row covers it |
| `mask_info.freq_*` is in GHz while `c_pfd.freq_*` is in MHz | Phase 02/03 test asserts the units on the 3074 rows; the mask flag only uses overlap after converting |
| Old stored results lack `pfd_checks` | API returns `pfd_outcome: null`; UI shows "re-assess to compute"; no migration needed |

## Unresolved questions

- Did the judge mean Table 21-4 specifically, or also the Appendix 5 coordination pfd thresholds? This plan does
  Table 21-4 only, as asked.
- Which RR edition does Traficom use for review (2020 or 2024)? Default: 2024.
- Who signs off the transcription of Table 21-4 (`review.status`)?

## Delivery notes (2026-11-07)

- Result: [pfd-261107-3074-art21.md](../reports/pfd-261107-3074-art21.md); code review:
  [code-reviewer-261107-1417-rr21-pfd-limit-check.md](../reports/code-reviewer-261107-1417-rr21-pfd-limit-check.md).
- Sources used: RR Edition of 2024, Vol. 1, Table 21-4 (pp. 287–294) and BR IFIC Preface, Table 3 (October 2026),
  both downloaded from itu.int. Rows tied to country footnotes that do not list Finland are under `excluded`.
- Deviations from the plan: checks are collapsed to one per (notice, row) because 3074 has 21,269 downlink groups;
  the `pfd_outcome` tie-breaker sits just before `ntc_id`, not right after the outcome key; `ingest` re-loads an
  issue when its table set changes, so no `--force` flag was needed; a `pwr_ds_max` inconsistent with `pep_max` is
  treated as a data error; a notified `c_pfd` is rescaled flat over the carrier, not over its own bandwidth.
- The dry run used a copy of the DB because the API dev server held the lock; `var/db` still holds pre-pfd results,
  which the UI shows as "Re-assess".
