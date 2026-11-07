"""`terra-1` version, assumptions and constants; docs/terrestrial-land-mobile.md is the source of truth."""

MODEL_VERSION = "terra-1"

LAND_MOBILE_CLASSES = ("FB", "ML")
TX_NOTICE_TYPES = ("T12", "G12", "T14", "G14")
RX_NOTICE_TYPES = ("T13", "G13")
NEIGHBOURS = ("RUS", "EST", "NOR", "S", "LVA", "LTU")

SCREENING_RANGE_KM = 1000.0
TIER1_MARGIN_DB = 3.0
MAX_BORDER_POINTS = 25
PATH_STEP_KM = 1.0
BORDER_SPACING_KM = 5.0
EIRP_TO_ERP_DB = 2.15

ASSUMPTIONS: dict[str, str] = {
    "A-T-FLAT": "Flat terrain and no clutter: P.1546 without terrain clearance angle or terminal heights "
    "(tca_not_applied). Conservative for screening; overstates reach over hills and into towns.",
    "A-T-ANT-OMNI": "No antenna diagram in the notice: the antenna is treated as non-directional at the "
    "notified maximum power.",
    "A-T-ANT-DIAG": "Directional antenna: the attenuation at the bearing to each Finnish point is "
    "interpolated linearly from fxm_ant_diag.",
    "A-T-ANT-MAX": "Several antenna rows: the one with the highest e.r.p. is assessed.",
    "A-T-EIRP-ERP": "Power notified as e.i.r.p. (pwr_eiv = I) is converted to e.r.p. by subtracting "
    "2.15 dB (RR Nos. 1.161-1.162: half-wave dipole gain relative to isotropic).",
    "A-T-H1-AGL": "h1 is the antenna height above ground (hgt_agl), not the effective height of Annex 5 "
    "section 3, because the effective height needs terrain data.",
    "A-T-DMIN-1KM": "A site less than 1 km from the nearest Finnish point is evaluated at 1 km, the P.1546 "
    "lower limit without the short-path antenna-height input.",
    "A-T-SEA-COLD": "Sea segments are cold sea (Baltic, Gulf of Finland, Barents Sea).",
    "A-T-LAND-MASK": "Land and sea along the path come from Natural Earth 1:10m land rasterised at 0.01°; "
    "short coastal segments can be misclassified. Lakes count as land, and so does everything outside the "
    "clip box (0-45°E, 50-75°N), including the Barents Sea east of 45°E.",
    "A-T-BORDER-SAMPLE": "The Finnish border and coastline are sampled every 5 km (Natural Earth 1:50m); "
    "the 25 nearest points are evaluated.",
    "A-T-TIER1-3DB": "Tier 1 screens out a notice whose upper bound at the nearest Finnish point (the larger "
    "of the all-sea and all-land values; below about 100 MHz land can exceed cold sea) is at least 3 dB "
    "below the trigger.",
    "A-T-BW-CHANNEL": "The occupied bandwidth (bdwdth) stands in for the channel spacing or block size in "
    "the criterion's bandwidth correction.",
    "A-T-ECC-NONPREF": "PCI and synchronisation-frequency alignment are not in the notice: the most "
    "restrictive ECC/REC/(11)04 border level (41 dB(µV/m)/5 MHz) is assessed.",
    "A-T-BILATERAL": "Bilateral agreements (FIN–RUS, FIN–EST, Nordic) override the indicative criteria; "
    "their contents are not in the repository.",
    "A-T-ECC-RUS": "Russia's CEPT membership is suspended: ECC criteria applied to RUS notices are "
    "indicative, and the FIN–RUS bilateral agreement governs.",
    "A-T-PUB-PARTS": "Publication part meanings (1 received, 2 recorded with findings, 3 returned) are "
    "inferred from the data and to be confirmed against the BR IFIC Preface.",
}
