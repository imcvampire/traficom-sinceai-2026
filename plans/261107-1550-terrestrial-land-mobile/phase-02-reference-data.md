---
phase: 2
title: "Reference data: criteria, frameworks, land mask"
status: done
priority: P1
effort: "3h"
dependencies: []
---

# Phase 2: Reference data: criteria, frameworks, land mask

## Goal

This phase adds the hand-curated, cited inputs the assessment needs. Each file carries a `cite` and a `review`
block, and its loader is `@cache`d, like `regulatory.load_windows`.

## Files

- Create: `data/ref/terrestrial_criteria.json`
- Create: `data/ref/terrestrial_frameworks.json`
- Create: `data/ref/region_land.geojson`, Natural Earth 1:10m land clipped to lon 0–45°E and lat 50–75°N.
- Create: `data/ref/SOURCES.md` entry, or append to the existing provenance note if one exists. Check first.
- Create: `backend/src/ific/terra/__init__.py`, `backend/src/ific/terra/refdata.py`
- Create: `backend/tests/test_terra_refdata.py`

## Steps

1. **Criteria file.** Each entry has these fields:
   - `id`, `title`, `citation`, `doc_url`, `doc_sha256`;
   - `f_min_mhz` and `f_max_mhz`, with the inclusive edge stated;
   - `time_pct`, `loc_pct`, `rx_height_m`, `reference_bw_khz`;
   - `bw_correction`: `"10log10(bw/ref)"` or `"none"`;
   - `bands[]`, each with its trigger in dBµV/m;
   - `evaluation`: `"border"`, or a distance into Finland in km;
   - `verified: false`, `verified_by: null`.

   It has two entries:
   - **`tr-25-08`.** Generated from `ific.propagation.tr2508.TRIGGERS`, which stays the single source of truth.
     The loader builds this entry from the module, so its values are never copied by hand. A test asserts the
     two agree.
   - **`ecc-rec-11-04`**, ECC/REC/(11)04 for 790–862 MHz. Transcribe the trigger values, receiver height, time
     %, reference bandwidth and evaluation lines from the PDF on docdb.cept.org. Record its SHA-256 the way
     `tr2508.py` does. Every value is quoted with page and section. Do not use values from memory. If the PDF
     cannot be fetched, leave the entry out and record why in `review.note`; the 800 MHz notices then become
     `not_assessed`.
2. **Frameworks file.** It has four parts:
   - **`rr_provisions`.** RR 11.2, 11.9, 11.17 and others, mapped to a label and citation, plus the publication
     part meanings (1 received, 2 recorded with findings, 3 returned). These are marked `to_confirm` with the
     BR IFIC Preface as the source.
   - **`ge06`.** It applies when `notice_typ` starts with `G` or `prov` starts with `GE06-`. It cites the GE06
     Agreement, Article 4.
   - **`ecc_applicability`.** Per administration: `{"RUS": {"status": "indicative", "reason": "CEPT membership
     suspended (user-confirmed 2026-11-07)", "governing": "FIN–RUS bilateral frequency coordination agreement
     (not in repo)"}}`. CEPT members near Finland (EST, S, NOR, LVA, LTU) are `"applicable"`. Every other
     administration defaults to `"unknown"`.
   - **`national`.** Regulation M4: the Finlex Traficom 2026/3 citation and URL, and the frequency allocation
     table source (opendata.traficom.fi Taajuusjakotaulukko, already in `ref.m4_allocation` via `m4.py`). The
     assessment cites the matching allocation row by its `ref` key.
3. **Land mask.** Download Natural Earth 10m land (public domain), clip it to the region, simplify it to about
   100 m tolerance, and keep the file under 2 MB. Record the source URL, version and SHA-256 in the provenance
   note. `refdata.is_land(lon, lat)` reuses the vectorised numpy point-in-polygon in `riia/geometry.py`
   (`_ring_contains` and its even-odd caller). Make that helper public, or import it as it is, rather than adding
   `shapely`. Precompute the polygon ring bounding boxes so that a path of about 200 samples is one vectorised
   call.
4. **Finland boundary sampling.** `refdata.finland_border_points(spacing_km=5)` returns deterministic points
   along the outline of `finland_land.geojson` (land border and coastline), sorted by a stable key. It is cached.

## Tests

- The criteria loader matches `tr2508.TRIGGERS` exactly.
- Every criterion has a citation and `verified` is present.
- A sea point in the Gulf of Finland (60.0°N 26.5°E) is not land. Kotka (60.47°N 26.95°E) and Narva
  (59.38°N 28.19°E) are land.
- The border points are stable across two calls, and their count is within ±1% of a pinned number.

## Validation

```sh
cd backend && uv run pytest tests/test_terra_refdata.py tests/test_tr2508.py -q
```

## Risks

The ECC/REC/(11)04 values are a transcription, which is why `verified: false` exists. The interpretation of the
evaluation line (border versus a distance inside the country) must be quoted, not inferred.
