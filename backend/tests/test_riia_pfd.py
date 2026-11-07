import math

import numpy as np
import pytest

from ific.riia.hazards import Geometry
from ific.riia.orbits import Constellation
from ific.riia.pfd import (
    Emission,
    Grid,
    NotifiedPfd,
    Params,
    PfdGroup,
    ngso_slant_range_km,
    notice_checks,
    summarise,
)
from ific.riia.pfd_limits import load_limits

R_E, R_GSO = 6378.137, 42164.2
HELSINKI = (60.17, 24.94)


def _spread(d_km: float) -> float:
    return 10 * math.log10(4 * math.pi * (d_km * 1e3) ** 2)


def _gso_hand(lat: float, lon: float, sat_lon: float) -> tuple[float, float]:
    """Slant range (km) and elevation (deg) to a GSO satellite, from the spherical-Earth triangle."""
    cos_g = math.cos(math.radians(lat)) * math.cos(math.radians(lon - sat_lon))
    d = math.sqrt(R_GSO**2 + R_E**2 - 2 * R_GSO * R_E * cos_g)
    el = math.degrees(math.asin((R_GSO * cos_g - R_E) / d))
    return d, el


def _grp(grp_id=1, lo=10.8e9, hi=10.85e9, emissions=None, gain=30.0, bore=None, psi0=None, cls=("EC",)):
    emissions = emissions or (Emission(None, -60.0, 36e6),)
    return PfdGroup(grp_id, lo, hi, tuple(emissions), gain, bore, psi0, cls)


def _gso(lon=0.0, te=0.0, tw=0.0):
    return Geometry("gso", lon_deg=lon, tol_east=te, tol_west=tw)


def _checks(groups, geom, ntc_type="G", notified=(), grid=None, **kw):
    grid = grid or Grid.of((HELSINKI,))
    return notice_checks(list(groups), list(notified), geom, ntc_type, "A", load_limits(), grid, **kw)


def _only(checks, row_id=None):
    picked = [c for c in checks if row_id is None or c["row_id"] == row_id]
    assert len(picked) == 1, picked
    return picked[0]


def test_gso_peak_gain_at_helsinki():
    """GSO at 0°E, Helsinki. pwr_ds_max −60 dB(W/Hz) → P_ref = −60 + 10·log10(4000) = −23.979 dBW in 4 kHz.
    cos γ = cos 60.17° · cos 24.94° = 0.45104; d = √(r² + R² − 2rR cos γ) ≈ 39 698 km;
    el = asin((r cos γ − R)/d) ≈ 18.57°. pfd = −23.979 + 30 − 10·log10(4π d²) ≈ −156.95 dB(W/m²);
    limit = −150 + 0.5(δ − 5) ≈ −143.22 dB(W/m²).
    """
    d, el = _gso_hand(*HELSINKI, 0.0)
    pfd = -60 + 10 * math.log10(4000) + 30 - _spread(d)
    limit = -150 + 0.5 * (el - 5)
    c = _only(_checks([_grp()], _gso()))
    assert c["row_id"] == "t21-4-10700-11700-fss-gso" and c["source"] == "calculated"
    assert c["delta_deg"] == pytest.approx(el, abs=0.01)
    assert c["pfd_dbw_m2"] == pytest.approx(pfd, abs=0.05)
    assert c["limit_dbw_m2"] == pytest.approx(limit, abs=0.05)
    assert c["margin_db"] == pytest.approx(pfd - limit, abs=0.05)
    assert c["outcome"] == ("exceeds" if pfd > limit else "meets")
    assert {a["id"] for a in c["assumptions"]} >= {"pfd_peak_gain", "pfd_near_db"}


def test_gso_with_boresight_uses_s672():
    """Same case with a beam aimed at 61°N 26°E, ψ0 = 1°: ψ is the angle at the satellite between the
    directions to Helsinki and to the boresight; G = Gmax − 3(ψ/ψ0)² (S.672, ψ/ψ0 ≤ 2.58).
    """

    def xyz(lat, lon, r):
        la, lo = math.radians(lat), math.radians(lon)
        return np.array([r * math.cos(la) * math.cos(lo), r * math.cos(la) * math.sin(lo), r * math.sin(la)])

    sat = np.array([R_GSO, 0.0, 0.0])
    a, b = xyz(*HELSINKI, R_E) - sat, xyz(61.0, 26.0, R_E) - sat
    psi = math.degrees(math.acos(a @ b / (np.linalg.norm(a) * np.linalg.norm(b))))
    assert psi / 1.0 <= 2.58
    d, _ = _gso_hand(*HELSINKI, 0.0)
    pfd = -60 + 10 * math.log10(4000) + (40 - 3 * psi**2) - _spread(d)
    c = _only(_checks([_grp(gain=40.0, bore=(26.0, 61.0), psi0=1.0)], _gso()))
    assert c["pfd_dbw_m2"] == pytest.approx(pfd, abs=0.05)
    assert "pfd_peak_gain" not in {a["id"] for a in c["assumptions"]}
    peak = _only(
        _checks([_grp(gain=40.0, bore=(26.0, 61.0), psi0=1.0)], _gso(), params=Params(use_boresight=False))
    )
    assert peak["pfd_dbw_m2"] == pytest.approx(pfd + 3 * psi**2, abs=0.05)


def test_ngso_at_minimum_altitude():
    """550 km, peak gain 20 dBi, pwr_ds_max −70 dB(W/Hz) → P_ref = −70 + 60 = −10 dBW in 1 MHz (10.7–11.7 GHz
    non-GSO row). d(90°) = 550 km. d(10°) = √((R+h)² − R² cos² 10°) − R sin 10° ≈ 1 816 km. Limit −116 at 90°,
    −126 + 0.5·5 = −123.5 at 10°. The check keeps the worst margin of the 0.5° sweep.
    """
    h = 550.0
    d10 = math.sqrt((R_E + h) ** 2 - (R_E * math.cos(math.radians(10))) ** 2) - R_E * math.sin(
        math.radians(10)
    )
    assert float(ngso_slant_range_km(np.array([90.0]), h)[0]) == pytest.approx(h, abs=1e-6)
    assert float(ngso_slant_range_km(np.array([10.0]), h)[0]) == pytest.approx(d10, abs=1e-6)
    p_ref, g = -70 + 60, 20.0
    margin_90 = p_ref + g - _spread(h) - (-116)
    margin_10 = p_ref + g - _spread(d10) - (-123.5)
    sweep = np.arange(0, 90.25, 0.5)
    d = np.sqrt((R_E + h) ** 2 - (R_E * np.cos(np.radians(sweep))) ** 2) - R_E * np.sin(np.radians(sweep))
    lim = np.interp(sweep, [0, 5, 25, 90], [-126, -126, -116, -116])
    hand = p_ref + g - 10 * np.log10(4 * np.pi * (d * 1e3) ** 2) - lim
    geom = Geometry("ngso", constellation=Constellation.from_planes([h], [87.0], [0.0], [10]), min_alt_km=h)
    grp = _grp(lo=11.0e9, hi=11.1e9, emissions=(Emission(None, -70.0, 10e6),), gain=g)
    c = _only(_checks([grp], geom, "N"))
    assert c["row_id"] == "t21-4-10700-11700-fss-ngso"
    assert c["margin_db"] == pytest.approx(float(hand.max()), abs=0.05)
    assert c["delta_deg"] == float(sweep[int(hand.argmax())])
    assert margin_90 == pytest.approx(float(hand[-1]), abs=1e-9)
    assert margin_10 == pytest.approx(float(hand[20]), abs=1e-9)


def test_narrow_carrier_counts_its_whole_power():
    """B_n = 100 kHz < B_ref = 1 MHz: P_ref is the carrier power pep_max = −10 dBW, not density + 60 dB."""
    geom = Geometry(
        "ngso", constellation=Constellation.from_planes([550.0], [87.0], [0.0], [10]), min_alt_km=550.0
    )
    grp = _grp(lo=11.0e9, hi=11.0001e9, emissions=(Emission(-10.0, -55.0, 100e3),), gain=0.0)
    c = _only(_checks([grp], geom, "N"))
    power = next(i for i in c["inputs"] if i["name"] == "Power in the reference bandwidth")
    assert power["value"] == pytest.approx(-10.0)


def test_tolerance_edge_nearer_finland_gives_the_worst_margin():
    """Flat −164 dB limit (5 150–5 216 MHz): only the range matters, so the edge nearer Finland (5°E) wins."""
    grp = _grp(lo=5.16e9, hi=5.17e9)
    c = _only(_checks([grp], _gso(0.0, te=5.0, tw=5.0)))
    d, _ = _gso_hand(*HELSINKI, 5.0)
    assert c["pfd_dbw_m2"] == pytest.approx(-60 + 10 * math.log10(4000) + 30 - _spread(d), abs=0.05)
    lon = next(i for i in c["inputs"] if i["name"] == "Satellite longitude at the worst point")
    assert lon["value"] == 5.0


def test_notified_pfd_takes_precedence_at_the_lowest_delta():
    grid = Grid.of(((60.0, 25.0), (69.5, 27.0)))
    _, el_low = _gso_hand(69.5, 27.0, 0.0)
    c = _only(_checks([_grp()], _gso(), notified=[NotifiedPfd(10.7e9, 10.95e9, -150.0, 4e3)], grid=grid))
    assert c["source"] == "notified" and c["pfd_dbw_m2"] == pytest.approx(-150.0)
    assert c["delta_deg"] == pytest.approx(el_low, abs=0.01)
    assert c["limit_dbw_m2"] == pytest.approx(-150 + 0.5 * (el_low - 5), abs=0.01)
    assert {a["id"] for a in c["assumptions"]} >= {"cpfd_flat", "cpfd_min_delta"}
    assert any(i["name"] == "Calculated margin" for i in c["inputs"])
    scaled = _only(
        _checks([_grp()], _gso(), notified=[NotifiedPfd(10.7e9, 10.95e9, -150.0, 40e3)], grid=grid)
    )
    assert scaled["pfd_dbw_m2"] == pytest.approx(-160.0)
    lenient = _only(
        _checks(
            [_grp()],
            _gso(),
            notified=[NotifiedPfd(10.7e9, 10.95e9, -150.0, 4e3)],
            grid=grid,
            params=Params(cpfd_delta="max"),
        )
    )
    assert lenient["delta_deg"] > c["delta_deg"]


def test_notified_pfd_without_bandwidth_falls_back_to_calculated():
    c = _only(_checks([_grp()], _gso(), notified=[NotifiedPfd(10.7e9, 10.95e9, -131.0, None)]))
    assert c["source"] == "calculated"
    assert "without reference bandwidth" in c["reason"]


@pytest.mark.parametrize(
    ("grp", "geom", "ntc_type", "outcome", "reason"),
    [
        (_grp(cls=()), _gso(), "G", "not_assessed", "srv_cls"),
        (_grp(cls=("XX",)), _gso(), "G", "not_assessed", "Unknown station class XX"),
        (_grp(lo=1.164e9, hi=1.215e9, cls=("EN",)), _gso(), "G", "not_applicable", "No Table 21-4 limit"),
        (_grp(gain=None), _gso(), "G", "not_assessed", "No power or gain"),
        (_grp(), _gso(-100.0), "G", "not_applicable", "Never visible"),
        (_grp(), None, "G", "not_assessed", "No orbit or GSO position"),
        (
            _grp(lo=3.7e9, hi=3.8e9),
            Geometry(
                "ngso", constellation=Constellation.from_planes([550.0], [87.0], [0.0], [4]), min_alt_km=550
            ),
            "N",
            "not_assessed",
            "Y",
        ),
        (
            _grp(lo=38e9, hi=38.5e9),
            Geometry(
                "ngso", constellation=Constellation.from_planes([550.0], [87.0], [0.0], [120]), min_alt_km=550
            ),
            "N",
            "not_assessed",
            "at most 99",
        ),
        (
            _grp(lo=18e9, hi=18.1e9),
            Geometry(
                "ngso",
                constellation=Constellation.from_planes([550.0], [53.0], [0.0], [1200]),
                min_alt_km=550,
            ),
            "N",
            "not_assessed",
            "Nv",
        ),
    ],
)
def test_outcome_mapping(grp, geom, ntc_type, outcome, reason):
    checks = _checks([grp], geom, ntc_type)
    c = next(c for c in checks if c["outcome"] == outcome)
    assert reason in c["reason"]
    assert summarise(checks, load_limits())["pfd_outcome"] == outcome


def test_heo_rows_follow_the_orbit_class():
    heo = Geometry(
        "ngso",
        constellation=Constellation.from_planes([39000.0], [63.4], [0.0], [3]),
        min_alt_km=1000,
        heo=True,
    )
    rows = {c["row_id"] for c in _checks([_grp(lo=11.0e9, hi=11.1e9)], heo, "N")}
    assert rows == {"t21-4-10700-12500-fss-ngso-heo"}


def test_suppressed_notice_and_es_notice():
    assert (
        _only(notice_checks([_grp()], [], _gso(), "G", "S", load_limits(), Grid.of((HELSINKI,))))["outcome"]
        == "not_applicable"
    )
    assert notice_checks([], [], None, "S", "A", load_limits(), Grid.of((HELSINKI,))) == []
    assert summarise([], load_limits())["pfd_outcome"] == "not_applicable"


def test_groups_sharing_a_row_collapse_to_the_worst():
    strong = _grp(grp_id=7, emissions=(Emission(None, -40.0, 36e6),))
    weak = _grp(grp_id=3, emissions=(Emission(None, -80.0, 36e6),))
    c = _only(_checks([weak, strong], _gso()))
    assert c["grp_id"] == 7 and c["n_groups"] == 2
    assert c["n_groups_exceeding"] == (1 if c["outcome"] == "exceeds" else 0)
    assert c["check_id"] == "t21-4-10700-11700-fss-gso#1"


def test_near_limit_and_summary():
    d, el = _gso_hand(*HELSINKI, 0.0)
    limit = -150 + 0.5 * (el - 5)
    # Set the density so the pfd sits 1 dB under the limit.
    pds = limit - 1 - 10 * math.log10(4000) - 30 + _spread(d)
    checks = _checks([_grp(emissions=(Emission(None, pds, 36e6),))], _gso())
    s = summarise(checks, load_limits())
    assert s["pfd_outcome"] == "meets" and s["pfd_near_limit"] is True
    assert s["max_pfd_margin_db"] == pytest.approx(-1.0, abs=0.01)
    assert (
        summarise(
            _checks([_grp(emissions=(Emission(None, pds, 36e6),))], _gso(), params=Params(near_db=0.5)),
            load_limits(),
        )["pfd_near_limit"]
        is False
    )
    assert len(s["pfd_limits_sha256"]) == 64 and s["pfd_check_version"] == "art21-1"


def test_deterministic():
    grid = Grid.of(((60.0, 25.0), (65.0, 26.0), (69.0, 27.0)))
    args = ([_grp(), _grp(grp_id=2, lo=12.0e9, hi=12.1e9)], _gso(10.0, 0.1, 0.1))
    assert _checks(*args, grid=grid) == _checks(*args, grid=grid)


def test_inconsistent_power_density_falls_back_to_pep():
    """pwr_ds_max +73 dB(W/Hz) with pep_max −4 dBW (a sign error in 3074): 73 + 10·log10(4000) ≫ −4, so the
    density is dropped and the 8 MHz carrier counts as flat: −4 − 10·log10(8e6) + 10·log10(4000) = −37.01 dBW.
    """
    e = Emission.of(-4.0, 73.0, 8e6, 2.25e9)
    assert e.pds_dbw_hz is None and e.pds_dropped
    assert e.p_ref_dbw(4000)[0] == pytest.approx(-4 - 10 * math.log10(8e6) + 10 * math.log10(4000))
    ok = Emission.of(21.5, -54.0, 36e6, 11e9)
    assert ok.pds_dbw_hz == -54.0 and not ok.pds_dropped
    # Above 15 GHz the averaging band is 1 MHz: −54 + 60 = 6 dBW ≤ pep 21.5 dBW, kept.
    assert Emission.of(21.5, -54.0, 36e6, 20e9).pds_dbw_hz == -54.0
    geom = Geometry(
        "ngso", constellation=Constellation.from_planes([300.0], [97.0], [0.0], [1]), min_alt_km=300
    )
    grp = _grp(lo=2.2e9, hi=2.29e9, emissions=(e,), gain=-10.0, cls=("ER",))
    c = _only(_checks([grp], geom, "N"))
    assert "pfd_density_inconsistent" in {a["id"] for a in c["assumptions"]}


def test_gain_offset_shifts_the_calculated_margin():
    base = _only(_checks([_grp()], _gso()))
    off = _only(_checks([_grp()], _gso(), params=Params(gain_offset_db=-10)))
    assert off["margin_db"] == pytest.approx(base["margin_db"] - 10, abs=1e-6)


def test_notified_pfd_scaling_is_capped_by_the_carrier():
    """−125 dB(W/m²) in 1 MHz for a 40 kHz carrier: all the power is in 40 kHz, so in 4 kHz it is
    −125 + 10·log10(4000 / 40000) = −135, not the flat-over-1-MHz −125 − 24 = −149."""
    grp = _grp(emissions=(Emission(None, -60.0, 40e3),))
    c = _only(_checks([grp], _gso(), notified=[NotifiedPfd(10.7e9, 10.95e9, -125.0, 1e6)]))
    assert c["pfd_dbw_m2"] == pytest.approx(-135.0)


def test_notified_meets_but_calculated_exceeds_is_explained():
    grp = _grp(emissions=(Emission(None, -20.0, 36e6),))
    c = _only(_checks([grp], _gso(), notified=[NotifiedPfd(10.7e9, 10.95e9, -170.0, 4e3)]))
    assert c["source"] == "notified" and c["outcome"] == "meets"
    assert "calculated pfd exceeds" in c["reason"]


def test_notice_gain_fallback_is_an_assumption():
    grp = PfdGroup(1, 10.8e9, 10.85e9, (Emission(None, -60.0, 36e6),), 30.0, None, None, ("EC",), False, True)
    assert "pfd_notice_gain" in {a["id"] for a in _only(_checks([grp], _gso()))["assumptions"]}
