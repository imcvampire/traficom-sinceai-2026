---
phase: 5
title: Docs and verification
status: completed
depends_on: [4]
---

# Phase 05: Docs and verification

## Files

| File | Action |
|---|---|
| `docs/propagation.md` | **New.** Covers both modules in `ific.propagation`. **P.1546:** the version, the port source and licence, the in-scope steps, the validation results with the skipped count, and the API and its assumptions. **T/R 25-08:** the edition, the citation, the trigger conditions and the wideband correction. Says how the side quest should call both. |
| `docs/frontend.md` | Add `maplibre-gl` to the stack table, a `/stations` section with its URL params and layers, the contour meaning and assumptions, and `VITE_MAP_TILE_URL` with the attribution. |
| `plans/reports/tester-<stamp>-station-map.md` | **New.** Commands run, results, and 2D/3D screenshots in light and dark. |

## Steps

1. `mise run lint`.
2. From `backend/`: `uv run pytest -q tests/test_p1546.py tests/test_tr2508.py tests/test_stations_api.py tests/test_special_interest.py tests/test_api.py`.
3. From `frontend/`: `bun run build`.
4. Reuse the API already listening on `127.0.0.1:8000`. Start only what is missing (`mise run web`). Open
   `/stations`, check acceptance criteria 5–8, and capture screenshots with the browser automation skill.
5. Stop any dev process this phase started.
6. Tell the scoring agent's owner that `ific.propagation` exists, for their terrestrial follow-up.
7. Set the plan's status to `completed` when every acceptance criterion holds.
