"""Satellite positions in Earth-fixed coordinates: GSO points and circular-orbit constellations."""

from dataclasses import dataclass

import numpy as np

from ific.riia.geometry import R_EARTH_KM, R_GSO_KM, ecef, horizon_central_angle_deg

MU_KM3_S2 = 398600.4418
OMEGA_EARTH_RAD_S = 7.2921150e-5


def gso_ecef(lon_deg: np.ndarray | float) -> np.ndarray:
    return ecef(0.0, lon_deg, R_GSO_KM)


@dataclass(frozen=True)
class Constellation:
    """Per-satellite circular-orbit elements; planes are evenly phased, no plane-to-plane phasing offset."""

    radius_km: np.ndarray
    incl_rad: np.ndarray
    raan_rad: np.ndarray
    phase_rad: np.ndarray
    plane: np.ndarray

    @classmethod
    def from_planes(
        cls, altitude_km: list[float], incl_deg: list[float], raan_deg: list[float], sats_per_plane: list[int]
    ) -> "Constellation":
        radius, incl, raan, phase, plane = [], [], [], [], []
        for p, (h, i, o, n) in enumerate(zip(altitude_km, incl_deg, raan_deg, sats_per_plane, strict=True)):
            n = max(int(n), 1)
            radius.append(np.full(n, R_EARTH_KM + h))
            incl.append(np.full(n, np.radians(i)))
            raan.append(np.full(n, np.radians(o)))
            phase.append(2 * np.pi * np.arange(n) / n)
            plane.append(np.full(n, p))
        return cls(*(np.concatenate(a) for a in (radius, incl, raan, phase)), np.concatenate(plane))

    @property
    def size(self) -> int:
        return int(self.radius_km.size)

    def positions(self, t_s: np.ndarray | float, idx: np.ndarray | None = None) -> np.ndarray:
        """ECEF positions (km), shape t.shape + (S, 3)."""
        sel = slice(None) if idx is None else idx
        r, i, o, ph = self.radius_km[sel], self.incl_rad[sel], self.raan_rad[sel], self.phase_rad[sel]
        t = np.asarray(t_s, dtype=float)[..., None]
        u = ph + np.sqrt(MU_KM3_S2 / r**3) * t
        om = o - OMEGA_EARTH_RAD_S * t
        cu, su, co, so, ci, si = np.cos(u), np.sin(u), np.cos(om), np.sin(om), np.cos(i), np.sin(i)
        return np.stack([r * (cu * co - su * ci * so), r * (cu * so + su * ci * co), r * su * si], -1)

    def max_visible(self, min_elev_deg: float = 0.0) -> int:
        """Strict upper bound on satellites simultaneously above `min_elev_deg` from any one point."""
        total = 0
        for p in np.unique(self.plane):
            m = self.plane == p
            n = int(m.sum())
            lam = float(horizon_central_angle_deg(self.radius_km[m][0], min_elev_deg))
            total += min(n, int(np.floor(n * 2 * lam / 360.0)) + 1)
        return total

    def min_range_km(self, site_lat_deg: np.ndarray, r_site_km: float) -> float:
        """Smallest possible slant range from any site to any satellite (orbit latitude band bound)."""
        i_eff = np.degrees(np.minimum(self.incl_rad, np.pi - self.incl_rad))
        lat = np.abs(np.asarray(site_lat_deg, dtype=float))[:, None]
        gap = np.clip(lat - i_eff[None, :], 0.0, None)
        r = self.radius_km[None, :]
        return float(np.sqrt(r**2 + r_site_km**2 - 2 * r * r_site_km * np.cos(np.radians(gap))).min())

    def max_reach_lat_deg(self, min_elev_deg: float = 0.0) -> float:
        i_eff = np.degrees(np.minimum(self.incl_rad, np.pi - self.incl_rad))
        return float((i_eff + horizon_central_angle_deg(self.radius_km, min_elev_deg)).max())
