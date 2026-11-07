---
title: Download the /risk notice table as CSV
description: A "Download CSV" button on /risk that exports the notices the table shows (after filters, search and sort, across all pages) as a CSV file, built in the browser from the data already loaded.
status: completed
mode: fast
priority: P3
effort: 2h
branch: main
tags: [frontend]
blockedBy: []
blocks: []
created: 2026-11-07
source: /ak-plan "add download as CSV for this page http://localhost:5173/risk"
---

# Download the /risk notice table as CSV

## Outcome

On `/risk`, next to **Ask about this view**, a **Download CSV** button saves the notices the table currently
shows, as one row per notice, to `ific<no>-notices-<as_of>.csv`. The file holds the same rows in the same order as
the table (filters, search and sort applied, all pages, not only the visible 25), with machine-readable values
rather than the display strings.

## Decisions (defaults taken; change before cooking if wrong)

| Decision | Choice | Why | Alternative |
|---|---|---|---|
| Where the CSV is built | In the browser, from `technical.data.notices` | The table already has the full notice list and does filtering/sorting client-side; no new endpoint, no extra DuckDB read, no `schemas.py`/`api.ts` sync | `GET /api/risk/issues/{no}/notices.csv` — only worth it for CLI/scripted use; would have to re-implement the table's filters server-side |
| Which rows | The filtered and sorted rows, all pages | "Download what I see" is the expected behaviour, and `RiskTable` already reports these ids (`onVisibleIdsChange`, used by the chat) | Always the whole issue — the user can clear filters first |
| Granularity | One row per notice (`NoticeSummary`) | That is what the page lists; per-hazard rows need `NoticeDetail` for every notice (N requests) | Per-hazard export — separate feature |
| Value format | Raw values: share as 0–1 number, dB as number, dates ISO, lists `;`-joined, services as labels | Spreadsheet-friendly; display formatting (`formatShare`, `—`) would break numeric columns | Display strings |
| Encoding | UTF-8 with BOM, CRLF, RFC 4180 quoting | Excel opens UTF-8 correctly only with a BOM; satellite names may contain commas/quotes | — |

## Contract

- **Constraints:**
  - **No composite score.** No `score`, rank or combined-risk column. Columns are the `NoticeSummary` fields only.
  - No backend change. `api.ts` types are unchanged.
  - CSV formula injection is neutralised: a text cell starting with `=`, `+`, `-`, `@`, tab or CR is prefixed with
    `'`. Numeric columns are emitted as numbers and are not prefixed (negative dB values stay numeric).
  - The existing draft-letter download (`notice-draft.tsx` `saveFile`) moves to a shared helper rather than being
    duplicated.
  - Regulatory fields reflect the page's `as_of` (they already do: the notices query is `as_of`-dated), and the
    filename carries it.
- **Non-goals:** server-side CSV endpoint; per-hazard or curve export; XLSX; exporting the compare view or notice
  sheet; a column picker; frontend test harness (the repo has none).
- **Acceptance criteria:**
  1. The button appears only when the assessment is loaded (same condition as **Ask about this view**) and is
     disabled with a tooltip when the filtered table is empty.
  2. With `outcome=exceeds&sort=days_left.asc`, the CSV has exactly the rows the table lists, in the same order,
     including rows on pages 2+.
  3. Header row is fixed (see phase 1 column list); no column named `score` or similar.
  4. A satellite name containing `,` and `"` round-trips in Excel/LibreOffice/`python -c "import csv"` as one
     cell; a name starting with `=` is written as `'=...`.
  5. Filename is `ific<ific_no>-notices-<as_of>.csv`; non-ASCII characters open correctly in Excel.
  6. The draft letter Download `.md` still works through the shared helper.
  7. `mise run lint` and `mise run build` pass.

## Phases

| # | Phase | Status | Effort |
|---|---|---|---|
| 1 | [CSV builder and button](phase-01-csv-builder-and-button.md) | completed | 1.5h |
| 2 | [Docs and verification](phase-02-docs-and-verify.md) | completed | 0.5h |
