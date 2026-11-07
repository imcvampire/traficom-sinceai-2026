import { useQuery } from '@tanstack/react-query'
import { getRouteApi, Link } from '@tanstack/react-router'
import { CalendarClock, CircleAlert, Flag, ListTodo, OctagonAlert, Radar } from 'lucide-react'
import { useCallback, useMemo } from 'react'
import { NoticeSheet } from '@/components/notice-sheet'
import { OutcomeBadge } from '@/components/outcome-badge'
import { RiskCompare } from '@/components/risk-compare'
import { RiskHeader } from '@/components/risk-header'
import { OUTCOME_ORDER, todayIso } from '@/components/risk-meta'
import { RiskTable, type RiskTableView } from '@/components/risk-table'
import { StatCard } from '@/components/stat-card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import type { NoticeSummary, NoticeView, Outcome } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { errorText, riskIssuesQuery, riskModelQuery, riskNoticesQuery } from '@/lib/queries'

export type RiskSearch = RiskTableView & {
  ific?: number
  view?: NoticeView
  ntc?: number
  compare?: string
  as_of?: string
}

const route = getRouteApi('/risk')

function countOutcomes(notices: NoticeSummary[]): Record<Outcome, number> {
  const counts = Object.fromEntries(OUTCOME_ORDER.map((o) => [o, 0])) as Record<Outcome, number>
  for (const n of notices) counts[n.worst_outcome]++
  return counts
}

function PageIntro() {
  return (
    <section className="space-y-1">
      <h2 className="text-2xl font-semibold tracking-tight">Interference risk</h2>
      <p className="max-w-3xl text-sm text-muted-foreground">
        Likelihood and consequence of interference to Finnish services from the satellite networks in an IFIC issue,
        read against each service's ITU-R protection criterion. Results are shown per hazard, never as a combined score.
        Filters, the open notice and the comparison are kept in the URL.
      </p>
    </section>
  )
}

export function RiskPage() {
  const search = route.useSearch()
  const navigate = route.useNavigate()
  const today = todayIso()
  const asOf = search.as_of ?? today
  const view: NoticeView = search.view ?? 'queue'

  const issues = useQuery(riskIssuesQuery)
  const model = useQuery(riskModelQuery)
  const list = issues.data ?? []
  const issue =
    list.find((i) => i.ific_no === search.ific) ?? (search.ific == null ? (list.find((i) => i.assessed) ?? list[0]) : undefined)
  const assessed = Boolean(issue?.assessed)
  const ificNo = issue?.ific_no ?? 0
  const assessedAt = issue?.assessed_at ?? null

  const technical = useQuery({ ...riskNoticesQuery(ificNo, asOf, 'technical', assessedAt), enabled: assessed })
  const active = useQuery({ ...riskNoticesQuery(ificNo, asOf, view, assessedAt), enabled: assessed })

  const patch = useCallback(
    (next: Partial<RiskSearch>) => void navigate({ search: (prev) => ({ ...prev, ...next }), replace: true }),
    [navigate],
  )

  const tableView = useMemo<RiskTableView>(
    () => ({
      outcome: search.outcome,
      service: search.service,
      adm: search.adm,
      prov: search.prov,
      orbit: search.orbit,
      q: search.q,
      sort: search.sort,
    }),
    [search.outcome, search.service, search.adm, search.prov, search.orbit, search.q, search.sort],
  )
  const setTableView = useCallback(
    ({ outcome, service, adm, prov, orbit, q, sort }: RiskTableView) =>
      patch({ outcome, service, adm, prov, orbit, q, sort }),
    [patch],
  )
  const selected = useMemo(() => (search.compare ? search.compare.split(',').map(Number) : []), [search.compare])

  const serviceLabels = useMemo(
    () => new Map(model.data?.receiver_classes.map((c) => [c.id, c.label]) ?? []),
    [model.data],
  )
  const serviceLabel = useCallback((id: string) => serviceLabels.get(id) ?? id, [serviceLabels])
  const openNotice = useCallback((ntc: number) => patch({ ntc }), [patch])
  const setSelected = useCallback(
    (ids: number[]) => patch({ compare: ids.length ? [...new Set(ids)].join(',') : undefined }),
    [patch],
  )

  const summary = useMemo(() => {
    const notices = technical.data?.notices ?? []
    const exceedingServices = [...new Set(notices.flatMap((n) => n.services_exceeding))]
    const published = notices.map((n) => n.regulatory.d_wic).filter((d): d is string => Boolean(d)).sort()[0]
    return {
      counts: issue?.outcome_counts ?? countOutcomes(notices),
      queue: notices.filter((n) => n.in_queue).length,
      fin: notices.filter((n) => n.regulatory.fin_identified).length,
      exceedingServices,
      published,
    }
  }, [technical.data, issue?.outcome_counts])

  if (issues.isPending)
    return (
      <>
        <PageIntro />
        <Skeleton className="h-36" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-24 first:col-span-2" />
          ))}
        </div>
        <Skeleton className="h-96" />
      </>
    )

  if (issues.isError && !issues.data)
    return (
      <>
        <PageIntro />
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>Could not load IFIC issues</AlertTitle>
          <AlertDescription>{errorText(issues.error)}</AlertDescription>
        </Alert>
      </>
    )

  if (!issue)
    return (
      <>
        <PageIntro />
        <Card>
          <CardHeader>
            <CardTitle>{search.ific != null ? `IFIC ${search.ific} is not available` : 'No IFIC issues yet'}</CardTitle>
            <CardDescription>
              {search.ific != null
                ? 'This issue has not been downloaded. Pick another issue or download it first.'
                : 'Download an IFIC issue first; it then appears here for assessment.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {search.ific != null && list.length > 0 && (
              <Button variant="outline" onClick={() => patch({ ific: undefined, ntc: undefined, compare: undefined })}>
                Show the latest assessed issue
              </Button>
            )}
            <Button variant="outline" asChild>
              <Link to="/sources">Go to Space IFIC sources</Link>
            </Button>
          </CardContent>
        </Card>
      </>
    )

  const queueEmpty = (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-3">
      <CalendarClock className="size-5" aria-hidden />
      <p>
        The work queue is empty as of {formatDate(asOf)}: no notice with an exceeding hazard or a BR finding for Finland
        has an open comment window.
        {summary.published && ` IFIC ${issue.ific_no} was published ${formatDate(summary.published)}.`} Set an earlier
        “As of” date to see the queue as it stood then.
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        {summary.published && summary.published !== asOf && (
          <Button variant="outline" size="sm" onClick={() => patch({ as_of: summary.published })}>
            As of {formatDate(summary.published)}
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={() => patch({ view: 'technical' })}>
          Show all notices
        </Button>
      </div>
    </div>
  )

  return (
    <>
      <PageIntro />

      <RiskHeader
        issues={list}
        issue={issue}
        asOf={asOf}
        asOfIsToday={asOf === today}
        modelVersion={technical.data?.model_version ?? issue.model_version}
        onIssueChange={(ific) => patch({ ific, ntc: undefined, compare: undefined })}
        onAsOfChange={(value) => patch({ as_of: value && value !== today ? value : undefined })}
      />

      {!assessed ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Radar className="size-4 text-primary" aria-hidden /> IFIC {issue.ific_no} has not been assessed
            </CardTitle>
            <CardDescription>
              {issue.job.status === 'running'
                ? 'The assessment is running. Results appear here when it finishes.'
                : 'Run Assess to inventory the hazards of every notice and compute their likelihood–consequence curves.'}
            </CardDescription>
          </CardHeader>
        </Card>
      ) : technical.isError && !technical.data ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>Could not load the assessment of IFIC {issue.ific_no}</AlertTitle>
          <AlertDescription>{errorText(technical.error)}</AlertDescription>
        </Alert>
      ) : (
        <>
          <section className="grid grid-cols-2 gap-4 lg:grid-cols-5 [&>*]:min-w-0" aria-label="Summary">
            <Card className="col-span-2 gap-0 py-4">
              <CardContent className="px-4">
                <div className="text-sm text-muted-foreground">Notices by worst outcome</div>
                {technical.isPending ? (
                  <Skeleton className="mt-2 h-8 w-full" />
                ) : (
                  <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-2">
                    {OUTCOME_ORDER.map((outcome) => (
                      <li key={outcome}>
                        <button
                          type="button"
                          onClick={() => patch({ outcome: search.outcome === outcome ? undefined : outcome })}
                          aria-pressed={search.outcome === outcome}
                          className="flex items-center gap-1.5 rounded-md p-0.5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none aria-pressed:ring-2 aria-pressed:ring-ring/60"
                        >
                          <OutcomeBadge outcome={outcome} />
                          <span className="text-lg font-semibold tabular-nums">{summary.counts[outcome]}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
            <StatCard
              label="Work queue"
              icon={ListTodo}
              loading={technical.isPending}
              value={summary.queue}
              hint={summary.queue ? 'Open comment window' : 'No open comment window'}
            />
            <StatCard
              label="BR identified Finland"
              icon={Flag}
              loading={technical.isPending}
              value={summary.fin}
              hint="provn or tr_aff_ntw lists FIN"
            />
            <StatCard
              label="Finnish services exceeding"
              icon={OctagonAlert}
              tone={summary.exceedingServices.length ? 'critical' : 'default'}
              loading={technical.isPending}
              value={summary.exceedingServices.length}
              hint={
                summary.exceedingServices.length ? (
                  <span title={summary.exceedingServices.map(serviceLabel).join(', ')}>
                    {summary.exceedingServices.map(serviceLabel).join(', ')}
                  </span>
                ) : (
                  'No hazard exceeds a criterion'
                )
              }
            />
          </section>

          <section className="min-w-0 space-y-3" aria-label="Notices">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <ToggleGroup
                type="single"
                variant="outline"
                size="sm"
                value={view}
                onValueChange={(value) => value && patch({ view: value === 'queue' ? undefined : (value as NoticeView) })}
                aria-label="Notice order"
              >
                <ToggleGroupItem value="queue" className="px-3">
                  Work queue
                </ToggleGroupItem>
                <ToggleGroupItem value="technical" className="px-3">
                  All notices
                </ToggleGroupItem>
              </ToggleGroup>
              <p className="text-xs text-muted-foreground">
                {view === 'queue'
                  ? 'Open comment window with an exceeding hazard or a BR finding; sorted by days left, then technical order.'
                  : 'Sorted by worst outcome, share violating, median exceedance, then notice id.'}
              </p>
            </div>
            {active.isError && !active.data ? (
              <Alert variant="destructive">
                <CircleAlert aria-hidden />
                <AlertTitle>Could not load notices</AlertTitle>
                <AlertDescription>{errorText(active.error)}</AlertDescription>
              </Alert>
            ) : (
              <RiskTable
                notices={active.data?.notices}
                isPending={active.isPending}
                view={tableView}
                onViewChange={setTableView}
                selected={selected}
                onSelectedChange={setSelected}
                onOpen={openNotice}
                serviceLabel={serviceLabel}
                empty={view === 'queue' ? queueEmpty : `IFIC ${issue.ific_no} has no assessed notices.`}
              />
            )}
          </section>

          {selected.length > 0 && (
            <RiskCompare
              ificNo={issue.ific_no}
              ids={selected}
              asOf={asOf}
              assessedAt={assessedAt}
              onRemove={(id) => setSelected(selected.filter((s) => s !== id))}
              onClear={() => setSelected([])}
            />
          )}

          <NoticeSheet
            ificNo={issue.ific_no}
            ntcId={search.ntc}
            asOf={asOf}
            assessedAt={assessedAt}
            onClose={() => patch({ ntc: undefined })}
          />
        </>
      )}
    </>
  )
}
