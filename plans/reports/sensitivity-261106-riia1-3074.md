# Sensitivity report: IFIC 3074, model riia-1

- Receiver source: `generic-m4`; `as_of`: 2026-11-06.
- Each `assumption` input below is moved to one end of its range and the issue is re-assessed. The perturbation list is fixed in `backend/src/ific/riia/sensitivity.py`, so the report is deterministic.
- A flip is a quantified hazard whose outcome changes to or from `exceeds`. Shifts are in the worst median `exceedance_db` of each hazard assessed in both runs.

## Outcome-sensitive assumptions

- `adjacent_extent`: 33 outcome flips
- `carrier_in_channel`: 5 outcome flips
- `class_values`: 8 outcome flips
- `dist:fixed:pointing_elev_deg`: 25 outcome flips
- `dist:fss_es:pointing_elev_deg`: 1 outcome flips
- `full_duty_cycle`: 117 outcome flips
- `peak_gain`: 117 outcome flips

## Perturbations

| Assumption | End | Change | Flips | Median shift | Max abs shift | Mean Δ share violating |
|---|---|---|---|---|---|---|
| `peak_gain` | low | Satellite gain −10 dB (beam not pointed at Finland) | 117 | -10.0 dB | +10.0 dB | -11.4 pp |
| `full_duty_cycle` | low | Activity factor 10 % (−10 dB) | 117 | -10.0 dB | +10.0 dB | -11.4 pp |
| `carrier_in_channel` | low | Carrier placed uniformly in its group band | 5 | +0.0 dB | +14.5 dB | -0.5 pp |
| `adjacent_extent` | low | Adjacent range 1.0 × B_n | 19 | +0.0 dB | +20.1 dB | +0.8 pp |
| `adjacent_extent` | high | Adjacent range 5.0 × B_n | 14 | +0.0 dB | +77.6 dB | -1.7 pp |
| `dist:fixed:pointing_elev_deg` | low | Fixed links point at 0–1° | 13 | -0.1 dB | +3.8 dB | -0.7 pp |
| `dist:fixed:pointing_elev_deg` | high | Fixed links point at 0–10° | 12 | +0.0 dB | +1.1 dB | +0.1 pp |
| `dist:radio_astronomy:pointing_elev_deg` | low | Telescopes point at 30–90° | 0 | -0.3 dB | +7.2 dB | +0.0 pp |
| `dist:fss_es:pointing_elev_deg` | high | FSS dishes point at 5–30° | 1 | -0.0 dB | +3.8 dB | -0.7 pp |
| `class_values` | high | Fixed pattern F.699 (peak envelope) instead of F.1245 (average) | 8 | +5.4 dB | +5.4 dB | +4.0 pp |

## Flips (first 10 per perturbation)

- `peak_gain` (low): 95500027 adjacent:fss_es exceeds → meets; 103500416 cochannel:mss_es exceeds → screened_out; 103500416 cochannel:rnss exceeds → screened_out; 103500417 cochannel:mss_es exceeds → screened_out; 103500417 cochannel:rnss exceeds → screened_out; 109500876 cochannel:fss_es exceeds → meets; 117520318 adjacent:fixed exceeds → meets; 117520318 adjacent:mss_es exceeds → meets; 117520318 cochannel:mss_es exceeds → meets; 117520372 adjacent:mss_es exceeds → meets; … 107 more
- `full_duty_cycle` (low): 95500027 adjacent:fss_es exceeds → meets; 103500416 cochannel:mss_es exceeds → screened_out; 103500416 cochannel:rnss exceeds → screened_out; 103500417 cochannel:mss_es exceeds → screened_out; 103500417 cochannel:rnss exceeds → screened_out; 109500876 cochannel:fss_es exceeds → meets; 117520318 adjacent:fixed exceeds → meets; 117520318 adjacent:mss_es exceeds → meets; 117520318 cochannel:mss_es exceeds → meets; 117520372 adjacent:mss_es exceeds → meets; … 107 more
- `carrier_in_channel` (low): 119500051 cochannel:fixed exceeds → meets; 125512022 cochannel:fss_es exceeds → meets; 126500107 cochannel:fixed exceeds → meets; 126545114 cochannel:fixed exceeds → meets; 309500876 cochannel:fixed exceeds → meets
- `adjacent_extent` (low): 119500051 adjacent:radio_astronomy exceeds → not_applicable; 124520187 adjacent:radio_astronomy exceeds → not_applicable; 124520220 adjacent:mss_es exceeds → not_applicable; 124520220 adjacent:radiolocation exceeds → not_applicable; 124520220 adjacent:radionavigation exceeds → not_applicable; 124520220 adjacent:rnss exceeds → not_applicable; 124545392 adjacent:radio_astronomy exceeds → not_applicable; 125520111 adjacent:fixed exceeds → meets; 125545393 adjacent:rnss exceeds → screened_out; 125545395 adjacent:radio_astronomy exceeds → not_applicable; … 9 more
- `adjacent_extent` (high): 95500027 adjacent:radio_astronomy not_applicable → exceeds; 123520028 adjacent:mss_es not_applicable → exceeds; 123520028 adjacent:radiolocation not_applicable → exceeds; 124520188 adjacent:radio_astronomy not_applicable → exceeds; 125500068 adjacent:radiolocation screened_out → exceeds; 125520053 adjacent:radionavigation meets → exceeds; 125545393 adjacent:metsat_es not_applicable → exceeds; 125545393 adjacent:radionavigation screened_out → exceeds; 125545396 adjacent:radionavigation not_applicable → exceeds; 126500063 adjacent:mss_es not_applicable → exceeds; … 4 more
- `dist:fixed:pointing_elev_deg` (low): 119500051 cochannel:fixed exceeds → meets; 124520194 adjacent:fixed exceeds → meets; 124520204 adjacent:fixed exceeds → meets; 124520204 cochannel:fixed exceeds → meets; 124520214 cochannel:fixed exceeds → meets; 125512022 cochannel:fixed exceeds → meets; 125512023 cochannel:fixed exceeds → meets; 126545114 cochannel:fixed exceeds → meets; 309500876 cochannel:fixed exceeds → meets; 319500051 cochannel:fixed exceeds → meets; … 3 more
- `dist:fixed:pointing_elev_deg` (high): 95500027 adjacent:fixed meets → exceeds; 95500027 cochannel:fixed meets → exceeds; 103500416 cochannel:fixed meets → exceeds; 109500876 cochannel:fixed meets → exceeds; 124520173 cochannel:fixed meets → exceeds; 303500416 cochannel:fixed meets → exceeds; 322500245 adjacent:fixed meets → exceeds; 322500245 cochannel:fixed meets → exceeds; 324520173 cochannel:fixed meets → exceeds; 324520204 adjacent:fixed meets → exceeds; … 2 more
- `dist:fss_es:pointing_elev_deg` (high): 125512023 cochannel:fss_es meets → exceeds
- `class_values` (high): 95500027 cochannel:fixed meets → exceeds; 124520173 cochannel:fixed meets → exceeds; 126545127 adjacent:fixed meets → exceeds; 322500245 cochannel:fixed meets → exceeds; 324520173 cochannel:fixed meets → exceeds; 324520204 adjacent:fixed meets → exceeds; 324520214 adjacent:fixed meets → exceeds; 325500168 adjacent:fixed meets → exceeds

## Not perturbed

- `grid`: Grid density changes only the number of sites, not any per-receiver level; not re-run for cost.
- `sample_size`: Fixed by the method (N rule); reproducibility is checked by the determinism test.
- `circular_orbit`: No alternative orbit model in riia-1.
- `generic_population`: The alternative is the stations source, a follow-up plan.
