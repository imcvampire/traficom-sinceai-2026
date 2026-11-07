"""Spherical-Earth geometry, in km and degrees. Arrays broadcast; last axis of a vector array is (x, y, z)."""

import numpy as np

R_EARTH_KM = 6378.137
R_GSO_KM = 42164.2


def unit(lat_deg: np.ndarray | float, lon_deg: np.ndarray | float) -> np.ndarray:
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    return np.stack(
        np.broadcast_arrays(np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)), -1
    )


def ecef(lat_deg: np.ndarray | float, lon_deg: np.ndarray | float, r_km: np.ndarray | float) -> np.ndarray:
    return unit(lat_deg, lon_deg) * np.asarray(r_km, dtype=float)[..., None]


def enu_basis(lat_deg: np.ndarray, lon_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Local east, north and up unit vectors at each site."""
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    east = np.stack([-np.sin(lon), np.cos(lon), np.zeros_like(lon)], -1)
    north = np.stack([-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)], -1)
    return east, north, unit(lat_deg, lon_deg)


def look_angles(
    site_ecef: np.ndarray, east: np.ndarray, north: np.ndarray, up: np.ndarray, sat_ecef: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Elevation (deg), azimuth (deg from north, clockwise) and slant range (km) from sites to satellites."""
    d = sat_ecef - site_ecef
    rng = np.linalg.norm(d, axis=-1)
    e, n, u = (np.einsum("...k,...k->...", d, b) for b in (east, north, up))
    elev = np.degrees(np.arcsin(np.clip(u / rng, -1.0, 1.0)))
    az = np.degrees(np.arctan2(e, n)) % 360.0
    return elev, az, rng


def pointing_vector(az_deg: np.ndarray, elev_deg: np.ndarray) -> np.ndarray:
    """Unit pointing direction in local (east, north, up) components."""
    az, el = np.radians(az_deg), np.radians(elev_deg)
    return np.stack([np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)], -1)


def off_axis_deg(
    az1_deg: np.ndarray, el1_deg: np.ndarray, az2_deg: np.ndarray, el2_deg: np.ndarray
) -> np.ndarray:
    """Angle between two directions given as (azimuth, elevation)."""
    a1, e1, a2, e2 = (np.radians(x) for x in (az1_deg, el1_deg, az2_deg, el2_deg))
    c = np.sin(e1) * np.sin(e2) + np.cos(e1) * np.cos(e2) * np.cos(a1 - a2)
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def angle_between_deg(v1: np.ndarray, v2: np.ndarray) -> np.ndarray:
    c = np.einsum("...k,...k->...", v1, v2) / (np.linalg.norm(v1, axis=-1) * np.linalg.norm(v2, axis=-1))
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(np.asarray(lon2) - np.asarray(lon1))
    h = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R_EARTH_KM * np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0)))


def slant_range_km(central_angle_deg: np.ndarray | float, r_site_km: float, r_sat_km: float) -> np.ndarray:
    g = np.radians(central_angle_deg)
    return np.sqrt(r_sat_km**2 + r_site_km**2 - 2 * r_sat_km * r_site_km * np.cos(g))


def horizon_central_angle_deg(r_sat_km: np.ndarray | float, min_elev_deg: float = 0.0) -> np.ndarray:
    """Largest Earth central angle at which a satellite at radius r is seen at or above `min_elev_deg`."""
    el = np.radians(min_elev_deg)
    return np.degrees(np.arccos(R_EARTH_KM / np.asarray(r_sat_km) * np.cos(el)) - el)


def _ring_contains(lon: np.ndarray, lat: np.ndarray, ring: np.ndarray) -> np.ndarray:
    inside = np.zeros(lon.shape, dtype=bool)
    x0, y0 = ring[:-1, 0], ring[:-1, 1]
    x1, y1 = ring[1:, 0], ring[1:, 1]
    for a, b, c, d in zip(x0, y0, x1, y1, strict=True):
        crosses = (b > lat) != (d > lat)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_at = a + (lat - b) * (c - a) / (d - b)
        inside ^= crosses & (lon < x_at)
    return inside


def in_multipolygon(lon: np.ndarray, lat: np.ndarray, polygons: list[list[list[list[float]]]]) -> np.ndarray:
    """Even-odd point-in-polygon for GeoJSON MultiPolygon coordinates (outer ring plus holes)."""
    lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
    inside = np.zeros(lon.shape, dtype=bool)
    for poly in polygons:
        acc = np.zeros(lon.shape, dtype=bool)
        for ring in poly:
            acc ^= _ring_contains(lon, lat, np.asarray(ring, dtype=float))
        inside |= acc
    return inside
