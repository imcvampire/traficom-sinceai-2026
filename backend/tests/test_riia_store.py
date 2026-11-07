from datetime import date
from pathlib import Path

from riia_fixtures import FIXTURE_ISSUE, loaded_db
from test_riia_assess import AS_OF, TwoStations

from ific.riia import store
from ific.riia.assess import assess_issue
from ific.riia.schemas import NoticeDetailOut, NoticeSummaryOut

PFD_KEYS = (
    "pfd_checks",
    "pfd_outcome",
    "max_pfd_margin_db",
    "pfd_near_limit",
    "pfd_check_version",
    "pfd_limits_sha256",
    "pfd_limits_review",
)


def test_round_trip_and_replace(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    results = assess_issue(con, FIXTURE_ISSUE, AS_OF, TwoStations())
    store.write_results(con, FIXTURE_ISSUE, "stations", results)
    store.write_results(con, FIXTURE_ISSUE, "stations", results)
    assert con.execute("SELECT count(*) FROM analytics.risk_notice").fetchone()[0] == 5
    n_haz = sum(len(r["hazards"]) for r in results)
    assert con.execute("SELECT count(*) FROM analytics.risk_hazard").fetchone()[0] == n_haz
    cols = {r[0] for r in con.execute("DESCRIBE analytics.risk_notice").fetchall()}
    assert not any("score" in c for c in cols)

    listing, assessed_at = store.list_notices(con, FIXTURE_ISSUE, "stations", AS_OF)
    assert assessed_at and [n["ntc_id"] for n in listing] == [r["ntc_id"] for r in results]
    assert "hazards" not in listing[0] and "pfd_checks" not in listing[0]
    assert "pfd_outcome" in listing[0]
    detail = store.get_notice(con, FIXTURE_ISSUE, "stations", 1001, date(2026, 11, 6), {"full_duty_cycle"})
    assert detail["regulatory"]["days_left"] == -14 and not detail["in_queue"]
    flagged = {a["id"] for h in detail["hazards"] for a in h["assumptions"] if a["sensitive"]}
    assert flagged == {"full_duty_cycle"}
    assert store.issue_summaries(con, "stations")[FIXTURE_ISSUE]["outcome_counts"]["exceeds"] >= 1


def test_canonical_export_is_byte_identical(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    a = store.canonical_json(assess_issue(con, FIXTURE_ISSUE, AS_OF, TwoStations()))
    b = store.canonical_json(assess_issue(con, FIXTURE_ISSUE, AS_OF, TwoStations()))
    assert a == b and "Infinity" not in a and "NaN" not in a


def test_canonical_export_covers_the_pfd_check(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    a = store.canonical_json(assess_issue(con, FIXTURE_ISSUE, AS_OF, TwoStations()))
    assert '"pfd_checks"' in a and '"margin_db"' in a


def test_results_stored_before_the_pfd_check_read_back_as_null(tmp_path: Path) -> None:
    con = loaded_db(tmp_path)
    results = [
        {k: v for k, v in r.items() if k not in PFD_KEYS}
        for r in assess_issue(con, FIXTURE_ISSUE, AS_OF, TwoStations())
    ]
    store.write_results(con, FIXTURE_ISSUE, "stations", results)
    listing, _ = store.list_notices(con, FIXTURE_ISSUE, "stations", AS_OF)
    assert all(NoticeSummaryOut(**n).pfd_outcome is None for n in listing)
    detail = NoticeDetailOut(**store.get_notice(con, FIXTURE_ISSUE, "stations", 1001, AS_OF, {"x"}))
    assert detail.pfd_checks is None and detail.pfd_check_version is None
