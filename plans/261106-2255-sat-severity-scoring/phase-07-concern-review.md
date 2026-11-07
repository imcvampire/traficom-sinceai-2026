---
phase: 07
title: Concern triage and manual-review export
status: completed
depends_on: [03, 06]
---

# Phase 07: Concern triage and manual-review export

## Context

The expert's three triggers become readings off the existing results, never a combined score:

| Trigger | Reading |
|---|---|
| Exceeds the defined limit | `exceeds`: a receiver violates a criterion point |
| Close-by exceedance / semi-high pfd near the frequency | `near_limit`: no violation, but the 95th-percentile `exceedance_db` is within 6 dB of a criterion (margin is an assumption); adjacent-band hazards carry "near the frequency" |
| High-gain antenna in direct line toward the IFIC location | `main_beam`: a directional station whose antenna (half-power beamwidth from its gain) contains the GSO position notified in the IFIC; deterministic geometry, reported with the off-axis angle |

## Requirements

- `riia/review.py`: per notice, concern readings for both receiver sources, the stations involved (id, class,
  band, azimuth, gain, off-axis angle to the GSO), and the BR's Finland findings.
- `ific review <no> --as-of … --out PATH` writes a Markdown report for manual review plus a CSV of the same rows.
- Order: notices with a stations `exceeds`, then stations `main_beam`, then stations `near_limit`, then generic-only
  findings; within a group by largest `share_violating`, then largest `exceedance_db`.

## Validation

- Unit tests: main-beam geometry at hand-checked angles; near-limit boundary.
- Dry run on 3074 → `plans/reports/review-261107-riia1-3074-concerns.md` and `.csv`, for manual review.
