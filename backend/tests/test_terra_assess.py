from pathlib import Path

from terra_fixtures import ISSUE_N, ISSUE_N1, assessed

from ific.terra.assess import assess_issue
from ific.terra.store import canonical_json


def _keys(x, found: set[str]) -> set[str]:
    if isinstance(x, dict):
        for k, v in x.items():
            found.add(k)
            _keys(v, found)
    elif isinstance(x, list):
        for v in x:
            _keys(v, found)
    return found


def test_two_runs_are_byte_identical_and_have_no_score(tmp_path: Path) -> None:
    con, res = assessed(tmp_path)
    for n in (ISSUE_N, ISSUE_N1):
        a = canonical_json(assess_issue(con, n))
        assert a == canonical_json(assess_issue(con, n))
        assert a == canonical_json(list(res[n].values()))
    assert not any("score" in k for k in _keys([r for v in res.values() for r in v.values()], set()))


def test_every_finding_has_sources_and_sort_key(tmp_path: Path) -> None:
    _, res = assessed(tmp_path, (ISSUE_N,))
    for r in res[ISSUE_N].values():
        assert r["model_version"] == "terra-1"
        assert r["sources"][0] == f"{ISSUE_N}:fxm_terra:{r['terrakey']}"
        assert len(r["sort_key"]) == 6 and r["sort_key"][-1] == r["terrakey"]
        assert r["outcome"] in ("exceeds", "meets", "screened_out", "not_applicable", "not_assessed")
        if r["outcome"] in ("exceeds", "meets"):
            assert r["criterion"]["citation"] and r["assumptions"]
