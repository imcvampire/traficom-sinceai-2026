---
phase: 1
title: "CSV builder and button"
status: completed
priority: P3
effort: "1.5h"
dependencies: []
---

# Phase 1: CSV builder and button

## Goal

Build the CSV from the table's filtered, sorted notices and save it from a button on `/risk`.

## Files to Create / Modify

- Create: `frontend/src/lib/download.ts` — `saveFile(name, text, type)`; moved from `notice-draft.tsx`.
- Create: `frontend/src/lib/csv.ts` — generic `toCsv(header, rows)` with RFC 4180 quoting, CRLF, BOM and the
  formula-injection guard.
- Modify: `frontend/src/components/risk-meta.ts` — `noticesCsv(notices, serviceLabel)` mapping `NoticeSummary`
  to the column list below (kept with the other risk labels/formatters).
- Modify: `frontend/src/components/notice-draft.tsx` — import `saveFile` from `@/lib/download`.
- Modify: `frontend/src/pages/risk.tsx` — the button, using `visibleIds` (already in state) to pick and order rows.

## Column list

`ntc_id, sat_name, adm, prov, stage, ntc_type, orbit, act_code, worst_outcome, hazards_exceeds, hazards_meets,
hazards_screened_out, hazards_not_applicable, hazards_not_assessed, services_exceeding, services_assessed,
max_share_violating, max_median_exceedance_db, max_worst_case_db, in_queue, window_open, d_wic, window_end,
days_left, fin_identified`

Booleans as `true`/`false`, nulls as empty cells, lists `;`-joined service labels, `orbit` as the raw code
(`gso`/`ngso`/`es`).

## Tasks & Steps

1. `lib/download.ts`: move `saveFile` and add the MIME type parameter. Defer `URL.revokeObjectURL` with
   `setTimeout(…, 0)` so Safari/Firefox do not cancel the download (the current synchronous revoke is a latent bug).
2. `lib/csv.ts`: `toCsv(header: string[], rows: (string | number | boolean | null | undefined)[][]): string`.
   Quote a cell when it contains `,`, `"`, CR or LF, doubling `"`. Prefix `'` to string cells starting with
   `= + - @ \t \r`. Prepend `﻿`, join lines with `\r\n`.
3. `risk-meta.ts`: `NOTICE_CSV_HEADER` and `noticesCsv(notices, serviceLabel)`.
4. `risk.tsx`: compute `exportRows` from `technical.data.notices` indexed by `ntc_id` and ordered by `visibleIds`.
   Add `<Button variant="outline" size="sm">` with the lucide `Download` icon beside **Ask about this view**,
   wrapped in a flex group; disabled with a tooltip ("No notices match the filters") when `visibleIds` is empty.
   Filename `ific${ificNo}-notices-${asOf}.csv`.

## Risks

- `visibleIds` is set in an effect, so it lags the table by one render; acceptable for a click handler. If it
  proves stale after a filter change, lift the row computation out of the effect instead.
- `visibleIds` ids absent from `notices` (should not happen) are skipped, not exported as blanks.

## Validation

- `cd frontend && bunx tsc -b --noEmit` and `mise run lint`.
- Manual in `mise run dev`: criteria 1, 2, 4, 5, 6 from `plan.md`. For 4, check the file with
  `python3 -c "import csv,sys; [print(r) for r in csv.reader(open(sys.argv[1], encoding='utf-8-sig'))]" <file>`.

## Rollback

Revert the commit; no data or API changes.
