---
title: "Plan: draft correspondence to notifying administrations"
date: 2026-11-07
summary: "Planned step 9 of the brief: deterministic draft letters per concern notice, with guarded LLM polish"
---

# Plan: draft correspondence to notifying administrations

## What happened
A coverage review of the Traficom brief found step 9 (name the counterparty administration and draft
correspondence for expert review) unimplemented: `adm` is stored but nothing produces a letter.
Plan written at `plans/261107-1313-correspondence-drafts/` (4 phases, ~1.5d).

## Decision
- The user chose (2026-11-07): a deterministic template with an optional LLM polish of the prose only;
  available from the notice sheet and an `ific draft` CLI command; drafts not stored; no Traficom
  template exists, so a neutral ITU-style letter will be designed.
- The letter kind comes from the stored regulatory context: RR 9.52 comment, 9.41 request for inclusion,
  9.3 API/A comment, or an informal enquiry when no comment window is open.
- Polish guard: every number, id, provision, date and administration code in the prose must survive
  verbatim, or the API returns 422 and the template text is kept. The annex never goes to the LLM.
- Station-level data (ids, coordinates, azimuths) appears only in internal reviewer notes, never in the
  letter.
- `ific draft` uses `_prepare` like `ific review`, so it needs the API stopped (DuckDB file lock).

## Next steps
- Implement with `/ak-cook plans/261107-1313-correspondence-drafts`.
- Transcribe the administration symbol table from the IFIC Preface; leave unverifiable names null.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
