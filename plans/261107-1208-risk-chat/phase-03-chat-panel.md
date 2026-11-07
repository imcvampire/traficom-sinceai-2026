---
phase: 3
title: Chat panel on /risk
status: completed
depends_on: [2]
---

# Phase 03: Chat panel on /risk

## Context

See [plan.md](plan.md) and [phase 02](phase-02-chat-api.md). Read:
- `frontend/src/router.tsx` (the `/risk` `validateSearch`);
- `frontend/src/pages/risk.tsx`;
- `frontend/src/components/risk-table.tsx` (the TanStack table instance);
- `frontend/src/components/notice-sheet.tsx` and `ui/sheet.tsx`;
- `frontend/src/lib/api.ts` (`request`, `ApiError`) and `lib/queries.ts`;
- `docs/frontend.md`.

Style: single quotes, no semicolons, 2 spaces. Use existing shadcn components; add `textarea` with
`bunx --bun shadcn@latest add textarea` if needed.

## Files

| File | Action |
|---|---|
| `frontend/src/lib/api.ts` | Types `ChatMessage`, `ChatRequest`, `ChatStatus`; `getChatStatus()`; `streamRiskChat(ificNo, asOf, body, { signal, onDelta }) -> Promise<{ usage }>`, which POSTs with `fetch`, throws `ApiError` on non-2xx (same detail parsing as `request`), reads `res.body` with a `TextDecoder`, splits on blank lines, dispatches `delta` / `done` / `error` events and throws on `error`. |
| `frontend/src/lib/queries.ts` | `chatStatusQuery` (`staleTime: Infinity`). |
| `frontend/src/components/risk-table.tsx` | Optional prop `onVisibleIdsChange?: (ids: number[]) => void`, called from an effect on `table.getPrePaginationRowModel().rows` (filtered and sorted, all pages). |
| `frontend/src/components/risk-chat.tsx` | **New.** The chat UI, see below. |
| `frontend/src/components/notice-sheet.tsx` | Props `chatOpen`, `onChatOpenChange`, `chat: ReactNode`. Header button "Ask" (lucide `MessageSquare`, `aria-pressed`). When open, the sheet widens (`sm:max-w-7xl`) and the body becomes two columns on `lg` (details scroll on the left, chat column ~28rem on the right); below `lg` the chat stacks above the details at a fixed height. |
| `frontend/src/pages/risk.tsx` | Visible-id state from the table; thread map; "Ask about this view" button above the table; the view-scope chat `Sheet`; wiring of the notice sheet; `onClose` clears `ntc` and `chat`. |
| `frontend/src/router.tsx` | `chat: asFlag(search.chat)`; add `chat?: boolean` to `RiskSearch`. |

## `RiskChat`

Props: `ificNo`, `asOf`, `scope: { kind: 'view'; ids: number[]; filters: Record<string, string> } | { kind:
'notice'; ntcId: number }`, `messages`, `onMessagesChange`.

- Header line: the scope in words ("59 notices · outcome Exceeds" or "Notice 326500094") and a muted
  "Explanation, not assessment · <model>" line.
- Disabled state from `chatStatusQuery`: an `Alert` with the server's `reason`; the composer is disabled.
- Empty state: three suggested questions per scope (view: "Which Finnish services are most affected?", "Which of
  these have an open comment window?", "What drives the largest exceedances?"; notice: "Why does this notice
  exceed?", "Which assumptions could change the outcome?", "What is the regulatory situation?").
- Messages: user right-aligned, assistant left, `whitespace-pre-wrap`, `aria-live="polite"` on the list. While
  waiting for the first delta, show "Thinking…".
- Composer: textarea, Enter sends, Shift+Enter newline, Stop button aborts via `AbortController`. Abort on unmount.
- Errors: 429 → "Another answer is being generated, try again shortly"; 503/502 and stream `error` → the detail,
  with a Retry that resends the last user turn. A failed or aborted assistant turn is not kept in history.
- Send: append the user turn, call `streamRiskChat` with the full history; `onDelta` appends to the pending
  assistant turn.

## Page wiring

- Thread key: view scope `view:${ificNo}:${asOf}:${JSON.stringify(filters)}`; notice scope
  `notice:${ificNo}:${asOf}:${ntc}`. Threads live in a `useState<Record<string, ChatMessage[]>>` in `RiskPage`.
- `filters` are the active `RiskTableView` values with labels (outcome label, service label, `q`, `open`, `br`,
  `sort`), so the model knows what the user filtered on.
- View sheet open when `search.chat && search.ntc == null`. The button and the sheet are hidden while no issue
  is assessed.

## Validation

```sh
cd frontend && bunx tsc -b --noEmit && bunx oxlint
```

Manual check with `mise run dev` (port 5173 is `strictPort`; free it, don't change it): on
`/risk?outcome=exceeds&chat=1` the request payload's `ntc_ids` length equals the table's filtered count; opening a
notice and pressing Ask shows details and chat side by side; reload keeps the panel open; closing the notice clears
`chat`.

## Rollback

Revert the listed frontend files and delete `risk-chat.tsx`.
