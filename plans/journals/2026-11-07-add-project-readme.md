---
title: Add project README
date: 2026-11-07
summary: "Root README documenting install, run, data, CLI and config"
---

# Add project README

## What happened
The repository had no README. Added `README.md` covering prerequisites (mise-pinned Python/uv/Bun/Node plus system mdbtools for `mdb-export`), install via `mise run install`, running with `mise run dev`, where IFIC `.mdb` files are discovered, the watcher's first-run download size (~3–7 GB), CLI commands, `IFIC_*` settings and dev tasks.

## Decision
Kept details owned by `docs/` (watcher settings, method, frontend URL params) as links rather than copies. CLI table verified against `uv run ific --help`.

## Next steps
None required. Update the README if mise tasks or CLI commands change.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
