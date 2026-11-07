"""Finnish receiver populations: the `Receiver` record, the `ReceiverPopulation` seam, the generic M4 grid."""

import json
import math
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Protocol

import duckdb
import numpy as np

from ific.config import settings
from ific.riia.geometry import in_multipolygon

GRID_DLAT_DEG = 0.25
GRID_DLON_DEG = 0.5


@dataclass(frozen=True, slots=True)
class Receiver:
    """One receiver. A `None` characteristic is drawn from (or defaulted by) its service class at assessment
    time.
    """

    id: str
    source: str
    service_class: str
    lat: float
    lon: float
    height_m: float | None
    f_lo_hz: float
    f_hi_hz: float
    bw_hz: float | None
    azimuth_deg: float | None = None
    pointing_elev_deg: float | None = None
    gain_dbi: float | None = None
    nf_db: float | None = None
    acs: float | None = None
    assumptions: tuple[str, ...] = ()
    citation: tuple[str, ...] = ()


class ReceiverPopulation(Protocol):
    name: str

    def receivers(self, con: duckdb.DuckDBPyConnection) -> list[Receiver]: ...


@dataclass(frozen=True)
class Criterion:
    metric: str
    level_db: float
    time_pct: float
    cite: str


@dataclass(frozen=True)
class Distribution:
    param: str
    kind: str
    low: float
    high: float
    cite: str
    source: str = "assumption"


@dataclass(frozen=True)
class ReceiverClass:
    id: str
    label: str
    metric: str
    pattern: str
    gain_dbi: float
    nf_db: float
    bw_hz: float
    acs_db: float
    min_elev_deg: float
    criteria: tuple[Criterion, ...]
    distributions: dict[str, Distribution]
    cites: dict[str, str] = field(default_factory=dict)
    spfd_points: tuple[tuple[float, float], ...] = ()
    spfd_cite: str | None = None

    @property
    def p_min(self) -> float:
        return min(c.time_pct for c in self.criteria)

    @property
    def min_level_db(self) -> float:
        return min(c.level_db for c in self.criteria)

    def spfd_threshold(self, f_hz: float) -> float:
        """RA.769 continuum threshold at the listed frequency nearest (in log frequency) to `f_hz`."""
        f = np.array([p[0] for p in self.spfd_points]) * 1e6
        i = int(np.argmin(np.abs(np.log(f) - np.log(f_hz))))
        return float(self.spfd_points[i][1])


@dataclass(frozen=True)
class ClassFile:
    raw: dict[str, Any]
    classes: dict[str, ReceiverClass]
    rules: tuple[dict[str, Any], ...]
    kt0_dbw_hz: float


def _receiver_class(c: dict[str, Any]) -> ReceiverClass:
    spfd = c.get("spfd_threshold_dbw_m2_hz") or {}
    return ReceiverClass(
        id=c["id"],
        label=c["label"],
        metric=c["metric"],
        pattern=c["pattern"]["value"],
        gain_dbi=float(c["gain_dbi"]["value"]),
        nf_db=float(c["nf_db"]["value"]),
        bw_hz=float(c["bw_hz"]["value"]),
        acs_db=float(c["acs_db"]["value"]),
        min_elev_deg=float(c["min_elev_deg"]["value"]),
        criteria=tuple(Criterion(**k) for k in c["criteria"]),
        distributions={d["param"]: Distribution(**d) for d in c["distributions"]},
        cites={k: c[k]["cite"] for k in ("pattern", "gain_dbi", "nf_db", "bw_hz", "acs_db", "min_elev_deg")},
        spfd_points=tuple((float(f), float(v)) for f, v in spfd.get("points_mhz", [])),
        spfd_cite=spfd.get("cite"),
    )


@cache
def load_classes(path: Path | None = None) -> ClassFile:
    path = path or settings.data_dir / "ref" / "receiver_classes.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ClassFile(
        raw=raw,
        classes={c["id"]: _receiver_class(c) for c in raw["classes"]},
        rules=tuple(raw["rules"]),
        kt0_dbw_hz=float(raw["noise"]["kt0_dbw_hz"]),
    )


def _has_downlink(line: str) -> bool:
    directions = [d for d in re.findall(r"\(([^)]*)\)", line) if "EARTH" in d or "SPACE" in d]
    return not directions or any("SPACE-TO-EARTH" in d for d in directions)


def classify_services(text: str | None, rules: tuple[dict[str, Any], ...]) -> list[tuple[str, str]]:
    """Map M4 `Services_in_Finland` text to (class id, line) pairs; primary lines only."""
    out: list[tuple[str, str]] = []
    for line in (text or "").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line or line != line.upper() or not any(ch.isalpha() for ch in line):
            continue
        for rule in rules:
            if not all(re.search(rf"(?<![A-Z-]){re.escape(k)}(?![A-Z-])", line) for k in rule["keywords"]):
                continue
            if rule.get("requires_downlink") and not _has_downlink(line):
                if rule.get("exclusive"):
                    break
                continue
            if rule["class"] and (rule["class"], line) not in out:
                out.append((rule["class"], line))
            if rule.get("exclusive"):
                break
    return out


def _merge(bands: list[tuple[int, int, int]]) -> list[tuple[int, int, list[int]]]:
    merged: list[tuple[int, int, list[int]]] = []
    for lo, hi, m4_id in sorted(bands):
        if merged and lo <= merged[-1][1]:
            plo, phi, ids = merged[-1]
            merged[-1] = (plo, max(phi, hi), [*ids, m4_id])
        else:
            merged.append((lo, hi, [m4_id]))
    return merged


@cache
def finland_grid(
    geojson: Path | None = None, dlat: float = GRID_DLAT_DEG, dlon: float = GRID_DLON_DEG
) -> tuple[tuple[float, float], ...]:
    """Cell centres of a dlat × dlon grid that fall inside Finland's land boundary."""
    geojson = geojson or settings.data_dir / "ref" / "finland_land.geojson"
    geom = json.loads(geojson.read_text(encoding="utf-8"))["features"][0]["geometry"]
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    lat = np.arange(59.0 + dlat / 2, 71.0, dlat)
    lon = np.arange(19.0 + dlon / 2, 32.0, dlon)
    la, lo = np.meshgrid(lat, lon, indexing="ij")
    inside = in_multipolygon(lo.ravel(), la.ravel(), polys)
    return tuple(
        (round(float(a), 4), round(float(b), 4))
        for a, b in zip(la.ravel()[inside], lo.ravel()[inside], strict=True)
    )


@dataclass(frozen=True)
class ClassBand:
    service_class: str
    f_lo_hz: int
    f_hi_hz: int
    m4_ids: tuple[int, ...]
    keywords: tuple[str, ...]


def m4_class_bands(con: duckdb.DuckDBPyConnection, rules: tuple[dict[str, Any], ...]) -> list[ClassBand]:
    rows = con.execute(
        "SELECT id, sub_band_lower_hz, sub_band_upper_hz, services_in_finland FROM ref.m4_allocation ORDER "
        "BY id"
    ).fetchall()
    per_class: dict[str, list[tuple[int, int, int]]] = {}
    keywords: dict[str, dict[int, str]] = {}
    for m4_id, lo, hi, services in rows:
        if hi <= lo:
            continue
        for cls, kw in classify_services(services, rules):
            per_class.setdefault(cls, []).append((lo, hi, m4_id))
            keywords.setdefault(cls, {})[m4_id] = kw
    out = []
    for cls, bands in sorted(per_class.items()):
        for lo, hi, ids in _merge(bands):
            kws = tuple(dict.fromkeys(keywords[cls][i] for i in ids))
            out.append(ClassBand(cls, lo, hi, tuple(ids), kws))
    return out


def m4_citation(band: ClassBand) -> str:
    ids = ", ".join(str(i) for i in band.m4_ids[:8]) + (
        f", … ({len(band.m4_ids)} rows)" if len(band.m4_ids) > 8 else ""
    )
    return f"M4 ref.m4_allocation ID {ids}; matched '{' / '.join(band.keywords[:3])}'"


class GenericM4Population:
    """One receiver per protected M4 class band × grid cell in Finland, with class reference values."""

    name = "generic-m4"

    def __init__(self, dlat: float = GRID_DLAT_DEG, dlon: float = GRID_DLON_DEG) -> None:
        self.dlat, self.dlon = dlat, dlon

    def receivers(self, con: duckdb.DuckDBPyConnection) -> list[Receiver]:
        cf = load_classes()
        cells = finland_grid(dlat=self.dlat, dlon=self.dlon)
        grid_note = f"generic grid {self.dlat}° × {self.dlon}° inside Finland ({len(cells)} cells)"
        out = []
        for band in m4_class_bands(con, cf.rules):
            cite = (m4_citation(band), "Natural Earth 1:50m Finland boundary (public domain)")
            for k, (lat, lon) in enumerate(cells):
                out.append(
                    Receiver(
                        id=f"{band.service_class}:{band.f_lo_hz}-{band.f_hi_hz}:{k}",
                        source=self.name,
                        service_class=band.service_class,
                        lat=lat,
                        lon=lon,
                        height_m=None,
                        f_lo_hz=float(band.f_lo_hz),
                        f_hi_hz=float(band.f_hi_hz),
                        bw_hz=None,
                        assumptions=("generic_population", grid_note),
                        citation=cite,
                    )
                )
        return out


LICENCE_CLASS = {"FX": "fixed"}
MAX_APERTURE_M = 4.0
APERTURE_EFFICIENCY = 0.6


def max_plausible_gain_dbi(f_hz: float) -> float:
    """Gain of a 4 m, 60 %-efficient aperture; larger station gains are taken as data errors (assumption)."""
    lam = 299_792_458.0 / f_hz
    return 20 * math.log10(math.pi * MAX_APERTURE_M / lam) + 10 * math.log10(APERTURE_EFFICIENCY)


TRANSMITTER_LICENCES = {"BC": "broadcast transmitter licence", "BT": "broadcast transmitter licence"}


class StationsPopulation:
    """One receiver per station of the frequencies-of-interest dataset that has a receive band.

    The service class is the riia-1 class of the M4 allocation at the receive band (licence class first);
    given azimuth, gain, height and bandwidth win over class values. Exclusions are kept in `excluded`.
    """

    name = "stations"

    def __init__(self) -> None:
        self.excluded: dict[str, int] = {}

    def _skip(self, reason: str) -> None:
        self.excluded[reason] = self.excluded.get(reason, 0) + 1

    def receivers(self, con: duckdb.DuckDBPyConnection) -> list[Receiver]:
        cf = load_classes()
        self.excluded = {}
        rows = con.execute(
            """
            SELECT s.source_row, s.station_no, s.licence_class, s.lat, s.lon, s.effective_agl_m,
                   s.rx_lower_hz,
                   s.rx_upper_hz, s.bandwidth_hz, s.azimuth_deg, s.ant_gain_db, s.directivity,
                   list(a.id ORDER BY a.id) AS m4_ids, list(a.services_in_finland ORDER BY a.id) AS services
            FROM ref.special_interest_station s
            LEFT JOIN ref.m4_allocation a
              ON a.sub_band_lower_hz <= (s.rx_lower_hz + s.rx_upper_hz) / 2
             AND a.sub_band_upper_hz > (s.rx_lower_hz + s.rx_upper_hz) / 2
            GROUP BY ALL
            ORDER BY s.source_row
            """
        ).fetchall()
        out = []
        for row, no, lic, lat, lon, h, lo, hi, bw, az, gain, directivity, m4_ids, services in rows:
            if lic in TRANSMITTER_LICENCES:
                self._skip(TRANSMITTER_LICENCES[lic])
                continue
            if lo is None or hi is None or hi <= lo or lat is None or lon is None:
                self._skip("no receive band or location")
                continue
            matches = [c for text in services if text for c, _ in classify_services(text, cf.rules)]
            if not matches:
                self._skip("no protected riia-1 class at the receive frequency")
                continue
            natural = LICENCE_CLASS.get(lic or "")
            cls = natural if natural in matches else matches[0]
            directional = directivity != "ND" and az is not None
            assumptions = ["stations_source"]
            if gain is not None:
                assumptions.append("station_gain_dbi")
                cap = max_plausible_gain_dbi((lo + hi) / 2)
                if gain > cap:
                    gain = round(cap, 1)
                    assumptions.append("station_gain_capped")
            if not directional:
                assumptions.append("station_azimuth_drawn")
            elif gain is not None and cf.classes[cls].pattern == "omni" and gain > cf.classes[cls].gain_dbi:
                assumptions.append("station_directional_pattern")
            ids = [i for i in m4_ids if i is not None]
            out.append(
                Receiver(
                    id=f"station:{no}:{row}",
                    source=self.name,
                    service_class=cls,
                    lat=float(lat),
                    lon=float(lon),
                    height_m=float(h) if h is not None else None,
                    f_lo_hz=float(lo),
                    f_hi_hz=float(hi),
                    bw_hz=float(bw) if bw else None,
                    azimuth_deg=float(az) if directional else None,
                    gain_dbi=float(gain) if gain is not None else None,
                    assumptions=tuple(assumptions),
                    citation=(
                        f"ref.special_interest_station row {row} (station {no}, licence {lic})",
                        f"M4 ref.m4_allocation ID {', '.join(map(str, ids[:4]))}; class {cls}",
                    ),
                )
            )
        return out
