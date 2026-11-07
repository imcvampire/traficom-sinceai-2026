"""Hazard evaluation: Tier 0 inventory and visibility, Tier 1 deterministic worst case, Tier 2 Monte Carlo.

Consequence c for one receiver and one time sample, in dB (I/N for active classes, spfd − RA.769 threshold for
passive ones):

c = 10·log10( Σ_s 10^((max(A − SP(d_s), B) + G_r(θ_s)) / 10) )

where the sum runs over satellites above the class minimum elevation, SP(d) = 10·log10(4π·d²) is the spreading
loss, A collects the calculated per-satellite terms of the strongest assignment group (power density,
satellite gain, overlap bandwidth, effective area, unwanted-emission attenuation, minus noise or threshold),
and B the same for groups whose pfd is notified in `c_pfd` (no spreading term). One beam per satellite is
assumed to point at the receiver (the maximum over groups, not their sum).
"""

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ific.riia import MODEL_VERSION, antenna, curves, emission
from ific.riia.geometry import (
    R_EARTH_KM,
    R_GSO_KM,
    ecef,
    enu_basis,
    horizon_central_angle_deg,
    pointing_vector,
    slant_range_km,
    unit,
)
from ific.riia.orbits import Constellation, gso_ecef
from ific.riia.receivers import ReceiverClass

C_LIGHT = 299_792_458.0
SAMPLES_MIN = 10_000
SAMPLES_CAP = 1_000_000
TIME_SAMPLES_MIN = 20
NGSO_WINDOW_S = 10 * 86_400
NGSO_FALLBACK_ALT_KM = 300.0
ES_SCREEN_KM = 1_000.0
ADJ_EXTENT_BN = 2.5
OUTCOME_RANK = {"exceeds": 0, "not_assessed": 1, "meets": 2, "screened_out": 3, "not_applicable": 4}
QUANTIFIED_MODES = ("cochannel", "adjacent")


@dataclass(frozen=True)
class Overrides:
    """Perturbations of `assumption` inputs, used by the sensitivity report. Defaults reproduce riia-1."""

    sat_gain_offset_db: float = 0.0
    activity_db: float = 0.0
    carrier: str = "worst"
    adj_extent_bn: float = ADJ_EXTENT_BN
    patterns: tuple[tuple[str, str], ...] = ()
    distributions: tuple[tuple[str, str, float, float], ...] = ()

    def pattern(self, cls: ReceiverClass) -> str:
        return dict(self.patterns).get(cls.id, cls.pattern)

    def distribution(self, cls: ReceiverClass, param: str) -> tuple[float, float]:
        for c, p, lo, hi in self.distributions:
            if c == cls.id and p == param:
                return lo, hi
        d = cls.distributions[param]
        return d.low, d.high


@dataclass(frozen=True)
class Grp:
    grp_id: int
    f_lo_hz: float
    f_hi_hz: float
    d_dbw_hz: float
    bn_hz: float
    p_dbw: float
    gain_dbi: float
    gain_assumed: bool
    bore: tuple[float, float] | None = None
    psi0_deg: float | None = None
    cpfd_dens: float | None = None


@dataclass
class Geometry:
    kind: str
    lon_deg: float | None = None
    tol_east: float = 0.0
    tol_west: float = 0.0
    constellation: Constellation | None = None
    missing_reason: str | None = None
    fallback_sats: int = 1
    min_alt_km: float | None = None
    heo: bool = False
    inputs: list[dict[str, Any]] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


@dataclass
class HazardReceivers:
    """Receivers of one hazard as arrays: `band` and `site` index into `bands` and the site arrays."""

    bands: list[tuple[float, float]]
    band: np.ndarray
    site: np.ndarray
    bw_hz: np.ndarray
    nf_db: np.ndarray
    acs_db: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    height_m: np.ndarray
    az: np.ndarray
    el: np.ndarray
    gain_dbi: np.ndarray
    pairs: dict[int, list[tuple[Grp, float]]]
    citations: list[str]
    assumptions: list[str]


def rng_for(ific_no: int, ntc_id: int, hazard_id: str) -> np.random.Generator:
    digest = hashlib.sha256(f"{MODEL_VERSION}|{ific_no}|{ntc_id}|{hazard_id}".encode()).digest()
    return np.random.Generator(np.random.PCG64(int.from_bytes(digest[:16], "big")))


def sample_plan(p_min_pct: float, n_sites: int) -> tuple[int, int]:
    """(sites used, time samples per site): N = max(10⁴, ⌈100/p⌉) samples, at least ⌈100/p⌉ per site, ≤ 10⁶
    total.
    """
    n = min(max(SAMPLES_MIN, math.ceil(100 / p_min_pct)), SAMPLES_CAP)
    t = max(math.ceil(n / max(n_sites, 1)), math.ceil(100 / p_min_pct), TIME_SAMPLES_MIN)
    sites = min(n_sites, max(1, SAMPLES_CAP // t))
    return sites, t


def spreading_db(d_km: np.ndarray | float) -> np.ndarray:
    return 10 * np.log10(4 * np.pi * (np.asarray(d_km) * 1e3) ** 2)


def _db_sum(x: np.ndarray, axis: int = -1) -> np.ndarray:
    with np.errstate(divide="ignore"):
        return 10 * np.log10(np.sum(10 ** (x / 10), axis=axis))


def _db_add(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore"):
        return 10 * np.log10(10 ** (np.asarray(a) / 10) + 10 ** (np.asarray(b) / 10))


def pair_terms(
    cls: ReceiverClass,
    mode: str,
    band: tuple[float, float],
    grp: Grp,
    gap_hz: float,
    bw_hz: float,
    nf_db: float,
    acs_db: float,
    kt0: float,
    ov: Overrides,
) -> float:
    """Per-satellite constant of one (receiver band, group) pair, excluding satellite gain and spreading."""
    lo, hi = band
    if mode == "cochannel":
        overlap = min(grp.f_hi_hz, hi) - max(grp.f_lo_hz, lo)
        b_ov = max(min(grp.bn_hz, bw_hz, overlap), 1.0)
        f_c = (max(grp.f_lo_hz, lo) + min(grp.f_hi_hz, hi)) / 2
        atten = 0.0
        if ov.carrier == "uniform":
            atten -= 10 * math.log10(max(min(1.0, overlap / max(grp.f_hi_hz - grp.f_lo_hz, grp.bn_hz)), 1e-6))
    else:
        b_ov = max(min(grp.bn_hz, bw_hz), 1.0)
        f_c = lo if grp.f_hi_hz <= lo else hi
        mask = float(emission.unwanted_attenuation_db(gap_hz, grp.bn_hz, grp.p_dbw))
        if cls.metric == "I/N":
            unwanted = -mask + 10 * math.log10(b_ov)
            leaked = 10 * math.log10(grp.bn_hz) - acs_db
            atten = -float(_db_add(unwanted, leaked)) + 10 * math.log10(b_ov)
        else:
            atten = mask
    density = (grp.cpfd_dens if grp.cpfd_dens is not None else grp.d_dbw_hz) + ov.activity_db
    if cls.metric == "I/N":
        aperture = 10 * math.log10((C_LIGHT / f_c) ** 2 / (4 * math.pi))
        noise = kt0 + 10 * math.log10(bw_hz) + nf_db
        return density + 10 * math.log10(b_ov) + aperture - atten - noise
    return density - atten - cls.spfd_threshold(f_c)


def _satellite_gain(grp: Grp, site_ecef: np.ndarray, geom: Geometry, ov: Overrides) -> np.ndarray:
    if grp.bore is None or grp.psi0_deg is None or geom.kind != "gso" or geom.lon_deg is None:
        return np.full(site_ecef.shape[0], grp.gain_dbi + ov.sat_gain_offset_db)
    sat = gso_ecef(geom.lon_deg)
    bore = ecef(grp.bore[1], grp.bore[0], R_EARTH_KM)
    to_bore, to_site = bore - sat, site_ecef - sat
    c = to_site @ to_bore / (np.linalg.norm(to_site, axis=-1) * np.linalg.norm(to_bore))
    psi = np.degrees(np.arccos(np.clip(c, -1, 1)))
    return antenna.s672(psi, grp.gain_dbi, grp.psi0_deg)


def receiver_constants(
    cls: ReceiverClass, mode: str, hr: HazardReceivers, geom: Geometry, kt0: float, ov: Overrides
) -> tuple[np.ndarray, np.ndarray]:
    """(A, B) per receiver: strongest calculated and notified-pfd terms, dB."""
    site_ecef = ecef(hr.lat, hr.lon, R_EARTH_KM + np.nan_to_num(hr.height_m) / 1e3)
    a = np.full(hr.band.size, -np.inf)
    b = np.full(hr.band.size, -np.inf)
    combos: dict[tuple[int, float, float, float], np.ndarray] = {}
    for i, key in enumerate(
        zip(hr.band.tolist(), hr.bw_hz.tolist(), hr.nf_db.tolist(), hr.acs_db.tolist(), strict=True)
    ):
        combos.setdefault(key, []).append(i)
    for (bi, bw, nf, acs), idx in combos.items():
        idx = np.asarray(idx)
        for grp, gap in hr.pairs[bi]:
            k = pair_terms(cls, mode, hr.bands[bi], grp, gap, bw, nf, acs, kt0, ov)
            if grp.cpfd_dens is not None:
                b[idx] = np.maximum(b[idx], k)
            else:
                g = _satellite_gain(grp, site_ecef, geom, ov)[hr.site[idx]]
                a[idx] = np.maximum(a[idx], k + g)
    return a, b


def _gso_central_angle_deg(geom: Geometry, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Earth central angle from each site to the nearest GSO position within the station-keeping tolerance."""
    lo, hi = geom.lon_deg - geom.tol_west, geom.lon_deg + geom.tol_east
    nearest = np.where(
        (lon >= lo) & (lon <= hi),
        0.0,
        np.minimum(np.abs(((lon - lo) + 180) % 360 - 180), np.abs(((lon - hi) + 180) % 360 - 180)),
    )
    return np.degrees(np.arccos(np.clip(np.cos(np.radians(lat)) * np.cos(np.radians(nearest)), -1, 1)))


def visible_anywhere(geom: Geometry, lat: np.ndarray, lon: np.ndarray, min_elev_deg: float) -> bool:
    """Tier 0: can the space station ever be above `min_elev_deg` at any site of the population?"""
    if geom.kind == "gso":
        gamma = _gso_central_angle_deg(geom, lat, lon)
        return bool((gamma <= horizon_central_angle_deg(R_GSO_KM, min_elev_deg)).any())
    if geom.kind == "ngso" and geom.constellation is not None:
        return geom.constellation.max_reach_lat_deg(min_elev_deg) >= float(np.abs(lat).min())
    return True


def tier1_worst(
    a: np.ndarray, b: np.ndarray, gmax: float, geom: Geometry, hr: HazardReceivers, max_height_m: float
) -> tuple[float, dict[str, Any]]:
    """Deterministic worst case: minimum slant range, receiver main beam, peak gains, most satellites.

    `max_height_m` is the highest receiver height Tier 2 can use (given or the top of the class range).
    """
    r_site = R_EARTH_KM + max_height_m / 1e3
    if geom.kind == "gso":
        gamma = _gso_central_angle_deg(geom, hr.lat, hr.lon)
        d_min, n_vis = float(slant_range_km(gamma, r_site, R_GSO_KM).min()), 1
    elif geom.constellation is not None:
        d_min = geom.constellation.min_range_km(hr.lat, r_site)
        n_vis = geom.constellation.max_visible(0.0)
    else:
        d_min, n_vis = NGSO_FALLBACK_ALT_KM, max(geom.fallback_sats, 1)
    worst = float(np.max(_db_add(a - spreading_db(d_min), b))) + gmax + 10 * math.log10(n_vis)
    return worst, {"d_min_km": d_min, "n_visible_max": n_vis}


@dataclass
class Tier2:
    x_at_p: dict[float, np.ndarray]
    max_db: float
    n_receivers: int
    n_samples: int
    sites_used: int
    time_samples: int


def _draw(rng: np.random.Generator, n: int, given: np.ndarray, lo: float, hi: float) -> np.ndarray:
    draw = rng.uniform(lo, hi, n)
    return np.where(np.isnan(given), draw, given)


def _site_sums(
    geom: Geometry,
    site_ecef: np.ndarray,
    up: np.ndarray,
    pv: np.ndarray,
    gain_fn: Callable[[np.ndarray], np.ndarray],
    min_elev_deg: float,
    t_samples: int,
    rng: np.random.Generator,
    need_m: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Per site and time sample: L = Σ 10^((G_r − SP)/10) and M = Σ 10^(G_r/10) over visible satellites."""
    ns = site_ecef.shape[0]
    sin_min = math.sin(math.radians(min_elev_deg))
    L = np.full((ns, t_samples), -np.inf)
    M = np.full((ns, t_samples), -np.inf)

    def accumulate(sat: np.ndarray, cols: slice | np.ndarray) -> None:
        d = sat[None, ...] - site_ecef.reshape((ns,) + (1,) * (sat.ndim - 1) + (3,))
        rng_km = np.linalg.norm(d, axis=-1)
        vis = (
            np.einsum("s...k,s...k->s...", d, up.reshape(up.shape[:1] + (1,) * (sat.ndim - 1) + (3,)))
            >= sin_min * rng_km
        )
        cos_t = (
            np.einsum("s...k,s...k->s...", d, pv.reshape(pv.shape[:1] + (1,) * (sat.ndim - 1) + (3,)))
            / rng_km
        )
        g = gain_fn(np.degrees(np.arccos(np.clip(cos_t, -1, 1))))
        with np.errstate(divide="ignore"):
            term = np.where(vis, g - spreading_db(rng_km), -np.inf)
            L[:, cols] = _db_sum(term) if sat.ndim == 3 else term
            if need_m:
                gm = np.where(vis, g, -np.inf)
                M[:, cols] = _db_sum(gm) if sat.ndim == 3 else gm

    if geom.kind == "gso":
        lon = geom.lon_deg + rng.uniform(-geom.tol_west, geom.tol_east, t_samples)
        accumulate(gso_ecef(lon), slice(None))
        return L, M
    const = geom.constellation
    t = rng.uniform(0.0, NGSO_WINDOW_S, t_samples)
    centre = unit(*_centroid(site_ecef))
    lam = float(horizon_central_angle_deg(const.radius_km.max(), min(min_elev_deg, 0.0)))
    spread = float(
        np.degrees(
            np.arccos(
                np.clip((site_ecef / np.linalg.norm(site_ecef, axis=-1, keepdims=True)) @ centre, -1, 1)
            )
        ).max()
    )
    cos_cut = math.cos(math.radians(min(lam + spread + 1.0, 180.0)))
    batch = max(1, 2_000_000 // max(ns * max(const.size // 10, 1), 1))
    for start in range(0, t_samples, batch):
        tb = t[start : start + batch]
        pos = const.positions(tb)
        cand = np.flatnonzero(
            ((pos / np.linalg.norm(pos, axis=-1, keepdims=True)) @ centre >= cos_cut).any(axis=0)
        )
        if cand.size == 0:
            continue
        sat = pos[:, cand, :]
        accumulate(sat, slice(start, start + tb.size))
    return L, M


def _centroid(site_ecef: np.ndarray) -> tuple[float, float]:
    c = site_ecef.mean(axis=0)
    return math.degrees(math.atan2(c[2], math.hypot(c[0], c[1]))), math.degrees(math.atan2(c[1], c[0]))


def tier2(
    cls: ReceiverClass,
    a: np.ndarray,
    b: np.ndarray,
    hr: HazardReceivers,
    geom: Geometry,
    rng: np.random.Generator,
    ov: Overrides,
) -> Tier2:
    pattern = ov.pattern(cls)
    n_sites = hr.lat.size
    sites_used, t_samples = sample_plan(cls.p_min, n_sites)
    keep_sites = (
        np.unique(np.linspace(0, n_sites - 1, sites_used).round().astype(int))
        if sites_used < n_sites
        else np.arange(n_sites)
    )
    lat, lon = hr.lat[keep_sites], hr.lon[keep_sites]
    h = (
        _draw(rng, n_sites, hr.height_m, *ov.distribution(cls, "height_m"))[keep_sites]
        if "height_m" in cls.distributions
        else np.nan_to_num(hr.height_m)[keep_sites]
    )
    az = (
        _draw(rng, n_sites, hr.az, *ov.distribution(cls, "azimuth_deg"))[keep_sites]
        if "azimuth_deg" in cls.distributions
        else np.zeros(keep_sites.size)
    )
    el = (
        _draw(rng, n_sites, hr.el, *ov.distribution(cls, "pointing_elev_deg"))[keep_sites]
        if "pointing_elev_deg" in cls.distributions
        else np.full(keep_sites.size, 90.0)
    )
    gmax = hr.gain_dbi[keep_sites]
    east, north, up = enu_basis(lat, lon)
    site_ecef = ecef(lat, lon, R_EARTH_KM + h / 1e3)
    local = pointing_vector(az, el)
    pv = local[:, :1] * east + local[:, 1:2] * north + local[:, 2:3] * up

    rx_mask = np.isin(hr.site, keep_sites)
    site_pos = np.searchsorted(keep_sites, hr.site[rx_mask])
    a_r, b_r, band_r = a[rx_mask], b[rx_mask], hr.band[rx_mask]
    need_m = bool(np.isfinite(b_r).any())

    variants: dict[tuple[float, float], list[int]] = {}
    for bi in np.unique(band_r).tolist():
        f_hz = sum(hr.bands[bi]) / 2
        variants.setdefault((f_hz if pattern == "BT.419" else 0.0, 0.0), []).append(bi)
    gains = sorted(set(gmax.tolist()))

    x_at_p: dict[float, np.ndarray] = {c.time_pct: np.full(a_r.size, -np.inf) for c in cls.criteria}
    max_db = -np.inf
    for (f_hz, _), band_ids in sorted(variants.items()):
        L = np.full((keep_sites.size, t_samples), -np.inf)
        M = np.full((keep_sites.size, t_samples), -np.inf)
        for g in gains:
            rows = np.flatnonzero(gmax == g)

            # A directional receiver with more gain than its omnidirectional class uses the F.1245 envelope.
            pat = "F.1245" if pattern == "omni" and g > cls.gain_dbi else pattern

            def gain_fn(theta: np.ndarray, f_hz: float = f_hz, g: float = g, pat: str = pat) -> np.ndarray:
                return antenna.receiver_gain(pat, theta, g, f_hz or 1e9)

            L[rows], M[rows] = _site_sums(
                geom, site_ecef[rows], up[rows], pv[rows], gain_fn, cls.min_elev_deg, t_samples, rng, need_m
            )
        sel = np.flatnonzero(np.isin(band_r, band_ids))
        c = _db_add(a_r[sel, None] + L[site_pos[sel]], b_r[sel, None] + M[site_pos[sel]])
        max_db = max(max_db, float(c.max()) if c.size else -np.inf)
        for p in x_at_p:
            x_at_p[p][sel] = curves.exceeded_for(c, p)
    return Tier2(
        x_at_p, max_db, int(a_r.size), int(keep_sites.size * t_samples), int(keep_sites.size), t_samples
    )


def _finite(x: float | None) -> float | None:
    return float(x) if x is not None and np.isfinite(x) else None


def summarise_tier2(cls: ReceiverClass, t2: Tier2) -> dict[str, Any]:
    violating = np.zeros(t2.n_receivers, dtype=bool)
    exceedance, risk = [], []
    for c in cls.criteria:
        x = t2.x_at_p[c.time_pct]
        violating |= curves.violates(x, c.level_db)
        diff = x - c.level_db
        exceedance.append(
            {
                "level_db": c.level_db,
                "time_pct": c.time_pct,
                "median_db": _finite(np.median(diff)) if diff.size else None,
                "p95_db": _finite(np.percentile(diff, 95, method="higher")) if diff.size else None,
            }
        )
    for p in sorted({c.time_pct for c in cls.criteria}):
        risk.append({"time_pct": p, "likelihood": curves.risk_curve(t2.x_at_p[p]).tolist()})
    share = float(violating.mean()) if violating.size else 0.0
    return {
        "outcome": "exceeds" if violating.any() else "meets",
        "share_violating": share,
        "exceedance_db": exceedance,
        "risk_curves": risk,
        "tier2_max_db": _finite(t2.max_db),
        "n_receivers": t2.n_receivers,
        "n_samples": t2.n_samples,
    }
