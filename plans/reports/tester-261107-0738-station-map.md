# Station map with P.1546 contours: verification

Plan: [261107-0720-station-map](../261107-0720-station-map/plan.md). Run on 2026-11-07, Europe/Helsinki.

## Result

The automated gates pass and the page works in the browser. One acceptance item is still open: a person has to
check the T/R 25-08 values against the PDF. Until then the module carries an `UNVERIFIED` note.

## Commands

| Command | Result |
|---|---|
| `mise run lint` (ruff check, ruff format --check, oxlint) | Pass, no warnings |
| `uv run pytest -q tests/test_p1546.py tests/test_tr2508.py tests/test_stations_api.py tests/test_special_interest.py tests/test_api.py` | 205 passed in 4.1 s |
| `bun run build` | Pass. The main chunk is 715 kB, the lazy `stations` chunk 1.1 MB and the MapLibre worker 519 kB |
| `geo.ts` check (bun script) | An azimuth-0 arrow points north and an azimuth-90 arrow points east. A 100 km circle at 70° N has a radius error of 0.000% against the haversine distance. This check uses the same spherical model, so it confirms the ring maths, not the Earth model |

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | The engine matches the reference | All 52 reference cases pass within 0.001 dB (tighter than the planned 0.1 dB). The largest deviation is 5×10⁻⁵ dB. **0 skipped**: every case has terrain inputs, and the engine accepts TCA, tropospheric-scatter, slope and transmitter-clutter inputs. The set does not cover `0 < h1 < 10 m`, warm sea or `q ≠ 50`; property tests cover those |
| 2 | The trigger table is sourced | It is cited to T/R 25-08 ed. 6 June 2025, A1.2.3, with the PDF SHA-256. The correction is 10·log10 (the plan's 6·log10 was wrong). Frequencies outside 29.7–470 MHz return `None`. A human check is **pending** |
| 3 | The list endpoint carries every contour input | 873 features. 444 have a contour. Reasons for no contour: `no_power` 328, `outside_p1546_range` 98, `missing_tx_frequency` 3 |
| 4 | Radius is consistent with the engine | For every exact contour, E recomputed at `radius_km` equals the threshold within 0.05 dB (`test_contour_radius_reproduces_threshold`) |
| 5 | The page renders | All stations show on OSM tiles with attribution, in light and dark themes. There are 444 discs, and arrows for the 188 directional stations with an azimuth |
| 6 | Controls work | Five slider key presses changed the URL once to `thr=35` and sent one `GET /api/stations?…threshold_dbuv=35` (seen in the API log). The 3D toggle tilts the map to 55° and shows columns. `ex=40` scales them. Tooltips give real metres |
| 7 | Detail is reachable and shareable | `?station=13` opens the sheet for station 5931 with Parameters, Contour, P.1546 intermediates, M4 overlaps, Quality flags and Source. A click hitting 11 stations opened the picker |
| 8 | The legend explains the drawing | It states the model, the T/R 25-08 citation, the user threshold, and the solid/dashed and arrow keys |
| 9 | Checks pass | See the table above. Screenshots are below |

The first uncached `/api/stations` call took 0.14 s, against a 1 s target.

## Screenshots (`assets/`)

- `station-map-2d-light.png`: 2D in the light theme, hovering station 645803.
- `station-map-2d-dark.png`: 2D in the dark theme.
- `station-map-3d-light.png`, `station-map-3d-dark.png`: 3D zoomed into central Finland, with columns and arrows.
- `station-sheet-dark.png`: the detail sheet for row 13.
- `station-map-phone-light.png`: 390 px wide, with no horizontal scroll. The blank strip under the map is from
  the full-page capture resizing the viewport after the canvas was sized.
- `station-map-api-error-light.png`: the error alert and retry button, captured while the API was down.

## Environment notes

- **Existing dev server.** The Vite dev server on :5173 (PID 67580, not started here) served a stale optimised
  copy of the new `maplibre-gl` dependency and returned 504 for it. I left it running. It needs a restart to
  load `/stations` in dev mode. Browser checks used `vite preview` of the production build on :4173 instead,
  which I started and then stopped.
- **API.** The API on :8000 (PID 32153, not started here) exited during the checks. I started `uv run ific serve`
  for the rest of the run and stopped it afterwards. Nothing listens on :8000 or :4173 now.

## Defects found and fixed during verification

- **Blank map.** MapLibre 6 looks for its worker next to its own module, which the bundle does not keep. Fixed
  with `setWorkerUrl` and Vite's `?worker&url`.
- **Map container collapsed.** MapLibre's unlayered CSS overrode Tailwind's `absolute inset-0`, so the canvas fell
  back to 300 px. Fixed by putting the layout on a wrapper.
- **Discs hid the map.** 444 stacked discs at 12% fill turned Finland solid blue. The fill is now 4%.
- **Columns invisible.** A 400 m column footprint was sub-pixel at country zoom. It is now 2 km, and the columns
  draw above the site dots.

## Re-run after the code review

The [review](code-reviewer-261107-0738-station-map.md) found one High, one Medium and seven Low issues. The High,
the Medium and six of the Lows (L1–L6) are fixed. L7 is kept on purpose.

| Command or check | Result |
|---|---|
| `mise run lint` | Passes |
| The five plan test files | 210 passed (5 new tests guard incomplete rows) |
| `bun run build` | Passes |
| `?band=1,1,2` | The URL becomes `band=1,2`, and bands 1 and 2 show as pressed |
| Turning off the last band | The URL becomes `band=none`, and every toggle shows as unpressed |

The preview server used for this check was stopped afterwards.
