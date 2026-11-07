---
phase: 4
title: Map page
status: completed
depends_on: [3]
---

# Phase 04: Map page

## Context

See [plan.md](plan.md) and [phase 03](phase-03-stations-api.md). Read:
- `docs/frontend.md`;
- `frontend/src/router.tsx`;
- `frontend/src/components/app-shell.tsx`;
- `frontend/src/lib/api.ts` and `queries.ts`;
- `frontend/src/components/notice-sheet.tsx`.

Load the `dataviz` skill before choosing the band palette and building the legend.

## Files

| File | Action |
|---|---|
| `frontend/package.json`, `bun.lock` | `bun add maplibre-gl` |
| `frontend/src/lib/api.ts` | Types `StationFeature`, `StationCollection`, `StationDetail`, `Contour`; functions `listStations(timePct, threshold)` and `getStation(sourceRow, timePct, threshold)`. |
| `frontend/src/lib/queries.ts` | `stationsQuery(timePct, threshold)` with `placeholderData: keepPreviousData`, so discs don't flash while the threshold changes. `stationQuery(...)`. |
| `frontend/src/lib/geo.ts` | **New.** `circlePolygon(center, radiusKm, steps = 96)`, `arrowLine(center, azimuthDeg, lengthKm)` and `hexagon(center, radiusM)`, using spherical destination-point maths. |
| `frontend/src/components/station-map.tsx` | **New.** Creates the MapLibre map once. Sources and layers are updated from props. No fetching. |
| `frontend/src/components/station-legend.tsx` | **New.** Band colours, the model statement, the threshold source, the exaggeration slider. |
| `frontend/src/components/station-sheet.tsx` | **New.** Parameters with units, the contour (inputs, threshold and citation, assumptions, P.1546 intermediates), the no-contour reason, M4 overlaps, quality flags, `source_row`. |
| `frontend/src/pages/stations.tsx` | **New.** |
| `frontend/src/router.tsx` | `/stations` with `validateSearch`: `band` (comma-separated 0–4), `q` (digits), `station` (int > 0), `view` (`2d`/`3d`), `t` (1/10/50), `thr` (-20 to 120). |
| `frontend/src/components/app-shell.tsx` | A NAV entry "Stations map" (lucide `MapPin`) and its title. |
| `frontend/src/index.css` | `--band-0..5` tokens for light and dark, if needed. Import the maplibre CSS. |
| `.env.example` | `VITE_MAP_TILE_URL`. |

## Layers (bottom to top)

1. **`osm` raster.** In dark mode set `raster-brightness-max: 0.55` and `raster-saturation: -0.6`. Attribution:
   © OpenStreetMap contributors.
2. **`contour` fill and outline.** Built from `contour.radius_km` with fill opacity 0.04 (0.12 hid the basemap under 444 overlapping discs) and a 1 px band-colour
   outline. `below_1km` contours are drawn as a 1 km disc with a dashed outline. `at_least_1000km` contours are
   clipped at 1000 km with a dashed outline. A toggle shows or hides the layer.
3. **`azimuth` line** for directional stations with an azimuth, 1.5 px, with length `min(radius_km, 20 km)`.
4. **`mast` fill-extrusion**, height `effective_agl_m × exaggeration`, shown in 3D only.
5. **`site` circle**, 5 px in the band colour, with a stroke in the background colour. A selected station gets a
   ring.

Filters use a layer `filter` expression. Contour polygons are rebuilt only when the contour data changes.
Exaggeration changes the paint expression only.

## Interaction

- **Hover:** a tooltip with the station number, TX frequency, bandwidth, ERP, AGL height in real metres, and the
  radius with its threshold source.
- **Click:** query the rendered `site` features. One station opens it directly; several open a picker popover.
  The choice is stored as `?station=`.
- **Header controls:**
  - band chips with counts;
  - station-number search;
  - time-percentage select;
  - threshold slider, debounced by 300 ms and labelled "used where T/R 25-08 doesn't apply";
  - a contour toggle;
  - a 2D/3D toggle.
- **States:**
  - Loading: a skeleton.
  - API error: an alert with a retry button.
  - WebGL unavailable: an alert.
  - Tiles failing: a small notice, while stations still render.

## Validation

- `bun run lint` and `bun run build`.
- Check `geo.ts` in the browser console:
  - an azimuth-0 arrow points north and an azimuth-90 arrow points east;
  - a circle's radius at latitude 70° is within 0.5% of the target.
- Manual check of plan acceptance criteria 5–8 in the light and dark themes and at phone width.
