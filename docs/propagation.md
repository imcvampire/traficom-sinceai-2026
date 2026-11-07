# Terrestrial propagation (`ific.propagation`)

Two standalone modules in `backend/src/ific/propagation/` are shared by the stations map (`/api/stations`, see
[frontend.md](frontend.md#stations-stations-map)) and the terrestrial side quest. Neither module touches the
database or HTTP.

## `p1546`: ITU-R P.1546-6 field strength

**Source.** This is a Python port of the MATLAB reference implementation approved by ITU-R Working Party 3K
(`P1546FieldStrMixed.m` v16, P1546 package 6.2, by Ivica Stevanovic of OFCOM CH). It was taken from
[eeveetza/p1546](https://github.com/eeveetza/p1546) at commit `0e42639`. The reference licence allows derivative
works that say what they changed, and the module docstring records those changes.

**Tables.** The 24 tabulated curves are in `data/p1546_tables.npz`. They were copied verbatim from the reference,
and `data/SOURCE.md` gives their layout and SHA-256.

**In scope:**
- Annex 5, steps 1–20.
- Land, cold-sea and warm-sea paths, plus mixed paths using the RRC-06 method.
- Time interpolation over 1–50%.
- Frequency interpolation and extrapolation over 30–4000 MHz.
- Distance interpolation over 1–1000 km, and paths shorter than 1 km.
- `h1` from 10 to 3000 m, below 10 m, and negative.
- Receiving-height correction for rural, suburban, urban, dense-urban and sea receivers.
- Location variability.
- The maximum field-strength cap.
- e.r.p. scaling.

These terrain-dependent terms run only when their inputs are passed:
- terrain clearance angle (`tca_deg`);
- tropospheric scatter (`eff1_deg` and `eff2_deg`);
- slope-path correction (`ha_m`, plus optional terminal ground heights);
- transmitter clutter (`r1_m`).

When a term's inputs are missing, the result lists the assumption it made instead, such as `tca_not_applied` or
`tropo_scatter_not_applied`.

**Not implemented (as in the reference):** Annex 7 (climatic regions) and Annex 5 §4.3a.

**Validation.** `tests/test_p1546.py` runs the reference validation set: 52 cases taken from the reference's
`validation_results` logs, in `tests/data/p1546_validation.csv`.

| Result | Value |
|---|---|
| Cases passed | All 52, with tolerance 0.001 dB |
| Largest deviation | 5×10⁻⁵ dB |
| Cases skipped | None. Every case has terrain inputs, and the engine accepts them. |

The cases cover land, sea and mixed paths, negative `h1`, 1/10/20/50% time, 90–2600 MHz, 0.1–235 km and all five
receiver environments. They do **not** cover `0 < h1 < 10 m`, warm sea, or `loc_pct ≠ 50`. Property tests cover
those cases instead:
- E does not increase with distance on land;
- an all-sea path gives a higher E than an all-land path;
- a mixed path lies between the two;
- location variability uses the inverse normal with σ = 12 dB for rural receivers.

The reference divides by `ln 2` instead of `log10 2` in the sea-path `h1 < 10 m` branch, eq. (11c). The port keeps
this so its results match the approved code.

**API**

```python
from ific.propagation import p1546

r = p1546.field_strength(
    f_mhz=450, t_pct=10,
    path=[("land", 30.0), ("sea_cold", 20.0)],  # zones from the transmitter
    h1_m=45,                                     # Annex 5 §3 height; the caller derives it
    h2_m=10, erp_dbw=30, loc_pct=50, rx_env="rural",
    ha_m=None, tca_deg=None, eff1_deg=None, eff2_deg=None,  # optional terrain inputs
)
r.e_dbuv_m      # dB(µV/m)
r.steps         # emax, per-type E, step-11 E, corrections, basic loss for 1 kW
r.assumptions   # e.g. ("tca_not_applied", "tropo_scatter_not_applied")
```

`field_strength` raises `ValueError` when any input is outside its range:
- f outside 30–4000 MHz;
- t outside 1–50%;
- total distance outside 0.001–1000 km;
- `h1` above 3000 m;
- a path shorter than 1 km without `ha_m`;
- `h2` below 1 m over land or below 3 m over sea;
- an unknown path kind or environment.

`erp_dbw = 30` is the 1 kW reference.

## `tr2508`: ECC T/R 25-08 coordination triggers

**Source.** ECC Recommendation T/R 25-08, latest amended 6 June 2025 (FM#110), from the
[ECC document database, document 909](https://docdb.cept.org/document/909). The values come from Annex 1 §A1.2.3
(page 6) and the bandwidth conversion formula on page 7. The PDF's SHA-256 is in the module docstring.

**Triggers.** The values are co-channel, at 50% locations, 10% time and 10 m receiving height, per 25 kHz, at the
border line. They are exposed as `TIME_PCT`, `LOC_PCT` and `RX_HEIGHT_M`.

| Range (MHz) | Trigger dB(µV/m) |
|---|---|
| 29.7–47 | 0 |
| 47–108 | 6 |
| 108–380 | 12 |
| 380–400 | 18 |
| 400–470 | 20 |

- **Range edges.** A shared edge belongs to the higher range, and 470 MHz belongs to the top range.
- **Wideband correction.** Above 25 kHz, `BC = 10·log10(channel spacing / 25 kHz)` dB is added. The recommendation
  allows this for uniform spectral power. The caller passes the occupied bandwidth as the channel spacing, and the
  result's `note` says so. Earlier drafts of the plan used `6·log10`, which the 2025 edition does not support.
- **Outside 29.7–470 MHz**, `trigger(f, bw)` returns `None`.
- **Not covered:** the Annex 3 and Annex 4 triggers between narrowband and >1 MHz systems in 410–430 and
  450–470 MHz.
- **Verification.** The module docstring carries an `UNVERIFIED` note until a person checks the values against
  the PDF and records their name and the date.

## How the stations map uses them

`ific.stations.contour` predicts each station with:
- `h1 = ha = effective_agl_m`, a flat-terrain assumption;
- an all-land path;
- `h2 = 10 m`;
- a rural receiver;
- 50% locations;
- the station's e.r.p., treated as omnidirectional.

It bisects in log-distance over 1–1000 km for the distance where E falls to the threshold. The threshold is the
T/R 25-08 trigger where one exists, and the request's `threshold_dbuv` otherwise.

The radius results are cached per physical input, so a data reload cannot serve stale values. The first full list
of 873 stations takes about 0.14 s.

## Use in the terrestrial assessment

The terrestrial land mobile model `terra-1` ([terrestrial-land-mobile.md](terrestrial-land-mobile.md)) consumes both
modules. `ific.terra.refdata` builds the `tr-25-08` criterion from `tr2508.TRIGGERS`, so those values are not copied.
`ific.terra.hazards` builds mixed land/sea paths from a Natural Earth 1:10m land mask (`data/ref/region_land.geojson`),
takes `h1` as the antenna height above ground over flat terrain, and calls `p1546.field_strength` at each criterion's
time %, location % and receiving height. Each finding stores the inputs, so `terra.hazards.reproduce` can re-run them.

Follow-ups shared with the map:
- terrain-based `h1` and the terrain clearance angle, from a DEM;
- the coastline mask for the station map (the terrestrial model has its own, `region_land.geojson`);
- antenna patterns (ITU-R F.699/F.1245).
