---
title: Stations map page planned
date: 2026-11-07
summary: "Planned /stations map: MapLibre + OSM, backend-derived horizon radius, beam sectors and mast height"
---

# Stations map page planned

## What happened
Planned a `/stations` map page for the 873 frequencies-of-interest stations in `plans/261107-0720-station-map/`
(3 phases: stations API, map page, docs and verification). Evidence figures were checked against the loaded
table, and three wrong numbers were corrected before the plan was written (AGL max 317 m, 237 directional, 508
with an azimuth).

## Decision
- The map uses MapLibre GL directly over OSM raster tiles. The tile URL can be swapped with `VITE_MAP_TILE_URL`.
  Leaflet was rejected because it cannot extrude height.
- "Radius" means the line-of-sight radio horizon under a 4/3-Earth model, with the receiver at 10 m. It works
  without power, which 342 rows lack, and it is labelled as not a coverage contour.
- Directional stations get a wedge. Beamwidth is derived from gain; without gain it defaults to 30° and is
  flagged. 49 directional stations have no azimuth and get a disc plus a flag.
- The backend owns the derived numbers (`/api/stations`, a new `stations.py` router), so they are testable and
  reusable. Only one line of the shared `api.py` changes.

## Next steps
- Run `/ak-cook plans/261107-0720-station-map/plan.md`.
- The scoring agent's phase 06 excludes BC/BT and stations without a class. That conflicts with Traficom's
  guidance that licence class is irrelevant (missing class means MUUT), and it needs its owner's review.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
