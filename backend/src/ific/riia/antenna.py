"""Reference antenna patterns (gain in dBi versus off-axis angle in degrees).

Each function implements the formula of its ITU-R Recommendation as transcribed in this module; the version is
in `PATTERN_CITES`. All patterns are capped at the peak gain so the Tier 1 worst case bounds Tier 2.
"""

from collections.abc import Callable

import numpy as np

PATTERN_CITES = {
    "F.1245": "Rec. ITU-R F.1245-3, Annex 1 (average side-lobe pattern, D/λ > 100 and D/λ ≤ 100)",
    "F.699": "Rec. ITU-R F.699-8, Annex 1 (peak side-lobe envelope, D/λ > 100 and D/λ ≤ 100)",
    "BT.419": "Rec. ITU-R BT.419-3, Fig. 1 (directivity discrimination, piecewise-linear reading)",
    "RA.1631": "Rec. ITU-R RA.1631-0, §2 (radio astronomy antenna pattern for compatibility analyses)",
    "S.465": "Rec. ITU-R S.465-6, recommends 2 (earth-station reference pattern, D/λ ≥ 50)",
    "S.672": "Rec. ITU-R S.672-4, Annex 1 (single-feed circular beam, Ls = −20 dB)",
    "omni": "Omnidirectional receiver (physics)",
}


def d_over_lambda(gmax_dbi: float) -> float:
    """F.699/F.1245 note: 20·log10(D/λ) ≈ Gmax − 7.7 dB."""
    return 10 ** ((gmax_dbi - 7.7) / 20)


def omni(phi: np.ndarray, gmax: float) -> np.ndarray:
    return np.full(np.shape(phi), float(gmax))


def f1245(phi: np.ndarray, gmax: float) -> np.ndarray:
    phi = np.maximum(np.abs(np.asarray(phi, dtype=float)), 1e-6)
    dl = d_over_lambda(gmax)
    g1 = 2 + 15 * np.log10(dl)
    phim = 20 / dl * np.sqrt(max(gmax - g1, 0.0))
    main = gmax - 2.5e-3 * (dl * phi) ** 2
    if dl > 100:
        phir = 12.02 * dl**-0.6
        knee = max(phim, phir)
        side = np.where(phi < 48, 29 - 25 * np.log10(phi), -13.0)
        g = np.where(phi < phim, main, np.where(phi < knee, g1, side))
    else:
        knee = max(phim, 39.8 / dl)
        side = np.where(phi < 48, 39 - 5 * np.log10(dl) - 25 * np.log10(phi), -3 - 5 * np.log10(dl))
        g = np.where(phi < phim, main, np.where(phi < knee, g1, side))
    return np.minimum(g, gmax)


def f699(phi: np.ndarray, gmax: float) -> np.ndarray:
    phi = np.maximum(np.abs(np.asarray(phi, dtype=float)), 1e-6)
    dl = d_over_lambda(gmax)
    g1 = 2 + 15 * np.log10(dl)
    phim = 20 / dl * np.sqrt(max(gmax - g1, 0.0))
    main = gmax - 2.5e-3 * (dl * phi) ** 2
    if dl > 100:
        phir = 15.85 * dl**-0.6
        side = np.where(phi < 48, 32 - 25 * np.log10(phi), -10.0)
        g = np.where(phi < phim, main, np.where(phi < max(phim, phir), g1, side))
    else:
        side = np.where(phi < 48, 52 - 10 * np.log10(dl) - 25 * np.log10(phi), 10 - 10 * np.log10(dl))
        g = np.where(phi < phim, main, np.where(phi < max(phim, 100 / dl), g1, side))
    return np.minimum(g, gmax)


def bt419(phi: np.ndarray, gmax: float, f_hz: float) -> np.ndarray:
    """Peak gain minus directivity discrimination: 0 dB within 20°, linear to the band maximum at 60°."""
    phi = np.abs(np.asarray(phi, dtype=float))
    dmax = 6.0 if f_hz < 174e6 else 12.0 if f_hz < 470e6 else 16.0
    disc = np.clip((phi - 20.0) / 40.0, 0.0, 1.0) * dmax
    return gmax - disc


def ra1631(phi: np.ndarray, gmax: float) -> np.ndarray:
    phi = np.maximum(np.abs(np.asarray(phi, dtype=float)), 1e-6)
    dl = 10 ** (gmax / 20) / np.pi
    g1 = -1 + 15 * np.log10(dl)
    phim = 20 / dl * np.sqrt(max(gmax - g1, 0.0))
    phir = 15.85 * dl**-0.6
    g = np.select(
        [phi < phim, phi < phir, phi < 10, phi < 34.1, phi < 80, phi < 120],
        [
            gmax - 2.5e-3 * (dl * phi) ** 2,
            np.full_like(phi, g1),
            29 - 25 * np.log10(phi),
            34 - 30 * np.log10(phi),
            -12.0,
            -7.0,
        ],
        -12.0,
    )
    return np.minimum(g, gmax)


def s465(phi: np.ndarray, gmax: float) -> np.ndarray:
    phi = np.maximum(np.abs(np.asarray(phi, dtype=float)), 1e-6)
    return np.minimum(np.where(phi < 48, 32 - 25 * np.log10(phi), -10.0), gmax)


def s672(psi: np.ndarray, gmax: float, psi0: float) -> np.ndarray:
    """Satellite roll-off around boresight; `psi0` is half the 3 dB beamwidth."""
    x = np.abs(np.asarray(psi, dtype=float)) / psi0
    ls, a, b = -20.0, 2.58, 6.32
    far = gmax + ls + 20 - 25 * np.log10(np.maximum(x, 1e-9))
    g = np.where(x <= a, gmax - 3 * x**2, np.where(x <= b, gmax + ls, np.maximum(far, 0.0)))
    return np.minimum(g, gmax)


RECEIVER_PATTERNS: dict[str, Callable[..., np.ndarray]] = {
    "omni": omni,
    "F.1245": f1245,
    "F.699": f699,
    "RA.1631": ra1631,
    "S.465": s465,
}


def receiver_gain(pattern: str, phi: np.ndarray, gmax: float, f_hz: float) -> np.ndarray:
    if pattern == "BT.419":
        return bt419(phi, gmax, f_hz)
    return RECEIVER_PATTERNS[pattern](phi, gmax)
