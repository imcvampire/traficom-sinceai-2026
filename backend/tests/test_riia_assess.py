import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from riia_fixtures import FIXTURE_ISSUE, loaded_db

from ific.riia import hazards
from ific.riia.assess import assess_issue, technical_sort_key
from ific.riia.receivers import Receiver

AS_OF = date(2026, 7, 1)


class TwoStations:
    """Seam test: a hand-built population plugs into assess_issue unchanged."""

    name = "stations"

    def receivers(self, con) -> list[Receiver]:
        base = Receiver(
            "fx-hki",
            self.name,
            "fixed",
            60.17,
            24.94,
            30.0,
            10.7e9,
            10.95e9,
            28e6,
            180.0,
            21.8,
            citation=("test station",),
        )
        return [
            base,
            replace(
                base,
                id="es-oulu",
                service_class="fss_es",
                lat=65.01,
                lon=25.47,
                f_hi_hz=12.0e9,
                bw_hz=None,
                azimuth_deg=None,
                pointing_elev_deg=None,
            ),
        ]


@pytest.fixture(scope="module")
def results(tmp_path_factory: pytest.TempPathFactory) -> list[dict]:
    con = loaded_db(tmp_path_factory.mktemp("assess"))
    return assess_issue(con, FIXTURE_ISSUE, AS_OF, TwoStations())


def _by_id(results: list[dict]) -> dict[int, dict]:
    return {r["ntc_id"]: r for r in results}


def _hazard(r: dict, hid: str) -> dict:
    return next(h for h in r["hazards"] if h["hazard_id"] == hid)


def test_every_notice_has_full_inventory(results: list[dict]) -> None:
    assert len(results) == 5
    for r in results:
        modes = {h["mode"] for h in r["hazards"]}
        assert {"cochannel", "adjacent", "es_terrestrial", "blocking_im", "aggregate_networks"} <= modes
        assert "score" not in json.dumps(r)
        assert (
            r["receiver_source"] == "stations"
            and r["model_version"] == "riia-1"
            and r["as_of"] == "2026-07-01"
        )


def test_gso_main_beam_station_exceeds(results: list[dict]) -> None:
    h = _hazard(_by_id(results)[1001], "cochannel:fixed")
    assert h["tier"] == 2 and h["outcome"] == "exceeds" and h["share_violating"] == 1.0
    assert h["worst_case_db"] >= h["tier2_max_db"]
    assert h["n_receivers"] == 1 and len(h["risk_curves"][0]["likelihood"]) == 81


def test_tier1_bounds_tier2_everywhere(results: list[dict]) -> None:
    for r in results:
        for h in r["hazards"]:
            if h["tier"] == 2 and h["tier2_max_db"] is not None:
                assert h["worst_case_db"] >= h["tier2_max_db"] - 1e-9, (r["ntc_id"], h["hazard_id"])


def test_suppression_and_invisible_notices(results: list[dict]) -> None:
    by = _by_id(results)
    assert all(
        h["outcome"] == "not_applicable" and h["reason"] == "suppressed"
        for h in by[1004]["hazards"]
        if h["mode"] in hazards.QUANTIFIED_MODES
    )
    far = _hazard(by[1005], "cochannel:fixed")
    assert far["outcome"] == "not_applicable" and "never above the horizon" in far["reason"]
    assert by[1004]["worst_outcome"] == by[1005]["worst_outcome"] == "not_applicable"


def test_direction_mapping_and_earth_station(results: list[dict]) -> None:
    by = _by_id(results)
    gso = _hazard(by[1001], "cochannel:fixed")
    assert gso["bands_hz"] == [[10.7e9, 10.95e9]]
    es = by[1003]
    assert all(
        h["outcome"] == "not_applicable" for h in es["hazards"] if h["mode"] in hazards.QUANTIFIED_MODES
    )
    terr = _hazard(es, "es_terrestrial")
    assert terr["outcome"] == "not_assessed" and terr["in_summary"]
    assert es["worst_outcome"] == "not_assessed"
    assert _hazard(by[1001], "es_terrestrial")["outcome"] == "not_assessed"


def test_ngso_constellation_runs_tier2(results: list[dict]) -> None:
    h = _hazard(_by_id(results)[1002], "cochannel:fss_es")
    assert h["tier"] in (1, 2)
    if h["tier"] == 2:
        assert h["n_samples"] == 10_000


def test_regulatory_context(results: list[dict]) -> None:
    reg = _by_id(results)[1001]["regulatory"]
    assert reg["stage"] == "CR/C" and reg["window_end"] == "2026-10-23" and reg["days_left"] == 114
    assert reg["fin_identified"] and {f["source"] for f in reg["findings"]} == {"provn", "tr_aff_ntw"}
    assert _by_id(results)[1001]["in_queue"]
    notification = _by_id(results)[1002]["regulatory"]
    assert notification["stage"] == "Notification" and notification["days_left"] is None
    assert not notification["fin_identified"]


def test_sorted_by_technical_key(results: list[dict]) -> None:
    assert [technical_sort_key(r) for r in results] == sorted(technical_sort_key(r) for r in results)
    assert results[0]["worst_outcome"] == "exceeds"


def test_seeded_reproducibility_and_as_of(tmp_path: Path, results: list[dict]) -> None:
    con = loaded_db(tmp_path)
    again = assess_issue(con, FIXTURE_ISSUE, AS_OF, TwoStations())
    assert json.dumps(again, sort_keys=True) == json.dumps(results, sort_keys=True)
    later = assess_issue(con, FIXTURE_ISSUE, date(2026, 11, 6), TwoStations())
    for a, b in zip(results, later, strict=True):
        assert a["hazards"] == b["hazards"]
        assert {k: v for k, v in a["regulatory"].items() if k not in ("days_left", "window_open")} == {
            k: v for k, v in b["regulatory"].items() if k not in ("days_left", "window_open")
        }
    assert _by_id(later)[1001]["regulatory"]["days_left"] == -14


def test_consistency_checks_pass_on_fixture(results: list[dict]) -> None:
    from ific.riia import consistency

    c = consistency.checks(results)
    assert c["tier_violations"] == [] and c["bad_exceeds"] == []
    assert [b["ntc_id"] for b in c["br"]] == [1001] and c["br"][0]["agrees"]
    text = consistency.report(FIXTURE_ISSUE, "2026-07-01", results, {"duration_ms": 1000})
    assert "1 of 1 agree" in text and "Run time" in text
    assert [s["ntc_id"] for s in consistency.summary_snapshot(results)] == sorted(
        r["ntc_id"] for r in results
    )


def test_notified_pfd_reference_bandwidth_is_khz(tmp_path: Path) -> None:
    from ific.riia.assess import _load_notices

    con = loaded_db(tmp_path)
    grp = next(g for g in _load_notices(con, FIXTURE_ISSUE)[1001].downlinks if g.grp_id == 2001)
    # −150 dB(W/m²) in 4 kHz → −150 − 10·log10(4000) = −186.02 dB(W/m²/Hz)
    assert grp.cpfd_dens == pytest.approx(-186.02, abs=0.01)
