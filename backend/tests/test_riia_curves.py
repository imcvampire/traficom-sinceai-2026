import numpy as np

from ific.riia import curves as c


def test_ccdf_is_strict() -> None:
    assert c.ccdf(np.array([1, 2, 3, 4]), np.array([0, 2, 4])).tolist() == [1.0, 0.5, 0.0]


def test_exceeded_for_and_boundary() -> None:
    s = np.arange(1, 11, dtype=float)
    x = c.exceeded_for(s, 20.0)
    assert x == 8.0
    assert c.violates(x, 7.9) and not c.violates(x, 8.0)
    assert c.exceeded_for(s, 0.01) == 10.0
    assert c.exceeded_for(np.stack([s, s + 1]), 50.0).tolist() == [5.0, 6.0]


def test_risk_curve_on_hand_population() -> None:
    x = np.array([-10.0, -5.0, 0.0, 5.0])
    curve = c.risk_curve(x)
    grid = c.GRID_DB.tolist()
    assert len(curve) == 81
    assert curve[grid.index(-11.0)] == 1.0
    assert curve[grid.index(-10.0)] == 0.75
    assert curve[grid.index(0.0)] == 0.25
    assert curve[grid.index(5.0)] == 0.0
