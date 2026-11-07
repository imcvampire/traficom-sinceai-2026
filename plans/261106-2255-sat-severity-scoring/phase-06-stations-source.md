---
phase: 06
title: Stations receiver source
status: completed
depends_on: [02]
---

# Phase 06: Stations receiver source

## Context

The expert trigger "high-gain Finnish antenna in direct line toward the transmitter" needs real receivers. The
frequencies-of-interest stations (`ref.special_interest_station`, 873 rows) carry location, receive band, antenna
height, azimuth (237 directional) and, for 85 stations, gain.

## Requirements

- `StationsPopulation` (`name = "stations"`) implements `ReceiverPopulation` and plugs into `assess_issue` unchanged.
- One receiver per station with a receive band. Receiving licence classes only (FX, MVV, MUUT); BC and BT are
  broadcast transmitter licences, excluded with the reason recorded.
- Service class: the riia-1 class of the M4 allocation at the station's receive band (primary services), preferring
  the licence's natural class (FX → fixed). A station with no class is excluded and counted.
- Given values win: azimuth (directional stations), `ant_gain_db` (taken as dBi, an assumption), effective antenna
  height, channel bandwidth. Missing values come from the class (gain, NF, ACS) or its distributions (pointing
  elevation; azimuth for non-directional stations), tagged `assumption`.
- Tier 2 supports per-receiver peak gain (group sites by gain).
- `ific assess <no> --source stations` stores results under `receiver_source = stations`.

## Validation

- Unit test: station rows → receivers (class, given azimuth/gain, exclusions).
- 3074 run with the stations source succeeds; Tier 1 ≥ Tier 2 holds.
