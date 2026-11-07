from pathlib import Path

import numpy as np
import pytest

from ific import db, m4, special_interest
from ific.config import Settings, settings
from ific.riia import review
from ific.riia.receivers import Receiver, StationsPopulation, max_plausible_gain_dbi


def test_half_power_beamwidth() -> None:
    assert review.half_power_beamwidth_deg(45.0) == pytest.approx(0.955, abs=0.002)


def test_min_off_axis_over_elevation_range() -> None:
    assert review.min_off_axis_deg(180.0, 0.0, 5.0, 180.0, 20.0) == pytest.approx(15.0)
    assert review.min_off_axis_deg(90.0, 0.0, 30.0, 90.0, 20.0) == pytest.approx(0.0, abs=1e-6)


def _h(outcome: str, p95: float | None) -> dict:
    return {"outcome": outcome, "exceedance_db": [{"p95_db": p95}]}


def test_near_limit_boundary() -> None:
    assert review.is_near_limit(_h("meets", -6.0))
    assert not review.is_near_limit(_h("meets", -6.01))
    assert not review.is_near_limit(_h("exceeds", -1.0))
    assert not review.is_near_limit(_h("meets", None))


def test_main_beam_requires_high_gain_pointed_at_the_gso() -> None:
    hazard = {
        "mode": "cochannel",
        "outcome": "exceeds",
        "service_class": "fss_es",
        "bands_hz": [[18.7e9, 18.8e9]],
    }
    dish = Receiver(
        "dish", "stations", "fss_es", 60.17, 24.94, 10.0, 18.7e9, 18.8e9, None, 180.0, gain_dbi=45.0
    )
    away = Receiver(
        "away", "stations", "fss_es", 60.17, 24.94, 10.0, 18.7e9, 18.8e9, None, 90.0, gain_dbi=45.0
    )
    hits = review.main_beam_hits([hazard], [dish, away], 25.0)
    assert [h.station for h in hits] == ["dish"] and hits[0].off_axis_deg < 0.5
    omni = {**hazard, "service_class": "mobile"}
    phone = Receiver("phone", "stations", "mobile", 60.17, 24.94, 2.0, 18.7e9, 18.8e9, None, 180.0)
    assert review.main_beam_hits([omni], [phone], 25.0) == []


def test_gain_cap() -> None:
    assert max_plausible_gain_dbi(25e9) == pytest.approx(58.2, abs=0.1)
    assert max_plausible_gain_dbi(460e6) == pytest.approx(23.5, abs=0.1)


def test_stations_population(tmp_path: Path) -> None:
    s = Settings(data_dir=settings.data_dir, db_dir=tmp_path / "db")
    con = db.connect(s.db_path, s.db_storage_version)
    m4.ensure_m4(con, s)
    special_interest.ensure_special_interest(con, s)
    pop = StationsPopulation()
    rx = pop.receivers(con)
    assert pop.excluded["broadcast transmitter licence"] > 0
    assert rx and all(r.f_hi_hz > r.f_lo_hz and r.source == "stations" for r in rx)
    fx = [r for r in rx if r.citation[0].endswith("licence FX)")]
    assert fx and all(r.service_class == "fixed" and r.azimuth_deg is not None for r in fx)
    capped = [r for r in rx if "station_gain_capped" in r.assumptions]
    assert capped and all(
        r.gain_dbi <= max_plausible_gain_dbi((r.f_lo_hz + r.f_hi_hz) / 2) + 0.05 for r in capped
    )
    assert np.isfinite([r.lat for r in rx]).all()
