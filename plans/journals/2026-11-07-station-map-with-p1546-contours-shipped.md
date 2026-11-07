---
title: Station map with P.1546 contours shipped
date: 2026-11-07
summary: "Ported ITU-R P.1546-6, sourced T/R 25-08 triggers, built /api/stations and the MapLibre /stations page"
---

# Station map with P.1546 contours shipped

## What happened

- **P.1546 engine.** `ific.propagation.p1546` is a Python port of the WP 3K MATLAB reference (eeveetza/p1546
  @0e42639). All 52 reference validation cases pass within 0.001 dB, and the largest deviation is 5×10⁻⁵ dB.
  The engine also accepts the terrain inputs, so no case had to be skipped.
- **T/R 25-08 triggers.** `ific.propagation.tr2508` uses the 6 June 2025 edition, Annex 1 A1.2.3. The PDF gives
  the bandwidth conversion as `10·log10(spacing/25 kHz)`. The plan said `6·log10`, which was wrong, and the plan
  is now corrected.
- **API.** `/api/stations` returns 873 features, 444 of them with contours. Radii come from log-distance
  bisection, and the first uncached call takes 0.14 s.
- **Map page.** `/stations` uses MapLibre 6, and all its state is in the URL.

## Surprises

- **Worker.** MapLibre 6 resolves `maplibre-gl-worker.mjs` relative to its own module URL, and a Vite bundle does
  not keep that file, so the map rendered blank. Fixed with `setWorkerUrl(import '…/maplibre-gl-worker.mjs?worker&url')`.
- **CSS.** `maplibre-gl.css` is unlayered, so `.maplibregl-map { position: relative }` beats Tailwind's
  `absolute`. The canvas collapsed to 300 px. Fixed by putting the layout on a wrapper.
- **Visual settings.** At 12% fill, 444 overlapping discs turned Finland solid blue, so the fill is now 4%. A
  400 m column footprint was invisible at country zoom, so it is now 2 km.
- **Dev servers.** The Vite dev server on :5173 that was already running (not mine) served a stale
  optimised-dependency copy, so the browser checks used `vite preview`. The API that was already running on :8000
  exited partway through, so I started my own and stopped it afterwards.
- **Review.** It found two real issues, both fixed. H1: a row with no antenna height or position would have made
  the whole list return 500. M1: turning off the last band brought every band back.

## Decision

- Radii are cached per physical input, not per data sha.
- The tolerance is 0.001 dB instead of 0.1 dB.

Both are recorded in the plan's Outcome section.

## Next steps

- A person checks the T/R 25-08 values against the PDF and removes the `UNVERIFIED` note in `tr2508.py`.
- Decide whether the T/R 25-08 trigger applies by frequency alone or only to land-mobile classes. FM broadcast
  currently gets radii of around 300 km.
- Restart the :5173 dev server to load `/stations` in dev mode.
- Follow-ups: DEM-based `h1` and terrain clearance angle, a coastline mask, and antenna patterns.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
