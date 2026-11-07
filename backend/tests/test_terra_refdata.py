import pytest

from ific.propagation import tr2508
from ific.terra import refdata


def test_tr2508_criterion_is_generated_from_the_module() -> None:
    tr = next(c for c in refdata.criteria() if c["id"] == refdata.TR2508_ID)
    assert [(b["f_min_mhz"], b["f_max_mhz"], b["trigger_dbuv_m"]) for b in tr["bands"]] == [
        (t.lower_mhz, t.upper_mhz, t.e_dbuv_m) for t in tr2508.TRIGGERS
    ]
    assert (tr["time_pct"], tr["loc_pct"], tr["rx_height_m"]) == (10.0, 50.0, 10.0)


def test_every_criterion_has_citation_and_verified_flag() -> None:
    for c in refdata.criteria():
        assert c["citation"] and c["doc_sha256"] and c["verified"] is False and "verified_by" in c
        assert all(b["quote"] for b in c["bands"])


@pytest.mark.parametrize(
    ("f_mhz", "expected"),
    [
        (29.7, "tr-25-08"),
        (470.0, "tr-25-08"),
        (470.1, None),
        (791.0, "ecc-rec-11-04"),
        (821.0, "ecc-rec-11-04"),
        (830.0, None),
        (900.0, None),
    ],
)
def test_criterion_band_edges(f_mhz: float, expected: str | None) -> None:
    c = refdata.criterion_for(f_mhz)
    assert (c["id"] if c else None) == expected


def test_ecc_trigger_bandwidth_correction() -> None:
    ecc = refdata.criterion_for(793.5)
    assert refdata.trigger(ecc, 793.5, 5000).e_dbuv_m == 41.0
    assert refdata.trigger(ecc, 794.74, 10000).bandwidth_correction_db == pytest.approx(3.0103, abs=1e-4)
    tr = refdata.criterion_for(450.0)
    assert refdata.trigger(tr, 450.0, 12.5).e_dbuv_m == 20.0


def test_land_mask_reference_points() -> None:
    lon = [26.5, 26.95, 28.19]
    lat = [60.0, 60.47, 59.38]
    assert refdata.is_land(lon, lat).tolist() == [False, True, True]


def test_border_points_are_stable_and_pinned() -> None:
    a = refdata.finland_border_points()
    refdata.finland_border_points.cache_clear()
    b = refdata.finland_border_points()
    assert a == b
    assert abs(len(a) - 798) <= 8
