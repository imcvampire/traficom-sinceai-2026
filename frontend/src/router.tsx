import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'
import { AppShell } from '@/components/app-shell'
import type { FilesTableView } from '@/components/files-table'
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
      view: search.view === 'technical' || search.view === 'queue' ? search.view : undefined,
      outcome: OUTCOMES.includes(search.outcome as Outcome) ? (search.outcome as Outcome) : undefined,
      service: asText(search.service),
      adm: asText(search.adm),
      prov: asText(search.prov),
      orbit: ORBITS.includes(search.orbit as OrbitType) ? (search.orbit as OrbitType) : undefined,
      q: asText(search.q),
      sort: sort && RISK_SORT_RE.test(sort) ? sort : undefined,
      ntc: asId(search.ntc),
      compare: compare && COMPARE_RE.test(compare) ? compare : undefined,
      as_of: asDate(search.as_of),
    }
  },
})

export const router = createRouter({
  routeTree: rootRoute.addChildren([overviewRoute, sourcesRoute, riskRoute]),
  defaultPreload: 'intent',
  scrollRestoration: true,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
