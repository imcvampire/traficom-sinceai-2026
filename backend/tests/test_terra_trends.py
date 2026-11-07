from pathlib import Path

from terra_fixtures import ISSUE_N, ISSUE_N1, assessed

from ific.terra import trends


def _rule(out: dict, rid: str) -> set[int]:
    return {m["terrakey"] for m in next(r for r in out["anomalies"] if r["id"] == rid)["matches"]}


def test_summed_counts_match_direct_part1_count_without_double_counting(tmp_path: Path) -> None:
    con, res = assessed(tmp_path)
    by_issue = {n: list(v.values()) for n, v in res.items()}
    out = trends.trends(ISSUE_N1, by_issue)
    direct = con.execute(
        "SELECT count(*) FROM terra.fxm_pub_hist h JOIN terra.fxm_terra t "
        "ON t.ific_no = h.ific_no AND t.terrakey = h.terrakey "
        "WHERE h.pub_no = h.ific_no AND h.pub_part = '1' AND t.stn_cls IN ('FB', 'ML') "
        "AND t.intent <> 'RECORDED' AND t.adm IN ('RUS', 'EST', 'NOR', 'S', 'LVA', 'LTU')"
    ).fetchone()[0]
    assert sum(p["received"] for p in out["per_issue"].values()) == direct
    assert sum(sum(v.values()) for v in out["counts"]["change"].values()) == direct
    # 90000001 is received in 9997 and recorded in 9998: counted once
    assert 90000001 not in {r["terrakey"] for r in trends.population(by_issue[ISSUE_N1])}


def test_anomaly_rules_fire_on_their_fixture_rows_only(tmp_path: Path) -> None:
    _, res = assessed(tmp_path)
    n = trends.trends(ISSUE_N, {ISSUE_N: list(res[ISSUE_N].values())})
    n1 = trends.trends(ISSUE_N1, {ISSUE_N1: list(res[ISSUE_N1].values())})
    assert _rule(n, "A1-new-band-near-border") == {90000002}
    assert _rule(n1, "A2-atypical-bandwidth") == {90000033}
    assert _rule(n1, "A3-erp-outlier") == {90000037}
    assert _rule(n, "A4-fin-coord-open") == {90000002} and not _rule(n1, "A4-fin-coord-open")
    assert all(r["citation"] and r["threshold"] for r in n["anomalies"])
