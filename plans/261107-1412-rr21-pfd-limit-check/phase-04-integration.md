---
phase: 04
title: Assessment, store, API, review, chat
status: completed
depends_on: [03]
effort: 4h
---

# Phase 04: Assessment, store, API, review, chat

## Requirements

- **assess.py**: in `assess_issue`, run `pfd.checks(notice, geometry, limits, grid)` once per notice (independent of
  the receiver source, so compute it once per run and attach to each source's payload). Add `pfd_checks`,
  `pfd_outcome`, `max_pfd_margin_db`, `pfd_near_limit`, `pfd_check_version = "art21-1"` and
  `pfd_limits_sha256`. `queue_sort_key` / `technical_sort_key`: add `pfd_outcome` rank as a tie-breaker after the
  existing outcome key only (documented in the method doc's sorting section). `model_version` and `rng_for`
  untouched.
- **store.py**: payload is JSON, so no schema change for the detail. If summary columns are materialised for list
  views, add `pfd_outcome` and `max_pfd_margin_db`. Old rows without the fields read back as `None`.
- **schemas.py**: `PfdCheckOut`; `NoticeSummaryOut` gains `pfd_outcome: Outcome | None`,
  `max_pfd_margin_db: float | None`, `pfd_near_limit: bool | None`; `NoticeDetailOut` gains
  `pfd_checks: list[PfdCheckOut] | None`, `pfd_check_version: str | None`.
- **method.py**: add the Table 21-4 input (`source: "rr"`, cite with review status) and the new assumptions
  (`pfd_peak_gain`, `cpfd_flat`, `cpfd_min_delta`, `pfd_near_db`, `pfd_mask_notified_not_loaded`).
- **sensitivity.py**: perturb `pfd_near_db` (3 → 6 dB) and peak-vs-S.672 gain; report notices whose
  `pfd_outcome` or near-limit reading changes.
- **review.py**: new group placed first, "pfd exceeds a Table 21-4 limit", ordered by `max_pfd_margin_db`; each
  notice line lists group, row, pfd, limit, δ, margin, source. CSV gains `pfd_outcome`, `max_pfd_margin_db`,
  `pfd_rows` columns.
- **chat.py**: add per-notice `pfd_checks` (without inputs) to the context. Keep the rules: no `score`, no rank, no
  curve arrays. Add a system-prompt line: "pfd margins are against RR Table 21-4 (review pending); quote them as
  stored."
- **consistency.py**: one check that `pfd_outcome == "exceeds"` implies some check has `margin_db > 0`.

## Files

| Action | Path |
|---|---|
| modify | `backend/src/ific/riia/assess.py`, `store.py`, `schemas.py`, `method.py`, `sensitivity.py`, `review.py`, `chat.py`, `consistency.py` |
| modify | `backend/tests/test_riia_assess.py`, `test_riia_api.py`, `test_riia_review.py`, `test_riia_chat.py`, `test_riia_store.py` |

## Validation

- `cd backend && uv run pytest tests/test_riia_assess.py tests/test_riia_api.py tests/test_riia_review.py tests/test_riia_chat.py tests/test_riia_store.py -q`
- Byte-identical JSON test over two runs still passes, and now covers `pfd_checks`.
- Existing Monte Carlo fixture numbers unchanged (the test that pins them must pass without edits).
- No-score test passes and is extended to `pfd_checks` and the chat context.
- API returns `pfd_outcome: null` for a payload stored before this change (fixture with the field removed).
- Then `mise run lint` and `mise run test` once, since `schemas.py` is a shared contract.
