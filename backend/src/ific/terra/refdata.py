"""Hand-curated, cited inputs of `terra-1`: coordination criteria, frameworks, the land mask and the Finnish
outline. Every loader is cached; the files live in `data/ref/`.

The land mask is Natural Earth 1:10m land clipped to lon 0-45°E, lat 50-75°N (`region_land.geojson`). It is
rasterised once to a 0.01° grid by an even-odd scanline fill of the cell centres, so classifying a path of a
few hundred samples is one array index. Points outside the clip box count as land (inland Eurasia).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from ific.config import settings
from ific.propagation import tr2508
from ific.riia.geometry import haversine_km

TR2508_ID = "tr-25-08"
LAND_RES_DEG = 0.01
_LAND_BOX = (0.0, 50.0, 45.0, 75.0)  # lon_min, lat_min, lon_max, lat_max


def _ref(name: str) -> Path:
    return settings.data_dir / "ref" / name


def _tr2508_entry() -> dict[str, Any]:
    """The T/R 25-08 criterion, generated from `ific.propagation.tr2508` so its values exist only there."""
    return {
        "id": TR2508_ID,
        "title": "ECC T/R 25-08: cross-border coordination for land mobile systems, 29.7-470 MHz",
        "citation": tr2508.CITATION,
        "doc_url": "https://docdb.cept.org/document/909",
        "doc_sha256": "d6460dd8fcc618cf2164c96d3fd0ab3a2c45cd78265a3130f7aa516e2d35c52c",
        "f_min_mhz": tr2508.RANGE_MHZ[0],
        "f_max_mhz": tr2508.RANGE_MHZ[1],
        "edges": "a shared edge belongs to the higher range; 470 MHz belongs to the top range",
        "time_pct": tr2508.TIME_PCT,
        "loc_pct": tr2508.LOC_PCT,
        "rx_height_m": tr2508.RX_HEIGHT_M,
        "reference_bw_khz": tr2508.REFERENCE_BW_KHZ,
        "bw_correction": "10log10(bw/ref) above ref",
        "evaluation": "border",
        "bands": [
            {
                "f_min_mhz": t.lower_mhz,
                "f_max_mhz": t.upper_mhz,
                "trigger_dbuv_m": t.e_dbuv_m,
                "evaluation_km": 0.0,
                "quote": t.note,
            }
            for t in tr2508.TRIGGERS
        ],
        "verified": False,
        "verified_by": None,
    }


@cache
def load_criteria() -> dict[str, Any]:
    raw = json.loads(_ref("terrestrial_criteria.json").read_text(encoding="utf-8"))
    criteria = [_tr2508_entry(), *raw["criteria"]]
    ids = [c["id"] for c in criteria]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate criterion ids in terrestrial_criteria.json: {ids}")
    return {"cite": raw["cite"], "review": raw["review"], "criteria": criteria}


def criteria() -> list[dict[str, Any]]:
    return load_criteria()["criteria"]


@cache
def load_frameworks() -> dict[str, Any]:
    return json.loads(_ref("terrestrial_frameworks.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Trigger:
    criterion_id: str
    base_dbuv_m: float
    bandwidth_correction_db: float
    e_dbuv_m: float
    evaluation_km: float
    note: str


def criterion_for(f_mhz: float) -> dict[str, Any] | None:
    for c in criteria():
        if c["id"] == TR2508_ID:
            if tr2508.trigger(f_mhz, None) is not None:
                return c
        elif c["f_min_mhz"] <= f_mhz <= c["f_max_mhz"]:
            return c
    return None


def trigger(criterion: dict[str, Any], f_mhz: float, bw_khz: float | None) -> Trigger | None:
    """Trigger at the criterion's evaluation line, with its bandwidth correction."""
    if criterion["id"] == TR2508_ID:
        t = tr2508.trigger(f_mhz, None if bw_khz is None else round(bw_khz * 1000))
        if t is None:
            return None
        return Trigger(TR2508_ID, t.base_dbuv_m, t.bandwidth_correction_db, t.e_dbuv_m, 0.0, t.note)
    band = next((b for b in criterion["bands"] if b["f_min_mhz"] <= f_mhz <= b["f_max_mhz"]), None)
    if band is None:
        return None
    ref = criterion["reference_bw_khz"]
    corr, note = 0.0, band["quote"]
    if criterion["bw_correction"] == "10log10(bw/ref)" and bw_khz:
        corr = 10 * math.log10(bw_khz / ref)
        note += f"; block size {bw_khz:g} kHz vs {ref:g} kHz reference"
    elif not bw_khz:
        note += "; bandwidth unknown, no correction"
    base = band["trigger_dbuv_m"]
    return Trigger(criterion["id"], base, corr, base + corr, band["evaluation_km"], note)


# --- land mask ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LandMask:
    grid: np.ndarray  # [row (lat), col (lon)] bool
    lon0: float
    lat0: float
    res: float

    def is_land(self, lon: np.ndarray | float, lat: np.ndarray | float) -> np.ndarray:
        lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
        col = np.floor((lon - self.lon0) / self.res).astype(int)
        row = np.floor((lat - self.lat0) / self.res).astype(int)
        rows, cols = self.grid.shape
        inside = (row >= 0) & (row < rows) & (col >= 0) & (col < cols)
        out = np.ones(lon.shape, dtype=bool)
        out[inside] = self.grid[row[inside], col[inside]]
        return out


def _rings(path: Path) -> list[np.ndarray]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rings: list[np.ndarray] = []
    for feature in data["features"]:
        geom = feature["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        rings.extend(np.asarray(ring, dtype=float) for poly in polys for ring in poly)
    return rings


@cache
def land_mask() -> LandMask:
    lon_min, lat_min, lon_max, lat_max = _LAND_BOX
    ncol = round((lon_max - lon_min) / LAND_RES_DEG)
    nrow = round((lat_max - lat_min) / LAND_RES_DEG)
    col_x = lon_min + (np.arange(ncol) + 0.5) * LAND_RES_DEG
    edges = [(r[:-1], r[1:]) for r in _rings(_ref("region_land.geojson"))]
    a = np.concatenate([e[0] for e in edges])
    b = np.concatenate([e[1] for e in edges])
    x0, y0, x1, y1 = a[:, 0], a[:, 1], b[:, 0], b[:, 1]
    grid = np.zeros((nrow, ncol), dtype=bool)
    for i in range(nrow):
        y = lat_min + (i + 0.5) * LAND_RES_DEG
        m = (y0 > y) != (y1 > y)
        xs = np.sort(x0[m] + (y - y0[m]) * (x1[m] - x0[m]) / (y1[m] - y0[m]))
        grid[i] = np.searchsorted(xs, col_x, side="right") % 2 == 1
    return LandMask(grid, lon_min, lat_min, LAND_RES_DEG)


def is_land(lon: np.ndarray | float, lat: np.ndarray | float) -> np.ndarray:
    return land_mask().is_land(lon, lat)


# --- Finnish outline ------------------------------------------------------------------------------------


@cache
def finland_border_points(spacing_km: float = 5.0) -> tuple[tuple[float, float], ...]:
    """Points every `spacing_km` along the outline of `finland_land.geojson` (land border and coastline),
    as (lat, lon), sorted by (lat, lon). The outline is Natural Earth 1:50m, so the spacing is nominal.
    """
    points: set[tuple[float, float]] = set()
    for ring in _rings(_ref("finland_land.geojson")):
        lon, lat = ring[:, 0], ring[:, 1]
        seg = haversine_km(lat[:-1], lon[:-1], lat[1:], lon[1:])
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        targets = np.arange(0.0, cum[-1], spacing_km)
        plat = np.interp(targets, cum, lat)
        plon = np.interp(targets, cum, lon)
        points.update((round(float(y), 5), round(float(x), 5)) for y, x in zip(plat, plon, strict=True))
    return tuple(sorted(points))
