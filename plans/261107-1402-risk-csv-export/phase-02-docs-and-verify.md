---
phase: 2
title: "Docs and verification"
status: completed
priority: P3
effort: "0.5h"
dependencies: [1]
---

# Phase 2: Docs and verification

## Goal

Document the export where frontend maintainers look and run the frontend gates.

## Files to Create / Modify

- Modify: `docs/frontend.md` — a paragraph in the `/risk` section after the Work queue paragraph: what
  **Download CSV** exports (filtered and sorted rows, all pages), the filename, raw-value format, BOM, and that it
  has no score column. No URL param changes, so the param table is unchanged.

## Tasks & Steps

1. Write the docs paragraph.
2. Run `mise run lint` and `mise run build`.
3. Walk the acceptance criteria in `plan.md` in the running app and mark the phases completed.

## Validation

All seven acceptance criteria in `plan.md` hold.
