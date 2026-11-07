---
phase: 01
title: Table 21-4 reference data
status: completed
depends_on: []
effort: 6h
---

# Phase 01: Table 21-4 reference data

## Context

`data/ref/rr21_pfd_limits.json` has 3 rows as free text ("−152 / −152+0.5(δ−5) / −142 dB(W/m²) in 4 kHz…") and is
read by nothing. It must become complete, machine-evaluable and citable. Source: ITU Radio Regulations, Article 21,
Section V, Table 21-4 (Edition of 2024, free PDF from itu.int). The implementer needs that PDF; it is not in the
repo.

## Requirements

Schema (version 2), one object per Table 21-4 row and service/orbit split:

```json
{
  "version": 2,
  "use": "pfd limits on the Earth's surface for space stations; evaluated by riia/pfd.py",
  "review": {"status": "pending", "note": "…"},
  "cite": "RR Article 21, Table 21-4 (Edition of 2024)",
  "rows": [
    {
      "id": "t21-4-10700-11700-fss-gso",
      "f_lo_mhz": 10700, "f_hi_mhz": 11700,
      "stn_cls": ["EC"],                 // space-station classes this row covers (Phase 02 mapping)
      "service": "FSS (space-to-Earth)",
      "orbit": "gso",                    // gso | ngso | any
      "regions": [1, 2, 3],
      "ref_bw_hz": 4000,
      "limit": {"kind": "piecewise", "points": [[0, -150], [5, -150], [25, -140], [90, -140]]},
      "encoded": true,
      "footnotes": ["21.16.x"],
      "cite": "RR Table 21-4, row 10.7–11.7 GHz, p. …"
    }
  ]
}
```

- `limit.kind`:
  - `piecewise`: linear interpolation in δ (degrees) over `points`, covering 0–90. This expresses every
    "A for 0–5°, A + k(δ−5) for 5–25°, B for 25–90°" row exactly.
  - `ngso_n`: the rows whose limit depends on the number of satellites N (e.g. 17.7–19.3 GHz NGSO FSS
    "−115 − X, X = f(N)"). Store the base piecewise curve plus `x_formula` ("5/119·(N−50)" style, as
    `{"n_lo": …, "n_hi": …, "x_lo": …, "x_hi": …}` breakpoints). N comes from `non_geo.nbr_sat_pl × nbr_plane`.
- Rows the schema cannot express (conditional footnotes, "until date" rows, aggregate-only limits) stay in the
  file with `"encoded": false, "reason": "…"`.
- Rows applying only to Region 2 or 3 are left out, with a top-level `excluded` list naming them (so the reader
  can see they were considered).
- Loader `backend/src/ific/riia/pfd_limits.py`: `load_limits(path=None) -> Limits`, `Limit.at(delta_deg, n_sats=None)`.
  Validates: δ points strictly increasing from 0 to 90, `f_lo < f_hi`, `ref_bw_hz > 0`, known `stn_cls`, known
  `orbit`; raises with the row id on failure. Exposes `sha256` and `raw` like `receivers.load_classes`.

## Files

| Action | Path |
|---|---|
| modify | `data/ref/rr21_pfd_limits.json` (full rewrite, schema v2) |
| create | `backend/src/ific/riia/pfd_limits.py` |
| create | `backend/tests/test_riia_pfd_limits.py` |

## Validation

- `cd backend && uv run pytest tests/test_riia_pfd_limits.py -q`
- Test 1: the shipped file loads and validates.
- Test 2: a hand-entered table in the test (independent of the JSON) of `(row id, δ, expected dB)` at δ = 0, 5,
  25, 90 for every encoded row; the loader matches to 0.001 dB. This is the transcription cross-check: the two
  lists are typed separately.
- Test 3: `ngso_n` row at N below, inside and above the formula range.
- Test 4: malformed rows (decreasing δ, missing 90°) raise with the row id.

## Risk / rollback

Transcription is the main risk; the cross-check test and `review.status: pending` contain it. Rollback: restore
the 3-row file (nothing read it before).
