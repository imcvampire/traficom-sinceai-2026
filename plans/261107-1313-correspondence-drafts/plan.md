---
title: Draft correspondence to the notifying administration
description: Generate a reviewable draft letter to the notifying administration for each notice with an interference concern, from stored riia-1 results, with an optional LLM prose polish that cannot change facts.
status: completed
mode: auto
priority: P2
effort: 1.5d
branch: main
tags: [backend, api, frontend, cli, llm]
blockedBy: []
blocks: []
created: 2026-11-07
source: /ak-ask step-coverage review (step 9 "identifying the relevant counterparty (administration) and drafting relevant correspondence template for expert review" found not implemented) → /ak-plan "work on that part 9"; decisions by the user 2026-11-07 (see Decisions)
---

# Draft correspondence to the notifying administration

## Outcome

For a notice with an interference concern, the analyser produces a **draft letter from the Administration of
Finland to the notifying administration**, ready for an expert to review and edit. The draft:

- names the counterparty (the notice's `adm`, with the administration name from a cited reference table);
- picks the Radio Regulations basis from the stored regulatory context (RR No. 9.52 comment on a CR/C, RR No. 9.41
  request for inclusion, RR No. 9.3 comment on an API/A, or an informal technical enquiry when there is no open
  comment window);
- states the concern with the stored hazard readings (`exceeds`, `near_limit`, `main_beam`) and their cited
  numbers, in a technical annex;
- carries a separate **reviewer notes** block, never meant to be sent, with the assumptions that can flip the
  outcome, the receiver source used, data caveats and the deadline.

The template is deterministic. An optional "Polish with LLM" step rewrites only the prose paragraphs, and is
rejected if any protected fact (number, id, provision, date, administration code) is changed or dropped.

## Contract

- **Constraints:**
  - Generated on demand from stored results. Nothing is written to `analytics` or any other table, and no draft
    state is stored (user decision 2026-11-07).
  - Deterministic: the same `(ific_no, ntc_id, as_of)` and stored results give byte-identical template output.
    `as_of` only changes the regulatory fields (days left, window open, letter kind), as everywhere else.
  - No composite score. The draft lists hazard readings with their criteria and citations, never a score, rank or
    "overall risk".
  - The LLM never decides anything: not the letter kind, not the provision, not which hazards are cited. It only
    rewrites prose it is given, under the same concurrency gate as the chat.
  - Every draft is labelled "DRAFT – for expert review, not sent" in the letter and in the UI.
  - Stations-source details (station ids, coordinates, azimuths) go in the reviewer notes only, never in the
    letter body or annex, because they come from an internal dataset and may be sensitive.
  - English only (an ITU working language).
- **Non-goals:** storing, editing in place or tracking drafts (draft/sent status); sending e-mail; "no objection"
  replies for notices without a concern; AP30/AP30A/AP30B plan-procedure letters (no such notices in the data, see
  `docs/interference-risk-assessment.md`, "Not covered"); .docx export; letters in French or Spanish; letter
  addresses of administrations; batching several notices into one letter.
- **Acceptance criteria:**
  1. For a CR/C notice with an open window and at least one reading, the draft kind is `comment_9_52` when the BR
     identified Finland and `inclusion_9_41` when it did not; an API/A notice with an open window gives
     `comment_9_3`; a notice with no open window (closed, Notification, Res49) gives `enquiry` with a warning that
     no RR comment window applies (unit tests on the fixture issue, one per kind).
  2. A notice with no `exceeds`, `near_limit` or `main_beam` reading in either receiver source gets no draft: the
     API returns 409 with the reason, and the UI shows that reason instead of the button.
  3. The letter names the notifying administration by code and, when the code is in
     `data/ref/itu_administrations.json`, by name; an unknown code gives a reviewer warning, never a guessed name.
  4. Every number in the annex equals the stored value it was read from (test compares the draft payload with
     `store.get_notice`), and every annex row carries its `hazard_id` and criterion citation.
  5. Two template renders with the same inputs are byte-identical; the payload and text contain no `score`.
  6. Polish: with a fake provider that returns faithful prose, the polished letter keeps every protected token and
     is returned; with one that alters a number or drops the `ntc_id`, the API returns 422 listing the missing
     tokens and the template text is kept. With the LLM not configured the polish endpoint returns 503 and the UI
     disables the button with the reason; over the concurrency limit it returns 429.
  7. `ific draft ISSUE --as-of D` writes one Markdown draft per notice with a concern (or only `--ntc` ones) and
     prints the kinds it wrote; it writes nothing to the database (like `ific review`, it needs the API stopped).
  8. On `/risk`, the notice sheet has a "Draft letter" section (`draft=1` in the URL) with the letter, reviewer
     notes, copy and download (`.md`), and polish. `docs/frontend.md`, the README CLI table and the method doc are
     updated. `mise run lint`, `mise run test` and `mise run build` pass.

## Evidence (inspected 2026-11-07)

| Source | Finding |
|---|---|
| `backend/src/ific/riia/regulatory.py`, `data/ref/rr_comment_windows.json` | Stage, provision, `window_end`, `days_left`, `window_open`, `fin_identified` and findings are already stored per notice and re-dated by `as_of`. Cites for 9.3, 9.52, 9.52C, 9.41 are in the JSON. |
| `backend/src/ific/riia/review.py` | `exceeds`, `near_limit` (`is_near_limit`, 6 dB) and `main_beam` (`main_beam_hits`) readings exist, but only inside the issue-wide `triage()` loop. A draft needs the same readings for one notice. |
| `backend/src/ific/riia/store.py` | `get_notice(con, ific_no, source, ntc_id, as_of)` returns the stored detail for each receiver source independently. |
| `backend/src/ific/api.py` | The API serves one receiver source (`jobs.source`); the review uses both stored sources. |
| `backend/src/ific/llm.py`, `api.py` chat route | `ChatClient` has `try_acquire`/`release` (shared gate), `open()` and `deltas()` (streaming only). Collecting the deltas server-side gives a non-streamed polish. |
| `space.notice` / fixture `notice.csv` | `adm` is a BR symbol (`USA`, `CHN`, `F`, `RUS`, ...). No administration-name table exists in `data/ref/`. |
| `docs/interference-risk-assessment.md` | "An LLM may explain results or draft letters, but it never decides relevance or a limit." AP30 plan notices are listed as not covered. |
| `frontend/src/components/notice-sheet.tsx`, `router.tsx` | The notice sheet has `Section` blocks; `chat=1` is the precedent for a URL flag. |

## Decisions

| Decision | Choice | Why | Alternative rejected |
|---|---|---|---|
| Generation (user, 2026-11-07) | Deterministic template; optional LLM polish of the prose paragraphs only, guarded by a protected-token check | Facts stay reproducible and cited; prose can read naturally | Template only (stiff wording); LLM writes the letter (numbers not guaranteed) |
| Surface (user, 2026-11-07) | Notice sheet section plus `ific draft` CLI | One-off review in the UI, batch next to `ific review` | UI only; CLI only |
| Persistence (user, 2026-11-07) | None; built on demand | No stale drafts, no new tables; the expert copies the text out | Stored drafts with status |
| Template (user, 2026-11-07) | No Traficom template exists; design a neutral ITU-style letter | — | — |
| Letter kind | A pure function of the stored regulatory context: stage, `window_open`, `fin_identified` | Keeps the LLM out of the decision; follows `rr_comment_windows.json` | Let the reviewer pick the kind (kept as a manual edit) |
| Evidence source | Stations source readings first, generic-m4 readings second, each labelled with its source; a source that is not assessed is skipped with a reviewer note | Same two sources and order as `ific review` | API source only: would lose stations readings when the server runs generic-m4 |
| Reuse of triage | Extract a per-notice `notice_readings()` from `review.triage()` and call it from both | One definition of `exceeds`/`near_limit`/`main_beam` | Recompute readings in the draft module (would drift) |
| Administration names | New `data/ref/itu_administrations.json` (symbol → name, cite, review status), transcribed from the BR symbol table in the IFIC Preface; unknown codes left unnamed with a warning | Every input carries a citation; no guessed names | Hard-coded dict in code; LLM supplies the name |
| Polish guard | Protected tokens are every number, `ntc_id`, provision, date, administration code and `hazard_id` in the prose; the LLM output must contain each verbatim, the annex is never sent to the LLM | Mechanical and testable | Similarity score (not a guarantee) |

## Phases

| # | Phase | Effort | Depends on | Status |
|---|---|---|---|---|
| 1 | [Draft model and template](phase-01-draft-model-and-template.md) | 5h | — | completed |
| 2 | [API, polish and CLI](phase-02-api-polish-and-cli.md) | 4h | 1 | completed |
| 3 | [Notice sheet section](phase-03-notice-sheet-section.md) | 3h | 2 | completed |
| 4 | [Docs and verification](phase-04-docs-and-verify.md) | 1.5h | 3 | completed |

## Extension trace

The next likely variant is another letter kind: an AP30A §7.1 comment once a plan-procedure notice appears, or a
"no objection" reply. The stable contract is `DraftKind` + `choose_kind(regulatory)` + one template function per
kind sharing the header, annex and reviewer notes. A new kind adds one enum value, one branch in `choose_kind`, one
body template and one test; the API, polish guard and UI are unchanged. Phase 1's kind tests prove the shape holds
for the four kinds here. No registry or plugin layer is added.

## Risks

| Risk | Mitigation |
|---|---|
| The RR provision wording in a letter is wrong or out of date | Wording quotes the cites already in `rr_comment_windows.json` (RR Edition of 2024); the reviewer notes repeat the cite; the draft is labelled for expert review. |
| A protected-token check misses a changed fact phrased in words ("four months" vs "4 months") | Prose templates write facts as digits only; the guard checks digits; the annex, where most numbers are, never goes to the LLM. |
| The administration name table has transcription errors | `review.status: pending` in the file, shown in the reviewer notes, as with `receiver_classes.json`. |
| Sensitive station data leaks into an outgoing letter | Station-level fields are only rendered in reviewer notes; a test asserts no station id appears in the letter or annex. |
| Drafts for the radio astronomy adjacent-band hazards overstate the concern (method doc, known weakness 8) | The reviewer notes list each hazard's sensitive assumptions and link the known weaknesses section. |

## Unresolved questions

- The administration symbol table must be transcribed from the IFIC Preface; if the implementer cannot open the
  source, the file ships with the codes present in the ingested issues and `name: null`, and drafts show the code
  only.
- Signatory, reference number and contact details stay placeholders (`[Reference]`, `[Name, title]`,
  `[e-mail]`) until Traficom supplies them.
