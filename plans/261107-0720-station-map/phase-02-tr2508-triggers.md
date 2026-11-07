---
phase: 2
title: T/R 25-08 trigger table
status: pending
depends_on: []
---

# Phase 02: T/R 25-08 trigger table

## Context

T/R 25-08 is the ECC recommendation for coordinating land mobile systems, 29.7–470 MHz in the current edition.
Its triggers are field strengths at the border line: 50% locations, 10% time, 10 m receiving height, per 25 kHz.
For wider channels, `6·log10(bw / 25 kHz)` dB is added. The 2008 table circulating online is superseded and must
not be used.

## Steps

1. Download the current edition and its amendments from the [ECC document database](https://docdb.cept.org/document/category/ECC_Recommendations/review).
   The latest amendment is from 6 June 2025. Record the document ID, edition date and the annex/table numbers.
2. Transcribe the co-channel trigger values by frequency range into `backend/src/ific/propagation/tr2508.py`, as
   a tuple of `Trigger(lower_mhz, upper_mhz, e_dbuv_m, reference_bw_khz, note)`. Put a citation comment on each
   range.
3. API:

   ```python
   @dataclass(frozen=True)
   class TriggerResult:
       e_dbuv_m: float
       base_dbuv_m: float
       bandwidth_correction_db: float
       citation: str

   def trigger(f_mhz: float, bandwidth_hz: int | None) -> TriggerResult | None
   ```

   - Returns `None` outside the recommendation's frequency range.
   - The bandwidth correction applies only when the bandwidth exceeds the reference bandwidth.
4. Add the reference conditions as constants (`TIME_PCT = 10`, `LOC_PCT = 50`, `RX_HEIGHT_M = 10`), so callers
   use the recommendation's conditions, not their own.
5. A person checks the transcribed values against the PDF. Record who checked and when in the module docstring,
   or leave a visible `UNVERIFIED` note in the docstring until then.

## Files

| File | Action |
|---|---|
| `backend/src/ific/propagation/tr2508.py` | **New.** |
| `backend/tests/test_tr2508.py` | **New.** Band edges, out-of-range `None`, the wideband correction (e.g. 200 kHz gives `+6·log10(8)`, about 5.42 dB), and no correction at 25 kHz or below. |

## Validation

- `uv run pytest -q tests/test_tr2508.py`.
- The values are human-checked, or the `UNVERIFIED` note is present.
