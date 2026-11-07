# Code review: station map (2026-11-07)

The review covered the new `ific.propagation` and `ific.stations` code, the `api.py` mount and the `/stations`
frontend. It found no Critical issues, one High, one Medium and seven Low. The reviewer confirmed:
- tooltips and the sheet are XSS-safe, because they use `textContent` and JSX;
- API parameter edge cases return the right codes (422 for NaN, inf or a non-numeric value; 404 for an unknown
  row);
- the MapLibre lifecycle survives a StrictMode double mount;
- `lru_cache` is safe in the thread pool.

| # | Severity | Finding | Outcome |
|---|---|---|---|
| H1 | High | A row with no antenna height, an antenna height above 3000 m, or no coordinates made `/api/stations` return 500 for every station. Today's data has no such row | **Fixed.** New no-contour reasons `missing_antenna_height` and `antenna_height_out_of_range`. Rows without a position are left out of the GeoJSON. Unit tests added |
| M1 | Medium | Turning off the last band dropped `band=` from the URL, so every band came back | **Fixed.** `band=none` is a valid value. Checked in the browser |
| L1 | Low | The selection ring ignored the filters | **Fixed.** `site-selected` now combines the station filter with its own `source_row` check |
| L2 | Low | Stations without a TX frequency disappeared under any band filter | **Fixed.** A band filter always keeps bin −1, because those stations have no band to filter on |
| L3 | Low | `band=1,1,2` broke the "all selected" check | **Fixed.** `validateSearch` removes duplicates and sorts the bins. Checked: the URL becomes `band=1,2` |
| L4 | Low | The sheet showed placeholder contour figures with no sign they were refreshing | **Fixed.** The sheet description says "updating" while the query has placeholder data |
| L5 | Low | The tooltip DOM was rebuilt on every mouse move | **Fixed.** It is rebuilt only when the hovered row changes |
| L6 | Low | The tile-failure notice never cleared | **Fixed.** It clears when a later `osm` tile loads |
| L7 | Low | `get_db` is copied from `api.py` | **Kept.** The plan limits `api.py` edits to one `include_router` line while another agent works in that file. Move it to a shared deps module later |

**Open question from the review:** should the T/R 25-08 trigger apply by frequency alone (the plan's decision), or
only to land-mobile classes? Broadcast FM stations in 47–108 MHz currently get the 6 dB(µV/m) trigger plus
bandwidth conversion, which gives radii of around 300 km.

Re-run after the fixes: `mise run lint` passes, the five plan test files give 210 passed, and `bun run build`
passes.
