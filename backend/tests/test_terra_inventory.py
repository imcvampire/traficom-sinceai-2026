from pathlib import Path

from terra_fixtures import ISSUE_N, ISSUE_N1, assessed, loaded_db

from ific.terra import inventory


class RecordingCon:
    def __init__(self, con) -> None:
        self.con, self.params = con, []

    def execute(self, sql, params=None):
        self.params.append(params)
        return self.con.execute(sql, params) if params is not None else self.con.execute(sql)


def test_selection_excludes_fin_and_recorded_rows(tmp_path: Path) -> None:
    _, res = assessed(tmp_path, (ISSUE_N,))
    keys = set(res[ISSUE_N])
    assert 90000007 not in keys  # FIN FX
    assert not {80000008, 80000009} & keys  # RECORDED before-states
    assert {r["stn_cls"] for r in res[ISSUE_N].values()} == {"FB", "ML"}


def test_change_classes_and_modify_diff(tmp_path: Path) -> None:
    _, res = assessed(tmp_path, (ISSUE_N,))
    r = res[ISSUE_N]
    assert r[90000001]["change"] == "new" and r[90000009]["change"] == "withdrawn"
    mod = r[90000008]
    assert mod["change"] == "modified" and mod["target"]["terrakey"] == 80000008
    diff = {(d["table"], d["field"]): (d["before"], d["after"]) for d in mod["diff"]}
    assert diff == {("fxm_ant", "pwr_dbw"): (10.0, 15.0), ("fxm_ant", "hgt_agl"): (40.0, 45.0)}
    assert r[90000009]["target"] == {"terrakey": 80000009, "action": "SUPPRESS", "intent": "RECORDED"}


def test_recorded_status_uses_only_the_issue_own_rows(tmp_path: Path) -> None:
    con = loaded_db(tmp_path, (ISSUE_N1,))  # 9997 is never loaded
    rec = RecordingCon(con)
    items = {a["terrakey"]: a for a in inventory.inventory(ISSUE_N1, inventory.load_issue(rec, ISSUE_N1))}
    assert rec.params and all(p == [ISSUE_N1] for p in rec.params)
    pub = items[90000001]["pub_status"]
    assert pub["status"] == "recorded" and pub["part"] == "2" and pub["first_published_in"] == ISSUE_N
    assert pub["finding"] == {"fdg_type": "REX", "fdg_status": "FINAL", "is_favorbl": True}
    assert items[90000020]["pub_status"]["status"] == "returned"


def test_cross_issue_lineage_from_each_issue_alone(tmp_path: Path) -> None:
    _, res = assessed(tmp_path)
    added = res[ISSUE_N][90000003]
    assert added["change"] == "new" and added["pub_status"]["status"] == "received"
    withdrawn = res[ISSUE_N1][90000021]
    assert withdrawn["change"] == "withdrawn" and withdrawn["target"]["terrakey"] == 90000003
    assert 90000003 not in res[ISSUE_N1]  # shipped only as the RECORDED before-state
