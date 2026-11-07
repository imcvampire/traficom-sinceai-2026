"""Tier 0 relevance to Finland: an explicit coordination signal, or a site within the P.1546 range."""

from __future__ import annotations

from functools import cache
from typing import Any

import numpy as np

from ific.riia.geometry import haversine_km
from ific.terra import refdata
from ific.terra.method import BORDER_SPACING_KM, SCREENING_RANGE_KM


@cache
def _border() -> tuple[np.ndarray, np.ndarray]:
    pts = np.asarray(refdata.finland_border_points(BORDER_SPACING_KM), dtype=float)
    return pts[:, 0], pts[:, 1]


def border_distances(lat: float, lon: float) -> np.ndarray:
    blat, blon = _border()
    return haversine_km(lat, lon, blat, blon)


def relevance(a: dict[str, Any], ge06_fin: bool, m4_overlap: bool) -> dict[str, Any]:
    signals: list[dict[str, Any]] = []
    fin = [c for c in a["coordination"] if c["adm"] == "FIN"]
    if fin:
        signals.append(
            {
                "id": "fin_coordination",
                "sufficient": True,
                "detail": "; ".join(f"{c['coord_prov']} {c['coord_st']}" for c in fin),
                "source": f"fxm_coord:{a['terrakey']}",
            }
        )
    if ge06_fin:
        signals.append(
            {
                "id": "ge06_affected",
                "sufficient": True,
                "detail": "FIN in ge06_adm_affected_broad",
                "source": f"ge06_notice_group:{a['terrakey']}",
            }
        )
    distance = None
    if a["site"] is not None:
        distance = float(border_distances(a["site"]["lat"], a["site"]["lon"]).min())
        if distance <= SCREENING_RANGE_KM:
            signals.append(
                {
                    "id": "within_range",
                    "sufficient": True,
                    "detail": f"{distance:.1f} km to the nearest Finnish border point "
                    f"(≤ {SCREENING_RANGE_KM:g} km)",
                    "source": f"fxm_geo:{a['site']['geo_key']}",
                }
            )
    if m4_overlap:
        signals.append(
            {
                "id": "freq_overlap_m4",
                "sufficient": False,
                "detail": "overlaps a Finnish M4 allocation row (recorded, never decides relevance)",
                "source": "ref.m4_allocation",
            }
        )
    return {
        "relevant": any(s["sufficient"] for s in signals),
        "signals": signals,
        "distance_km": distance,
        "fin_coordination": fin,
        "fin_coord_required": any(c["coord_st"] == "COORD REQUIRED" for c in fin),
    }
