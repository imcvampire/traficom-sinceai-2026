---
phase: 3
title: "Notice sheet section"
status: completed
priority: P2
effort: "3h"
dependencies: [2]
---

# Phase 3: Notice sheet section

## Goal

A "Draft letter" section in the `/risk` notice sheet that shows the draft, its reviewer notes and warnings, and
offers copy, download and polish.

## Files to Create / Modify

- Modify: `frontend/src/lib/api.ts` (types mirroring `DraftOut`, `DraftPolishOut`; `getDraft`, `polishDraft`)
- Modify: `frontend/src/lib/queries.ts` (`draftQueryOptions(ific, ntc, asOf)`, `usePolishDraft` mutation)
- Modify: `frontend/src/router.tsx` (`draft` flag in `/risk` `validateSearch`, same handling as `chat`)
- Create: `frontend/src/components/notice-draft.tsx`
- Modify: `frontend/src/components/notice-sheet.tsx` (mount the section; closing the sheet clears `draft`)
- Modify: `frontend/src/components/risk-meta.ts` (kind labels and descriptions)

## Tasks & Steps

1. **Types and client.** Keep `api.ts` in sync with `schemas.py`. A 409 from the GET is a normal state
   ("no concern to describe: …"), not an error toast; a 422 from polish shows the missing tokens.
2. **URL state.** `draft=1` opens the section (all page state lives in the URL). The query is enabled only when
   `draft=1`, so opening a notice does not build a draft.
3. **Section layout** (`notice-draft.tsx`), using existing `Section`, shadcn components and status tokens:
   - header line: kind label with a `TermHint` explaining the provision (from `risk-meta.ts`), counterparty
     "`<name>` (`<adm>`)", days left;
   - warnings (enquiry, unknown administration, skipped source) as an alert above the letter;
   - the letter in a read-only monospace block, with a "Template" / "Polished" toggle once a polish succeeded;
   - buttons: Copy, Download `.md` (`ific<no>-<ntc_id>-<kind>.md`), Polish with LLM (disabled with the reason
     from `GET /api/risk/chat` when the chat is off, spinner while running);
   - reviewer notes in a collapsible block labelled "Internal – do not send".
   - Every view shows "DRAFT – for expert review, not sent".
4. **Polished text** lives in component state only (no persistence, per the plan decision); it is dropped when the
   notice or `as_of` changes.

## Verification

- `cd frontend && bunx tsc -b --noEmit`
- `mise run lint` (oxlint)
- `mise run build`
- Manual smoke with `mise run dev` on an assessed issue (3074 or 3083): open an `exceeds` notice with an open CR/C
  window, toggle `draft=1`, check the kind, counterparty, annex numbers against the hazard table, copy and
  download; open a no-concern notice and see the 409 reason; polish once with the LLM configured. Stop the dev
  servers afterwards.
