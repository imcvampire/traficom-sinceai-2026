import copy
import json

import pytest

from ific.config import settings
from ific.riia import pfd_limits
from ific.riia.pfd_limits import LimitsError, NotEvaluable, load_limits, parse

# Typed from RR Table 21-4 (Edition of 2024) independently of data/ref/rr21_pfd_limits.json: the limit in
# dB(W/m²) at δ = 0, 5, 25 and 90°, and at the extra breakpoints of the rows that have them.
STD = (0, 5, 25, 90)
EXPECTED: dict[str, dict[float, float]] = {
    "t21-4-1670-1700-eess-metsat": dict(zip(STD, (-133, -133, -133, -133), strict=True)),
    "t21-4-1525-1530-sr-so-eess-metsat": dict(zip(STD, (-154, -154, -144, -144), strict=True)),
    "t21-4-1700-1710-sr-so-eess-metsat": dict(zip(STD, (-154, -154, -144, -144), strict=True)),
    "t21-4-2025-2110-sr-so-eess-metsat": dict(zip(STD, (-154, -154, -144, -144), strict=True)),
    "t21-4-2200-2300-sr-so-eess-metsat": {0: -154, 5: -154, 15: -149, 25: -144, 90: -144},
    "t21-4-2500-2690-fss": {0: -136, 5: -136, 15: -130.5, 25: -125, 90: -125},
    "t21-4-2520-2670-bss": dict(zip(STD, (-136, -136, -125, -125), strict=True)),
    "t21-4-2500-2520-mss": dict(zip(STD, (-136, -136, -125, -125), strict=True)),
    "t21-4-2520-2535-mss": dict(zip(STD, (-136, -136, -125, -125), strict=True)),
    "t21-4-3400-4200-fss-gso": dict(zip(STD, (-152, -152, -142, -142), strict=True)),
    "t21-4-4500-4800-fss-metsat-mss-sr": dict(zip(STD, (-152, -152, -142, -142), strict=True)),
    "t21-4-7250-7900-fss-metsat-mss-sr": dict(zip(STD, (-152, -152, -142, -142), strict=True)),
    "t21-4-5150-5216-fss": dict(zip(STD, (-164, -164, -164, -164), strict=True)),
    "t21-4-6700-6825-fss": dict(zip(STD, (-137, -137, -127, -127), strict=True)),
    "t21-4-6825-7075-fss-4k": dict(zip(STD, (-154, -154, -144, -144), strict=True)),
    "t21-4-6825-7075-fss-1m": dict(zip(STD, (-134, -134, -124, -124), strict=True)),
    "t21-4-8025-8500-eess-sr": dict(zip(STD, (-150, -150, -140, -140), strict=True)),
    "t21-4-10700-11700-fss-gso": {0: -150, 5: -150, 15: -145, 25: -140, 90: -140},
    "t21-4-10700-11700-fss-ngso": dict(zip(STD, (-126, -126, -116, -116), strict=True)),
    "t21-4-10700-12500-fss-ngso-heo": {0: -129, 5: -129, 15: -121.5, 25: -114, 90: -114},
    "t21-4-11700-12500-fss-ngso": dict(zip(STD, (-124, -124, -114, -114), strict=True)),
    "t21-4-13400-13650-fss-gso": {0: -159, 5: -157, 25: -149, 80: -149, 82: -150, 84: -151, 90: -151},
    "t21-4-17700-19300-fss-iss-gso": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-17700-19300-metsat": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-17700-19700-fss-ngso-heo": {0: -120, 3: -120, 5: -118.2222, 12: -112, 25: -105, 90: -105},
    "t21-4-19300-19700-fss-bss-eess-iss-sr": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-21400-22000-fss-bss-eess-iss-sr": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-22550-23550-fss-bss-eess-iss-sr": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-24450-24750-fss-bss-eess-iss-sr": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-25250-27500-fss-bss-eess-iss-sr": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-27500-27501-fss": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-31000-31300-sr": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-31800-32300-sr": {0: -120, 5: -120, 15: -112.5, 25: -105, 90: -105},
    "t21-4-32300-33000-iss": {0: -135, 5: -135, 15: -125, 25: -115, 90: -115},
    "t21-4-37000-38000-sr-ngso": dict(zip(STD, (-120, -120, -105, -105), strict=True)),
    "t21-4-37000-38000-sr-gso": {0: -125, 5: -125, 15: -115, 25: -105, 90: -105},
    "t21-4-37500-40000-fss-mss-ngso": dict(zip(STD, (-120, -120, -105, -105), strict=True)),
    "t21-4-37500-40000-fss-mss-gso": {0: -127, 5: -127, 20: -107, 22.5: -106, 25: -105, 90: -105},
    "t21-4-40000-40500-fss-mss": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-40500-42000-fss-bss-ngso": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-40500-42000-fss-bss-gso": {0: -120, 5: -120, 10: -115, 15: -110, 20: -107.5, 25: -105, 90: -105},
    "t21-4-42000-42500-fss-bss-ngso": dict(zip(STD, (-120, -120, -105, -105), strict=True)),
    "t21-4-42000-42500-fss-bss-gso": {0: -127, 5: -127, 20: -107, 25: -105, 90: -105},
    "t21-4-47500-47900-fss-gso": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-48200-48540-fss-gso": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
    "t21-4-49440-50200-fss-gso": dict(zip(STD, (-115, -115, -105, -105), strict=True)),
}
# N = 50 → X = 0 for the 17.7-19.3 GHz non-GSO FSS row.
EXPECTED["t21-4-17700-19300-fss-ngso"] = dict(zip(STD, (-115, -115, -105, -105), strict=True))


def _raw() -> dict:
    return json.loads((settings.data_dir / "ref" / "rr21_pfd_limits.json").read_text(encoding="utf-8"))


def test_shipped_file_loads_and_stays_pending_review():
    lim = load_limits()
    assert lim.review_status == "pending"
    assert len(lim.sha256) == 64
    assert lim.raw["excluded"], "excluded entries must stay listed"
    for r in lim.rows:
        assert r.cite.startswith("RR")
        assert r.encoded or r.reason


def test_every_encoded_row_matches_the_hand_typed_table():
    rows = {r.id: r for r in load_limits().rows}
    encoded = {i for i, r in rows.items() if r.encoded}
    assert encoded == set(EXPECTED), "every encoded row needs a hand-typed cross-check, and vice versa"
    for rid, points in EXPECTED.items():
        for delta, want in points.items():
            n = 50 if rows[rid].x else None
            assert rows[rid].at(delta, n) == pytest.approx(want, abs=1e-3), (rid, delta)


@pytest.mark.parametrize(
    ("n", "at_0", "at_15"),
    [(10, -115, -110), (50, -115, -110), (169, -120, -112.5), (288, -125, -115), (357, -126, -115.5)],
)
def test_ngso_x_function(n, at_0, at_15):
    row = next(r for r in load_limits().rows if r.id == "t21-4-17700-19300-fss-ngso")
    assert row.at(0, n) == pytest.approx(at_0, abs=1e-3)
    assert row.at(15, n) == pytest.approx(at_15, abs=1e-3)
    assert row.at(25, n) == pytest.approx(-105, abs=1e-3)


@pytest.mark.parametrize("n", [None, 1000, 6000])
def test_ngso_x_outside_the_encoded_range_is_not_evaluable(n):
    row = next(r for r in load_limits().rows if r.id == "t21-4-17700-19300-fss-ngso")
    with pytest.raises(NotEvaluable):
        row.at(10, n)


def test_constellation_size_cap_and_unencoded_rows():
    rows = {r.id: r for r in load_limits().rows}
    assert rows["t21-4-37500-40000-fss-mss-ngso"].at(25, 99) == pytest.approx(-105)
    with pytest.raises(NotEvaluable, match="at most 99"):
        rows["t21-4-37500-40000-fss-mss-ngso"].at(25, 100)
    with pytest.raises(NotEvaluable, match="Y"):
        rows["t21-4-3400-4200-fss-ngso"].at(10)


def test_station_classes_are_known():
    assert {"EC", "EK", "ER", "ED", "EI", "EV", "EH", "EW", "ES"} <= pfd_limits.KNOWN_CLASSES
    rows = {r.id: r for r in load_limits().rows}
    assert rows["t21-4-2025-2110-sr-so-eess-metsat"].stn_cls >= {"EK", "ER", "ED", "ET", "EH", "EW", "EM"}


@pytest.mark.parametrize(
    ("patch", "match"),
    [
        (
            {"limit": {"kind": "piecewise", "points": [[0, -150], [25, -140], [5, -150], [90, -140]]}},
            "increasing",
        ),
        ({"limit": {"kind": "piecewise", "points": [[0, -150], [25, -140]]}}, "end at 90"),
        ({"f_lo_mhz": 11700}, "below"),
        ({"orbit": "meo"}, "orbit"),
        ({"services": ["fixed"]}, "services"),
        ({"ref_bw_hz": 0}, "positive"),
        ({"encoded": False}, "reason"),
    ],
)
def test_malformed_rows_raise_with_the_row_id(patch, match):
    raw = _raw()
    bad = copy.deepcopy(raw)
    row = next(r for r in bad["rows"] if r["id"] == "t21-4-10700-11700-fss-gso")
    row.update(patch)
    with pytest.raises(LimitsError, match=rf"t21-4-10700-11700-fss-gso: .*{match}"):
        parse(bad)
