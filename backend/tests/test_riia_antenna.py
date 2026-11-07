import numpy as np
import pytest

from ific.riia import antenna as a

ANGLES = np.linspace(0.01, 180, 2000)


@pytest.mark.parametrize("fn", [a.f1245, a.f699, a.s465])
def test_boresight_and_monotonic(fn) -> None:
    g = fn(ANGLES, 38.0)
    assert float(fn(np.array([0.0]), 38.0)[0]) == pytest.approx(38.0)
    # The Recommendations' rounded constants leave a ≤ 0.05 dB step up to the floor at 48°.
    assert np.all(np.diff(g) <= 0.05)
    assert g.max() <= 38.0


def test_f1245_hand_values() -> None:
    assert a.f1245(np.array([1.0, 10.0, 90.0]), 38.0) == pytest.approx([35.33, 6.43, -10.57], abs=0.02)


def test_f699_hand_values() -> None:
    assert a.f699(np.array([10.0, 90.0]), 38.0) == pytest.approx([11.85, -5.15], abs=0.02)


def test_s465_hand_values() -> None:
    assert a.s465(np.array([0.1, 1.0, 10.0, 60.0]), 45.0) == pytest.approx([45.0, 32.0, 7.0, -10.0])


def test_ra1631_hand_values() -> None:
    g = a.ra1631(np.array([0.0, 0.4, 1.0, 20.0, 50.0, 100.0, 150.0]), 60.0)
    assert g == pytest.approx([60.0, 36.54, 29.0, -5.03, -12.0, -7.0, -12.0], abs=0.02)


def test_bt419_hand_values() -> None:
    g = a.bt419(np.array([0.0, 20.0, 40.0, 60.0, 90.0]), 12.0, 600e6)
    assert g == pytest.approx([12.0, 12.0, 4.0, -4.0, -4.0])
    assert float(a.bt419(np.array([90.0]), 7.0, 200e6)[0]) == pytest.approx(-5.0)


def test_s672_rolloff() -> None:
    g = a.s672(np.array([0.0, 1.0, 2.0, 4.0, 10.0, 60.0]), 30.0, 1.0)
    assert g == pytest.approx([30.0, 27.0, 18.0, 10.0, 5.0, 0.0])
    assert np.all(np.diff(a.s672(ANGLES, 30.0, 1.0)) <= 1e-9)


def test_omni() -> None:
    assert a.receiver_gain("omni", ANGLES, 3.0, 1e9) == pytest.approx(np.full(ANGLES.size, 3.0))
