import csv
import io
from pathlib import Path

from terra_fixtures import ISSUE_N, ISSUE_N1, assessed

from ific.terra import export, store
from ific.terra.assess import assess_issue


def test_reassessing_one_issue_leaves_the_other_byte_identical(tmp_path: Path) -> None:
    con, res = assessed(tmp_path)
    for n in res:
        store.write_results(con, n, list(res[n].values()))
    before = con.execute(
        "SELECT terrakey, payload FROM analytics.terra_assessment WHERE ific_no = ? ORDER BY terrakey",
        [ISSUE_N],
    ).fetchall()
    store.write_results(con, ISSUE_N1, assess_issue(con, ISSUE_N1))
    after = con.execute(
        "SELECT terrakey, payload FROM analytics.terra_assessment WHERE ific_no = ? ORDER BY terrakey",
        [ISSUE_N],
    ).fetchall()
    assert after == before
    assert store.canonical_json(store.all_results(con, ISSUE_N)) == store.canonical_json(
        list(res[ISSUE_N].values())
    )


def test_no_score_column_and_sorted_listing(tmp_path: Path) -> None:
    con, res = assessed(tmp_path, (ISSUE_N,))
    store.write_results(con, ISSUE_N, list(res[ISSUE_N].values()))
    cols = [
        r[0]
        for r in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name LIKE 'terra_%'"
        ).fetchall()
    ]
    assert cols and not any("score" in c for c in cols)
    rows = store.list_assignments(con, ISSUE_N)
    assert [r["sort_key"] for r in rows] == sorted(r["sort_key"] for r in rows)
    assert rows[0]["outcome"] == "exceeds"
    assert all("p1546" not in (r["hazard"].get("tier2") or {}) for r in rows)
    assert {r["terrakey"] for r in store.list_assignments(con, ISSUE_N, relevant=False)} == {90000005}
    assert [r["terrakey"] for r in store.list_assignments(con, ISSUE_N, q="slancy")] == [90000001]
    summary = store.issue_summaries(con)[ISSUE_N]
    assert summary["assignments"] == len(res[ISSUE_N]) and summary["outcome_counts"]["exceeds"] == 1


def test_exports(tmp_path: Path) -> None:
    _, res = assessed(tmp_path, (ISSUE_N,))
    results = list(res[ISSUE_N].values())
    rows = list(csv.DictReader(io.StringIO(export.to_csv(results))))
    assert tuple(rows[0]) == export.CSV_COLUMNS and len(rows) == len(results)
    assert rows[0]["outcome"] == "exceeds" and rows[0]["sources"].startswith(f"{ISSUE_N}:fxm_terra:")
    md = export.to_markdown(ISSUE_N, results)
    assert "## exceeds (1)" in md and "terrakey 90000008" in md and "| score" not in md.lower()
    assert export.to_json(results) == store.canonical_json(results)
