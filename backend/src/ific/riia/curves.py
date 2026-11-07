"""Exceedance curves, per-receiver time quantiles, population risk curves and criterion checks.

"Exceeds" is strict throughout: a consequence equal to the criterion level does not exceed it.
"""

import numpy as np

GRID_START_DB, GRID_STOP_DB, GRID_STEP_DB = -40.0, 40.0, 1.0
GRID_DB = np.arange(GRID_START_DB, GRID_STOP_DB + GRID_STEP_DB / 2, GRID_STEP_DB)


def ccdf(samples: np.ndarray, x: np.ndarray) -> np.ndarray:
    """F(x) = share of samples strictly above x."""
    s = np.sort(np.asarray(samples, dtype=float))
    return 1.0 - np.searchsorted(s, np.asarray(x, dtype=float), side="right") / s.size


def exceeded_for(samples: np.ndarray, time_pct: float) -> np.ndarray:
    """X_r(p): the k-th largest sample along the last axis, k = floor(p·T/100) (0-based).

    A receiver exceeds level L for more than p % of the time exactly when X_r(p) > L.
    """
    s = np.asarray(samples, dtype=float)
    t = s.shape[-1]
    k = min(int(np.floor(time_pct / 100.0 * t)), t - 1)
    return -np.partition(-s, k, axis=-1)[..., k]


def violates(x_at_p: np.ndarray, level_db: float) -> np.ndarray:
    return np.asarray(x_at_p) > level_db


def risk_curve(x_at_p: np.ndarray, grid: np.ndarray = GRID_DB) -> np.ndarray:
    """L_p(x) = share of receivers with X_r(p) > x, on the fixed grid."""
    return ccdf(x_at_p, grid)
