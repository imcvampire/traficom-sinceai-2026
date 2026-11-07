import { createRootRoute, createRoute, createRouter, lazyRouteComponent } from '@tanstack/react-router'
import { AppShell } from '@/components/app-shell'
import { THRESHOLD_RANGE, type StationsSearch } from '@/components/station-meta'
import type { FilesTableView } from '@/components/files-table'
import { PFD_FILTERS, type PfdFilter } from '@/components/risk-meta'
import { RISK_SORT_RE } from '@/components/risk-table'
import type { FileStatus, OrbitType, Outcome } from '@/lib/api'
import { NotFound } from '@/pages/not-found'
import { OverviewPage } from '@/pages/overview'
import { RiskPage, type RiskSearch } from '@/pages/risk'
import { SourcesPage } from '@/pages/sources'

const FILE_STATUSES: readonly FileStatus[] = ['new', 'downloading', 'downloaded', 'failed']
const SORT_RE = /^(ific_no|published_on|status|size_bytes|downloaded_at)\.(asc|desc)$/

const OUTCOMES: readonly Outcome[] = ['exceeds', 'meets', 'screened_out', 'not_applicable', 'not_assessed']
const ORBITS: readonly OrbitType[] = ['gso', 'ngso', 'es']
const COMPARE_RE = /^\d+(,\d+)*$/
const BAND_RE = /^[0-4](,[0-4])*$/
const TIME_PCTS = [1, 10, 50] as const
const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/

// Search values arrive JSON-parsed, so a numeric-looking string may already be a number.
const asText = (value: unknown) =>
  (typeof value === 'string' && value) || (typeof value === 'number' && Number.isFinite(value) ? String(value) : undefined)

function asId(value: unknown): number | undefined {
  const n = typeof value === 'number' ? value : typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : NaN
  return Number.isSafeInteger(n) && n > 0 ? n : undefined
}

function asDate(value: unknown): string | undefined {
  const match = typeof value === 'string' ? DATE_RE.exec(value) : null
  if (!match) return undefined
  const [y, m, d] = match.slice(1).map(Number)
  const date = new Date(y, m - 1, d)
  return date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d ? value as string : undefined
}

const rootRoute = createRootRoute({ component: AppShell, notFoundComponent: NotFound })

const overviewRoute = createRoute({ getParentRoute: () => rootRoute, path: '/', component: OverviewPage })

const sourcesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/sources',
  component: SourcesPage,
  validateSearch: (search: Record<string, unknown>): FilesTableView => ({
    status: FILE_STATUSES.includes(search.status as FileStatus) ? (search.status as FileStatus) : undefined,
    q: typeof search.q === 'string' && search.q ? search.q : undefined,
    sort: typeof search.sort === 'string' && SORT_RE.test(search.sort) ? search.sort : undefined,
  }),
})

const riskRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/risk',
  component: RiskPage,
  validateSearch: (search: Record<string, unknown>): RiskSearch => {
    const compare = asText(search.compare)
    const sort = asText(search.sort)
    return {
      ific: asId(search.ific),
      outcome: OUTCOMES.includes(search.outcome as Outcome) ? (search.outcome as Outcome) : undefined,
      service: asText(search.service),
      adm: asText(search.adm),
      prov: asText(search.prov),
      orbit: ORBITS.includes(search.orbit as OrbitType) ? (search.orbit as OrbitType) : undefined,
      open: asFlag(search.open),
      br: asFlag(search.br),
      pfd: PFD_FILTERS.includes(search.pfd as PfdFilter) ? (search.pfd as PfdFilter) : undefined,
      q: asText(search.q),
      sort: sort && RISK_SORT_RE.test(sort) ? sort : undefined,
      ntc: asId(search.ntc),
      compare: compare && COMPARE_RE.test(compare) ? compare : undefined,
      as_of: asDate(search.as_of),
      chat: asFlag(search.chat),
      draft: asFlag(search.draft),
    }
  },
})

const asFlag = (value: unknown) => (value === true || value === 'true' || value === 1 || value === '1' ? true : undefined)

function asInt(value: unknown, min: number, max: number): number | undefined {
  const n = typeof value === 'number' ? value : typeof value === 'string' && /^-?\d+$/.test(value) ? Number(value) : NaN
  return Number.isInteger(n) && n >= min && n <= max ? n : undefined
}

const stationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/stations',
  // MapLibre is large, so the map page loads on first visit.
  component: lazyRouteComponent(() => import('@/pages/stations'), 'StationsPage'),
  validateSearch: (search: Record<string, unknown>): StationsSearch => {
    const band = asText(search.band)
    const q = asText(search.q)
    const t = asInt(search.t, 1, 50)
    return {
      band: band === 'none' ? band : band && BAND_RE.test(band) ? [...new Set(band.split(','))].sort().join(',') : undefined,
      q: q && /^\d+$/.test(q) ? q : undefined,
      station: asId(search.station),
      view: search.view === '3d' || search.view === '2d' ? search.view : undefined,
      t: TIME_PCTS.find((v) => v === t),
      thr: asInt(search.thr, THRESHOLD_RANGE[0], THRESHOLD_RANGE[1]),
      contours: search.contours === 'off' ? 'off' : undefined,
      ex: asInt(search.ex, 1, 50),
    }
  },
})

export const router = createRouter({
  routeTree: rootRoute.addChildren([overviewRoute, sourcesRoute, riskRoute, stationsRoute]),
  defaultPreload: 'intent',
  scrollRestoration: true,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
