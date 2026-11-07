"""Assess every notice of one Space IFIC issue against a Finnish receiver population (model riia-1)."""

import logging
import math
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import duckdb
import numpy as np

from ific.riia import MODEL_VERSION, antenna, curves, emission, hazards, pfd, regulatory
from ific.riia.geometry import haversine_km
from ific.riia.hazards import Geometry, Grp, HazardReceivers, Overrides
from ific.riia.orbits import Constellation
from ific.riia.pfd_limits import HEO_APOGEE_KM, HEO_INCL_DEG, load_limits
from ific.riia.receivers import Receiver, ReceiverClass, ReceiverPopulation, finland_grid, load_classes
from ific.special_interest import parse_designator_bandwidth_hz

log = logging.getLogger("ific.riia")

Progress = Callable[[int, int], None]

INVENTORY_MODES = ("es_terrestrial", "blocking_im", "aggregate_networks")
MODE_LABEL = {
    "cochannel": "Co-channel, space→Earth",
    "adjacent": "Adjacent-band unwanted emissions, space→Earth",
    "es_terrestrial": "Earth-station emissions over a terrestrial path",
    "blocking_im": "Receiver blocking and intermodulation",
    "aggregate_networks": "Aggregate across different networks",
}

ASSUMPTIONS = {
    "generic_population": "Each protected M4 service is assumed deployed all over Finland (generic grid)",
    "peak_gain": "Steerable non-GSO beams and beams without boresight use peak gain toward every receiver",
    "full_duty_cycle": "Carriers transmit at pep_max all the time (no duty cycle)",
    "single_beam": "One beam per satellite points at the receiver (maximum over groups, not their sum)",
    "carrier_in_channel": "Co-channel: the carrier is placed inside the receiver channel (worst placement)",
    "adjacent_extent": "Adjacent band: groups within 2.5 × B_n of the receiver band",
    "circular_orbit": "Circular orbits; elliptical orbits use the apogee altitude",
    "orbit_config": "With several orbit configurations, the one with the most satellites is assessed",
    "plane_phasing": "Satellites evenly spaced in each plane, no inter-plane phasing; time uniform, 10 days",
    "gso_station_keeping": "GSO position uniform within the E/W tolerance; S.672 gain at nominal",
    "sample_size": "N = max(10⁴, ⌈100/p⌉) samples per hazard, at least ⌈100/p⌉ per site, at most 10⁶",
    "grid": "Generic grid 0.25° × 0.5° inside the Natural Earth 1:50m Finland boundary",
    "stations_source": "Receivers are the frequencies-of-interest stations; gaps filled from the class",
    "station_gain_dbi": "Station antenna gain from the dataset is taken as dBi",
    "station_gain_capped": "Station gain above a 4 m, 60 % aperture is capped at that aperture's gain",
    "station_directional_pattern": "Directional stations above the class gain use the F.1245 envelope",
    "station_azimuth_drawn": "Non-directional stations or stations without azimuth draw the class azimuth",
    "class_values": "Receiver values are ITU-R reference values (receiver_classes.json, pending review)",
}


@dataclass
class _Notice:
    ntc_id: int
    prov: str
    adm: str
    ntc_type: str
    act_code: str | None
    d_wic: Any
    sat_name: str | None
    downlinks: list[Grp] = field(default_factory=list)
    has_uplink: bool = False
    has_mask: bool = False
    findings: list[regulatory.Finding] = field(default_factory=list)
    es_points: list[tuple[float, float]] = field(default_factory=list)
    pfd_groups: list[pfd.PfdGroup] = field(default_factory=list)
    pfd_notified: list[pfd.NotifiedPfd] = field(default_factory=list)


def _bn_hz(designator: str | None, bdwdth_khz: float | None) -> float | None:
    if designator and len(designator) >= 4:
        try:
            v = parse_designator_bandwidth_hz(designator[:4])
            if v:
                return float(v)
        except ValueError:
            pass
    return float(bdwdth_khz) * 1e3 if bdwdth_khz else None


def _load_notices(con: duckdb.DuckDBPyConnection, ific_no: int) -> dict[int, _Notice]:
    notices: dict[int, _Notice] = {}
    for ntc_id, prov, adm, ntc_type, act_code, d_wic, name in con.execute(
        """
        SELECT n.ntc_id, n.prov, n.adm, n.ntc_type, n.act_code, n.d_wic,
               coalesce(g.sat_name, ng.sat_name, c.sat_name, c.stn_name)
        FROM space.notice n
        LEFT JOIN space.geo g USING (ific_no, ntc_id)
        LEFT JOIN space.non_geo ng USING (ific_no, ntc_id)
        LEFT JOIN (SELECT ntc_id, min(sat_name) sat_name, min(stn_name) stn_name
                   FROM space.com_el WHERE ific_no = $1 GROUP BY 1) c USING (ntc_id)
        WHERE n.ific_no = $1 ORDER BY n.ntc_id
        """,
        [ific_no],
    ).fetchall():
        notices[ntc_id] = _Notice(ntc_id, prov, adm, ntc_type, act_code, d_wic, name)

    cpfd: dict[int, list[tuple[float, float, float, float | None]]] = defaultdict(list)
    for ntc_id, lo, hi, val, bw, ra in con.execute(
        "SELECT ntc_id, freq_min, freq_max, pfd, bdwdth, ra_stn_type FROM space.c_pfd WHERE ific_no = ? AND "
        "pfd IS NOT NULL ORDER BY ntc_id, seq_no",
        [ific_no],
    ).fetchall():
        cpfd[ntc_id].append((lo * 1e6, hi * 1e6, val, bw))
        if ntc_id in notices and not ra:
            notices[ntc_id].pfd_notified.append(
                pfd.NotifiedPfd(lo * 1e6, hi * 1e6, val, bw * 1e3 if bw else None)
            )
    for (ntc_id,) in con.execute(
        "SELECT DISTINCT ntc_id FROM space.mask_info WHERE ific_no = ?", [ific_no]
    ).fetchall():
        if ntc_id in notices:
            notices[ntc_id].has_mask = True
    pfd_masks: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for ntc_id, lo, hi in con.execute(
        "SELECT ntc_id, freq_min, freq_max FROM space.mask_info WHERE ific_no = ? AND f_mask = 'P'", [ific_no]
    ).fetchall():
        pfd_masks[ntc_id].append((lo * 1e9, hi * 1e9))
    stn_cls: dict[int, list[str]] = defaultdict(list)
    if con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'space' AND table_name = 'srv_cls'"
    ).fetchone():
        for grp_id, cls in con.execute(
            "SELECT DISTINCT grp_id, stn_cls FROM space.srv_cls WHERE ific_no = ? AND stn_cls IS NOT NULL "
            "ORDER BY 1, 2",
            [ific_no],
        ).fetchall():
            stn_cls[grp_id].append(cls)

    rows = con.execute(
        """
        SELECT g.ntc_id, g.grp_id, g.emi_rcp, g.freq_min, g.freq_max, g.bdwdth, e.design_emi, e.pep_max,
               e.pwr_ds_max, b.gain, b.bore_long, b.bore_lat, b.maj_axis, b.min_axis
        FROM space.grp g
        JOIN space.notice n ON n.ific_no = g.ific_no AND n.ntc_id = g.ntc_id
        LEFT JOIN space.emiss e ON e.ific_no = g.ific_no AND e.grp_id = g.grp_id
        LEFT JOIN space.s_beam b ON b.ific_no = g.ific_no AND b.ntc_id = g.ntc_id
             AND b.emi_rcp = g.emi_rcp AND b.beam_name = g.beam_name
        WHERE g.ific_no = ? ORDER BY g.grp_id, e.seq_no
        """,
        [ific_no],
    ).fetchall()
    best: dict[int, tuple] = {}
    pfd_meta: dict[int, tuple] = {}
    pfd_emissions: dict[int, list[pfd.Emission]] = defaultdict(list)
    for ntc_id, grp_id, emi_rcp, fmin, fmax, bdw, des, pep, pds, gain, blon, blat, maj, mn in rows:
        n = notices.get(ntc_id)
        if n is None:
            continue
        if emi_rcp == "R":
            n.has_uplink = True
            continue
        if n.ntc_type not in ("G", "N") or fmin is None:
            continue
        bn = _bn_hz(des, bdw) or max((fmax - fmin) * 1e6, 1e3)
        pfd_meta.setdefault(grp_id, (ntc_id, fmin, fmax, gain, blon, blat, maj, mn))
        if pep is not None or pds is not None:
            pfd_emissions[grp_id].append(pfd.Emission.of(pep, pds, bn, fmin * 1e6))
        if pep is not None:
            dens, p = pep - 10 * math.log10(bn), pep
        elif pds is not None:
            dens, p = pds, pds + 10 * math.log10(bn)
        else:
            continue
        cur = best.get(grp_id)
        if cur is None or dens > cur[2]:
            best[grp_id] = (ntc_id, grp_id, dens, bn, p, fmin, fmax, bdw, gain, blon, blat, maj, mn)
    notice_gain: dict[int, float] = {}
    for v in best.values():
        if v[8] is not None:
            notice_gain[v[0]] = max(notice_gain.get(v[0], -math.inf), float(v[8]))
    for grp_id, (ntc_id, fmin, fmax, own_gain, blon, blat, maj, mn) in pfd_meta.items():
        gain = own_gain if own_gain is not None else notice_gain.get(ntc_id)
        lo, hi = fmin * 1e6, fmax * 1e6
        notices[ntc_id].pfd_groups.append(
            pfd.PfdGroup(
                grp_id,
                lo,
                hi,
                tuple(pfd_emissions.get(grp_id, ())),
                float(gain) if gain is not None else None,
                (blon, blat) if blon is not None and blat is not None else None,
                ((maj + (mn or maj)) / 4) if maj else None,
                tuple(stn_cls.get(grp_id, ())),
                any(m_lo < hi and lo < m_hi for m_lo, m_hi in pfd_masks.get(ntc_id, ())),
                own_gain is None and gain is not None,
            )
        )
    for ntc_id, grp_id, dens, bn, p, fmin, fmax, _bdw, gain, blon, blat, maj, mn in best.values():
        if gain is None:
            gain = notice_gain.get(ntc_id)
        if gain is None:
            continue
        lo, hi = fmin * 1e6, fmax * 1e6
        if hi - lo < bn:
            c = (lo + hi) / 2
            lo, hi = c - bn / 2, c + bn / 2
        notified = max(
            (
                pfd - 10 * math.log10(bw * 1e3 if bw else bn)
                for clo, chi, pfd, bw in cpfd.get(ntc_id, [])
                if clo < hi and chi > lo
            ),
            default=None,
        )
        bore = (blon, blat) if blon is not None and blat is not None else None
        psi0 = ((maj + (mn or maj)) / 4) if maj else None
        notices[ntc_id].downlinks.append(
            Grp(
                grp_id,
                lo,
                hi,
                dens,
                bn,
                p,
                float(gain) if gain is not None else 0.0,
                gain is None or bore is None or psi0 is None,
                bore,
                psi0,
                notified,
            )
        )

    for ntc_id, grp_id, coord_prov, agree_st in con.execute(
        """
        SELECT g.ntc_id, p.grp_id, p.coord_prov, p.agree_st FROM space.provn p
        JOIN space.grp g ON g.ific_no = p.ific_no AND g.grp_id = p.grp_id
        WHERE p.ific_no = ? ORDER BY p.grp_id, p.seq_no
        """,
        [ific_no],
    ).fetchall():
        if ntc_id in notices:
            notices[ntc_id].findings.append(
                regulatory.Finding("provn", coord_prov, agree_st, grp_id, None, None)
            )
    for ntc_id, coord_prov, agree_st, aff, sat in con.execute(
        "SELECT ntc_id, coord_prov, agree_st, aff_ntc_id, sat_name FROM space.tr_aff_ntw WHERE ific_no = ? "
        "ORDER BY ntc_id, aff_ntc_id, coord_prov",
        [ific_no],
    ).fetchall():
        if ntc_id in notices:
            notices[ntc_id].findings.append(
                regulatory.Finding("tr_aff_ntw", coord_prov, agree_st, None, aff, sat)
            )
    for ntc_id, lat, lon in con.execute(
        "SELECT ntc_id, lat_dec, long_dec FROM space.e_stn WHERE ific_no = ? AND lat_dec IS NOT NULL",
        [ific_no],
    ).fetchall():
        if ntc_id in notices:
            notices[ntc_id].es_points.append((lat, lon))
    return notices


def _load_geometry(con: duckdb.DuckDBPyConnection, ific_no: int) -> dict[int, Geometry]:
    out: dict[int, Geometry] = {}
    for ntc_id, lon, te, tw in con.execute(
        "SELECT ntc_id, long_nom, tol_east, tol_west FROM space.geo WHERE ific_no = ?", [ific_no]
    ).fetchall():
        if lon is None:
            continue
        out[ntc_id] = Geometry(
            "gso",
            lon_deg=float(lon),
            tol_east=float(te or 0.0),
            tol_west=float(tw or 0.0),
            inputs=[
                _input("GSO nominal longitude", lon, "°E", "data", "space.geo.long_nom"),
                _input(
                    "Station-keeping tolerance E/W",
                    f"{te or 0}/{tw or 0}",
                    "°",
                    "data",
                    "space.geo.tol_east, tol_west",
                ),
            ],
            assumptions=["gso_station_keeping"],
        )
    planes: dict[int, dict[str, list[tuple]]] = defaultdict(lambda: defaultdict(list))
    for ntc_id, set_id, n_pl, raan, inc, apog, perig, op in con.execute(
        "SELECT ntc_id, coalesce(orbit_set_id, '1'), nbr_sat_pl, right_asc, inclin_ang, apog_km, perig_km, "
        "op_ht_km "
        "FROM space.orbit WHERE ific_no = ? ORDER BY ntc_id, orbit_set_id, orb_id",
        [ific_no],
    ).fetchall():
        alt = apog if apog is not None else op if op is not None else perig
        if alt is None or inc is None:
            continue
        planes[ntc_id][set_id].append((alt, inc, raan or 0.0, n_pl or 1, (apog or alt) - (perig or alt)))
    for ntc_id, sets in planes.items():
        set_id, rows = max(
            sets.items(), key=lambda kv: (sum(r[3] for r in kv[1]), -int(kv[0]) if kv[0].isdigit() else 0)
        )
        const = Constellation.from_planes(
            [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows]
        )
        assumptions = ["circular_orbit", "plane_phasing"] + (["orbit_config"] if len(sets) > 1 else [])
        out[ntc_id] = Geometry(
            "ngso",
            constellation=const,
            min_alt_km=min(r[0] - r[4] for r in rows),
            heo=any(r[0] > HEO_APOGEE_KM and HEO_INCL_DEG[0] <= r[1] <= HEO_INCL_DEG[1] for r in rows),
            inputs=[
                _input(
                    "Constellation",
                    f"{len(rows)} planes, {const.size} satellites (set {set_id})",
                    None,
                    "data",
                    "space.orbit",
                ),
                _input(
                    "Altitude range",
                    f"{min(r[0] for r in rows):.0f}–{max(r[0] for r in rows):.0f}",
                    "km",
                    "data",
                    "space.orbit.apog_km / op_ht_km",
                ),
                _input(
                    "Inclination range",
                    f"{min(r[1] for r in rows):.1f}–{max(r[1] for r in rows):.1f}",
                    "°",
                    "data",
                    "space.orbit.inclin_ang",
                ),
            ],
            assumptions=assumptions,
        )
    for ntc_id, nh, sh in con.execute(
        "SELECT ntc_id, nbr_sat_nh, nbr_sat_sh FROM space.non_geo WHERE ific_no = ?", [ific_no]
    ).fetchall():
        if ntc_id not in out:
            n = sum(int(x) for x in (nh, sh) if x and str(x).isdigit()) or 1
            out[ntc_id] = Geometry(
                "none",
                missing_reason="Tier 2 not possible: orbit missing",
                fallback_sats=n,
                inputs=[
                    _input(
                        "Satellites (non_geo, worst-case count)",
                        n,
                        None,
                        "data",
                        "space.non_geo.nbr_sat_nh + nbr_sat_sh",
                    ),
                    _input(
                        "Fallback minimum altitude",
                        hazards.NGSO_FALLBACK_ALT_KM,
                        "km",
                        "assumption",
                        "assumption: lowest LEO altitude for the Tier 1 bound",
                    ),
                ],
            )
    return out


def _input(name: str, value: Any, unit: str | None, source: str, cite: str) -> dict[str, Any]:
    if isinstance(value, float):
        value = round(value, 4)
    return {"name": name, "value": value, "unit": unit, "source": source, "cite": cite}


@dataclass
class _Population:
    bands: list[tuple[str, float, float]]
    rx_band: np.ndarray
    rx_site: np.ndarray
    rx_bw: np.ndarray
    rx_nf: np.ndarray
    rx_acs: np.ndarray
    site_lat: np.ndarray
    site_lon: np.ndarray
    site_h: np.ndarray
    site_az: np.ndarray
    site_el: np.ndarray
    site_gain: np.ndarray
    band_cites: list[list[str]]
    assumptions: list[str]


def _nan(x: float | None) -> float:
    return np.nan if x is None else float(x)


def _index_population(receivers: list[Receiver], classes: dict[str, ReceiverClass]) -> _Population:
    band_ix: dict[tuple[str, float, float], int] = {}
    site_ix: dict[tuple, int] = {}
    cites: list[list[str]] = []
    rb, rs, bw, nf, acs, assumptions = [], [], [], [], [], {}
    sites: list[tuple] = []
    for r in receivers:
        cls = classes[r.service_class]
        bkey = (r.service_class, r.f_lo_hz, r.f_hi_hz)
        if bkey not in band_ix:
            band_ix[bkey] = len(band_ix)
            cites.append(list(r.citation))
        skey = (
            r.lat,
            r.lon,
            r.height_m,
            r.azimuth_deg,
            r.pointing_elev_deg,
            r.gain_dbi if r.gain_dbi is not None else cls.gain_dbi,
        )
        if skey not in site_ix:
            site_ix[skey] = len(sites)
            sites.append(skey)
        rb.append(band_ix[bkey])
        rs.append(site_ix[skey])
        bw.append(r.bw_hz or cls.bw_hz)
        nf.append(cls.nf_db if r.nf_db is None else r.nf_db)
        acs.append(cls.acs_db if r.acs is None else r.acs)
        for a in r.assumptions:
            assumptions[a] = None
    s = list(zip(*sites, strict=True)) if sites else [()] * 6
    return _Population(
        bands=list(band_ix),
        rx_band=np.asarray(rb, dtype=int),
        rx_site=np.asarray(rs, dtype=int),
        rx_bw=np.asarray(bw, dtype=float),
        rx_nf=np.asarray(nf, dtype=float),
        rx_acs=np.asarray(acs, dtype=float),
        site_lat=np.asarray(s[0], dtype=float),
        site_lon=np.asarray(s[1], dtype=float),
        site_h=np.asarray([_nan(x) for x in s[2]]),
        site_az=np.asarray([_nan(x) for x in s[3]]),
        site_el=np.asarray([_nan(x) for x in s[4]]),
        site_gain=np.asarray(s[5], dtype=float),
        band_cites=cites,
        assumptions=list(assumptions),
    )


def _pairs(
    con: duckdb.DuckDBPyConnection, notices: dict[int, _Notice], pop: _Population, adj_extent_bn: float
) -> dict[tuple[int, str, str], dict[int, list[tuple[Grp, float]]]]:
    """One DuckDB range join of all downlink groups against the population bands (co-channel and adjacent)."""
    grps = [
        (n.ntc_id, i, g.f_lo_hz, g.f_hi_hz, g.bn_hz)
        for n in notices.values()
        for i, g in enumerate(n.downlinks)
    ]
    out: dict[tuple[int, str, str], dict[int, list[tuple[Grp, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    if not grps or not pop.bands:
        return out
    cur = con.cursor()
    try:
        cur.execute(
            "CREATE OR REPLACE TEMP TABLE riia_grp AS SELECT unnest(?::BIGINT[]) ntc_id, "
            "unnest(?::INTEGER[]) gi, "
            "unnest(?::DOUBLE[]) lo, unnest(?::DOUBLE[]) hi, unnest(?::DOUBLE[]) bn",
            [list(c) for c in zip(*grps, strict=True)],
        )
        cur.execute(
            "CREATE OR REPLACE TEMP TABLE riia_band AS SELECT unnest(?::INTEGER[]) bi, unnest(?::DOUBLE[]) "
            "lo, unnest(?::DOUBLE[]) hi",
            [list(range(len(pop.bands))), [b[1] for b in pop.bands], [b[2] for b in pop.bands]],
        )
        rows = cur.execute(
            """
            SELECT g.ntc_id, g.gi, b.bi, greatest(b.lo - g.hi, g.lo - b.hi) AS gap
            FROM riia_grp g JOIN riia_band b
              ON b.lo < g.hi + ? * g.bn AND b.hi > g.lo - ? * g.bn
            ORDER BY 1, 2, 3
            """,
            [adj_extent_bn, adj_extent_bn],
        ).fetchall()
    finally:
        cur.close()
    for ntc_id, gi, bi, gap in rows:
        mode = "cochannel" if gap < 0 else "adjacent"
        out[(ntc_id, pop.bands[bi][0], mode)][bi].append((notices[ntc_id].downlinks[gi], max(gap, 0.0)))
    return out


def _hazard_receivers(pop: _Population, pairs: dict[int, list[tuple[Grp, float]]]) -> HazardReceivers:
    band_ids = sorted(pairs)
    mask = np.isin(pop.rx_band, band_ids)
    sites = np.unique(pop.rx_site[mask])
    remap = {b: i for i, b in enumerate(band_ids)}
    cites = sorted({c for b in band_ids for c in pop.band_cites[b]})
    return HazardReceivers(
        bands=[(pop.bands[b][1], pop.bands[b][2]) for b in band_ids],
        band=np.asarray([remap[b] for b in pop.rx_band[mask]], dtype=int),
        site=np.searchsorted(sites, pop.rx_site[mask]),
        bw_hz=pop.rx_bw[mask],
        nf_db=pop.rx_nf[mask],
        acs_db=pop.rx_acs[mask],
        lat=pop.site_lat[sites],
        lon=pop.site_lon[sites],
        height_m=pop.site_h[sites],
        az=pop.site_az[sites],
        el=pop.site_el[sites],
        gain_dbi=pop.site_gain[sites],
        pairs={remap[b]: pairs[b] for b in band_ids},
        citations=cites,
        assumptions=list(pop.assumptions),
    )


def _criteria(cls: ReceiverClass) -> list[dict[str, Any]]:
    return [vars(c) for c in cls.criteria]


def _hazard(
    mode: str, cls: ReceiverClass | None, outcome: str, reason: str | None, **kw: Any
) -> dict[str, Any]:
    h = {
        "hazard_id": f"{mode}:{cls.id}" if cls else mode,
        "mode": mode,
        "service_class": cls.id if cls else None,
        "service_label": cls.label if cls else None,
        "bands_hz": [],
        "tier": 0,
        "outcome": outcome,
        "reason": reason,
        "n_receivers": 0,
        "n_samples": 0,
        "share_violating": None,
        "exceedance_db": [],
        "risk_curves": [],
        "worst_case_db": None,
        "tier2_max_db": None,
        "criteria": _criteria(cls) if cls else [],
        "inputs": [],
        "citations": [],
        "assumptions": [],
        "in_summary": mode in hazards.QUANTIFIED_MODES,
    }
    h.update(kw)
    return h


def _assumption_list(ids: list[str], extra: list[str] = ()) -> list[dict[str, Any]]:
    out = [{"id": i, "text": ASSUMPTIONS.get(i, i), "sensitive": False} for i in dict.fromkeys(ids)]
    out += [{"id": f"note:{k}", "text": t, "sensitive": False} for k, t in enumerate(extra)]
    return out


def _quantified(
    ific_no: int,
    n: _Notice,
    cls: ReceiverClass,
    mode: str,
    pairs: dict[int, list[tuple[Grp, float]]],
    pop: _Population,
    geom: Geometry | None,
    kt0: float,
    ov: Overrides,
    stats: dict[str, float],
) -> dict[str, Any]:
    hr = _hazard_receivers(pop, pairs)
    grps = {g.grp_id: g for v in pairs.values() for g, _ in v}
    pattern = ov.pattern(cls)
    citations = [
        *hr.citations,
        antenna.PATTERN_CITES[pattern],
        *(c.cite for c in cls.criteria),
        f"space.grp / space.emiss / space.s_beam: {len(grps)} assignment groups",
    ]
    if mode == "adjacent":
        citations += [emission.OOB_CITE, emission.SPURIOUS_CITE]
    if cls.spfd_cite:
        citations.append(cls.spfd_cite)
    generic = "generic_population" in hr.assumptions
    assumption_ids = [
        *(a for a in hr.assumptions if a in ASSUMPTIONS),
        "full_duty_cycle",
        "single_beam",
        "class_values",
        "sample_size",
        "grid" if generic else "",
    ]
    if any(g.gain_assumed and g.cpfd_dens is None for g in grps.values()):
        assumption_ids.append("peak_gain")
    assumption_ids.append("carrier_in_channel" if mode == "cochannel" else "adjacent_extent")
    assumption_ids += [f"dist:{cls.id}:{p}" for p in cls.distributions]
    if geom:
        assumption_ids += geom.assumptions
    dens = max(g.d_dbw_hz for g in grps.values())
    inputs = [
        _input("Receiver bands", len(hr.bands), None, "data", "ref.m4_allocation (merged class bands)"),
        _input(
            "Receiver sites",
            int(hr.lat.size),
            None,
            "assumption" if generic else "data",
            "generic grid over Finland" if generic else "ref.special_interest_station",
        ),
        _input(
            "Max carrier power density",
            dens,
            "dB(W/Hz)",
            "data",
            "space.emiss.pep_max − 10·log10(B_n from design_emi)",
        ),
        _input(
            "Max satellite antenna gain",
            max(g.gain_dbi for g in grps.values()),
            "dBi",
            "data",
            "space.s_beam.gain",
        ),
        _input("Receiver pattern", pattern, None, "itu-r", antenna.PATTERN_CITES[pattern]),
        _input("Receiver peak gain", cls.gain_dbi, "dBi", "itu-r", cls.cites["gain_dbi"]),
        _input("Receiver noise figure", cls.nf_db, "dB", "itu-r", cls.cites["nf_db"]),
        _input("Receiver bandwidth", cls.bw_hz, "Hz", "itu-r", cls.cites["bw_hz"]),
        _input("Thermal noise k·T0", load_classes().kt0_dbw_hz, "dB(W/Hz)", "physics", "k·T0, T0 = 290 K"),
    ]
    if mode == "adjacent":
        inputs.append(_input("Receiver selectivity (ACS)", cls.acs_db, "dB", "itu-r", cls.cites["acs_db"]))
    if any(g.cpfd_dens is not None for g in grps.values()):
        inputs.append(
            _input("Notified pfd used", "yes", None, "data", "space.c_pfd replaces the calculated pfd")
        )
    if n.has_mask:
        inputs.append(
            _input(
                "pfd mask notified", "values not loaded; calculated pfd used", None, "data", "space.mask_info"
            )
        )
    if geom:
        inputs += geom.inputs
    for d in cls.distributions.values():
        lo, hi = ov.distribution(cls, d.param)
        inputs.append(_input(f"{d.param} distribution", f"U({lo:g}, {hi:g})", None, "assumption", d.cite))
    base = {
        "bands_hz": [[lo, hi] for lo, hi in hr.bands],
        "inputs": inputs,
        "citations": list(dict.fromkeys(c for c in citations if c)),
        "assumptions": _assumption_list([a for a in assumption_ids if a]),
    }
    if geom is None:
        return _hazard(mode, cls, "not_assessed", "No orbit or GSO position for this notice", **base)
    if not hazards.visible_anywhere(geom, hr.lat, hr.lon, 0.0):
        return _hazard(
            mode, cls, "not_applicable", "The space station is never above the horizon in Finland", **base
        )

    t0 = time.perf_counter()
    a, b = hazards.receiver_constants(cls, mode, hr, geom, load_classes().kt0_dbw_hz, ov)
    given_h = float(np.nanmax(hr.height_m)) if np.isfinite(hr.height_m).any() else 0.0
    dist_h = ov.distribution(cls, "height_m")[1] if "height_m" in cls.distributions else 0.0
    worst, t1_info = hazards.tier1_worst(a, b, float(hr.gain_dbi.max()), geom, hr, max(given_h, dist_h))
    base["inputs"] += [
        _input(
            "Tier 1 minimum slant range",
            t1_info["d_min_km"],
            "km",
            "physics",
            "orbit geometry over the receiver sites",
        ),
        _input(
            "Tier 1 satellites in view (bound)",
            t1_info["n_visible_max"],
            None,
            "physics",
            "evenly spaced satellites per plane within 2λ of arc",
        ),
    ]
    stats["tier1_s"] += time.perf_counter() - t0
    base.update(tier=1, worst_case_db=hazards._finite(worst), n_receivers=int(a.size))
    if worst <= cls.min_level_db:
        stats["tier1_screened"] += 1
        return _hazard(
            mode,
            cls,
            "screened_out",
            f"Tier 1 worst case {worst:.1f} dB does not exceed the lowest criterion level "
            f"{cls.min_level_db:g} dB",
            **base,
        )
    if geom.kind == "none":
        return _hazard(mode, cls, "not_assessed", geom.missing_reason, **base)
    t0 = time.perf_counter()
    rng = hazards.rng_for(ific_no, n.ntc_id, f"{mode}:{cls.id}")
    t2 = hazards.tier2(cls, a, b, hr, geom, rng, ov)
    summary = hazards.summarise_tier2(cls, t2)
    stats["tier2_s"] += time.perf_counter() - t0
    stats["tier2"] += 1
    if t2.sites_used < hr.lat.size:
        base["assumptions"] += _assumption_list(
            [], [f"Tier 2 used {t2.sites_used} of {hr.lat.size} sites to keep N ≤ 10⁶"]
        )
    reason = None if summary["outcome"] == "exceeds" else "No receiver exceeds a criterion point"
    if summary["outcome"] == "exceeds":
        reason = f"{summary['share_violating']:.1%} of receivers exceed a criterion point"
    outcome = summary.pop("outcome")
    return _hazard(mode, cls, outcome, reason, **{**base, **summary, "tier": 2})


def _inventory(n: _Notice, finland: tuple[np.ndarray, np.ndarray]) -> list[dict[str, Any]]:
    out = []
    if n.ntc_type == "S":
        if n.es_points:
            lat, lon = finland
            d = min(float(haversine_km(la, lo, lat, lon).min()) for la, lo in n.es_points)
            inputs = [
                _input(
                    "Distance from earth station to Finland",
                    round(d, 1),
                    "km",
                    "physics",
                    "space.e_stn lat/long, haversine",
                )
            ]
            if d <= hazards.ES_SCREEN_KM:
                out.append(
                    _hazard(
                        "es_terrestrial",
                        None,
                        "not_assessed",
                        f"Earth station {d:.0f} km from Finland; terrestrial propagation module not built "
                        f"yet",
                        inputs=inputs,
                        in_summary=True,
                    )
                )
            else:
                out.append(
                    _hazard(
                        "es_terrestrial",
                        None,
                        "not_applicable",
                        f"Earth station {d:.0f} km from Finland, beyond the {hazards.ES_SCREEN_KM:.0f} km "
                        f"screening radius (assumption)",
                        inputs=inputs,
                    )
                )
        else:
            out.append(
                _hazard(
                    "es_terrestrial",
                    None,
                    "not_assessed",
                    "Earth-station location not notified",
                    in_summary=True,
                )
            )
    elif n.has_uplink:
        out.append(
            _hazard(
                "es_terrestrial",
                None,
                "not_assessed",
                "Typical earth stations of the network are not located; terrestrial propagation module not "
                "built yet",
            )
        )
    else:
        out.append(_hazard("es_terrestrial", None, "not_applicable", "No Earth-to-space assignments"))
    if n.downlinks:
        out.append(
            _hazard("blocking_im", None, "not_assessed", "No receiver blocking or intermodulation data")
        )
    else:
        out.append(_hazard("blocking_im", None, "not_applicable", "No space-to-Earth assignments"))
    out.append(_hazard("aggregate_networks", None, "not_assessed", "riia-1 assesses one notice at a time"))
    return out


def summarise(hazard_list: list[dict[str, Any]], classes: dict[str, ReceiverClass]) -> dict[str, Any]:
    counted = [h for h in hazard_list if h["in_summary"]]
    worst = min(
        (h["outcome"] for h in counted), key=hazards.OUTCOME_RANK.__getitem__, default="not_applicable"
    )
    counts = {o: 0 for o in hazards.OUTCOME_RANK}
    for h in hazard_list:
        counts[h["outcome"]] += 1
    shares = [h["share_violating"] for h in counted if h["share_violating"] is not None]
    medians = [e["median_db"] for h in counted for e in h["exceedance_db"] if e["median_db"] is not None]
    rel_worst = [
        h["worst_case_db"] - min(c["level_db"] for c in h["criteria"])
        for h in counted
        if h["worst_case_db"] is not None and h["criteria"]
    ]
    return {
        "worst_outcome": worst,
        "hazard_counts": counts,
        "services_exceeding": sorted(
            {h["service_class"] for h in counted if h["outcome"] == "exceeds" and h["service_class"]}
        ),
        "services_assessed": sorted(
            {h["service_class"] for h in counted if h["tier"] >= 1 and h["service_class"]}
        ),
        "max_share_violating": max(shares) if shares else None,
        "max_median_exceedance_db": max(medians) if medians else None,
        "max_worst_case_db": max(rel_worst) if rel_worst else None,
    }


def technical_sort_key(n: dict[str, Any]) -> tuple:
    """Doc, 'Sorting a list of notices': "1. Outcome: exceeds, then not_assessed only, then meets, then
    screened_out. 2. Largest share_violating. 3. Largest median exceedance_db. 4. ntc_id." The pfd outcome
    breaks ties before ntc_id; results stored before the pfd check sort last among ties."""
    return (
        hazards.OUTCOME_RANK[n["worst_outcome"]],
        -(n["max_share_violating"] or 0.0),
        -(n["max_median_exceedance_db"] if n["max_median_exceedance_db"] is not None else -math.inf),
        hazards.OUTCOME_RANK.get(n.get("pfd_outcome"), len(hazards.OUTCOME_RANK)),
        n["ntc_id"],
    )


def window_not_closed(regulatory: dict[str, Any]) -> bool:
    """The comment window is open on the as-of date, or the notice is at a stage without one."""
    return regulatory["days_left"] is None or regulatory["days_left"] >= 0


def in_queue(n: dict[str, Any]) -> bool:
    """Doc, 'Work queue': "the notices with at least one exceeds hazard whose comment window has not
    closed"."""
    return n["worst_outcome"] == "exceeds" and window_not_closed(n["regulatory"])


def queue_sort_key(n: dict[str, Any]) -> tuple:
    """Soonest deadline first; notices without a comment window after those with one."""
    days_left = n["regulatory"]["days_left"]
    return (days_left is None, days_left or 0, *technical_sort_key(n))


def apply_as_of(n: dict[str, Any], as_of: date) -> dict[str, Any]:
    out = {**n, "as_of": as_of.isoformat(), "regulatory": regulatory.with_as_of(n["regulatory"], as_of)}
    out["in_queue"] = in_queue(out)
    return out


def orbit_type(ntc_type: str) -> str:
    return {"G": "gso", "N": "ngso"}.get(ntc_type, "es")


def pfd_results(
    notices: dict[int, _Notice], geoms: dict[int, Geometry], params: pfd.Params = pfd.DEFAULT_PARAMS
) -> dict[int, dict[str, Any]]:
    """The Table 21-4 pfd check of every notice (doc: 'pfd on Finnish territory vs RR Table 21-4')."""
    limits, grid = load_limits(), pfd.Grid.of(finland_grid())
    out = {}
    for n in notices.values():
        try:
            checks = pfd.notice_checks(
                n.pfd_groups,
                n.pfd_notified,
                geoms.get(n.ntc_id),
                n.ntc_type,
                n.act_code,
                limits,
                grid,
                params,
            )
        except Exception as e:
            log.warning("pfd check ntc=%d failed: %s", n.ntc_id, e)
            checks = pfd.failed(f"pfd check failed: {e}", orbit_type(n.ntc_type), limits)
        out[n.ntc_id] = pfd.summarise(checks, limits)
    return out


def assess_issue(
    con: duckdb.DuckDBPyConnection,
    ific_no: int,
    as_of: date,
    population: ReceiverPopulation,
    overrides: Overrides | None = None,
    progress: Progress | None = None,
    only: set[int] | None = None,
    classes: tuple[str, ...] = (),
    stats_out: dict[str, float] | None = None,
    pfd_params: pfd.Params = pfd.DEFAULT_PARAMS,
) -> list[dict[str, Any]]:
    """Assess every notice of `ific_no`; returns NoticeAssessment dicts in technical sort order."""
    started = time.perf_counter()
    ov = overrides or Overrides()
    cf = load_classes()
    notices = _load_notices(con, ific_no)
    if only is not None:
        notices = {k: v for k, v in notices.items() if k in only}
    geoms = _load_geometry(con, ific_no)
    pop = _index_population(population.receivers(con), cf.classes)
    all_pairs = _pairs(con, notices, pop, ov.adj_extent_bn)
    pfd_out = pfd_results(notices, geoms, pfd_params)
    finland = (pop.site_lat, pop.site_lon)
    stats = defaultdict(float)
    results = []
    total = len(notices)
    for done, n in enumerate(notices.values(), start=1):
        hazard_list = []
        for cls in (c for c in cf.classes.values() if not classes or c.id in classes):
            for mode in hazards.QUANTIFIED_MODES:
                pairs = all_pairs.get((n.ntc_id, cls.id, mode))
                if n.act_code == "S":
                    h = _hazard(mode, cls, "not_applicable", "suppressed")
                elif n.ntc_type == "S":
                    h = _hazard(
                        mode, cls, "not_applicable", "Earth-station notice: no space-station emissions"
                    )
                elif not pairs:
                    h = _hazard(
                        mode,
                        cls,
                        "not_applicable",
                        "No downlink overlaps a Finnish band of this class"
                        if mode == "cochannel"
                        else "No downlink within the adjacent-band range of a Finnish band of this class",
                    )
                else:
                    try:
                        h = _quantified(
                            ific_no, n, cls, mode, pairs, pop, geoms.get(n.ntc_id), cf.kt0_dbw_hz, ov, stats
                        )
                    except Exception as e:
                        log.warning(
                            "riia ific=%d ntc=%d hazard=%s:%s failed: %s", ific_no, n.ntc_id, mode, cls.id, e
                        )
                        h = _hazard(mode, cls, "not_assessed", f"assessment failed: {e}")
                hazard_list.append(h)
        hazard_list += _inventory(n, finland)
        summary = summarise(hazard_list, cf.classes)
        reg = regulatory.context(n.prov, n.d_wic, n.findings, as_of)
        result = {
            "ific_no": ific_no,
            "ntc_id": n.ntc_id,
            "sat_name": n.sat_name,
            "adm": n.adm,
            "prov": n.prov,
            "ntc_type": n.ntc_type,
            "orbit": orbit_type(n.ntc_type),
            "act_code": n.act_code,
            "receiver_source": population.name,
            "model_version": MODEL_VERSION,
            "as_of": as_of.isoformat(),
            "curve_grid_db": {
                "start": curves.GRID_START_DB,
                "stop": curves.GRID_STOP_DB,
                "step": curves.GRID_STEP_DB,
            },
            **summary,
            **pfd_out[n.ntc_id],
            "regulatory": reg,
            "hazards": hazard_list,
        }
        result["in_queue"] = in_queue(result)
        results.append(result)
        if progress:
            progress(done, total)
    results.sort(key=technical_sort_key)
    ms = round((time.perf_counter() - started) * 1000)
    n_h = sum(len(r["hazards"]) for r in results)
    log.info(
        "riia assess ific=%d source=%s notices=%d hazards=%d tier1_screened=%d tier2=%d tier1_ms=%d "
        "tier2_ms=%d duration_ms=%d",
        ific_no,
        population.name,
        len(results),
        n_h,
        stats["tier1_screened"],
        stats["tier2"],
        stats["tier1_s"] * 1000,
        stats["tier2_s"] * 1000,
        ms,
    )
    if stats_out is not None:
        stats_out.update({**stats, "duration_ms": ms, "notices": len(results), "hazards": n_h})
    return results
