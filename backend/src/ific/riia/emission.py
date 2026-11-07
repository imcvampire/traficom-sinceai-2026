"""Unwanted-emission attenuation of a space-station carrier and receiver selectivity."""

import numpy as np

OOB_CITE = (
    "Rec. ITU-R SM.1541-6, Annex 5 (space services): 40·log10(F/50 + 1) dBsd, F in % of B_n from the edge"
)
SPURIOUS_CITE = (
    "RR Appendix 3, Table II (space services): 43 + 10·log10(P) or 60 dBc, whichever is less stringent"
)
OOB_EDGE_PCT = 200.0


def oob_attenuation_db(offset_pct: np.ndarray) -> np.ndarray:
    """SM.1541 out-of-band mask; `offset_pct` is the offset from the carrier edge in % of B_n."""
    return 40 * np.log10(np.clip(np.asarray(offset_pct, dtype=float), 0.0, None) / 50 + 1)


def spurious_attenuation_db(power_dbw: float) -> float:
    return float(min(43 + power_dbw, 60.0))


def unwanted_attenuation_db(gap_hz: np.ndarray, bn_hz: float, power_dbw: float) -> np.ndarray:
    """Attenuation at `gap_hz` beyond the carrier edge: OoB domain to 200 % of B_n, then spurious."""
    pct = np.asarray(gap_hz, dtype=float) / bn_hz * 100.0
    return np.where(pct <= OOB_EDGE_PCT, oob_attenuation_db(pct), spurious_attenuation_db(power_dbw))


def acir_db(mask_db: np.ndarray, acs_db: float) -> np.ndarray:
    """Adjacent-channel interference ratio: transmitter leakage and receiver selectivity added in power."""
    return -10 * np.log10(10 ** (-np.asarray(mask_db) / 10) + 10 ** (-acs_db / 10))
