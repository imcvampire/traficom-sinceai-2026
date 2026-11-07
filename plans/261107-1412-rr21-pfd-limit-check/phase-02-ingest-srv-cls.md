---
phase: 02
title: Ingest space-station class (srv_cls)
status: completed
depends_on: []
effort: 1h
---

# Phase 02: Ingest space-station class (`srv_cls`)

## Context

Table 21-4 rows are per service. The IFIC `.mdb` has `srv_cls(grp_id, seq_no, stn_cls, nat_srv)` (60 529 rows in
3074, e.g. `EC`/`CP` for an FSS space station). `ingest.py` does not load it today.

## Requirements

- Add `"srv_cls": None` to `ingest.TABLES`; `grp_id` is already in `_BIGINT`, `seq_no` in `_INTEGER`.
- Add the station-class codes used by Table 21-4 to `pfd_limits.py` as a small mapping with a comment citing the
  BR IFIC/SRS code list (`EC` FSS, `EB` BSS, `EG`/`EU` MSS, `EW` MetSat, `EH` space research, `EE` EESS, `ER`
  radionavigation-satellite…); verify each code against the BR "Preface" code tables before use and record the
  citation. Unknown codes → `not_assessed`, reason names the code.
- Note that `mask_info.freq_min/max` are GHz (3074: `5.925`), unlike `c_pfd` (MHz). Record it in the
  `ingest.py` note next to the existing provn note.
- Re-ingest is a no-op on unchanged files (sha256), so existing DBs need `ific ingest --force` or equivalent; check
  what the CLI offers and document the step in the phase 06 runbook.

## Files

| Action | Path |
|---|---|
| modify | `backend/src/ific/ingest.py` |
| create | `backend/tests/fixtures/ific/srv_cls.csv` (rows for the fixture downlink groups, incl. one unknown code) |
| modify | `backend/tests/test_ingest.py` |

## Validation

- `cd backend && uv run pytest tests/test_ingest.py -q`
- The fixture issue loads `space.srv_cls` with the expected row count.
