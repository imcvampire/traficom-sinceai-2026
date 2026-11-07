from pathlib import Path

from terra_fixtures import ISSUE_N, assessed


def _signals(r) -> set[str]:
    return {s["id"] for s in r["relevance"]["signals"]}


def test_fin_coordination_and_site_range_make_relevant(tmp_path: Path) -> None:
    _, res = assessed(tmp_path, (ISSUE_N,))
    r = res[ISSUE_N]
    assert r[90000002]["relevance"]["relevant"] and {"fin_coordination", "ge06_affected"} <= _signals(
        r[90000002]
    )
    assert r[90000002]["relevance"]["fin_coord_required"] is True
    assert r[90000001]["relevance"]["relevant"] and "within_range" in _signals(r[90000001])
    assert r[90000004]["relevance"]["fin_coord_required"] is False  # COORD COMPLETED only


def test_far_notice_is_not_relevant_despite_m4_overlap(tmp_path: Path) -> None:
    _, res = assessed(tmp_path, (ISSUE_N,))
    chn = res[ISSUE_N][90000005]
    assert _signals(chn) == {"freq_overlap_m4"}
    assert chn["relevance"]["relevant"] is False and chn["relevance"]["distance_km"] > 1000
    assert chn["outcome"] == "not_applicable" and chn["reason"] == "not_relevant"
