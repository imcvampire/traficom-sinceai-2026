---
phase: 3
title: Stations API with contours
status: pending
depends_on: [1, 2]
---

# Phase 03: Stations API with contours

## Context

See [plan.md](plan.md). Read:
- `backend/src/ific/special_interest.py`: `TABLE`, `OVERLAP_VIEW`, `COLUMNS`.
- `backend/src/ific/api.py`: the `Db` dependency.
- `backend/tests/conftest.py`.

## Contour logic (`backend/src/ific/stations.py`)

```python
def contour(
    row, time_pct: float, user_threshold_dbuv: float,
) -> tuple[Contour | None, str | None]  # (contour, reason when None)
```

- **Reasons for no contour:**
  - `missing_tx_frequency`;
  - `outside_p1546_range` (f outside 30–4000 MHz);
  - `no_power` (`radiated_power_dbw` is null);
  - `unsupported_power_type` (type not `E` and not empty). An empty type with power present is treated as ERP and
    flagged `power_type_assumed_erp`.
- **Threshold:** `tr2508.trigger(f, bandwidth_hz)` when not `None`, giving `threshold_source = "tr2508"` and its
  citation. Otherwise the user threshold, giving `threshold_source = "user"`.
- **Inputs:**
  - `h1 = effective_agl_m`, with the assumption `h1_flat_terrain`;
  - `h2 = 10`;
  - path `[("land", d)]`, with the assumption `path_assumed_land`;
  - `rx_env = "rural"`.
  - Directional stations add `omni_worst_case`.
- **Solve:** bisection on d over [1, 1000] km, to a tolerance of 0.01 km.
  - If `E(1 km) < threshold`, the result is `bound = "below_1km"` and `radius_km = 1`.
  - If `E(1000 km) ≥ threshold`, the result is `bound = "at_least_1000km"`.
- **Contour fields:** `radius_km`, `bound`, `threshold_dbuv`, `threshold_source`, `threshold_citation`,
  `time_pct`, `h1_m`, `h2_m`, `erp_dbw`, `f_mhz` and `assumptions`.
- **Caching:** cache the computed contours per `(time_pct, user_threshold_dbuv)` in memory with
  `functools.lru_cache(maxsize=16)`, keyed together with the `ref.source` sha of the station data so a reload
  invalidates them.

## Routes

- `GET /api/stations`
  - Query params: `time_pct` ∈ {1, 10, 50}, default 10; `threshold_dbuv` from -20 to 120, default 30.
  - Returns a GeoJSON `FeatureCollection` of points. Properties: `source_row`, `station_no`, `licence_class`,
    `tx_hz`, `rx_hz`, `bandwidth_hz`, `effective_agl_m`, `effective_asl_m`, `ground_height_m`, `azimuth_deg`,
    `directivity`, `ant_gain_db`, `polarisation`, `emission_class`, `radiated_power_dbw`, `band_bin`
    (0–5 by edges 30 MHz / 300 MHz / 1 GHz / 3 GHz / 10 GHz, or null), `m4_services`, `quality_flags`,
    `contour` and `no_contour_reason`.
  - A top-level `model` object lists the P.1546 version, the T/R 25-08 citation and the fixed parameters.
- `GET /api/stations/{source_row}`
  - Takes the same query params.
  - Returns the same properties, plus the raw text columns, the full M4 overlap rows and the P.1546 `steps`
    intermediates at the contour distance.
  - Returns 404 for an unknown row.
- Use Pydantic response models.
- Mount with `app.include_router(stations.router)`. Re-read `api.py` right before this one-line edit.

## Files

| File | Action |
|---|---|
| `backend/src/ific/stations.py` | **New.** |
| `backend/src/ific/api.py` | One import and one `include_router` line. |
| `backend/tests/test_stations_api.py` | **New.** |

## Validation

`uv run pytest -q tests/test_stations_api.py` covers:
- the count of 873;
- 444 non-null contours at the defaults;
- the reason counts: `no_power` 328, `outside_p1546_range` 98, `missing_tx_frequency` 3;
- a property test that E at `radius_km` equals the threshold within 0.05 dB for exact contours;
- a T/R 25-08-band station getting `threshold_source = "tr2508"`;
- a contour radius that does not increase when the threshold rises;
- detail for `source_row` 13, and 404 for row 1;
- a timing assertion of the first uncached call, logged, with a target under 1 s.
