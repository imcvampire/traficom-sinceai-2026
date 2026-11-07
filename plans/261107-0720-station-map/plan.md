---
title: Map page for special-interest stations, with P.1546 contours
description: A /stations map whose station radius is an ITU-R P.1546 field-strength contour. The propagation engine and T/R 25-08 trigger lookup are shared with the terrestrial side quest.
status: completed
mode: hard
priority: P1
effort: 2d
branch: main
tags: [frontend, api, map, propagation]
blockedBy: []
blocks: []
created: 2026-11-07
source: /ak-plan "Add a FE page to show these stations in a map ... Draw station with the characterisc of frequency like: a radius (if possible), height (if possible), etc." + "Use P.1546 propagation so it can be used to solve side-quest."
---

# Map page for special-interest stations, with P.1546 contours

## Outcome

A new `/stations` page shows every station in `ref.special_interest_station` on an OpenStreetMap basemap. Each
station is drawn with its radio characteristics:

- **Colour:** the frequency band of its TX frequency.
- **Radius:** the distance at which its field strength, predicted with **ITU-R P.1546**, falls to a threshold.
  The threshold is the T/R 25-08 coordination trigger where that recommendation covers the band, and a
  user-chosen value otherwise. The disc is the station's coordination zone.
- **Direction:** an arrow along its azimuth.
- **Height:** an extruded column for its antenna height, shown in a tilted 3D view.

The P.1546 engine and the T/R 25-08 lookup are standalone backend modules. The terrestrial side quest can then
compute the field strength a foreign notified station causes at the Finnish border or at a Finnish station by
calling the same code with the transmitter and receiver swapped.

## Evidence (inspected 2026-11-07)

| Source | Finding |
|---|---|
| `ref.special_interest_station` | 873 rows, all inside the Finland bounding box. 772 have a TX frequency within P.1546's range of 30–4000 MHz, and 444 of those have a radiated power. The other 328 in range have no power: all 320 FX fixed links and 8 MUUT. The other 98 are out of range: 9 MF/HF broadcast stations below 30 MHz, and 89 MUUT/MVV stations above 4 GHz. 3 stations have no TX frequency. Power type is `E` (ERP) wherever given. `effective_agl_m` is 1–317 m. 237 stations are directional (`D`), 188 of them with an azimuth. |
| ITU-R P.1546 reference code | [eeveetza/p1546](https://github.com/eeveetza/p1546) is a MATLAB/Octave implementation that its README says matches the reference version approved by ITU-R WP 3K. It includes `validateP1546.m`. The [ITU software copyright page](https://www.itu.int/en/ITU-R/study-groups/software-copyright-statements/Pages/default.aspx) lists the P.1546 script under OFCOM (Switzerland). No maintained Python port was found. Octave is not installed. |
| T/R 25-08 | The current edition covers land mobile 29.7–470 MHz (amended 6 June 2025, [ECC docdb](https://docdb.cept.org/document/category/ECC_Recommendations/review)). Its triggers are defined at 50% locations, 10% time and a 10 m receiving height, at the border line, per 25 kHz, with `+10·log10(channel spacing/25 kHz)` for wideband (A1.2.3, verified in the PDF on 2026-11-07; an earlier draft said `6·log10`). The 2008 table found online is superseded and must not be used. |
| Backend | `numpy` is already a dependency, added by the scoring work. The scoring plan (`plans/261106-2255-sat-severity-scoring/plan.md`, extension trace) names "P.1546 field strength against T/R 25-08" as its terrestrial follow-up and has not built it. |
| `frontend/` | React 19, Vite, TanStack Router and Query, shadcn/ui, Tailwind v4 tokens. No map library yet. |

## Decisions

| Decision | Choice | Why | Alternative rejected |
|---|---|---|---|
| Propagation model | A Python port of the WP 3K-approved P.1546 reference code ([eeveetza/p1546](https://github.com/eeveetza/p1546)), validated against that repo's validation cases | The brief names P.1546 for the side quest. Porting the approved reference and matching its outputs is the most credible path for criterion A. | Writing it from the Recommendation text alone: harder to prove correct. Running the MATLAB through Octave: a heavy runtime dependency that is not installed. |
| Port scope | Annex 5 steps for land, sea and mixed paths. Interpolation over time (1–50%), frequency and distance. Transmitter height `h1` handling, including negative values. Receiving-height correction. Location variability. | This covers the map and the side quest. | Terrain-clearance-angle correction: it needs a terrain model, so it is left out, reported as `tca_not_applied` and listed as a follow-up. |
| Engine boundary | `field_strength(f_mhz, t_pct, path: list[(kind, km)], h1_m, h2_m, erp_dbw, loc_pct=50, env=...) -> FieldResult`, which returns E in dBµV/m plus every intermediate value. Callers classify land and sea along the path. | The engine stays pure and testable. The map and the side quest differ only in how they build the path. | Engine-side coastline lookup: it couples the engine to geodata. |
| `h1` without terrain | `h1 = effective_agl_m`, the flat-terrain approximation, flagged `h1_flat_terrain` | The repo has no terrain model. Finland is mostly flat, and the assumption stays visible. | Loading a DEM: a large dataset and its own phase. Listed as a follow-up. |
| Map path type | All land, flagged `path_assumed_land`. Coastal stations will understate their reach over the sea. | The map is indicative. The side quest adds a land/sea mask for cross-border paths. | |
| Contour threshold | Where T/R 25-08 covers the station's band (29.7–470 MHz), use its trigger for the station's bandwidth. Otherwise use the page's threshold slider (default 30 dBµV/m). The sheet shows which source applied. | The reach then means "coordination zone" where a standard defines one, and the threshold is always stated where none does. | One global threshold: it ignores the only standard the brief names. |
| Prediction settings | 10% time, 50% locations, `h2 = 10 m`: the T/R 25-08 reference conditions. 1% and 50% time are selectable. | These are the coordination conditions. 50% time shows typical rather than interference-level reach. | |
| Radius solve | Bisection on distance between 1 and 1000 km. E is monotonic in distance, and P.1546 is only valid in that range. If the threshold is reached under 1 km, the radius is reported as below 1 km. If it isn't reached by 1000 km, the radius is reported as 1000 km or more. | Deterministic and auditable. | Inverting the curve tables directly: fragile across interpolation. |
| Stations without a contour | No disc. The sheet gives the reason: `no_power` (328), `outside_p1546_range` (98) or `missing_tx_frequency` (3). | No invented ERP. A horizon disc as a fallback would mean something different from the other discs. | A typical ERP per class: an invented input. |
| Directional antennas | A circle at the maximum ERP (worst case, since P.1546 has no antenna pattern), plus an azimuth arrow. Flagged `omni_worst_case`. **No beamwidth is derived or assumed.** | The data has no antenna patterns. A wedge would need a beamwidth for the 49 directional stations without gain, and an off-axis pattern for all 237 (ITU-R F.699/F.1245). The worst-case circle is safe for protection. | A beamwidth wedge with a 30° default: an invented number that judges would question. |
| Map library and basemap | `maplibre-gl` used directly, over OSM raster tiles with attribution. The tile URL comes from `VITE_MAP_TILE_URL`. In dark mode the raster paint is dimmed. | Free with no API key, and `fill-extrusion` supports height. | Leaflet: it has no 3D extrusion. |
| Height | `fill-extrusion` of a 2 km hexagon (400 m was sub-pixel at country zoom), height `effective_agl_m × exaggeration` (1–50×, default 20×), in 3D view at a 55° pitch | A real-scale mast is invisible at country zoom. Tooltips show real metres. | |
| Colour | Six ordered TX-frequency bins with a sequential palette from the `dataviz` skill | The data spans 1.5 MHz–27.5 GHz. | Licence class: it has no meaning, per Traficom. |
| Where calculations live | Backend: P.1546, the T/R 25-08 lookup, radius, band bin and flags. Frontend: polygon vertices only. | One auditable implementation, shared with the side quest. | |
| API placement | New `ific/propagation/` package (`p1546.py`, `tr2508.py`) and a `ific/stations.py` router, mounted with one `include_router` line in the shared `api.py` | This keeps edits to `api.py` minimal while the scoring agent works in it. | |

## Extension trace

The real next variant is the terrestrial side quest: a foreign land-mobile notice in IFIC 3076 acting on Finland.

The stable contracts are:
- `p1546.field_strength(...)`;
- `tr2508.trigger(f, bw)`;
- the `FieldResult` record of inputs, intermediates and assumptions.

What would change:
- The caller builds the path from the notice's coordinates to the border or a Finnish station, classified into
  land and sea with a coastline mask.
- The comparison runs E against the trigger at the border.

Phase 01 proves the boundary: it validates mixed land/sea paths against the reference cases, even though the map
uses land paths only. No side-quest code is built here.

## Phases

| # | Phase | Status | Depends on |
|---|---|---|---|
| 01 | [P.1546 engine](phase-01-p1546-engine.md) | completed | — |
| 02 | [T/R 25-08 trigger table](phase-02-tr2508-triggers.md) | completed | — |
| 03 | [Stations API with contours](phase-03-stations-api.md) | completed | 01, 02 |
| 04 | [Map page](phase-04-map-page.md) | completed | 03 |
| 05 | [Docs and verification](phase-05-docs-and-verify.md) | completed | 04 |

Phases 01 and 02 own disjoint files and can run in parallel.

## Acceptance criteria

1. **The engine matches the reference code.** `p1546.field_strength` reproduces every in-scope case in the
   reference repo's validation set within 0.1 dB, including land, sea and mixed paths, `h1` below 10 m and
   negative, and 1%, 10% and 50% time. Cases needing terrain-clearance-angle correction are listed as skipped,
   with their count.
2. **The trigger table is sourced.** `tr2508.trigger` returns the current edition's values, transcribed with a
   citation (document, edition date, table) and the wideband correction. Frequencies outside 29.7–470 MHz return
   `None`.
3. **The list endpoint carries every contour input.** `GET /api/stations?time_pct=10&threshold_dbuv=30` returns
   873 features. Each has the station parameters, `band_bin`, `quality_flags`, `source_row`, and a `contour`
   object with `radius_km`, `bound` (`exact`, `below_1km` or `at_least_1000km`), `threshold_dbuv`,
   `threshold_source` (`tr2508` or `user`), `time_pct`, `h1_m`, `h2_m`, `erp_dbw` and `assumptions`. When there
   is no contour, `contour` is null and a reason is given.
4. **Radius is consistent with the engine.** For every exact contour, the field strength recomputed at
   `radius_km` equals the threshold within 0.05 dB (property test).
5. **The page renders.** `/stations` shows all stations on OSM tiles with attribution, in light and dark themes.
   Contour discs appear for the 444 stations with power in range, and azimuth arrows for the 188 directional
   stations that have an azimuth.
6. **Controls work.** The threshold slider and time selector re-fetch contours (debounced). The 3D toggle and
   exaggeration slider work, and tooltips show real metres.
7. **Detail is reachable and shareable.** Clicking a shared site lists all of its stations. The sheet shows
   parameters, the contour inputs and assumptions, M4 overlaps, quality flags and `source_row`. All state is in
   the URL.
8. **The legend explains the drawing.** It states the model ("ITU-R P.1546, 10% time, 50% locations, receiver
   10 m, land path, flat terrain") and where the threshold comes from.
9. **Checks pass.** `mise run lint`, the backend tests for these phases and `bun run build` pass. Screenshots in
   2D and 3D are in the phase 05 report.

## Outcome (2026-11-07)

All phases are done. The evidence is in [the tester report](../reports/tester-261107-0738-station-map.md) and
the docs are in [docs/propagation.md](../../docs/propagation.md). These deviations were driven by evidence:

- **Wideband correction.** It is `10·log10`, per the 2025 PDF, not `6·log10`.
- **Engine inputs.** The engine also accepts the optional terrain inputs (TCA, tropospheric scatter, slope,
  transmitter clutter). So none of the 52 reference cases is skipped, and the tolerance is 0.001 dB instead of
  0.1 dB.
- **Radius cache.** Radii are cached per physical input (`f`, `t`, `h1`, e.r.p., threshold) instead of per
  `(sha, t, threshold)`, so a data reload cannot serve stale values.
- **Bisection.** It runs in log-distance to 1e-7, not to 0.01 km. At 0.01 km, the 0.05 dB consistency criterion
  would fail near 1 km.
- **Disc fill.** It is 4% opacity, not 12%, because 444 overlapping discs hid the basemap.
- **Columns.** They have a 2 km footprint and draw above the site dots.
- **Extra URL params.** `contours=off` and `ex` are in the URL, so all state is.

Open item: a person must check the T/R 25-08 values against the PDF and replace the `UNVERIFIED` note in
`tr2508.py`.

## Risks

| Risk | Mitigation |
|---|---|
| The port has subtle errors in interpolation or `h1` handling. | Acceptance criterion 1 rests on the reference validation set. Intermediate values are returned so a mismatch can be located. |
| The reference code's licence doesn't permit a port. | Phase 01 checks the licence first. If porting isn't allowed, implement from the Recommendation text and still validate against the published cases, with attribution. |
| The P.1546 tabulated curves must be obtained. | Take them from the reference repo or the ITU Recommendation's tabulation files, store them as a checked data file with source and version, and test a few known table values. |
| The T/R 25-08 values are transcribed wrongly. | Each value is cited in code, and a person checks them against the PDF (phase 02 task). |
| The flat-terrain and land-only assumptions overstate or understate reach. | They are flagged per station and stated in the legend. Terrain and a coastline mask are follow-ups that the side quest also needs. |
| A threshold change makes the request slow. | 444 bisections of about 30 vectorised evaluations each. Cache by `(time_pct, threshold)`. Target under 1 s, measured in phase 03. |
| Edits to `api.py` collide with the scoring agent. | One `include_router` line only. Re-read the file before editing. |
| Losing internet removes the basemap. | Stations and discs still render, and the page shows a notice. |

## Coordination

- The scoring plan's terrestrial follow-up should import `ific.propagation.p1546` and `tr2508` rather than build
  its own. Tell the scoring agent's owner once phase 01 lands.
- The scoring agent's pending phase 06 excludes BC/BT and stations without a class, which contradicts Traficom's
  guidance that class is irrelevant. That agent's owner should revisit it.

## Follow-ups (not in this plan)

- Terrain-clearance-angle correction and terrain-based `h1`, from a DEM.
- Coastline land/sea mask for mixed paths. The side quest needs this first.
- Antenna patterns (F.699/F.1245) for directional contours.

## Unresolved questions

- Is the default 30 dBµV/m threshold acceptable outside T/R 25-08's range, or should the page start without
  discs until the user picks a threshold?
