import json

import numpy as np
import pytest

from ific.config import settings
from ific.riia import geometry as g
from ific.riia.orbits import gso_ecef

HELSINKI = (60.1699, 24.9384)


def _look(lat: float, lon: float, sat: np.ndarray) -> tuple[float, float, float]:
    e, n, u = g.enu_basis(np.array([lat]), np.array([lon]))
    site = g.ecef(np.array([lat]), np.array([lon]), g.R_EARTH_KM)
    el, az, rng = g.look_angles(site, e, n, u, sat[None, :])
    return float(el[0]), float(az[0]), float(rng[0])


def test_gso_25e_from_helsinki() -> None:
    el, az, _ = _look(*HELSINKI, gso_ecef(25.0))
    assert el == pytest.approx(21.8, abs=0.1)
    assert az == pytest.approx(180.0, abs=0.2)


def test_slant_range_at_zero_elevation() -> None:
    gamma = float(g.horizon_central_angle_deg(g.R_GSO_KM))
    assert float(g.slant_range_km(gamma, g.R_EARTH_KM, g.R_GSO_KM)) == pytest.approx(41_679, abs=2)


def test_off_axis_angles() -> None:
    assert float(g.off_axis_deg(0, 0, 90, 0)) == pytest.approx(90)
    assert float(g.off_axis_deg(180, 20, 180, 30)) == pytest.approx(10)
    assert float(g.off_axis_deg(10, 90, 250, 0)) == pytest.approx(90)
    assert float(g.angle_between_deg(np.array([1, 0, 0]), np.array([1, 1, 0]))) == pytest.approx(45)


def test_pointing_vector_matches_look_angles() -> None:
    el, az, _ = _look(*HELSINKI, gso_ecef(40.0))
    e, n, u = g.enu_basis(np.array([HELSINKI[0]]), np.array([HELSINKI[1]]))
    local = g.pointing_vector(np.array([az]), np.array([el]))
    pv = local[:, :1] * e + local[:, 1:2] * n + local[:, 2:3] * u
    to_sat = gso_ecef(40.0) - g.ecef(np.array([HELSINKI[0]]), np.array([HELSINKI[1]]), g.R_EARTH_KM)
    assert float(g.angle_between_deg(pv, to_sat)[0]) == pytest.approx(0.0, abs=1e-5)


def test_haversine_helsinki_tallinn() -> None:
    assert float(g.haversine_km(*HELSINKI, 59.437, 24.7536)) == pytest.approx(82, abs=2)


def test_point_in_finland() -> None:
    geom = json.loads((settings.data_dir / "ref" / "finland_land.geojson").read_text())["features"][0][
        "geometry"
    ]
    lon = np.array([HELSINKI[1], 18.07, 24.75, 27.0])
    lat = np.array([HELSINKI[0], 59.33, 59.44, 66.5])
    assert g.in_multipolygon(lon, lat, geom["coordinates"]).tolist() == [True, False, False, True]
