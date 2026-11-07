import { useQuery } from '@tanstack/react-query'
import { getRouteApi, Link } from '@tanstack/react-router'
import { CircleAlert, Download, Flag, ListTodo, MessageSquare, OctagonAlert, Radar } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { NoticeSheet } from '@/components/notice-sheet'
import { OutcomeBadge } from '@/components/outcome-badge'
import { RiskChat, type ChatScope, type MessagesUpdate } from '@/components/risk-chat'
import { RiskCompare } from '@/components/risk-compare'
import { RiskHeader } from '@/components/risk-header'
import {
  BR_DESCRIPTION,
  ORBIT_LABEL,
  OUTCOME_META,
  OUTCOME_ORDER,
  PFD_FILTER_LABEL,
  WORK_QUEUE_DESCRIPTION,
  WORK_QUEUE_FILTER,
  noticesCsv,
  todayIso,
} from '@/components/risk-meta'
import { RiskTable, type RiskTableView } from '@/components/risk-table'
import { StatCard } from '@/components/stat-card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { ChatMessage, NoticeSummary, Outcome } from '@/lib/api'
import { saveFile } from '@/lib/download'
import { errorText, riskIssuesQuery, riskModelQuery, riskNoticesQuery } from '@/lib/queries'

export type RiskSearch = RiskTableView & {
  ific?: number
  ntc?: number
  compare?: string
  as_of?: string
  chat?: boolean
  draft?: boolean
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

  const issues = useQuery(riskIssuesQuery)
  const model = useQuery(riskModelQuery)
  const list = issues.data ?? []
  const issue =
    list.find((i) => i.ific_no === search.ific) ?? (search.ific == null ? (list.find((i) => i.assessed) ?? list[0]) : undefined)
  const assessed = Boolean(issue?.assessed)
  const ificNo = issue?.ific_no ?? 0
  const assessedAt = issue?.assessed_at ?? null

  const technical = useQuery({ ...riskNoticesQuery(ificNo, asOf, 'technical', assessedAt), enabled: assessed })

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
      open: search.open,
      br: search.br,
      pfd: search.pfd,
      q: search.q,
      sort: search.sort,
    }),
    [search.outcome, search.service, search.adm, search.prov, search.orbit, search.open, search.br, search.pfd, search.q, search.sort],
  )
  const setTableView = useCallback(
    ({ outcome, service, adm, prov, orbit, open, br, pfd, q, sort }: RiskTableView) =>
      patch({ outcome, service, adm, prov, orbit, open, br, pfd, q, sort }),
    [patch],
  )
  const inQueueView =
    search.outcome === WORK_QUEUE_FILTER.outcome &&
    search.open === WORK_QUEUE_FILTER.open &&
    !search.br &&
    !search.pfd &&
    search.sort === WORK_QUEUE_FILTER.sort
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

  const [visibleIds, setVisibleIds] = useState<number[]>([])
  const [threads, setThreads] = useState<Record<string, ChatMessage[]>>({})
  // Labels, not raw params, so the model knows what the user filtered on.
  const chatFilters = useMemo(() => {
    const entries: [string, string | undefined][] = [
      ['outcome', search.outcome && OUTCOME_META[search.outcome].label],
      ['service', search.service && serviceLabel(search.service)],
      ['administration', search.adm],
      ['provision', search.prov],
      ['orbit', search.orbit && ORBIT_LABEL[search.orbit]],
      ['comment window', search.open ? 'not closed' : undefined],
      ['BR identified Finland', search.br ? 'yes' : undefined],
      ['pfd vs RR Table 21-4', search.pfd && PFD_FILTER_LABEL[search.pfd]],
      ['search', search.q],
      ['sort', search.sort],
    ]
    return Object.fromEntries(entries.filter((e): e is [string, string] => Boolean(e[1])))
  }, [search.outcome, search.service, search.adm, search.prov, search.orbit, search.open, search.br, search.pfd, search.q, search.sort, serviceLabel])
  const chatScope: ChatScope =
    search.ntc != null ? { kind: 'notice', ntcId: search.ntc } : { kind: 'view', ids: visibleIds, filters: chatFilters }
  const threadKey =
    chatScope.kind === 'notice'
      ? `notice:${ificNo}:${asOf}:${chatScope.ntcId}`
      : `view:${ificNo}:${asOf}:${JSON.stringify(chatFilters)}`
  const updateThread = useCallback<MessagesUpdate>(
    (update) => setThreads((prev) => ({ ...prev, [threadKey]: update(prev[threadKey] ?? []) })),
    [threadKey],
  )
  const chatPanel = (
    <RiskChat
      key={threadKey}
      ificNo={ificNo}
      asOf={asOf}
      scope={chatScope}
      messages={threads[threadKey] ?? []}
      onMessagesChange={updateThread}
      className={chatScope.kind === 'notice' ? 'h-full' : 'flex-1'}
    />
  )

  const downloadCsv = () => {
    const byId = new Map((technical.data?.notices ?? []).map((n) => [n.ntc_id, n]))
    const rows = visibleIds.flatMap((id) => byId.get(id) ?? [])
    saveFile(`ific${ificNo}-notices-${asOf}.csv`, noticesCsv(rows, serviceLabel), 'text/csv;charset=utf-8')
  }

  const summary = useMemo(() => {
    const notices = technical.data?.notices ?? []
    const exceedingServices = [...new Set(notices.flatMap((n) => n.services_exceeding))]
    return {
      counts: issue?.outcome_counts ?? countOutcomes(notices),
      queue: notices.filter((n) => n.in_queue).length,
      fin: notices.filter((n) => n.regulatory.fin_identified).length,
      exceedingServices,
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
              <Link to="/sources">Go to IFIC watcher</Link>
            </Button>
          </CardContent>
        </Card>
      </>
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
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type="button"
                              onClick={() => patch({ outcome: search.outcome === outcome ? undefined : outcome })}
                              aria-pressed={search.outcome === outcome}
                              className="flex items-center gap-1.5 rounded-md p-0.5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none aria-pressed:ring-2 aria-pressed:ring-ring/60"
                            >
                              <OutcomeBadge outcome={outcome} />
                              <span className="text-lg font-semibold tabular-nums">{summary.counts[outcome]}</span>
                            </button>
                          </TooltipTrigger>
                          <TooltipContent className="flex-col items-start gap-1">
                            <span>{OUTCOME_META[outcome].description}</span>
                            <span className="opacity-70">
                              A notice counts once, under its worst hazard. Click to{' '}
                              {search.outcome === outcome ? 'clear the filter' : 'filter the table'}.
                            </span>
                          </TooltipContent>
                        </Tooltip>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
            <StatCard
              label="Work queue"
              labelHint={WORK_QUEUE_DESCRIPTION}
              icon={ListTodo}
              loading={technical.isPending}
              value={summary.queue}
              hint="Exceeds, window not closed"
              onClick={() => patch(WORK_QUEUE_FILTER)}
              pressed={inQueueView}
            />
            <StatCard
              label="BR identified Finland"
              labelHint={BR_DESCRIPTION}
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
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                Sorted by worst outcome, share violating, median exceedance, pfd outcome, then notice id, unless a column is sorted.
              </p>
              {technical.data && (
                <div className="flex flex-wrap gap-2">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      {/* A disabled button gets no pointer events, so the span carries the tooltip. */}
                      <span tabIndex={visibleIds.length ? undefined : 0}>
                        <Button variant="outline" size="sm" onClick={downloadCsv} disabled={!visibleIds.length}>
                          <Download aria-hidden /> Download CSV
                        </Button>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      {visibleIds.length
                        ? `The ${visibleIds.length} notices the table shows, in table order, across all pages`
                        : 'No notices match the filters'}
                    </TooltipContent>
                  </Tooltip>
                  <Button variant="outline" size="sm" onClick={() => patch({ chat: true })}>
                    <MessageSquare aria-hidden /> Ask about this view
                  </Button>
                </div>
              )}
            </div>
            <RiskTable
              notices={technical.data?.notices}
              isPending={technical.isPending}
              view={tableView}
              onViewChange={setTableView}
              selected={selected}
              onSelectedChange={setSelected}
              onOpen={openNotice}
              serviceLabel={serviceLabel}
              empty={`IFIC ${issue.ific_no} has no assessed notices.`}
              onVisibleIdsChange={setVisibleIds}
            />
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
            onClose={() => patch({ ntc: undefined, chat: undefined, draft: undefined })}
            chatOpen={Boolean(search.chat)}
            onChatOpenChange={(open) => patch({ chat: open || undefined })}
            draftOpen={Boolean(search.draft)}
            onDraftOpenChange={(open) => patch({ draft: open || undefined })}
            chat={search.ntc != null && chatPanel}
          />

          <Sheet
            open={Boolean(search.chat) && search.ntc == null && Boolean(technical.data)}
            onOpenChange={(open) => !open && patch({ chat: undefined })}
          >
            <SheetContent className="w-full gap-0 data-[side=right]:sm:max-w-md">
              <SheetHeader className="pr-12">
                <SheetTitle>Ask about this view</SheetTitle>
                <SheetDescription>The notices the table shows, after filters and search.</SheetDescription>
              </SheetHeader>
              {search.ntc == null && chatPanel}
            </SheetContent>
          </Sheet>
        </>
      )}
    </>
  )
}
