import numpy as np
import pytest

from ific.riia.geometry import R_EARTH_KM
from ific.riia.orbits import Constellation


def _lat(pos: np.ndarray) -> np.ndarray:
    return np.degrees(np.arcsin(pos[..., 2] / np.linalg.norm(pos, axis=-1)))


def test_polar_orbit_reaches_89_degrees() -> None:
    c = Constellation.from_planes([600], [89], [0], [1])
    t = np.linspace(0, 6000, 4001)
    lat = _lat(c.positions(t))
    assert lat.max() == pytest.approx(89, abs=0.05)
    assert lat.min() == pytest.approx(-89, abs=0.05)


def test_equatorial_orbit_stays_on_equator() -> None:
    c = Constellation.from_planes([600], [0], [0], [4])
    assert np.abs(_lat(c.positions(np.linspace(0, 86400, 100)))).max() < 1e-9


def test_radius_and_reproducibility() -> None:
    c = Constellation.from_planes([550, 550], [53, 53], [0, 90], [3, 3])
    p1, p2 = c.positions(np.array([0.0, 123.0])), c.positions(np.array([0.0, 123.0]))
    assert np.array_equal(p1, p2)
    assert np.allclose(np.linalg.norm(p1, axis=-1), R_EARTH_KM + 550)
    assert c.size == 6


def test_visibility_bounds() -> None:
    c = Constellation.from_planes([600], [90], [0], [36])
    assert c.max_visible(0.0) == 5
    assert c.min_range_km(np.array([60.0, 65.0]), R_EARTH_KM) == pytest.approx(600)
    eq = Constellation.from_planes([600], [0], [0], [10])
    assert eq.max_reach_lat_deg(0.0) == pytest.approx(24.0, abs=0.1)
