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
| Map | [MapLibre GL JS](https://maplibre.org) 6 | Used directly; OSM raster tiles from `VITE_MAP_TILE_URL`. The worker is bundled through Vite (`?worker&url`) and the `/stations` route is lazy-loaded |

## Layout

- `src/lib/`: the typed API client (`api.ts`), queries and mutations, formatters, and status metadata.
- `src/components/`: the app shell (sidebar and header), watcher controls, files table, status badge and meter, and the
  theme provider and toggle.
- `src/pages/`: `overview.tsx` (`/`), `sources.tsx` (`/sources?status=&q=&sort=`), `risk.tsx` (`/risk`),
  `stations.tsx` (`/stations`) and the 404 page.

## `/risk` (interference risk)

The risk-informed interference assessment demo ([method](interference-risk-assessment.md)). It reads `/api/risk/*`
and never shows a composite score. All state is in the URL, and invalid values are dropped:

| Param | Values |
|---|---|
| `ific` | Issue number |
| `outcome` | `exceeds`, `meets`, `screened_out`, `not_applicable`, `not_assessed` |
| `service`, `adm`, `prov`, `q` | Service class id, administration, provision, free-text search |
| `orbit` | `gso`, `ngso`, `es` |
| `open` | `true`: hide notices whose comment window has closed by the `as_of` date (keeps open windows and stages without one) |
| `br` | `true`: only notices where the BR identified Finland (`provn` or `tr_aff_ntw` lists FIN) |
| `sort` | `<column>.(asc\|desc)`; without it the table keeps the server's technical order (worst outcome, share violating, median exceedance, `ntc_id`) |
| `ntc` | Opens the detail sheet for that notice, so a detail view can be shared |
| `compare` | Comma-separated `ntc_id` list for the compare view |
| `as_of` | `YYYY-MM-DD` evaluation date for the regulatory context; omitted means today |
| `chat` | `true`: opens the chat panel. Its scope is the open notice (`ntc`), else the notices the table shows after filters and search. Closing the notice sheet clears it |
| `draft` | `true`: shows the **Draft letter** section of the open notice (`ntc`); the draft is only fetched while it is set. Closing the notice sheet clears it |

The **Work queue** stat card counts the notices the API flags `in_queue` (an `exceeds` outcome and a comment window
that has not closed). Clicking it sets `outcome=exceeds&open=true&sort=days_left.asc`, which lists the same notices; the
**Window not closed** filter is the `open` param.

The **chat panel** (`risk-chat.tsx`) answers questions about stored results. In view scope it opens as a right sheet
from **Ask about this view** and sends the table's filtered `ntc_id`s in sort order, plus the active filters as
labels. In notice scope the **Ask** button in the notice sheet widens it and shows the chat as a column beside the
details (stacked above them below `lg`). The server builds the context from stored results and the method doc, so the
browser never sends record data. Answers are labelled "Explanation, not assessment". Conversations live in page
memory per scope and are lost on reload; only the open state is in the URL. When `GET /api/risk/chat` reports
`enabled: false`, the panel shows the reason and the composer is disabled.

The **Draft letter** section (`notice-draft.tsx`) shows the letter kind with its RR basis, the counterparty, the
deadline and any warnings above the letter, with Copy, Download `.md` (`ific<no>-<ntc_id>-<kind>.md`) and **Polish
with LLM**. A notice without a concern shows the API's 409 reason instead. A polished letter lives in component state
only, with a Template/Polished toggle, and is dropped when the notice or `as_of` changes; a rejected polish keeps the
template and lists the protected tokens that changed. The polish button is disabled with the reason when the chat
reports the LLM is off. Reviewer notes sit in a collapsed "Internal – do not send" block. Every view carries the
"DRAFT – for expert review, not sent" banner.

Components: `risk-header.tsx` (issue picker, Assess button with 3 s job polling, Method popover), `risk-table.tsx`,
`notice-sheet.tsx` (detail), `risk-chart.tsx` (inline-SVG likelihood–consequence chart), `hazard-inventory.tsx`,
`risk-compare.tsx`, `risk-chat.tsx`, `notice-draft.tsx`, `outcome-badge.tsx` and `risk-meta.ts`. Chart series use the `--series-1..5` tokens, so the
status tokens stay reserved for state.

## `/stations` (stations map)

Every station in `ref.special_interest_station` on an OpenStreetMap basemap. It reads `/api/stations` and
`/api/stations/{source_row}`. The backend computes the contours ([propagation](propagation.md)); the frontend only
draws them.

**What each mark means**

| Mark | Meaning |
|---|---|
| Colour | TX-frequency bin, split where the disc's meaning changes: <30 MHz (below P.1546, no disc), 30–470 MHz (disc to the T/R 25-08 trigger), 470 MHz–1 GHz and 1–4 GHz (disc to the map threshold), >4 GHz (above P.1546, no disc). 470 MHz and 4000 MHz are inclusive upper limits, as in the standards. The 1 GHz split only breaks up a large group and carries no regulatory meaning. An ordinal one-hue ramp in the `--band-0..4` tokens, validated with the dataviz ramp checks in both themes |
| Disc | Radius where the ITU-R P.1546-6 field strength falls to the threshold: 50% locations, receiver 10 m, rural, land path, flat terrain (`h1` = antenna AGL), omnidirectional at maximum e.r.p. The threshold is the T/R 25-08 trigger in 29.7–470 MHz and the slider value elsewhere. Solid outline: radius solved in 1–1000 km. Dashed: below 1 km (drawn at 1 km) or 1000 km and more |
| No disc | 429 stations: 328 without power, 98 outside 30–4000 MHz, 3 without TX frequency. The sheet gives the reason. A missing or >3000 m antenna height also gives no disc, and a station without a position is left off the map |
| Arrow | Azimuth of a directional station, `min(radius, 20 km)` long (5 km without a disc) |
| Column (3D) | Antenna height above ground × exaggeration, on a 2 km hexagon so it shows from zoom 6. Tooltips give real metres |

Layers from bottom to top: `osm` raster (dimmed in dark mode), `contour-fill` at 4% opacity with its outlines,
`azimuth`, `site`, `site-selected`, and `mast`. The masts are on top so that in 3D they stand in front of the flat
dots.

**URL params.** Invalid values are dropped.

| Param | Values |
|---|---|
| `band` | Comma-separated bins `0`–`4` (deduplicated), or `none`; absent means all. Stations without a TX frequency are never hidden by the band filter |
| `q` | Digits of a station number |
| `station` | `source_row`; opens the detail sheet |
| `view` | `2d` (default) or `3d` (55° pitch, columns) |
| `t` | Time percentage `1`, `10` (default) or `50` |
| `thr` | Threshold −20 to 120 dBµV/m, default 30, used where T/R 25-08 does not apply. The slider is debounced by 300 ms |
| `contours` | `off` hides the discs |
| `ex` | Column exaggeration 1–50, default 20 |

**Interaction**
- Hovering a station shows a tooltip and highlights its disc: a 25% fill with a 2.5 px outline in the foreground ink, so it stands out from the blue band outlines. The highlight shows even when contours are switched off.
- Clicking a station opens its sheet.
- A click that hits several stations within 6 px opens a picker.

The sheet shows:
- parameters with units;
- the contour inputs, threshold, citation and assumptions;
- the P.1546 intermediates at the radius;
- M4 overlaps;
- quality flags;
- the spreadsheet row and raw columns.

**States**
- API error: an alert with a retry button.
- WebGL missing: an alert.
- Tile errors: a small notice, while stations still render.

Components: `station-map.tsx` (MapLibre, created once, updated from props), `station-legend.tsx`,
`station-sheet.tsx`, `station-meta.ts` (bins, labels, formatters, search type) and `src/lib/geo.ts` (spherical
circle, arrow and hexagon geometry).

**Basemap.** `VITE_MAP_TILE_URL` is a raster XYZ URL read at build time. Its default is
`https://tile.openstreetmap.org/{z}/{x}/{y}.png`. The OSM tile usage policy allows light use with the
"© OpenStreetMap contributors" attribution, which the map shows. Point the variable at another tile server for
heavier use.

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
- **MapLibre CSS.** `maplibre-gl.css` is unlayered, so it beats Tailwind utilities on the same element (for example,
  `.maplibregl-map` forces `position: relative`). Put layout classes on a wrapper, not on the map container.
- **Lint.** `oxlint` ignores the generated `src/components/ui/**` files (see `.oxlintrc.json`).
