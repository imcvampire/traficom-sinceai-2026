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
  `terrestrial.tsx` (`/terrestrial`), `stations.tsx` (`/stations`) and the 404 page.

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
| `pfd` | RR Table 21-4 check: `exceeds` (pfd above a limit on Finnish territory), `near` (within 3 dB below a limit), `any_limit` (at least one row was evaluated) |
| `sort` | `<column>.(asc\|desc)`, columns `outcome`, `network`, `adm`, `prov`, `share`, `exceedance`, `pfd`, `days_left`, `fin`; without it the table keeps the server's technical order (worst outcome, share violating, median exceedance, pfd outcome, `ntc_id`) |
| `ntc` | Opens the detail sheet for that notice, so a detail view can be shared |
| `compare` | Comma-separated `ntc_id` list for the compare view |
| `as_of` | `YYYY-MM-DD` evaluation date for the regulatory context; omitted means today |
| `chat` | `true`: opens the chat panel. Its scope is the open notice (`ntc`), else the notices the table shows after filters and search. Closing the notice sheet clears it |
| `draft` | `true`: shows the **Draft letter** section of the open notice (`ntc`); the draft is only fetched while it is set. Closing the notice sheet clears it |

The **Work queue** stat card counts the notices the API flags `in_queue` (an `exceeds` outcome and a comment window
that has not closed). Clicking it sets `outcome=exceeds&open=true&sort=days_left.asc`, which lists the same notices; the
**Window not closed** filter is the `open` param.

The **pfd vs Art. 21** column shows `max_pfd_margin_db` (pfd minus the Table 21-4 limit) coloured by the pfd outcome:
`exceeds`, near limit, `meets`, "No limit" (no Table 21-4 row applies, greyed, not green) and "Re-assess" for results
stored before the check existed. The notice sheet lists every check under **pfd limits (RR Art. 21, Table 21-4)**,
with inputs, citations and assumptions per row, and a "review pending" banner while the Table 21-4 transcription is
unreviewed. The column and the section do not change the worst outcome or the work queue.

**Download CSV** saves the notices the table shows (after filters, search and sort, across all pages, in table order)
to `ific<no>-notices-<as_of>.csv`. It is built in the browser from the loaded notice list, one row per notice, with
raw values: share violating as 0–1, dB as numbers, ISO dates, `true`/`false`, empty cells for nulls, and service labels
joined by `; `. The file is UTF-8 with a BOM so Excel reads non-ASCII names, and text cells that start with `=`, `+`,
`-` or `@` get a leading `'` so spreadsheets do not run them as formulas. There is no score or rank column. Regulatory
columns follow the page's `as_of`. The `pfd_outcome` and `max_pfd_margin_db` columns are empty for results stored
before the pfd check.

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

Components: `risk-header.tsx` (issue picker, Assess button with 3 s job polling), `risk-method.tsx` (Method & parameters sheet: method steps, model settings, assumptions with outcome-sensitive ones flagged, receiver-class characteristics with citations and Monte Carlo distributions, input sources), `risk-table.tsx`,
`notice-sheet.tsx` (detail), `risk-chart.tsx` (inline-SVG likelihood–consequence chart), `hazard-inventory.tsx`,
`risk-compare.tsx`, `risk-chat.tsx`, `notice-draft.tsx`, `outcome-badge.tsx` and `risk-meta.ts`. Chart series use the `--series-1..5` tokens, so the
status tokens stay reserved for state.

## `/terrestrial` (terrestrial land mobile)

Expert review of one BR IFIC (terrestrial) issue: foreign land mobile assignments, their relevance to Finland and the
ITU-R P.1546 field strength at the Finnish border against the coordination criterion of their band. It reads
`/api/terrestrial/*` and never shows a composite score. The page is lazy-loaded because the map tab uses MapLibre.

**URL params.** All state is in the URL, and invalid values are dropped (an invalid item of a list is dropped on its
own). Lists are comma-separated.

| Param | Values |
|---|---|
| `issue` | BR IFIC number; omitted means the latest assessed issue |
| `outcome` | List of `exceeds`, `meets`, `screened_out`, `not_applicable`, `not_assessed`, kept in that API order |
| `adm` | List of administration codes (1–3 letters, upper-cased, at most 8) |
| `change` | `new`, `modified` or `withdrawn` |
| `status` | Publication status `received`, `recorded` or `returned` (sent to the API as `pub_status`) |
| `relevant` | `all` includes the non-relevant rows for false-negative review; omitted means relevant only |
| `criterion` | Criterion id, for example `tr-25-08` |
| `q` | Free text (at most 80 characters) matched against `adm_ref_id`, site name or frequency |
| `ntc` | `terrakey`; opens the evidence sheet |
| `tab` | `map` or `trends`; omitted means the findings table |
| `trend_issues` | List of other assessed issues summed into the trends panel |
| `draft` | Administration code; opens its draft letter |

**Header.** Issue picker, assessment state, and an Assess / Re-assess button (`POST /api/terrestrial/issues/{n}`,
then `GET /issues` is polled every 3 s while the job runs; a 409 shows "already being assessed"). It lists the model
and P.1546 versions and the criteria from `/model`, with a "verified" badge once a transcription has been
checked. The summary card counts every assignment of the issue by outcome; clicking an outcome toggles the `outcome`
filter. The draft-letters card lists the administrations `/drafts` returns.

**Findings table** (`terra-table.tsx`). Rows come in the server's order (outcome, FIN coordination required, margin,
change, publication status) and the client never re-ranks them; 50 rows per page. **Download CSV** fetches
`/assignments.csv` with the current filters, so the file holds every matching row in the same order, not only the
visible page. Columns: outcome and margin (dB),
administration and `adm_ref_id`, class / notice type / change / publication status, f, bandwidth, e.r.p., h1,
criterion (with an "indicative" chip where the criterion does not bind the administration, for example RUS), FIN
coordination status and distance to Finland.

**Evidence sheet** (`terra-sheet.tsx`, opened by `ntc`). Fetches the single assignment, which carries the full P.1546
record: the trigger, the Tier 1 upper bound and the Tier 2 worst point with path segments, other trigger levels, the
parameters table and the P.1546 inputs and steps (collapsed); the relevance signals with their sources; the
regulatory context (RR provision, GE06, criterion applicability, governing bilateral basis, M4 rows, citations); the
MODIFY diff; the notice, site, antenna and publication fields with their source tags; and the assumptions by id, with
their text from `/model`.

**Map** (`terra-map.tsx`). Same MapLibre setup and OSM basemap as `/stations`. It draws the relevant transmitters of the
filtered list, coloured by outcome with the status tokens (legend with icon and label). Every `exceeds` site also
shows its worst Finnish point as a ring. Clicking a site selects it: a dashed line goes to its worst Finnish point
(Tier 2, else the Tier 1 nearest point), labelled with E and the margin, and a card offers **Open evidence**. The
selection is not in the URL; it starts from `ntc`.

**Trends** (`terra-trends.tsx`). Per neighbour administration, small multiples of the notices first published
(received, part 1) in the summed issues, by band, distance bin, station class and bandwidth, one `--series-1..4`
colour per dimension. The anomaly rules of the selected issue list their matches, each linking to its row (`ntc`).

**Draft letter** (`terra-draft.tsx`, opened by `draft`). The "DRAFT – for expert review, not sent" banner, the letter
kind (chosen by the server), the addressee, warnings, Copy and Download `.md` (`brific<no>-<adm>-<kind>.md`), the
annex table, the basis and the collapsed reviewer notes. **Polish with LLM** rewrites the body paragraphs; a rejected
polish (422) keeps the template and shows the reason with the dropped and added protected tokens, 429 and 503 show
their reasons, and the button is disabled when `/api/risk/chat` reports the LLM is off. A 409 shows the API's
"no concern" reason. A polished letter lives in component state only.

Components: `pages/terrestrial.tsx` (header, filters, tabs), `terra-table.tsx`, `terra-sheet.tsx`, `terra-map.tsx`,
`terra-trends.tsx`, `terra-draft.tsx` and `terra-meta.ts` (search type, labels, term hints, formatters). The types are
the `Terra*` block of `src/lib/api.ts`, mirrored from `backend/src/ific/terra/schemas.py`.

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
