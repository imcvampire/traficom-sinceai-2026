import json

import numpy as np
import pytest

from ific.config import settings
from ific.riia import hazards
from ific.riia.receivers import classify_services, load_classes


def test_sample_plan() -> None:
    assert hazards.sample_plan(20.0, 495) == (495, 21)
    assert hazards.sample_plan(2.0, 495) == (495, 50)
    sites, t = hazards.sample_plan(0.0125, 495)
    assert t == 8000 and sites == 125 and sites * t <= hazards.SAMPLES_CAP
    assert hazards.sample_plan(20.0, 1) == (1, 10_000)


def test_seed_is_stable_and_hazard_specific() -> None:
    a = hazards.rng_for(3074, 1, "cochannel:fixed").uniform(size=3)
    assert np.array_equal(a, hazards.rng_for(3074, 1, "cochannel:fixed").uniform(size=3))
    assert not np.array_equal(a, hazards.rng_for(3074, 1, "adjacent:fixed").uniform(size=3))


def test_spreading_loss() -> None:
    assert float(hazards.spreading_db(1000.0)) == pytest.approx(130.99, abs=0.01)


def test_pfd_i_and_n_hand_values() -> None:
    cf = load_classes()
    fixed = cf.classes["fixed"]
    grp = hazards.Grp(1, 10.7e9, 10.736e9, -55.563, 36e6, 20.0, 30.0, True)
    k = hazards.pair_terms(
        fixed, "cochannel", (10.7e9, 11.7e9), grp, 0.0, 28e6, 6.0, 45.0, cf.kt0_dbw_hz, hazards.Overrides()
    )
    # pfd = −55.563 + 30 − 162.58 = −188.14 dB(W/m²/Hz); 10log(λ²/4π) = −42.07 dB; N/B = −203.98 + 6 dB(W/Hz)
    pfd = -55.563 + 30 - float(hazards.spreading_db(38_000.0))
    lam = 299_792_458.0 / ((10.7e9 + 10.736e9) / 2)
    i = pfd + 10 * np.log10(28e6) + 10 * np.log10(lam**2 / (4 * np.pi))
    n = -203.98 + 10 * np.log10(28e6) + 6.0
    assert k + 30 - float(hazards.spreading_db(38_000.0)) == pytest.approx(i - n, abs=1e-9)
    assert i - n == pytest.approx(-32.23, abs=0.01)


def test_receiver_classes_are_cited() -> None:
    raw = json.loads((settings.data_dir / "ref" / "receiver_classes.json").read_text())
    for c in raw["classes"]:
        for key in ("pattern", "gain_dbi", "nf_db", "bw_hz", "acs_db", "min_elev_deg"):
            assert c[key]["cite"], (c["id"], key)
        assert c["criteria"] and all(k["cite"] for k in c["criteria"])
        assert all(d["source"] == "assumption" and d["cite"] for d in c["distributions"])


@pytest.mark.parametrize(
    ("text", "classes"),
    [
        ("FIXED\nMOBILE", ["fixed", "mobile"]),
        ("FIXED SATELLITE (SPACE-TO-EARTH)", ["fss_es"]),
        ("FIXED SATELLITE (EARTH-TO-SPACE)", []),
        ("MOBILE-SATELLITE (EARTH-TO-SPACE)\nMOBILE", ["mobile"]),
        ("EARTH EXPLORATION-SATELLITE (PASSIVE)\nRADIO ASTRONOMY", ["radio_astronomy"]),
        ("Radiolocation", []),
        ("AERONAUTICAL RADIONAVIGATION", ["radionavigation"]),
        ("RADIONAVIGATION-SATELLITE (SPACE-TO-EARTH, SPACE-TO-SPACE)", ["rnss"]),
    ],
)
def test_classify_services(text: str, classes: list[str]) -> None:
    assert [c for c, _ in classify_services(text, load_classes().rules)] == classes


def test_site_sums_keep_higher_orbit_satellites() -> None:
    from ific.riia.geometry import R_EARTH_KM, ecef, enu_basis
    from ific.riia.orbits import Constellation

    const = Constellation.from_planes([550, 8000], [53, 0], [0, 0], [40, 6])
    geom = hazards.Geometry("ngso", constellation=const)
    lat, lon = np.array([60.0, 70.0, 65.0]), np.array([20.0, 30.0, 25.0])
    e, n, up = enu_basis(lat, lon)
    site = ecef(lat, lon, R_EARTH_KM)
    L, _ = hazards._site_sums(
        geom, site, up, up, lambda th: np.zeros_like(th), 0.0, 200, hazards.rng_for(1, 1, "t"), False
    )
    t = hazards.rng_for(1, 1, "t").uniform(0.0, hazards.NGSO_WINDOW_S, 200)
    pos = const.positions(t)
    d = pos[None] - site[:, None, None, :]
    rng = np.linalg.norm(d, axis=-1)
    vis = np.einsum("stk,sk->st", d.reshape(3, -1, 3), up).reshape(rng.shape) >= 0
    with np.errstate(divide="ignore"):
        brute = 10 * np.log10(np.where(vis, 10 ** (-hazards.spreading_db(rng) / 10), 0).sum(axis=-1))
    assert np.allclose(L, brute, equal_nan=True)
