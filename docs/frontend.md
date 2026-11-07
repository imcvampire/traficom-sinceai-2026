# Frontend

The frontend is a React 19 single-page app in `frontend/`, built with Vite. It talks only to the FastAPI backend
through the `/api` proxy (`vite.config.ts` → `127.0.0.1:8000`). Run it with `mise run web`, or with `mise run dev`
to start the API as well.

## Stack

| Concern | Choice | Notes |
|---|---|---|
| Components | [shadcn/ui](https://ui.shadcn.com) (Radix base, `nova` preset) | Generated into `src/components/ui/`. Add more with `bunx --bun shadcn@latest add <name>` |
| Styling | Tailwind CSS v4 | Theme tokens live in `src/index.css` |
| Server state | TanStack Query | Query options and mutations are in `src/lib/queries.ts` |
| Routing | TanStack Router, code-based | `src/router.tsx`. Table filters live in the URL search params |
| Tables | TanStack Table v8 | `src/components/files-table.tsx` |
| Icons, toasts | lucide-react, Sonner | |

## Layout

- `src/lib/`: the typed API client (`api.ts`), queries and mutations, formatters, and status metadata.
- `src/components/`: the app shell (sidebar and header), watcher controls, files table, status badge and meter, and the
  theme provider and toggle.
- `src/pages/`: `overview.tsx` (`/`), `sources.tsx` (`/sources?status=&q=&sort=`), `risk.tsx` (`/risk`) and the 404
  page.

## `/risk` (interference risk)

The risk-informed interference assessment demo ([method](interference-risk-assessment.md)). It reads `/api/risk/*`
and never shows a composite score. All state is in the URL, and invalid values are dropped:

| Param | Values |
|---|---|
| `ific` | Issue number |
| `view` | `queue` (default) or `technical` |
| `outcome` | `exceeds`, `meets`, `screened_out`, `not_applicable`, `not_assessed` |
| `service`, `adm`, `prov`, `q` | Service class id, administration, provision, free-text search |
| `orbit` | `gso`, `ngso`, `es` |
| `sort` | `<column>.(asc\|desc)`; without it the table keeps the server order of the active view |
| `ntc` | Opens the detail sheet for that notice, so a detail view can be shared |
| `compare` | Comma-separated `ntc_id` list for the compare view |
| `as_of` | `YYYY-MM-DD` evaluation date for the regulatory context; omitted means today |

Components: `risk-header.tsx` (issue picker, Assess button with 3 s job polling, Method popover), `risk-table.tsx`,
`notice-sheet.tsx` (detail), `risk-chart.tsx` (inline-SVG likelihood–consequence chart), `hazard-inventory.tsx`,
`risk-compare.tsx`, `outcome-badge.tsx` and `risk-meta.ts`. Chart series use the `--series-1..5` tokens, so the
status tokens stay reserved for state.

## Conventions

- **Theme tokens.** Colors are CSS variables in `src/index.css`.
  - `primary` is blue.
  - `status-good`, `status-warning`, `status-critical` and `status-neutral` are reserved for state. They are never
    used for decoration, and they always appear together with an icon and a label.
- **Polling.** The watcher state refetches every 15 s, or every 3 s while a check is running. TanStack Query pauses
  polling while the tab is hidden. The pause/resume toggle updates the UI optimistically and rolls back if the request
  fails.
- **TanStack Table state.** Any controlled table state, such as `sorting` and `columnFilters`, must be memoised. A new
  array on every render makes the row models recompute, and the page-index auto-reset then re-renders forever.
- **Theme.** `src/components/theme-provider.tsx` handles light, dark and system themes. `index.html` applies the saved
  theme before first paint. `next-themes` is deliberately not used: its inline script triggers a React 19 error in a
  client-only app.
- **Lint.** `oxlint` ignores the generated `src/components/ui/**` files (see `.oxlintrc.json`).
