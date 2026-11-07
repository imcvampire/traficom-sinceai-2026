"""ECC Recommendation T/R 25-08 indicative coordination thresholds for land mobile systems, 29.7-470 MHz.

Source: T/R 25-08 "Planning criteria and cross-border coordination of frequencies for land mobile systems
in the range 29.7-470 MHz", approved 15 January 1990, latest amended 6 June 2025 (FM#110), ECC document
database https://docdb.cept.org/document/909, file TR_25-08.pdf (download 4789, SHA-256
d6460dd8fcc618cf2164c96d3fd0ab3a2c45cd78265a3130f7aa516e2d35c52c). Values are Annex 1 section A1.2.3
(page 6) and the bandwidth conversion formula on page 7.

The thresholds hold co-channel, at 50 % locations, 10 % time and a 10 m receiving antenna height, within a
25 kHz reference bandwidth, at the border line. For channel spacing above 25 kHz with a uniform spectral
power distribution, ``BC = 10 log10(channel spacing / 25 kHz)`` dB is added. Callers pass the occupied
bandwidth as the channel spacing; the result says so in ``note``.

The document gives adjacent ranges as "between 29.7 and 47 MHz", "between 47 and 108 MHz" and so on. A
shared edge is assigned to the higher range, and 470 MHz belongs to the top range.

Not covered here: the Annex 3 and Annex 4 triggers between narrowband and >1 MHz systems in 410-430 and
450-470 MHz, which are per 5 MHz at 3 m or per 25 kHz under preferential regimes. Bilateral agreements
override these indicative values.

UNVERIFIED: transcribed from the PDF text on 2026-11-07. A person still has to check each value against
page 6 of the PDF and record their name and the date here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

TIME_PCT = 10.0
LOC_PCT = 50.0
RX_HEIGHT_M = 10.0
REFERENCE_BW_KHZ = 25.0
RANGE_MHZ = (29.7, 470.0)

CITATION = "ECC T/R 25-08 (ed. 6 June 2025), Annex 1 A1.2.3"


@dataclass(frozen=True)
class Trigger:
    lower_mhz: float
    upper_mhz: float
    e_dbuv_m: float
    reference_bw_khz: float
    note: str


TRIGGERS: tuple[Trigger, ...] = (
    Trigger(29.7, 47.0, 0.0, REFERENCE_BW_KHZ, "A1.2.3: 0 dB(uV/m), 29.7-47 MHz"),
    Trigger(47.0, 108.0, 6.0, REFERENCE_BW_KHZ, "A1.2.3: 6 dB(uV/m), 47-108 MHz"),
    Trigger(108.0, 380.0, 12.0, REFERENCE_BW_KHZ, "A1.2.3: 12 dB(uV/m), 108-380 MHz"),
    Trigger(380.0, 400.0, 18.0, REFERENCE_BW_KHZ, "A1.2.3: 18 dB(uV/m), 380-400 MHz"),
    Trigger(400.0, 470.0, 20.0, REFERENCE_BW_KHZ, "A1.2.3: 20 dB(uV/m), 400-470 MHz"),
)


@dataclass(frozen=True)
class TriggerResult:
    e_dbuv_m: float
    base_dbuv_m: float
    bandwidth_correction_db: float
    citation: str
    note: str


def _band(f_mhz: float) -> Trigger | None:
    for band in TRIGGERS:
        if band.lower_mhz <= f_mhz < band.upper_mhz:
            return band
    if f_mhz == TRIGGERS[-1].upper_mhz:
        return TRIGGERS[-1]
    return None


def trigger(f_mhz: float, bandwidth_hz: int | None) -> TriggerResult | None:
    """Coordination trigger for a co-channel land mobile assignment, or None outside 29.7-470 MHz.

    ``bandwidth_hz`` stands in for the channel spacing. Unknown or up to 25 kHz gets no correction.
    """
    band = _band(f_mhz)
    if band is None:
        return None
    correction = 0.0
    note = band.note
    if bandwidth_hz is not None and bandwidth_hz > band.reference_bw_khz * 1000:
        correction = 10 * math.log10(bandwidth_hz / (band.reference_bw_khz * 1000))
        note += "; bandwidth used as channel spacing, uniform spectral power assumed"
    elif bandwidth_hz is None:
        note += "; bandwidth unknown, no bandwidth conversion"
    return TriggerResult(
        e_dbuv_m=band.e_dbuv_m + correction,
        base_dbuv_m=band.e_dbuv_m,
        bandwidth_correction_db=correction,
        citation=CITATION,
        note=note,
    )
