import math

import pytest

from ific.propagation import tr2508


@pytest.mark.parametrize(
    ("f_mhz", "expected"),
    [
        (29.7, 0),
        (46.99, 0),
        (47, 6),
        (107.9, 6),
        (108, 12),
        (156.8, 12),
        (379.99, 12),
        (380, 18),
        (400, 20),
        (470, 20),
    ],
)
def test_band_values_and_edges(f_mhz: float, expected: float) -> None:
    result = tr2508.trigger(f_mhz, 25_000)
    assert result is not None
    assert result.base_dbuv_m == expected
    assert result.e_dbuv_m == expected
    assert result.citation.startswith("ECC T/R 25-08")


@pytest.mark.parametrize("f_mhz", [29.69, 470.01, 800, 10])
def test_outside_range_returns_none(f_mhz: float) -> None:
    assert tr2508.trigger(f_mhz, 25_000) is None


def test_wideband_correction() -> None:
    result = tr2508.trigger(160, 200_000)
    assert result is not None
    assert result.bandwidth_correction_db == pytest.approx(10 * math.log10(8))
    assert result.e_dbuv_m == pytest.approx(12 + 9.0309, abs=1e-4)


@pytest.mark.parametrize("bandwidth_hz", [25_000, 12_500, None])
def test_no_correction_at_or_below_reference(bandwidth_hz: int | None) -> None:
    result = tr2508.trigger(160, bandwidth_hz)
    assert result is not None
    assert result.bandwidth_correction_db == 0


def test_reference_conditions() -> None:
    assert (tr2508.TIME_PCT, tr2508.LOC_PCT, tr2508.RX_HEIGHT_M) == (10, 50, 10)


def test_unverified_note_present_until_human_check() -> None:
    assert tr2508.__doc__ is not None
    assert "UNVERIFIED" in tr2508.__doc__ or "Checked by" in tr2508.__doc__
