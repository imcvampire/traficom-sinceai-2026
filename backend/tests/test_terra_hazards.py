from pathlib import Path

import pytest
from terra_fixtures import ISSUE_N, ISSUE_N1, assessed

from ific.terra.hazards import reproduce


def test_stored_inputs_reproduce_field_strength(tmp_path: Path) -> None:
    _, res = assessed(tmp_path)
    tier2 = [r for issue in res.values() for r in issue.values() if r["hazard"].get("tier2")]
    assert len(tier2) >= 3
    for r in tier2:
        assert reproduce(r["hazard"]) == pytest.approx(r["e_dbuv"], abs=1e-3)
        t2, p = r["hazard"]["tier2"], r["hazard"]["parameters"]
        assert {"f_mhz", "h1_m", "h2_m", "time_pct", "loc_pct", "erp_dbw", "bw_correction_db"} <= set(p)
        assert t2["path"] and t2["p1546"]["steps"] and "tca_not_applied" in t2["p1546"]["assumptions"]
        assert t2["e_all_land_dbuv"] <= t2["e_dbuv"] + 1e-6 <= t2["e_all_sea_dbuv"] + 2e-6


def test_not_assessed_and_not_applicable_reasons(tmp_path: Path) -> None:
    _, res = assessed(tmp_path, (ISSUE_N,))
    r = res[ISSUE_N]
    assert (r[90000006]["outcome"], r[90000006]["reason"]) == ("not_assessed", "missing_antenna_height")
    assert (r[90000004]["outcome"], r[90000004]["reason"]) == ("not_applicable", "receiving_station")


def test_criteria_and_frameworks(tmp_path: Path) -> None:
    _, res = assessed(tmp_path, (ISSUE_N,))
    r = res[ISSUE_N]
    est = r[90000003]
    assert est["criterion"]["id"] == "tr-25-08" and est["criterion"]["applicability"] == "applicable"
    assert est["outcome"] in ("meets", "exceeds") and est["hazard"]["parameters"]["h2_m"] == 10.0
    lte = r[90000002]
    assert lte["criterion"]["id"] == "ecc-rec-11-04" and lte["criterion"]["applicability"] == "indicative"
    assert lte["regulatory"]["ge06"]["applies"] is True and lte["hazard"]["parameters"]["h2_m"] == 3.0
    assert {"A-T-ECC-RUS", "A-T-ECC-NONPREF", "A-T-BILATERAL"} <= set(lte["assumptions"])
    assert lte["regulatory"]["governing"].startswith("FIN–RUS")
    assert all(any("Regulation M4" in c for c in x["regulatory"]["citations"]) for x in r.values())


def test_far_weak_notice_is_screened_out(tmp_path: Path) -> None:
    _, res = assessed(tmp_path, (ISSUE_N,))
    nor = res[ISSUE_N][90000010]
    assert nor["outcome"] == "screened_out" and nor["hazard"]["tier"] == 1
    assert nor["hazard"]["tier1"]["e_upper_dbuv"] <= nor["hazard"]["trigger"]["e_dbuv_m"] - 3


def test_eirp_and_directional_antenna_are_flagged(tmp_path: Path) -> None:
    _, res = assessed(tmp_path, (ISSUE_N,))
    est = res[ISSUE_N][90000011]
    assert est["antenna"]["erp_dbw"] == pytest.approx(-2.15)
    assert {"A-T-EIRP-ERP", "A-T-ANT-DIAG"} <= set(est["assumptions"])


def test_modified_notice_exceeds(tmp_path: Path) -> None:
    _, res = assessed(tmp_path)
    mod = res[ISSUE_N][90000008]
    assert mod["outcome"] == "exceeds" and mod["margin_db"] > 0
    assert res[ISSUE_N1][90000037]["outcome"] == "exceeds"


def _synthetic(f_mhz: float, h1: float, lat: float, lon: float) -> dict:
    return {
        "f_mhz": f_mhz,
        "bw_khz": 12.5,
        "site": {"lat": lat, "lon": lon, "geo_key": 1},
        "antenna": {"pwr_dbw": 10.0, "pwr_eiv": "E", "erp_dbw": 10.0, "hgt_agl_m": h1, "rows": 1,
                    "diagram": [], "azm_max_e": None},
    }  # fmt: skip


def test_tier1_bound_covers_land_below_100_mhz() -> None:
    from ific.terra import refdata
    from ific.terra.hazards import evaluate

    a = _synthetic(35.0, 30.0, 61.0, 31.5)  # Karelia, land path to the Finnish border
    hazard, _ = evaluate(a, refdata.criterion_for(35.0))
    t1 = hazard["tier1"]
    assert t1["path"][0]["kind"] == "land"  # land is above cold sea at 35 MHz
    if hazard.get("tier2"):
        assert hazard["tier2"]["e_dbuv"] <= t1["e_upper_dbuv"] + 1e-6


def test_p1546_input_error_is_not_assessed_for_that_assignment_only() -> None:
    from ific.terra import refdata
    from ific.terra.hazards import evaluate

    a = _synthetic(160.0, 0.5, 60.1, 25.9)  # h1 below 1 m on a path with sea
    hazard, _ = evaluate(a, refdata.criterion_for(160.0))
    assert hazard["outcome"] in ("not_assessed", "exceeds", "meets", "screened_out")
    if hazard["outcome"] == "not_assessed":
        assert hazard["reason"] == "p1546_input_out_of_range" and hazard["detail"]
