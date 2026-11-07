# 2026-11-07: terrestrial land mobile side quest delivered (`terra-1`)

Plan `261107-1550-terrestrial-land-mobile` is complete. All eight phases are done. The evidence is in
`plans/reports/verify-261107-1640-terrestrial-land-mobile.md`.

## What happened

- The backend was built in sequence: ingest, reference data, model, store/API/CLI, then trends and drafts. Two
  delegates ran beside it, one on the watcher (phase 6) and one on the `/terrestrial` page (phase 7). An
  independent reviewer checked the backend afterwards.
- The job runner was extracted into `ific/jobs.py` and the draft helpers into `ific/drafting.py`. The riia tests
  passed unchanged on both, so there was no fallback copy and no duplication debt.
- ECC/REC/(11)04 was transcribed from the official PDF (edition of 7 November 2025), with every value quoted by
  page. It covers 791–821 MHz, which is the base-station downlink, not 790–862 MHz.

## Surprises

- The user's dev server reloads and runs the watcher, so the half-built terrestrial watcher went live and
  downloaded 3062–3083 (about 800 MB) while I had said nothing would download without approval. I corrected that
  to the user. Lesson: in this repo a running `--reload` server executes new code at once, watcher included.
- `ref_stn_cls_nat_srv` maps station class to nature of service, not to the service itself, so it cannot select
  land mobile assignments. Selection is by FB/ML class instead.
- The review found that the "all-sea" Tier 1 bound is not an upper bound below about 100 MHz, where P.1546 land
  exceeds cold sea by up to 8 dB. Tier 1 now takes max(sea, land). This is latent on 3075–3077.
- The plan's "column stays VARCHAR on a cast failure" rule would have retyped the column for every issue. A bad
  value is now stored as NULL, with its text in `<col>_raw`.
- The AC3 contract counted 16 FIN coordination rows as "15 TX + 1 RX". One of the rows belongs to a RECORDED
  before-state, so it was reported as found, not adjusted to pass.

## Open

- Questions for Traficom: which publication part to act on, adding ECC/REC/(08)02, ECC applicability per
  administration, and verifying the criterion values against the PDFs.
- `mise run build` was not rerun after the final optional `api.ts` field, because a local hook blocks the word
  "build". The type-check passes.
