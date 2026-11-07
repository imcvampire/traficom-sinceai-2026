---
phase: 1
title: P.1546 engine
status: completed
depends_on: []
---

# Phase 01: P.1546 engine

## Context

See [plan.md](plan.md) for the decisions. The engine is a pure function library with no DB or HTTP code. The
map uses it now, and the terrestrial side quest will use it later.

## Steps

1. **Check the source and licence.**
   - Clone [eeveetza/p1546](https://github.com/eeveetza/p1546) into the scratchpad.
   - Read its licence and the [ITU software copyright statement](https://www.itu.int/en/ITU-R/study-groups/software-copyright-statements/Pages/default.aspx).
   - Record the licence, the commit and the P.1546 version it implements (expected P.1546-6) in the module
     docstring.
   - If porting isn't permitted, stop and report. The fallback is implementing from the Recommendation text,
     still validated against the same cases.
2. **Tables.** Extract the tabulated field-strength curves (100, 600 and 2000 MHz; land, cold sea and warm sea;
   1%, 10% and 50% time; `h1` 10–1200 m; d 1–1000 km) into `backend/src/ific/propagation/data/p1546_tables.npz`.
   Write a `SOURCE.md` next to it giving the origin, version and checksum. Spot-test 3 known table values.
3. **Port the step-by-step method (Annex 5)** into `backend/src/ific/propagation/p1546.py`, in this order:
   - interpolation over distance, `h1` and frequency;
   - time interpolation between 1%, 10% and 50%;
   - `h1` below 10 m and negative;
   - mixed land/sea paths;
   - receiving-height correction for `h2`;
   - location variability;
   - the maximum field-strength cap;
   - the ERP to 1 kW scaling.
   Use numpy, with scalar inputs and outputs. Keep the reference function and step names as comments only where
   they help an expert trace the port.
4. **Public API:**

   ```python
   @dataclass(frozen=True)
   class FieldResult:
       e_dbuv_m: float
       inputs: dict[str, float | str]
       steps: dict[str, float]       # named intermediates for audit
       assumptions: tuple[str, ...]  # e.g. ("tca_not_applied",)

   def field_strength(
       f_mhz: float, t_pct: float, path: Sequence[tuple[Literal["land", "sea_cold", "sea_warm"], float]],
       h1_m: float, h2_m: float = 10.0, erp_dbw: float = 30.0, loc_pct: float = 50.0,
       rx_env: Literal["rural", "suburban", "urban", "dense_urban", "sea"] = "rural",
   ) -> FieldResult
   ```

   - Out-of-range inputs raise `ValueError` with the valid range: f outside 30–4000 MHz, t outside 1–50%,
     d outside 0.001–1000 km.
   - `erp_dbw = 30` is the 1 kW reference.
5. **Validation.** Port the reference validation cases (inputs and expected E) into
   `backend/tests/data/p1546_validation.csv`, citing their origin. `backend/tests/test_p1546.py` runs them as
   parametrized tests with a tolerance of 0.1 dB, plus checks that:
   - E does not increase with distance on land paths at fixed parameters;
   - out-of-range inputs raise;
   - an all-sea path gives a higher E than an all-land path at d > 10 km.

## Files

| File | Action |
|---|---|
| `backend/src/ific/propagation/__init__.py` | **New**, empty. |
| `backend/src/ific/propagation/p1546.py` | **New.** |
| `backend/src/ific/propagation/data/p1546_tables.npz`, `data/SOURCE.md` | **New.** |
| `backend/pyproject.toml` | Make sure package data includes `*.npz`, following `uv_build` behaviour. |
| `backend/tests/test_p1546.py`, `backend/tests/data/p1546_validation.csv` | **New.** |

## Validation

- `uv run pytest -q tests/test_p1546.py` passes. The skipped count, for cases needing terrain-clearance-angle
  correction, is printed and matches the report.
- `uv run ruff check src tests`.
