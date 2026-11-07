import logging
import time
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from ific import stations
from ific.propagation import p1546


def _features(client: TestClient, **params: float) -> list[dict]:
    res = client.get("/api/stations", params=params)
    assert res.status_code == 200, res.text
    return res.json()["features"]


def test_list_counts_and_reasons(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    stations.solve_radius.cache_clear()
    caplog.set_level(logging.INFO, logger="ific.stations")
    started = time.perf_counter()
    res = client.get("/api/stations", params={"time_pct": 10, "threshold_dbuv": 30})
    elapsed = time.perf_counter() - started
    logging.getLogger("ific.stations").info("first uncached /api/stations call: %.3f s", elapsed)
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "FeatureCollection"
    assert body["model"]["p1546_version"] == "ITU-R P.1546-6"
    features = body["features"]
    assert len(features) == 873
    with_contour = [f for f in features if f["properties"]["contour"] is not None]
    assert len(with_contour) == 444
    reasons = Counter(
        f["properties"]["no_contour_reason"] for f in features if not f["properties"]["contour"]
    )
    assert reasons == {"no_power": 328, "outside_p1546_range": 98, "missing_tx_frequency": 3}
    directional = [f for f in features if f["properties"]["directivity"] == "D"]
    assert sum(f["properties"]["azimuth_deg"] is not None for f in directional) == 188
    assert elapsed < 1.0, f"first uncached call took {elapsed:.3f} s"


def test_feature_shape(client: TestClient) -> None:
    feature = _features(client)[0]
    assert feature["geometry"]["type"] == "Point"
    lon, lat = feature["geometry"]["coordinates"]
    assert 19 < lon < 32 and 59 < lat < 71
    props = feature["properties"]
    for key in ("source_row", "band_bin", "quality_flags", "m4_services", "contour", "no_contour_reason"):
        assert key in props
    assert feature["id"] == props["source_row"]


def test_contour_radius_reproduces_threshold(client: TestClient) -> None:
    features = _features(client, time_pct=10, threshold_dbuv=30)
    exact = [
        f["properties"]["contour"]
        for f in features
        if (f["properties"]["contour"] or {}).get("bound") == "exact"
    ]
    assert len(exact) > 100
    for c in exact:
        e = p1546.field_strength(
            c["f_mhz"],
            c["time_pct"],
            [("land", c["radius_km"])],
            h1_m=c["h1_m"],
            h2_m=c["h2_m"],
            erp_dbw=c["erp_dbw"],
            ha_m=c["h1_m"],
        ).e_dbuv_m
        assert e == pytest.approx(c["threshold_dbuv"], abs=0.05)
    for c in exact:
        assert {"h1_flat_terrain", "path_assumed_land", "tca_not_applied"} <= set(c["assumptions"])


def test_threshold_sources(client: TestClient) -> None:
    features = _features(client)
    contours = [f["properties"] for f in features if f["properties"]["contour"]]
    tr = [p for p in contours if 29.7e6 <= p["tx_hz"] <= 470e6]
    assert tr and all(p["contour"]["threshold_source"] == "tr2508" for p in tr)
    assert all(p["contour"]["threshold_citation"].startswith("ECC T/R 25-08") for p in tr)
    user = [p for p in contours if p["tx_hz"] > 470e6]
    assert user and all(p["contour"]["threshold_source"] == "user" for p in user)
    assert all(p["contour"]["threshold_dbuv"] == 30 for p in user)


def test_radius_does_not_grow_with_threshold(client: TestClient) -> None:
    def radii(threshold: float) -> dict[int, float]:
        return {
            f["id"]: f["properties"]["contour"]["radius_km"]
            for f in _features(client, threshold_dbuv=threshold)
            if f["properties"]["contour"] and f["properties"]["contour"]["threshold_source"] == "user"
        }

    low, high = radii(20), radii(60)
    assert low.keys() == high.keys()
    assert all(high[k] <= low[k] + 1e-9 for k in low)
    assert any(high[k] < low[k] for k in low)


def test_time_percentage_changes_reach(client: TestClient) -> None:
    def total(t: int) -> float:
        return sum(
            f["properties"]["contour"]["radius_km"]
            for f in _features(client, time_pct=t)
            if f["properties"]["contour"]
        )

    assert total(1) > total(10) > total(50)


def test_band_bins() -> None:
    assert [stations.band_bin(hz) for hz in (1_500_000, 87_900_000, 450e6, 1.8e9, 3.5e9, 27.5e9, None)] == [
        0,
        1,
        2,
        3,
        4,
        5,
        None,
    ]


def test_detail(client: TestClient) -> None:
    res = client.get("/api/stations/13")
    assert res.status_code == 200
    body = res.json()
    assert body["properties"]["source_row"] == 13
    assert body["raw"]["tx_frequency"] == "87.900 MHz"
    assert body["m4_overlaps"]
    assert body["properties"]["contour"]["threshold_source"] == "tr2508"
    assert body["p1546_steps"]["emax_dbuv"] > 0
    assert body["model"]["tr2508_citation"].startswith("ECC T/R 25-08")


def test_detail_unknown_row(client: TestClient) -> None:
    assert client.get("/api/stations/1").status_code == 404


@pytest.mark.parametrize("params", [{"time_pct": 5}, {"threshold_dbuv": 121}, {"threshold_dbuv": -21}])
def test_invalid_params(client: TestClient, params: dict) -> None:
    assert client.get("/api/stations", params=params).status_code == 422


def _row(**overrides: object) -> dict:
    base = {
        "tx_hz": 450_000_000,
        "radiated_power_dbw": 10.0,
        "radiated_power_type": "E",
        "directivity": None,
        "bandwidth_hz": 25_000,
        "effective_agl_m": 30.0,
    }
    return base | overrides


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"effective_agl_m": None}, "missing_antenna_height"),
        ({"effective_agl_m": 3500.0}, "antenna_height_out_of_range"),
        ({"tx_hz": None}, "missing_tx_frequency"),
        ({"radiated_power_type": "P"}, "unsupported_power_type"),
    ],
)
def test_contour_rejects_incomplete_rows(overrides: dict, reason: str) -> None:
    assert stations.contour(_row(**overrides), 10, 30) == (None, reason)


def test_contour_for_complete_row() -> None:
    c, reason = stations.contour(_row(), 10, 30)
    assert reason is None and c is not None and c.threshold_source == "tr2508"
