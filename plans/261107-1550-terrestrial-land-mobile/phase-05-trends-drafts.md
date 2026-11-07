---
phase: 5
title: "Trends, anomalies and draft letters"
status: done
priority: P2
effort: "4h"
dependencies: [4]
---

# Phase 5: Trends, anomalies and draft letters

## Goal

This phase adds per-issue trends and a few deterministic anomaly rules for neighbouring administrations. It also
adds on-demand draft letters built under the same contract as `riia/draft.py`.

## Files

- Create: `backend/src/ific/terra/trends.py`, `backend/src/ific/terra/draft.py`
- Create: `data/ref/terrestrial_letter_kinds.json`, which holds the provisions and wording basis per kind, cited
- Modify: `backend/src/ific/riia/draft.py` **only** to move generic helpers (`load_administrations`,
  `protected_tokens`, `_multiset_diff`, `PolishCheck`/`check_polish` core, `BANNER`) into
  `backend/src/ific/drafting.py`, which `riia/draft.py` re-imports. `test_riia_draft.py` and
  `test_riia_draft_api.py` pass unchanged.
- Modify: `backend/src/ific/terra/api.py`, `terra/schemas.py`, `cli.py` (`terra-draft`)
- Create: `backend/tests/test_terra_trends.py`, `test_terra_draft.py`

## Steps

1. **Trends** (`trends.py`) are computed from stored results for one issue, plus the sum over the issues the
   caller selects. No join across issues happens at assessment time.
   - **Population.** Neighbours are RUS, EST, NOR, S, LVA and LTU, from a constant cited in the method doc. Only
     notices with `pub_status = received`, meaning first published in this issue, are counted, so nothing is
     counted twice.
   - **Dimensions.** The counts cover:
     - band: the criterion band, else the M4 band row;
     - distance bin to Finland: under 50, 50–150, 150–300 and 300–1000 km;
     - station class, notice type and bandwidth code;
     - `change`.
2. **Anomaly rules.** Each rule has an id, a description, a threshold, the matching terrakeys and a citation of
   its rule. There are four:
   - `A1-new-band-near-border`: an administration has received notices in a band within 150 km where none of
     this issue's RECORDED before-states or other notices from that administration are in that band. This is
     the per-issue proxy; the doc states its limits.
   - `A2-atypical-bandwidth`: a bandwidth more than 4× the median for its band and administration in this issue,
     with at least 5 notices.
   - `A3-erp-outlier`: an e.r.p. above the 95th percentile for its band and administration, with at least 10
     notices.
   - `A4-fin-coord-open`: FIN coordination is still `COORD REQUIRED` on a notice that is in this issue.
3. **Letter kinds** (`terra/draft.py`). `choose_kind(regulatory, assignment)` is a pure function:
   - FIN coordination `COORD REQUIRED`, or `exceeds` without any FIN coordination row, gives
     `coordination_request`;
   - `exceeds` with `COORD COMPLETED` gives `enquiry`, which asks the administration to confirm the coordinated
     parameters;
   - anything else gives no draft (409 with a reason).

   The basis paragraph cites the file's provisions. For RUS it cites the bilateral agreement as governing and
   the ECC criterion as indicative.
4. **Draft payload** (`build_draft(con, ific_no, adm)`). There is one letter per administration and issue,
   covering that administration's `exceeds` and `COORD REQUIRED` assignments, with the annex rows listing
   `adm_ref_id`, frequency, bandwidth, e.r.p., h1, criterion, trigger, E and margin.
   - Station site coordinates and terrakeys go in the reviewer notes, and the letter refers to `adm_ref_id`.
     This follows the space rule.
   - The draft is never stored. `prose_paragraphs` are the only part the polish may touch, and the shared
     `check_polish` guards them.
5. **API.**
   - `GET /api/terrestrial/issues/{n}/trends?issues=3075,3076,3077` returns the trends for one issue, or summed
     over the listed issues.
   - `GET /api/terrestrial/issues/{n}/drafts/{adm}` returns the template letter.
   - `POST .../drafts/{adm}/polish` gives the LLM polish, under the same concurrency gate as the space polish
     (`get_chat`).
6. **CLI.** `ific terra-draft t3076 --adm RUS --out DIR`.

## Tests

- **Trends.**
  - The summed counts over the fixtures match a direct count of part-1 rows.
  - The 9998 recorded copy of the 9997 notice is not counted twice.
  - Each anomaly rule fires on its fixture row and not on the control rows.
- **Draft.**
  - The kind for each fixture case is correct.
  - The RUS letter cites the bilateral agreement.
  - The letter contains no coordinates or terrakeys.
  - A polish that alters a number is rejected.
  - Without an LLM, the template is returned.
  - The output is byte-identical across runs.

## Validation

```sh
cd backend && uv run pytest tests/test_riia_draft.py tests/test_riia_draft_api.py -q   # unchanged
cd backend && uv run pytest tests/test_terra_trends.py tests/test_terra_draft.py -q
```
