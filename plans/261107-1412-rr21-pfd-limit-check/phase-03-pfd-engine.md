---
phase: 03
title: pfd engine (riia/pfd.py)
status: completed
depends_on: [01, 02]
effort: 6h
---

# Phase 03: pfd engine (`riia/pfd.py`)

## Context

Reuse what exists; do not fork the physics:

- Group power and density: `assess._load_notices` already builds `Grp(d_dbw_hz, bn_hz, p_dbw, gain_dbi, bore,
  psi0_deg, cpfd_dens)` per downlink group. Extend `Grp` (or `_Notice`) with the `stn_cls` set and the raw
  `c_pfd` rows (value + bandwidth) rather than re-querying.
- Geometry: `assess._load_geometry` → `Geometry` (GSO lon and tolerance, NGSO `Constellation`).
- Helpers: `hazards.spreading_db`, `hazards._satellite_gain` (S.672 around boresight), `hazards._gso_central_angle_deg`,
  `geometry.look_angles`, `geometry.slant_range_km`, `orbits.Constellation.max_reach_lat_deg`,
  `receivers.finland_grid`.

The method section in `docs/interference-risk-assessment.md` (phase 06, step 1) is written first and this code
quotes it.

## Method

For a downlink group g and a Table 21-4 row r with overlapping band, matching `stn_cls`, matching orbit and
`encoded: true`:

```
pfd_ref(point) = D_g + 10·log10(min(B_ref, B_n)) + G_s(point) − 10·log10(4π·d(point)²)    dB(W/m²) in B_ref
  D_g = peak density dBW/Hz (emiss.pep_max − 10·log10(B_n), or pwr_ds_max)
  if B_n < B_ref: the whole carrier power P_g counts (10·log10(B_n) instead of 10·log10(B_ref))
margin(point) = pfd_ref(point) − limit_r(δ(point))
```

- **GSO.** Points = Finland grid; δ and d from the satellite at the nominal longitude, and at both tolerance
  edges; keep the worst margin. `G_s` from `_satellite_gain` (peak gain + assumption when no boresight).
- **NGSO.** δ sweep 0–90° step 0.5°, d(δ) at the lowest altitude of the constellation (perigee for elliptical),
  peak gain (assumption `pfd_peak_gain`). Limit the sweep to δ reachable from Finnish latitudes
  (`max_reach_lat_deg` per δ); if none, outcome `not_applicable`, reason "never visible from Finland".
  N for `ngso_n` rows from `non_geo`; missing N → `not_assessed`.
- **Notified `c_pfd`.** When a `c_pfd` row overlaps the group and has a bandwidth: `pfd_ref = pfd + 10·log10(B_ref /
  B_cpfd)` (flat-spectrum assumption `cpfd_flat`) and compare with the limit at the lowest δ seen from Finland
  (assumption `cpfd_min_delta`). `source: "notified"`. No bandwidth → calculated path, reason recorded.
- **Mask.** A group overlapping a `mask_info` row with `f_mask = 'P'` (GHz → MHz) gets the flag
  `pfd_mask_notified_not_loaded` in its assumptions; the calculated or notified value is still compared.
- No row for the band/service → `not_applicable`. Row with `encoded: false` → `not_assessed` with its reason.
  Missing power or gain → `not_assessed`, reason "no power/gain in the notice".

Per check output (`dict`, rounded via `store.round_floats`):

```
{check_id, grp_id, row_id, band_hz: [lo, hi], service, orbit, ref_bw_hz, source: calculated|notified,
 pfd_dbw_m2: float|None, limit_dbw_m2: float|None, delta_deg: float|None, margin_db: float|None,
 outcome: exceeds|meets|not_applicable|not_assessed, near_limit: bool, reason: str|None,
 inputs: [...], citations: [...], assumptions: [...]}
```

Notice-level: `pfd_outcome` = worst by `hazards.OUTCOME_RANK`, `max_pfd_margin_db` over checks with a margin,
`pfd_near_limit` = any check with `−pfd_near_db ≤ margin < 0`.

Deterministic: no RNG. Check order is `(grp_id, row_id)`.

## Files

| Action | Path |
|---|---|
| create | `backend/src/ific/riia/pfd.py` |
| modify | `backend/src/ific/riia/assess.py` (carry `stn_cls`, raw `c_pfd`, mask rows into `_Notice`/`Grp`) |
| modify | `backend/tests/fixtures/ific/*.csv` (one GSO notice in 10.7–11.7 GHz FSS with boresight; one NGSO in a row with δ-dependence; one `c_pfd` with and one without bandwidth; one `f_mask = 'P'`) |
| create | `backend/tests/test_riia_pfd.py` |

## Validation

- `cd backend && uv run pytest tests/test_riia_pfd.py -q`, then `tests/test_riia_assess.py`.
- Hand-calculated cases (write the arithmetic in the test docstring): GSO at 0° E, 50 dBW, 4 kHz-density case,
  Helsinki point, with and without boresight; NGSO 550 km at δ = 90° and δ = 10°. ±0.05 dB.
- B_n < B_ref case uses carrier power.
- Tolerance edges: worst margin comes from the edge nearer Finland.
- Outcome mapping for each `not_*` reason.
- Two calls give equal output (determinism).
- `uv run --project backend ruff check backend && uv run --project backend ruff format --check backend`.
