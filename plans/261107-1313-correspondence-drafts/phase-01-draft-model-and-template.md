---
phase: 1
title: "Draft model and template"
status: completed
priority: P2
effort: "5h"
dependencies: []
---

# Phase 1: Draft model and template

## Goal

A pure backend module that turns the stored results of one notice into a deterministic draft (letter, technical
annex, reviewer notes), with the letter kind chosen from the regulatory context.

## Files to Create / Modify

- Create: `backend/src/ific/riia/draft.py`
- Create: `data/ref/itu_administrations.json`
- Modify: `backend/src/ific/riia/review.py` (extract `notice_readings()`; `triage()` calls it)
- Create: `backend/tests/test_riia_draft.py`
- Modify: `backend/tests/fixtures/ific/*.csv` only if a kind cannot be reached with the existing fixture notices
  (for example a `provn` row naming FIN for a CR/C notice, and one CR/C without)

## Tasks & Steps

1. **Per-notice readings.** In `review.py`, move the body of the `triage()` loop that builds `exceeds`, `near`,
   `beams` into `notice_readings(detail, stations, lon_nom) -> Readings` (a frozen dataclass with the three lists
   plus the source). `triage()` keeps its output exactly; `test_riia_review.py` must pass unchanged.
2. **Administration table.** `data/ref/itu_administrations.json`:
   `{"cite": "ITU BR IFIC Preface, Table of symbols of administrations (edition …)", "review": {"status":
   "pending", "note": "…"}, "admins": {"USA": "United States of America", …}}`. Transcribe from the Preface. Cover
   at least every distinct `space.notice.adm` in the ingested issues (`SELECT DISTINCT adm FROM space.notice`) and
   the fixture codes. Codes that cannot be verified get `null`, never a guess. Load it with `@cache`, like
   `regulatory.load_windows`.
3. **Kind.** `DraftKind = Literal["comment_9_52", "inclusion_9_41", "comment_9_3", "enquiry"]` and
   `choose_kind(regulatory) -> DraftKind`:
   - stage `CR/C` and `window_open`: `comment_9_52` if `fin_identified`, else `inclusion_9_41`;
   - stage `API/A` and `window_open`: `comment_9_3`;
   - anything else: `enquiry`.
4. **Draft payload.** `build_draft(con, ific_no, ntc_id, as_of) -> Draft | NoConcern`:
   - load `store.get_notice` for `stations` then `generic-m4`; skip a source with no stored result and add a
     reviewer note;
   - compute readings per source with `notice_readings`; if both are empty, return `NoConcern(reason)`;
   - `Draft` fields: `kind`, `ific_no`, `ntc_id`, `sat_name`, `adm`, `adm_name`, `stage`, `provision`,
     `d_wic`, `window_end`, `days_left`, `fin_identified`, `br_provisions`, `annex` (rows), `warnings`,
     `reviewer_notes`, `letter_md` (rendered), `prose_paragraphs` (the parts the polish may rewrite),
     `model_version`, `as_of`.
   - Annex row per cited hazard: `source`, `hazard_id`, `reading` (`exceeds` / `near_limit` / `main_beam`),
     `service_label`, band in MHz, `share_violating`, worst p95 dB, `worst_case_db`, criterion
     (`metric`, `level_db`, `time_pct`, `cite`). Values are taken from the stored hazard without recomputation;
     only display rounding (fixed decimals) is applied in the rendered text.
   - Main-beam rows in the annex say "a Finnish directional station in the band … has the notified GSO position
     within its main beam" with band and service class only. Station id, coordinates, azimuth and gain go to
     `reviewer_notes`.
5. **Template.** One header (From: Administration of Finland; To: Administration of `<name>` (`<adm>`);
   Subject: IFIC `<no>`, `<sat_name>`, notice `<ntc_id>`, `<provision>`; date `as_of`; `[Reference]`), one body per
   kind, one shared annex table and closing (`[Name, title]`, `[e-mail]`). Bodies:
   - `comment_9_52`: Finland, identified by the BR under `<br_provisions>`, informs under RR No. 9.52 that it does
     not agree / requests coordination, citing the annex;
   - `inclusion_9_41`: Finland requests inclusion in the coordination procedure under RR No. 9.41 for the listed
     assignments, with comments under RR No. 9.52;
   - `comment_9_3`: comments under RR No. 9.3 on the advance publication, informing of anticipated interference;
   - `enquiry`: informal technical enquiry; reviewer warning that no RR comment window applies at this stage or
     the window has closed (with `window_end`).
   Prose states every fact as digits ("within 4 months", "by 2026-10-23"), so the polish guard can check it. The
   RR cite text from `rr_comment_windows.json` (which spells "four months") is quoted verbatim in a "Basis" line
   under the annex, which is never sent to the LLM. Body paragraphs are `prose_paragraphs`; header, annex and the
   Basis line are not.
   The letter starts and ends with `DRAFT – for expert review, not sent`.
6. **Reviewer notes.** Days left and window end; receiver sources used and skipped; sensitive assumptions per
   cited hazard (from the stored `assumptions[].sensitive`); `review.status` of `receiver_classes.json` and
   `itu_administrations.json`; known-weakness link for radio astronomy adjacent hazards; station details for
   main-beam readings; any unknown administration code.
7. **Protected tokens.** `protected_tokens(prose: str) -> set[str]`: numbers (incl. signed/decimal, dates),
   `ntc_id`, provisions (`9.52`, `9.41`, `9.3`, `9.11`, …), the `adm` code and `hazard_id`s found in the prose.
   Used by phase 2.

## Tests (`backend/tests/test_riia_draft.py`, fixture issue 9999)

- One test per kind with a chosen `as_of` (window open / closed) and fixture notice.
- Notice with no reading → `NoConcern`.
- Annex values equal the stored hazard values; each row has `hazard_id` and criterion `cite`.
- Unknown `adm` → `adm_name is None` and a warning; known code → name.
- Two renders are byte-identical; no `score` in the payload keys or text.
- No station id from the stations population appears in `letter_md`.
- `protected_tokens` extracts the expected set from a sample paragraph.
- `test_riia_review.py` still passes (refactor guard).

## Verification

- `cd backend && uv run pytest tests/test_riia_draft.py tests/test_riia_review.py -q`
- `uv run --project backend ruff check backend && uv run --project backend ruff format --check backend`
