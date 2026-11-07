import copy
import json
from dataclasses import asdict
from datetime import date

import duckdb
import pytest
from riia_fixtures import FIXTURE_ISSUE, loaded_db
from test_riia_assess import TwoStations

from ific import m4, special_interest
from ific.config import settings
from ific.riia import draft, regulatory, store
from ific.riia.assess import assess_issue
from ific.riia.receivers import Receiver

AS_OF = date(2026, 7, 1)
AFTER_WINDOW = date(2026, 11, 6)
NOT_IDENTIFIED = 1101
API_UNKNOWN_ADM = 1102
DISH = Receiver(
    "dish-x", "stations", "fss_es", 60.17, 24.94, 10.0, 10.7e9, 12.0e9, None, 180.0, gain_dbi=45.0
)


class GenericTwoStations(TwoStations):
    name = "generic-m4"


class OneDish:
    """Stations population for the main-beam reading: a high-gain FSS dish pointed at 25°E."""

    def receivers(self, con: duckdb.DuckDBPyConnection) -> list[Receiver]:
        return [DISH]


def _variant(r: dict, ntc_id: int, prov: str, adm: str) -> dict:
    """A copy of a fixture result under another regulatory context; its hazard readings are unchanged."""
    out = copy.deepcopy(r)
    out.update(ntc_id=ntc_id, prov=prov, adm=adm, sat_name=f"VARIANT-{ntc_id}")
    out["regulatory"] = regulatory.context(prov, date(2026, 6, 23), [], AS_OF)
    return out


@pytest.fixture(scope="module")
def con(tmp_path_factory: pytest.TempPathFactory) -> duckdb.DuckDBPyConnection:
    con = loaded_db(tmp_path_factory.mktemp("draft"))
    m4.ensure_m4(con, settings)
    special_interest.ensure_special_interest(con, settings)
    for population in (TwoStations(), GenericTwoStations()):
        results = assess_issue(con, FIXTURE_ISSUE, AS_OF, population)
        base = next(r for r in results if r["ntc_id"] == 1001)
        results += [
            _variant(base, NOT_IDENTIFIED, "9.6", "USA"),
            _variant(base, API_UNKNOWN_ADM, "9.1A", "ZZZ"),
        ]
        store.write_results(con, FIXTURE_ISSUE, population.name, results)
    return con


@pytest.fixture(autouse=True)
def one_dish(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(draft, "StationsPopulation", OneDish)


def _draft(con: duckdb.DuckDBPyConnection, ntc_id: int, as_of: date = AS_OF) -> draft.Draft:
    d = draft.build_draft(con, FIXTURE_ISSUE, ntc_id, as_of)
    assert isinstance(d, draft.Draft), d
    return d


def test_choose_kind() -> None:
    reg = {"stage": "CR/C", "window_open": True, "fin_identified": True}
    assert draft.choose_kind(reg) == "comment_9_52"
    assert draft.choose_kind({**reg, "fin_identified": False}) == "inclusion_9_41"
    assert draft.choose_kind({**reg, "stage": "API/A"}) == "comment_9_3"
    assert draft.choose_kind({**reg, "window_open": False}) == "enquiry"
    assert draft.choose_kind({**reg, "stage": "Notification", "window_open": False}) == "enquiry"


def test_comment_9_52_when_finland_identified(con: duckdb.DuckDBPyConnection) -> None:
    d = _draft(con, 1001)
    assert d.kind == "comment_9_52" and d.fin_identified and d.window_end == "2026-10-23"
    assert d.adm == "USA" and d.adm_name == "United States of America"
    assert d.br_provisions == ["9.11", "A30A#7.1"]
    assert "RR No. 9.11, Appendix 30A, § 7.1" in d.letter_md
    assert "To: Administration of United States of America (USA)" in d.letter_md
    assert d.warnings == []


def test_inclusion_9_41_when_not_identified(con: duckdb.DuckDBPyConnection) -> None:
    d = _draft(con, NOT_IDENTIFIED)
    assert d.kind == "inclusion_9_41" and not d.fin_identified
    assert "Pursuant to RR No. 9.41" in d.letter_md
    assert "RR No. 9.41: an administration may request inclusion" in d.letter_md.split("## Annex")[1]


def test_comment_9_3_and_unknown_administration(con: duckdb.DuckDBPyConnection) -> None:
    d = _draft(con, API_UNKNOWN_ADM)
    assert d.kind == "comment_9_3" and d.stage == "API/A"
    assert d.adm_name is None and "To: Administration (ZZZ)" in d.letter_md
    assert any("`ZZZ` is not in `data/ref/itu_administrations.json`" in w for w in d.warnings)


def test_enquiry_without_window_and_after_window(con: duckdb.DuckDBPyConnection) -> None:
    notification = _draft(con, 1002)
    assert notification.kind == "enquiry" and notification.stage == "Notification"
    assert any("No RR comment window applies at stage Notification" in w for w in notification.warnings)
    closed = _draft(con, 1001, AFTER_WINDOW)
    assert closed.kind == "enquiry" and closed.days_left == -14
    assert any("closed on 2026-10-23" in w for w in closed.warnings)
    assert "Pursuant to RR" not in closed.letter_md


def test_no_concern_and_not_assessed(con: duckdb.DuckDBPyConnection) -> None:
    for ntc in (1003, 1004, 1005):
        out = draft.build_draft(con, FIXTURE_ISSUE, ntc, AS_OF)
        assert isinstance(out, draft.NoConcern) and f"notice {ntc}" in out.reason
    assert draft.build_draft(con, FIXTURE_ISSUE, 424242, AS_OF) is None


def test_annex_values_equal_stored_values(con: duckdb.DuckDBPyConnection) -> None:
    d = _draft(con, 1001)
    assert {(r.source, r.reading) for r in d.annex} >= {
        ("stations", "exceeds"),
        ("stations", "main_beam"),
        ("generic-m4", "exceeds"),
    }
    for row in d.annex:
        stored = store.get_notice(con, FIXTURE_ISSUE, row.source, 1001, AS_OF)
        h = next(h for h in stored["hazards"] if h["hazard_id"] == row.hazard_id)
        assert row.share_violating == h["share_violating"] and row.worst_case_db == h["worst_case_db"]
        assert row.bands_hz == [tuple(b) for b in h["bands_hz"]]
        p95 = [e["p95_db"] for e in h["exceedance_db"] if e["p95_db"] is not None]
        assert row.worst_p95_db == (max(p95) if p95 else None)
        assert row.hazard_id and row.cite in {c["cite"] for c in h["criteria"]}
        assert f"`{row.hazard_id}`" in d.letter_md and row.cite in d.letter_md


def test_station_details_stay_in_reviewer_notes(con: duckdb.DuckDBPyConnection) -> None:
    d = _draft(con, 1001)
    assert any(r.reading == "main_beam" and r.hazard_id == "cochannel:fss_es" for r in d.annex)
    assert DISH.id not in d.letter_md and "180°" not in d.letter_md
    assert any(DISH.id in n and "azimuth 180°" in n for n in d.reviewer_notes)


def test_banner_reviewer_notes_and_reproducibility(con: duckdb.DuckDBPyConnection) -> None:
    a, b = _draft(con, 1001), _draft(con, 1001)
    assert a.letter_md == b.letter_md and asdict(a) == asdict(b)
    assert a.letter_md.startswith(f"**{draft.BANNER}**") and a.letter_md.rstrip().endswith(
        f"**{draft.BANNER}**"
    )
    assert a.reviewer_notes[0] == "Comment window ends 2026-10-23: 114 days left as of 2026-07-01."
    assert "`receiver_classes.json` review status: pending." in a.reviewer_notes
    assert "`itu_administrations.json` review status: pending." in a.reviewer_notes
    payload = json.dumps(asdict(a))
    assert "score" not in payload


def test_prose_is_in_letter_and_annex_is_not_prose(con: duckdb.DuckDBPyConnection) -> None:
    d = _draft(con, 1001)
    assert len(d.prose_paragraphs) == 4 and all(p in d.letter_md for p in d.prose_paragraphs)
    assert not any("| " in p or "Basis (" in p for p in d.prose_paragraphs)
    assert draft.render_letter(d, d.prose_paragraphs) == d.letter_md


def test_protected_tokens() -> None:
    text = (
        "The Administration of Finland refers to notice 1001 by the Administration of France (F), published "
        "in BR IFIC 3074 of 2026-06-23 under provision 9.1A. Pursuant to RR No. 9.52C, within 6 dB "
        "(cochannel:fixed), Appendix 30A, § 7.1."
    )
    assert draft.protected_tokens(text, "F") == sorted(
        ["1001", "3074", "2026-06-23", "9.1A", "9.52C", "6", "cochannel:fixed", "30A", "7.1", "(F)"]
    )


def test_check_polish(con: duckdb.DuckDBPyConnection) -> None:
    d = _draft(con, 1001)
    faithful = "\n\n".join(p.replace("refers to", "wishes to refer to") for p in d.prose_paragraphs)
    ok = draft.check_polish(d, faithful)
    assert ok.reason is None and ok.paragraphs and len(ok.paragraphs) == 4
    changed = draft.check_polish(d, faithful.replace("2026-10-23", "2026-11-23"))
    assert (
        changed.paragraphs is None and changed.missing == ["2026-10-23"] and changed.added == ["2026-11-23"]
    )
    dropped = draft.check_polish(d, faithful.replace("notice 1001", "this notice"))
    assert dropped.missing == ["1001"]
    merged = draft.check_polish(d, faithful.replace("\n\n", " ", 1))
    assert merged.paragraphs is None and "paragraphs" in (merged.reason or "")


def test_administration_table_has_ingested_codes() -> None:
    table = draft.load_administrations()
    assert table["cite"] and table["review"]["status"] == "pending"
    assert {"USA", "CHN", "F", "RUS", "IND", "FIN"} <= set(table["admins"])
    assert all(isinstance(v, str) or v is None for v in table["admins"].values())


def test_triage_uses_the_same_readings(con: duckdb.DuckDBPyConnection) -> None:
    from ific.riia import review

    rows, _ = review.triage(con, FIXTURE_ISSUE, AS_OF)
    by_id = {r["ntc_id"]: r for r in rows}
    assert by_id[1001]["group"] == "A" and by_id[1001]["exceeds"][0].startswith("cochannel:fixed ")
    assert 1004 not in by_id and 1005 not in by_id
