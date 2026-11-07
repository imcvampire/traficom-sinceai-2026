import csv
import math
from pathlib import Path

import pytest

from ific.propagation import p1546

VALIDATION = Path(__file__).parent / "data" / "p1546_validation.csv"
AREA = {
    "Rural": "rural",
    "Suburban": "suburban",
    "Urban": "urban",
    "Dense Urban": "dense_urban",
    "Sea": "sea",
}


def _cases() -> list[dict[str, str]]:
    with VALIDATION.open(encoding="utf-8") as fh:
        return list(csv.DictReader(line for line in fh if not line.startswith("#")))


def _opt(row: dict[str, str], key: str) -> float | None:
    return float(row[key]) if row[key] != "" else None


def _run(row: dict[str, str]) -> p1546.FieldResult:
    path: list[tuple[p1546.PathKind, float]] = []
    if float(row["d_land_km"]) > 0:
        path.append(("land", float(row["d_land_km"])))
    if float(row["d_sea_km"]) > 0:
        path.append(("sea_cold", float(row["d_sea_km"])))
    return p1546.field_strength(
        float(row["f_mhz"]),
        float(row["t_pct"]),
        path,
        h1_m=float(row["h1_m"]),
        h2_m=float(row["h2_m"]),
        erp_dbw=10 * math.log10(float(row["ptx_kw"]) * 1000),
        loc_pct=float(row["q_pct"]),
        rx_env=AREA[row["area"]],
        r2_m=float(row["r2_m"]),
        ha_m=_opt(row, "ha_m"),
        r1_m=_opt(row, "r1_m"),
        tca_deg=_opt(row, "tca_deg"),
        eff1_deg=_opt(row, "eff1_deg"),
        eff2_deg=_opt(row, "tca_deg"),
        htter_m=_opt(row, "htter_m"),
        hrter_m=_opt(row, "hrter_m"),
        wa_m=_opt(row, "wa_m"),
    )


CASES = _cases()


def test_validation_set_is_complete() -> None:
    # Every case in the reference set has terrain inputs, so none is skipped for a missing TCA correction.
    assert len(CASES) == 52
    assert all(row["tca_deg"] != "" for row in CASES)


@pytest.mark.parametrize("row", CASES, ids=[row["case"] for row in CASES])
def test_matches_reference(row: dict[str, str]) -> None:
    result = _run(row)
    assert result.steps["emax_dbuv"] == pytest.approx(float(row["emax_dbuv"]), abs=1e-3)
    assert result.steps["e_step11_dbuv"] == pytest.approx(float(row["e_step11_dbuv"]), abs=1e-3)
    assert result.e_dbuv_m == pytest.approx(float(row["expected_e_dbuv"]), abs=1e-3)


@pytest.mark.parametrize(
    ("figure", "d_km", "h_m", "expected"),
    [(1, 1, 10, 89.9759), (4, 1, 10, 97.9306), (9, 1, 10, 92.6814)],
)
def test_tabulated_values(figure: int, d_km: float, h_m: float, expected: float) -> None:
    assert p1546.table_value(figure, d_km, h_m) == pytest.approx(expected, abs=1e-4)


def test_tabulated_curves_end_at_free_space_limits() -> None:
    # Annex 5 section 2: 50 % land curves never exceed free space, 106.9 - 20 log d.
    for d in (1, 10, 100, 1000):
        assert p1546.table_value(1, d, 1200) <= 106.9 - 20 * math.log10(d) + 1e-3


@pytest.mark.parametrize("t_pct", [1, 10, 50])
@pytest.mark.parametrize("f_mhz", [50, 150, 450, 900, 3500])
@pytest.mark.parametrize("h1_m", [-5, 4, 25, 300])
def test_land_field_does_not_increase_with_distance(t_pct: float, f_mhz: float, h1_m: float) -> None:
    distances = [1, 1.5, 3, 7, 12, 25, 60, 140, 300, 700, 1000]
    values = [p1546.field_strength(f_mhz, t_pct, [("land", d)], h1_m=h1_m).e_dbuv_m for d in distances]
    assert all(b <= a + 1e-9 for a, b in zip(values, values[1:], strict=False))


def test_sea_path_is_stronger_than_land_path() -> None:
    for d in (20, 50, 200):
        land = p1546.field_strength(600, 10, [("land", d)], h1_m=50).e_dbuv_m
        sea = p1546.field_strength(600, 10, [("sea_cold", d)], h1_m=50).e_dbuv_m
        assert sea > land


def test_mixed_path_lies_between_land_and_sea() -> None:
    land = p1546.field_strength(200, 10, [("land", 80)], h1_m=50).e_dbuv_m
    sea = p1546.field_strength(200, 10, [("sea_warm", 80)], h1_m=50).e_dbuv_m
    mixed = p1546.field_strength(200, 10, [("land", 30), ("sea_warm", 50)], h1_m=50).e_dbuv_m
    assert land < mixed < sea


def test_erp_scales_linearly_in_db() -> None:
    a = p1546.field_strength(450, 10, [("land", 40)], h1_m=30, erp_dbw=30).e_dbuv_m
    b = p1546.field_strength(450, 10, [("land", 40)], h1_m=30, erp_dbw=13).e_dbuv_m
    assert a - b == pytest.approx(17)


def test_location_variability_uses_inverse_normal() -> None:
    median = p1546.field_strength(450, 50, [("land", 40)], h1_m=30).e_dbuv_m
    at_90 = p1546.field_strength(450, 50, [("land", 40)], h1_m=30, loc_pct=90).e_dbuv_m
    # Q^-1(0.9) = -1.2816 with rural sigma 12 dB.
    assert at_90 - median == pytest.approx(-1.2816 * 12, abs=0.01)


def test_assumptions_name_missing_terrain_corrections() -> None:
    result = p1546.field_strength(450, 10, [("land", 40)], h1_m=30)
    assert "tca_not_applied" in result.assumptions
    assert "tropo_scatter_not_applied" in result.assumptions
    assert result.inputs["f_mhz"] == 450


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"f_mhz": 29.9}, "f_mhz"),
        ({"f_mhz": 4000.1}, "f_mhz"),
        ({"t_pct": 0.5}, "t_pct"),
        ({"t_pct": 51}, "t_pct"),
        ({"path": [("land", 1001)]}, "d_km"),
        ({"path": [("land", 0.0005)], "ha_m": 10}, "d_km"),
        ({"path": [("land", 0.5)]}, "ha_m"),
        ({"h1_m": 3001}, "h1_m"),
        ({"path": [("lake", 10)]}, "path kind"),
    ],
)
def test_out_of_range_inputs_raise(kwargs: dict, message: str) -> None:
    args = {"f_mhz": 450, "t_pct": 10, "path": [("land", 10)], "h1_m": 30} | kwargs
    with pytest.raises(ValueError, match=message):
        p1546.field_strength(**args)
