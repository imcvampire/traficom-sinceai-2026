"""ITU-R P.1546-6 point-to-area field strength, 30-4000 MHz, 1-1000 km.

Port of the MATLAB reference implementation approved by ITU-R Working Party 3K
(``P1546FieldStrMixed.m`` v16, P1546 package version 6.2, by Ivica Stevanovic, OFCOM CH, based on Jef
Statham's calculator), taken from https://github.com/eeveetza/p1546 at commit
0e4263999ce055100f42257c2aafbac96ac630af. The reference licence allows modified works provided they say
what changed; this notice does so:

- 2026-11-07: translated to Python. The caller supplies the transmitting height ``h1`` already determined
  per Annex 5 section 3 (the reference derives it from ``heff``/``ha``/``hb``), so ``h1Calc`` is not ported
  apart from the 3 m floor on all-sea paths. Inputs outside 30-4000 MHz, 1-50 % time, 0.001-1000 km or
  ``h1`` above 3000 m raise ``ValueError`` instead of warning or clamping. Every intermediate value is
  returned in ``FieldResult.steps``. Annex 7 (climatic regions) and Annex 5 section 4.3a are not
  implemented, as in the reference.

The terrain-dependent corrections (terrain clearance angle, tropospheric scatter, slope with terminal
ground heights, transmitter clutter) are applied only when their inputs are given. Without them the
result carries ``tca_not_applied`` and ``tropo_scatter_not_applied``.

Validated against the reference's validation set in ``tests/data/p1546_validation.csv``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Literal

import numpy as np

VERSION = "ITU-R P.1546-6"
REFERENCE = "eeveetza/p1546@0e42639 (P1546FieldStrMixed.m v16, WP 3K reference)"

PathKind = Literal["land", "sea_cold", "sea_warm"]
RxEnv = Literal["rural", "suburban", "urban", "dense_urban", "sea"]

F_RANGE_MHZ = (30.0, 4000.0)
T_RANGE_PCT = (1.0, 50.0)
D_RANGE_KM = (0.001, 1000.0)
H1_MAX_M = 3000.0

_DEFAULT_R2_M: dict[str, float] = {"rural": 10, "suburban": 10, "urban": 15, "dense_urban": 20, "sea": 10}
_SIGMA_L_DB: dict[str, float] = {"rural": 12, "suburban": 10, "urban": 8, "dense_urban": 8, "sea": 0}
_NOMINAL_T = (1.0, 10.0, 50.0)
_NOMINAL_F = (100.0, 600.0, 2000.0)

_TABLES_PATH = Path(__file__).parent / "data" / "p1546_tables.npz"


@dataclass(frozen=True)
class FieldResult:
    e_dbuv_m: float
    inputs: dict[str, float | str]
    steps: dict[str, float] = field(default_factory=dict)
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Tables:
    distances: tuple[float, ...]
    heights: tuple[float, ...]
    # (figure no.) -> {distance: {height: E}}
    field: dict[int, dict[float, dict[float, float]]]
    # (time, path code, f) -> figure numbers in reference order; path 1 land, 2 sea, 3 cold, 4 warm
    figures: tuple[tuple[float, int, float, int], ...]


@cache
def _tables() -> _Tables:
    with np.load(_TABLES_PATH) as z:
        distances = tuple(float(d) for d in z["distances_km"])
        heights = tuple(float(h) for h in z["heights_m"])
        grid = z["field"]
        figures = tuple((float(t), int(p), float(f), int(n)) for t, p, f, n in z["figures"])
    by_fig = {
        n + 1: {d: {h: float(grid[n, i, j]) for j, h in enumerate(heights)} for i, d in enumerate(distances)}
        for n in range(grid.shape[0])
    }
    return _Tables(distances, heights, by_fig, figures)


def table_value(figure: int, d_km: float, h1_m: float) -> float:
    """Tabulated field strength for 1 kW e.r.p. at a nominal distance and height (figures 1-24)."""
    return _tables().field[figure][float(d_km)][float(h1_m)]


def _search_closest(x: Sequence[float], v: float) -> tuple[float, float]:
    # Reference ``searchclosest``: nominal values around v; the end pair when v is outside x.
    if v > x[-1]:
        return x[-2], x[-1]
    if v < x[0]:
        return x[0], x[1]
    lo, hi = 0, len(x) - 1
    while lo <= hi:
        mid = (lo + hi + 1) // 2
        if x[mid] == v:
            return v, v
        if x[mid] < v:
            lo = mid + 1
        else:
            hi = mid - 1
    return x[hi], x[lo]


def _q_inv(x: float) -> float:
    """Inverse complementary cumulative normal, Annex 5 section 16 (39)."""

    def t(y: float) -> float:
        return math.sqrt(-2 * math.log(y))

    def c(z: float) -> float:
        tz = t(z)
        num = (0.010328 * tz + 0.802853) * tz + 2.515517
        return num / (((0.001308 * tz + 0.189269) * tz + 1.432788) * tz + 1)

    if x <= 0.5:
        return t(x) - c(x)
    return -(t(1 - x) - c(1 - x))


def _j(nu: float) -> float:
    return 6.9 + 20 * math.log10(math.sqrt((nu - 0.1) ** 2 + 1) + nu - 0.1)


def _atand(x: float) -> float:
    return math.degrees(math.atan(x))


def _d06(f: float, h1: float, h2: float) -> float:
    """Path length for 0.6 Fresnel clearance over smooth Earth, section 18 (41)."""
    h1 = max(h1, 0.0)
    df = 0.0000389 * f * h1 * h2
    dh = 4.1 * (math.sqrt(h1) + math.sqrt(h2))
    return max(df * dh / (df + dh), 0.001)


def _emax(t: float, dland: float, dsea: float) -> float:
    """Maximum field strength, section 2 (1)-(3), interpolated for mixed paths (42)."""
    dtotal = dland + dsea
    efs = 106.9 - 20 * math.log10(dtotal)
    ese = 2.38 * (1 - math.exp(-dtotal / 8.94)) * math.log10(50 / t)
    return efs + dsea * ese / dtotal


def _dslope(ha: float, h2: float, d: float, htter: float | None, hrter: float | None) -> float:
    if htter is None or hrter is None:
        return math.sqrt(d * d + 1e-6 * (ha - h2) ** 2)
    return math.sqrt(d * d + 1e-6 * ((ha + htter) - (h2 + hrter)) ** 2)


def _v(fnom: float, h1: float) -> float:
    k = {100.0: 1.35, 600.0: 3.31, 2000.0: 6.0}[fnom]
    return k * _atand(-h1 / 9000)


def _c_h1(fnom: float, h1: float) -> float:
    # (12)-(12c): 6.03 - J(v), with J = 0 for v <= -0.7806
    v = _v(fnom, h1)
    return 6.03 - (_j(v) if v > -0.7806 else 0.0)


def _e_at_height(figure: int, h: float, dinf: float, dsup: float, d: float) -> float:
    """Steps 8.1.4-8.1.5: nominal height, interpolated over distance (13)."""
    einf = table_value(figure, dinf, h)
    if dsup == dinf:
        return einf
    esup = table_value(figure, dsup, h)
    return einf + (esup - einf) * math.log10(d / dinf) / math.log10(dsup / dinf)


def _step81(figure: int, h1: float, dinf: float, dsup: float, d: float, emax: float) -> float:
    hinf, hsup = _search_closest(_tables().heights, h1)
    if hinf == hsup:
        e = _e_at_height(figure, hsup, dinf, dsup, d)
    else:
        einf = _e_at_height(figure, hinf, dinf, dsup, d)
        esup = _e_at_height(figure, hsup, dinf, dsup, d)
        e = einf + (esup - einf) * math.log10(h1 / hinf) / math.log10(hsup / hinf)  # (8)
    return min(e, emax)


def _step82(
    figure: int,
    h1: float,
    dinf: float,
    dsup: float,
    d: float,
    general: str,
    fnom: float,
    emax: float,
    t: float,
) -> float:
    """Step 8.2: h1 below 10 m, sections 4.2 (land, sea) and 4.3 case b (negative h1)."""
    e10 = _e_at_height(figure, 10.0, dinf, dsup, d)
    e20 = _e_at_height(figure, 20.0, dinf, dsup, d)
    ezero = e10 + 0.5 * ((e10 - e20) + _c_h1(fnom, -10.0))  # (9a), (9b)
    if general == "land":
        if h1 >= 0:
            return ezero + 0.1 * h1 * (e10 - ezero)  # (9)
        return ezero + _c_h1(fnom, h1)  # (12)
    if h1 < 1:
        raise ValueError("h1 must be at least 1 m on a sea path")
    dh1 = _d06(fnom, h1, 10)  # (10a)
    d20 = _d06(fnom, 20, 10)  # (10b)
    if d <= dh1:
        return emax  # (11a)
    if d < d20:
        dinf1, dsup1 = _search_closest(_tables().distances, d20)
        e10d20 = _e_at_height(figure, 10.0, dinf1, dsup1, d20)
        e20d20 = _e_at_height(figure, 20.0, dinf1, dsup1, d20)
        ed20 = e10d20 + (e20d20 - e10d20) * math.log10(h1 / 10) / math.log10(2)
        edh1 = _emax(t, 0, dh1)
        return edh1 + (ed20 - edh1) * math.log10(d / dh1) / math.log10(d20 / dh1)  # (11b)
    # The reference divides by the natural log of 2 here; kept so results match the approved code.
    e1 = e10 + (e20 - e10) * math.log10(h1 / 10) / math.log(2)
    e2 = ezero + 0.1 * h1 * (e10 - ezero)
    fs = (d - d20) / d
    return e1 * (1 - fs) + e2 * fs  # (11c)


def _figure(t_nom: float, kind: PathKind, f_nom: float) -> int:
    general = 1 if kind == "land" else None
    for t, p, f, n in _tables().figures:
        if t != t_nom or f != f_nom:
            continue
        if general == 1:
            if p == 1:
                return n
        elif kind == "sea_warm" and t_nom in (1.0, 10.0):
            if p == 4:
                return n
        elif p > 1:
            return n  # first sea figure in reference order: sea (50 %) or cold sea
    raise AssertionError(f"no curve for t={t_nom} {kind} f={f_nom}")


def _step7(
    t_nom: float,
    kind: PathKind,
    h1: float,
    dinf: float,
    dsup: float,
    d: float,
    f: float,
    emax: float,
    t: float,
) -> float:
    """Steps 7-9: frequency interpolation/extrapolation, section 6 (14)."""
    general = "land" if kind == "land" else "sea"
    finf, fsup = _search_closest(_NOMINAL_F, f)
    ef = []
    for fn in (finf,) if finf == fsup else (finf, fsup):
        fig = _figure(t_nom, kind, fn)
        if h1 >= 10:
            ef.append(min(_step81(fig, h1, dinf, dsup, d, emax), emax))
        else:
            ef.append(_step82(fig, h1, dinf, dsup, d, general, fn, emax, t))
    if finf == fsup:
        return ef[0]
    e = ef[0] + (ef[1] - ef[0]) * math.log10(f / finf) / math.log10(fsup / finf)
    return min(e, emax) if f > 2000 else e


def _step6_10(kind: PathKind, h1: float, dinf: float, dsup: float, d: float, f: float, emax: float, t: float):
    """Steps 6-10 for one propagation type: curves at nominal times, then time interpolation (16)."""
    tinf, tsup = _search_closest(_NOMINAL_T, t)
    ep: dict[float, float] = {}
    for tn in (tsup,) if tinf == tsup else (tinf, tsup):
        df = _d06(f, h1, 10)
        d600 = _d06(600, h1, 10)
        if kind != "land" and f < 100 and d < d600:
            if d <= df:
                ep[tn] = _emax(t, 0, d)  # (15a)
            else:
                edf = _emax(t, 0, df)
                d600inf, d600sup = _search_closest(_tables().distances, d600)
                ed600 = _step7(tn, kind, h1, d600inf, d600sup, d600, f, emax, t)
                ep[tn] = edf + (ed600 - edf) * math.log10(d / df) / math.log10(d600 / df)  # (15b)
        else:
            ep[tn] = _step7(tn, kind, h1, dinf, dsup, d, f, emax, t)
    if tinf == tsup:
        return ep[tsup]
    qsup, qinf, qt = _q_inv(tsup / 100), _q_inv(tinf / 100), _q_inv(t / 100)
    return ep[tsup] * (qinf - qt) / (qinf - qsup) + ep[tinf] * (qt - qsup) / (qinf - qsup)


def _mixed(eland: float | None, esea: float | None, dland: float, dsea: float) -> float:
    """Step 11, section 8 (22)-(26), the RRC-06 mixed-path method."""
    if dsea == 0:
        assert eland is not None
        return eland
    if dland == 0:
        assert esea is not None
        return esea
    assert eland is not None and esea is not None
    fsea = dsea / (dland + dsea)
    delta = esea - eland
    v = max(1.0, 1.0 + delta / 40)
    a = (1 - (1 - fsea) ** (2 / 3)) ** v
    return (1 - a) * eland + a * esea


def _rx_height_correction(
    h1: float, d: float, r2: float, h2: float, f: float, env: RxEnv
) -> tuple[float, float]:
    """Step 14, section 9 (27)-(29): returns (correction, R2')."""
    k_h2 = 3.2 + 6.2 * math.log10(f)
    if env != "sea":
        if h2 < 1:
            raise ValueError("h2 must be at least 1 m when the receiver is on land")
        rp = max((1000 * d * r2 - 15 * h1) / (1000 * d - 15), 1.0)
        if env == "rural":
            return k_h2 * math.log10(h2 / 10), 10.0
        if h2 < rp:
            h_dif = rp - h2
            nu = 0.0108 * math.sqrt(f) * math.sqrt(h_dif * _atand(h_dif / 27))
            corr = 6.03 - _j(nu)  # (28a)
        else:
            corr = k_h2 * math.log10(h2 / rp)  # (28b)
        if rp < 10:
            corr -= k_h2 * math.log10(10 / rp)
        return corr, rp
    if h2 < 3:
        raise ValueError("h2 must be at least 3 m when the receiver is adjacent to sea")
    c10 = k_h2 * math.log10(h2 / 10)
    if h2 >= 10:
        return c10, 10.0
    d10 = _d06(f, h1, 10)
    dh2 = _d06(f, h1, h2)
    if d >= d10:
        return c10, 10.0
    if d <= dh2:
        return 0.0, 10.0
    return c10 * math.log10(d / dh2) / math.log10(d10 / dh2), 10.0


def _check(name: str, value: float, lo: float, hi: float) -> None:
    if not (lo <= value <= hi) or math.isnan(value):
        raise ValueError(f"{name}={value} is outside the P.1546 range {lo}-{hi}")


def field_strength(
    f_mhz: float,
    t_pct: float,
    path: Sequence[tuple[PathKind, float]],
    h1_m: float,
    h2_m: float = 10.0,
    erp_dbw: float = 30.0,
    loc_pct: float = 50.0,
    rx_env: RxEnv = "rural",
    *,
    r2_m: float | None = None,
    ha_m: float | None = None,
    r1_m: float | None = None,
    tca_deg: float | None = None,
    eff1_deg: float | None = None,
    eff2_deg: float | None = None,
    htter_m: float | None = None,
    hrter_m: float | None = None,
    wa_m: float | None = None,
) -> FieldResult:
    """Field strength in dB(uV/m) exceeded at ``loc_pct`` locations for ``t_pct`` time.

    ``path`` lists the zones from the transmitter, each ``(kind, length_km)``. ``h1_m`` is the
    transmitting/base height of Annex 5 section 3. ``erp_dbw`` 30 is the 1 kW reference. ``ha_m`` (antenna
    height above ground) enables the slope-path correction and is required below 1 km. ``r1_m`` needs
    ``ha_m`` and enables the transmitter clutter correction. ``wa_m`` selects the terrain-aware
    location-variability formula (34) instead of the default sigma for ``rx_env``.
    """
    _check("f_mhz", f_mhz, *F_RANGE_MHZ)
    _check("t_pct", t_pct, *T_RANGE_PCT)
    _check("loc_pct", loc_pct, 1.0, 99.0)
    if not path:
        raise ValueError("path needs at least one zone")
    for kind, length in path:
        if kind not in ("land", "sea_cold", "sea_warm"):
            raise ValueError(f"unknown path kind {kind!r}")
        if not length > 0:
            raise ValueError(f"path zone lengths must be positive, got {length}")
    if rx_env not in _DEFAULT_R2_M:
        raise ValueError(f"unknown rx_env {rx_env!r}")
    d = sum(length for _, length in path)
    _check("d_km", d, *D_RANGE_KM)
    if h1_m > H1_MAX_M:
        raise ValueError(f"h1_m={h1_m} is above the P.1546 limit of {H1_MAX_M} m")
    if d < 1 and ha_m is None:
        raise ValueError("ha_m is required for paths shorter than 1 km (Annex 5 section 15)")

    assumptions: list[str] = []
    kinds = [kind for kind, _ in path]
    if "sea_warm" in kinds and "sea_cold" in kinds:
        kinds = ["sea_warm" if k == "sea_cold" else k for k in kinds]
        assumptions.append("cold_sea_treated_as_warm")
    dland = sum(length for (k, length) in path if k == "land")
    dsea = d - dland
    h1 = h1_m
    if len(path) == 1 and kinds[0] != "land" and h1 < 3:
        h1 = 3.0
        assumptions.append("h1_raised_to_3m_for_sea")

    r2 = _DEFAULT_R2_M[rx_env] if r2_m is None else r2_m
    steps: dict[str, float] = {"h1_m": h1, "d_km": d, "d_land_km": dland, "d_sea_km": dsea}

    dinf, dsup = _search_closest(_tables().distances, d)
    dc = max(d, 1.0)  # steps 1-16 use 1 km below 1 km
    if d < 1:
        dinf = dsup = 1.0

    emax = _emax(t_pct, dland, dsea)
    if ha_m is not None:
        emax += 20 * math.log10(d / _dslope(ha_m, h2_m, d, htter_m, hrter_m))
    steps["emax_dbuv"] = emax

    eland = esea = None
    for kind in dict.fromkeys(kinds):
        e = _step6_10(kind, h1, dinf, dsup, dc, f_mhz, emax, t_pct)
        if kind == "land":
            eland = e
            steps["e_land_dbuv"] = e
        else:
            esea = e
            steps["e_sea_dbuv"] = e
    e = _mixed(eland, esea, dland, dsea)
    steps["e_step11_dbuv"] = e

    if tca_deg is not None:
        tca = min(max(tca_deg, 0.55), 40.0)
        nup = 0.036 * math.sqrt(f_mhz)
        nu = 0.065 * tca * math.sqrt(f_mhz)
        corr = (_j(nup) if nup > -0.7806 else 0.0) - (_j(nu) if nu > -0.7806 else 0.0)
        e += corr
        steps["tca_correction_db"] = corr
    else:
        assumptions.append("tca_not_applied")

    if eff1_deg is not None and eff2_deg is not None:
        theta_s = max(180 * dc / math.pi / 4 * 3 / 6370 + eff1_deg + eff2_deg, 0.0)  # (35)
        lf = math.log10(f_mhz)
        ets = (
            24.4
            - 20 * math.log10(dc)
            - 10 * theta_s
            - (5 * lf - 2.5 * (lf - 3.3) ** 2)
            + 0.15 * 325
            + 10.1 * (-math.log10(0.02 * t_pct)) ** 0.7
        )  # (36)
        e = max(e, ets)
        steps["theta_s_deg"] = theta_s
        steps["e_tropo_dbuv"] = ets
    else:
        assumptions.append("tropo_scatter_not_applied")

    corr, rp = _rx_height_correction(h1, dc, r2, h2_m, f_mhz, rx_env)
    e += corr
    steps["r2_prime_m"] = rp
    steps["rx_height_correction_db"] = corr

    if ha_m is not None and r1_m is not None:
        hdif1 = ha_m - r1_m
        mag = 0.0108 * math.sqrt(f_mhz) * math.sqrt(hdif1 * _atand(hdif1 / 27))
        nu = mag if r1_m >= ha_m else -mag
        corr = -_j(nu) if nu > -0.7806 else 0.0  # (30)
        e += corr
        steps["tx_clutter_correction_db"] = corr

    if ha_m is not None:
        corr = 20 * math.log10(dc / _dslope(ha_m, h2_m, dc, htter_m, hrter_m))  # (37)
        e += corr
        steps["slope_correction_db"] = corr

    if d < 0.9999999999:
        assert ha_m is not None
        ds = _dslope(ha_m, h2_m, d, htter_m, hrter_m)
        if d <= 0.04:
            e = 106.9 - 20 * math.log10(ds)
        else:
            dinf_s = _dslope(ha_m, h2_m, 0.04, htter_m, hrter_m)
            dsup_s = _dslope(ha_m, h2_m, 1.0, htter_m, hrter_m)
            einf = 106.9 - 20 * math.log10(dinf_s)
            e = einf + (e - einf) * math.log10(ds / dinf_s) / math.log10(dsup_s / dinf_s)  # (38)
        steps["e_short_path_dbuv"] = e

    if loc_pct != 50 and rx_env != "sea":
        # (34) when the receiving area width is known, otherwise the default sigma for the environment
        sigma = _SIGMA_L_DB[rx_env] if wa_m is None else (0.024 * f_mhz / 1000 + 0.52) * wa_m**0.28
        e += _q_inv(loc_pct / 100) * sigma  # (33)
        steps["sigma_l_db"] = sigma

    if e > emax:
        e = emax
        steps["capped_at_emax"] = 1.0
    steps["e_1kw_dbuv"] = e
    steps["basic_loss_db"] = 139.3 - e + 20 * math.log10(f_mhz)  # (40), for 1 kW

    e += erp_dbw - 30.0
    inputs: dict[str, float | str] = {
        "f_mhz": f_mhz,
        "t_pct": t_pct,
        "path": ";".join(f"{k}:{length:g}" for k, length in path),
        "h1_m": h1_m,
        "h2_m": h2_m,
        "erp_dbw": erp_dbw,
        "loc_pct": loc_pct,
        "rx_env": rx_env,
        "r2_m": r2,
    }
    for name, value in (
        ("ha_m", ha_m),
        ("r1_m", r1_m),
        ("tca_deg", tca_deg),
        ("eff1_deg", eff1_deg),
        ("eff2_deg", eff2_deg),
        ("htter_m", htter_m),
        ("hrter_m", hrter_m),
        ("wa_m", wa_m),
    ):
        if value is not None:
            inputs[name] = value
    return FieldResult(e_dbuv_m=e, inputs=inputs, steps=steps, assumptions=tuple(assumptions))
