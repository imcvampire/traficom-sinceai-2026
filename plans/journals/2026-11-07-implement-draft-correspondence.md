---
title: "Implemented draft correspondence to notifying administrations"
date: 2026-11-07
summary: "riia/draft.py, two API routes, ific draft CLI and the Draft letter section in the notice sheet"
---

# Implemented draft correspondence to notifying administrations

## What happened
Executed `plans/261107-1313-correspondence-drafts/` in one pass. `review.triage()` now calls a per-notice
`notice_readings()`, and `riia/draft.py` builds the letter, annex and reviewer notes from it. The API has
`GET …/draft` and `POST …/draft/polish`, there is an `ific draft` CLI command, and `/risk` has a `draft=1` section.

## Findings
- On real data (IFIC 3074 at `as_of` 2026-07-01) all four kinds occur: 9 `comment_9_52`, 39 `inclusion_9_41`,
  15 `comment_9_3`, 19 `enquiry`; 114 notices have no concern. At 2026-11-06 all 82 drafts are enquiries because
  every window has closed.
- The real DB has no `stations` results and an empty `analytics.risk_sensitivity`, so real drafts carry a
  skipped-source warning and no sensitive-assumption notes. The sensitivity note had to be worded so that it does not
  claim whether a run happened.
- The fixture cannot reach `inclusion_9_41` or `comment_9_3` with a real reading, so the draft tests store copies of
  notice 1001 under other regulatory contexts instead of changing the shared CSVs.
- The concern paragraph lists every cited hazard, so it can run to thousands of characters on notices with many
  hazards (5 kB file for 124545403).
- The administration names were written from knowledge of the ITU symbol table, not checked against the Preface;
  the file is marked `review.status: pending`.

## Next steps
- Check `data/ref/itu_administrations.json` against the IFIC Preface.
- Decide whether long concern paragraphs should be capped and point to the annex.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
