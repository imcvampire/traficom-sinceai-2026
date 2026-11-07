import { useQuery } from '@tanstack/react-query'
import { getRouteApi, Link } from '@tanstack/react-router'
import { CircleAlert, Download, FileText, LoaderCircle, Play, Radar, RotateCw, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState, type ComponentProps } from 'react'
import { OutcomeBadge } from '@/components/outcome-badge'
import { TerraDraft } from '@/components/terra-draft'
import { TerraMap } from '@/components/terra-map'
import {
  CHANGE_LABEL,
  MAX_Q,
  PUB_STATUS_LABEL,
  TERMS,
  TERRA_CHANGES,
  TERRA_OUTCOMES,
  TERRA_OUTCOME_DESCRIPTION,
  TERRA_STATUSES,
  splitIds,
  splitList,
  terraFilters,
  type TerraChangeFilter,
  type TerraSearch,
  type TerraStatusFilter,
  type TerraTab,
} from '@/components/terra-meta'
import { TerraSheet } from '@/components/terra-sheet'
import { TerraTable } from '@/components/terra-table'
import { TerraTrends } from '@/components/terra-trends'
import { TermHint } from '@/components/term-hint'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { Outcome, TerraIssueOut } from '@/lib/api'
import { terraAssignmentsCsvUrl } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import {
  errorText,
  terraAssignmentsQuery,
  terraDraftsQuery,
  terraIssuesQuery,
  terraModelQuery,
  useAssessTerraIssue,
} from '@/lib/queries'

const route = getRouteApi('/terrestrial')
const ALL = 'all'
const DEBOUNCE_MS = 300
const TAB_LABEL: Record<TerraTab, string> = { findings: 'Findings', map: 'Map', trends: 'Trends' }

function issueState(issue: TerraIssueOut): string {
  const { job } = issue
  if (job.status === 'running') return job.total ? `Assessing ${job.done}/${job.total}` : 'Assessing…'
  if (job.status === 'failed') return 'Assessment failed'
  if (issue.assessed)
    return `Assessed${issue.relevant_count != null ? ` · ${issue.relevant_count} relevant of ${issue.assignment_count ?? '?'}` : ''}`
  return issue.ingested ? 'Not assessed' : 'Not ingested'
}

function PageIntro() {
  return (
    <section className="space-y-1">
      <h2 className="text-2xl font-semibold tracking-tight">Terrestrial land mobile</h2>
      <p className="max-w-3xl text-sm text-muted-foreground">
        Foreign land mobile assignments in a BR IFIC (terrestrial) issue, read against the cross-border coordination
        criterion for their band: the ITU-R P.1546 field strength at the Finnish border compared with the trigger.
        Results are hazard outcomes in the API's order, never a combined score. Filters, the open assignment and the
        tab are kept in the URL.
      </p>
    </section>
  )
}

/** A text filter that commits to the URL after a pause in typing, and follows the URL when it changes elsewhere. */
function FilterInput({
  id,
  value,
  onCommit,
  ...props
}: { id: string; value: string | undefined; onCommit: (value: string | undefined) => void } & Omit<
  ComponentProps<typeof Input>,
  'value' | 'onChange' | 'id'
>) {
  const [draft, setDraft] = useState(value ?? '')
  const [seen, setSeen] = useState(value)
  if (seen !== value) {
    setSeen(value)
    setDraft(value ?? '')
  }
  useEffect(() => {
    const next = draft.trim() || undefined
    if (next === value) return
    const timer = setTimeout(() => onCommit(next), DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [draft, value, onCommit])
  return <Input id={id} value={draft} onChange={(e) => setDraft(e.target.value)} {...props} />
}

function Header({ issues, issue, onIssueChange }: { issues: TerraIssueOut[]; issue: TerraIssueOut; onIssueChange: (n: number) => void }) {
  const assess = useAssessTerraIssue()
  const model = useQuery(terraModelQuery)
  const running = issue.job.status === 'running'
  const busy = running || assess.isPending
  const progress = issue.job.total ? (issue.job.done / issue.job.total) * 100 : 0

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div className="grid min-w-0 gap-1.5">
            <Label htmlFor="terra-issue">BR IFIC issue</Label>
            <Select value={String(issue.ific_no)} onValueChange={(value) => onIssueChange(Number(value))}>
              <SelectTrigger id="terra-issue" className="w-full sm:w-80">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {issues.map((i) => (
                  <SelectItem key={i.ific_no} value={String(i.ific_no)}>
                    <span className="font-mono">BR IFIC {i.ific_no}</span>
                    <span className="text-muted-foreground">{issueState(i)}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-wrap items-center gap-2 lg:ml-auto">
            <Button
              onClick={() => assess.mutate(issue.ific_no)}
              disabled={busy}
              aria-describedby={running ? 'terra-job-progress' : undefined}
            >
              {busy ? (
                <LoaderCircle className="animate-spin" aria-hidden />
              ) : issue.assessed ? (
                <RotateCw aria-hidden />
              ) : (
                <Play aria-hidden />
              )}
              {running ? 'Assessing…' : issue.assessed ? 'Re-assess' : 'Assess'}
            </Button>
          </div>
        </div>

        {running && (
          <div id="terra-job-progress" className="space-y-1.5" role="status" aria-live="polite">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Assessing BR IFIC {issue.ific_no}</span>
              <span className="tabular-nums">
                {issue.job.done} of {issue.job.total || '…'} assignments
              </span>
            </div>
            <Progress value={progress} aria-label="Assessment progress" />
          </div>
        )}
        {issue.job.status === 'failed' && (
          <Alert variant="destructive">
            <CircleAlert aria-hidden />
            <AlertTitle>The last assessment of BR IFIC {issue.ific_no} failed</AlertTitle>
            <AlertDescription>{issue.job.error ?? 'No error detail was recorded.'}</AlertDescription>
          </Alert>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
          <span>{issueState(issue)}</span>
          <span>
            Model <span className="font-mono text-foreground">{issue.model_version ?? model.data?.model_version ?? '—'}</span>
          </span>
          {model.data && <span>{model.data.p1546_version}</span>}
          {issue.assessed_at && <span>Assessed {formatDateTime(issue.assessed_at)}</span>}
          <span className="font-mono break-all">{issue.path}</span>
        </div>

        {model.data && (
          <div className="space-y-1.5">
            <div className="text-xs font-medium text-muted-foreground">Criteria</div>
            <ul className="flex flex-wrap gap-2">
              {model.data.criteria.map((c) => (
                <li key={c.id} className="flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs">
                  <Tooltip>
                    <TooltipTrigger className="cursor-help font-mono underline decoration-dotted underline-offset-4">
                      {c.id}
                    </TooltipTrigger>
                    <TooltipContent className="flex-col items-start gap-1">
                      <span>{c.title}</span>
                      <span className="opacity-70">{c.citation}</span>
                      <span className="opacity-70">
                        {c.f_min_mhz}–{c.f_max_mhz} MHz · {c.time_pct}% time · {c.loc_pct}% locations · receiver{' '}
                        {c.rx_height_m} m
                      </span>
                    </TooltipContent>
                  </Tooltip>
                  <span className="text-muted-foreground tabular-nums">
                    {c.f_min_mhz}–{c.f_max_mhz} MHz
                  </span>
                  {c.verified && (
                    <Badge variant="secondary" className="text-[10px]">
                      verified{c.verified_by ? ` by ${c.verified_by}` : ''}
                    </Badge>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function TerrestrialPage() {
  const search = route.useSearch()
  const navigate = route.useNavigate()
  const issues = useQuery(terraIssuesQuery)
  const list = issues.data ?? []
  const issue =
    list.find((i) => i.ific_no === search.issue) ??
    (search.issue == null ? (list.find((i) => i.assessed) ?? list[0]) : undefined)
  const assessed = Boolean(issue?.assessed)
  const ificNo = issue?.ific_no ?? 0
  const assessedAt = issue?.assessed_at ?? null

  const filters = useMemo(() => terraFilters(search), [search])
  const assignments = useQuery({ ...terraAssignmentsQuery(ificNo, filters, assessedAt), enabled: assessed })
  const drafts = useQuery({ ...terraDraftsQuery(ificNo, assessedAt), enabled: assessed })
  const model = useQuery(terraModelQuery)
  const draftAdms = useMemo(() => new Set(drafts.data?.map((d) => d.adm) ?? []), [drafts.data])

  const patch = useCallback(
    (next: Partial<TerraSearch>) => void navigate({ search: (prev) => ({ ...prev, ...next }), replace: true }),
    [navigate],
  )
  const openAssignment = useCallback((ntc: number) => patch({ ntc }), [patch])
  const commitAdm = useCallback(
    (value: string | undefined) => patch({ adm: value?.split(/[\s,]+/).filter(Boolean).join(',').toUpperCase() || undefined }),
    [patch],
  )
  const commitQ = useCallback((q: string | undefined) => patch({ q }), [patch])

  const outcomes = splitList(search.outcome) as Outcome[]
  const toggleOutcome = (o: Outcome) => {
    const next = outcomes.includes(o) ? outcomes.filter((x) => x !== o) : [...outcomes, o]
    patch({ outcome: next.length ? TERRA_OUTCOMES.filter((x) => next.includes(x)).join(',') : undefined })
  }
  const filtered =
    outcomes.length > 0 || search.adm || search.change || search.status || search.relevant || search.criterion || search.q
  const tab: TerraTab = search.tab ?? 'findings'
  const trendIssues = splitIds(search.trend_issues)
  const otherIssues = list.filter((i) => i.assessed && i.ific_no !== ificNo).map((i) => i.ific_no)

  if (issues.isPending)
    return (
      <>
        <PageIntro />
        <Skeleton className="h-36" />
        <Skeleton className="h-96" />
      </>
    )

  if (issues.isError && !issues.data)
    return (
      <>
        <PageIntro />
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>Could not load BR IFIC issues</AlertTitle>
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
            <CardTitle>{search.issue != null ? `BR IFIC ${search.issue} is not available` : 'No BR IFIC issues yet'}</CardTitle>
            <CardDescription>
              {search.issue != null
                ? 'This issue has not been downloaded. Pick another issue or download it first.'
                : 'Download a BR IFIC issue first; it then appears here for assessment.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {search.issue != null && list.length > 0 && (
              <Button variant="outline" onClick={() => patch({ issue: undefined, ntc: undefined, draft: undefined })}>
                Show the latest assessed issue
              </Button>
            )}
            <Button variant="outline" asChild>
              <Link to="/sources">Go to sources</Link>
            </Button>
          </CardContent>
        </Card>
      </>
    )

  const counts = issue.outcome_counts
  return (
    <>
      <PageIntro />
      <Header
        issues={list}
        issue={issue}
        onIssueChange={(n) => patch({ issue: n, ntc: undefined, draft: undefined, trend_issues: undefined })}
      />

      {!assessed ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Radar className="size-4 text-primary" aria-hidden /> BR IFIC {issue.ific_no} has not been assessed
            </CardTitle>
            <CardDescription>
              {issue.job.status === 'running'
                ? 'The assessment is running. Results appear here when it finishes.'
                : 'Run Assess to find the assignments relevant to Finland and compute their field strength at the border.'}
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <>
          <section className="grid gap-4 lg:grid-cols-3 [&>*]:min-w-0" aria-label="Summary">
            <Card className="gap-0 py-4 lg:col-span-2">
              <CardContent className="px-4">
                <div className="text-sm text-muted-foreground">
                  Assignments by outcome{' '}
                  {issue.relevant_count != null && (
                    <span>
                      · {issue.relevant_count} <TermHint hint={TERMS.relevant}>relevant</TermHint> of{' '}
                      {issue.assignment_count}
                    </span>
                  )}
                </div>
                <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-2">
                  {TERRA_OUTCOMES.map((o) => (
                    <li key={o}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            type="button"
                            onClick={() => toggleOutcome(o)}
                            aria-pressed={outcomes.includes(o)}
                            className="flex items-center gap-1.5 rounded-md p-0.5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none aria-pressed:ring-2 aria-pressed:ring-ring/60"
                          >
                            <OutcomeBadge outcome={o} />
                            <span className="text-lg font-semibold tabular-nums">{counts?.[o] ?? 0}</span>
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="flex-col items-start gap-1">
                          <span>{TERRA_OUTCOME_DESCRIPTION[o]}</span>
                          <span className="opacity-70">Counts every assignment of the issue. Click to filter the findings.</span>
                        </TooltipContent>
                      </Tooltip>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
            <Card className="gap-0 py-4">
              <CardContent className="space-y-2 px-4">
                <div className="text-sm text-muted-foreground">Draft letters</div>
                {drafts.isPending ? (
                  <Skeleton className="h-8" />
                ) : drafts.isError ? (
                  <p className="text-xs text-status-critical-foreground">{errorText(drafts.error)}</p>
                ) : drafts.data.length ? (
                  <div className="flex flex-wrap gap-2">
                    {drafts.data.map((d) => (
                      <Button key={d.adm} variant="outline" size="sm" onClick={() => patch({ draft: d.adm })}>
                        <FileText aria-hidden /> {d.adm_name ?? d.adm}
                        <span className="text-muted-foreground tabular-nums">{d.assignments}</span>
                      </Button>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">No administration has a concern to describe.</p>
                )}
              </CardContent>
            </Card>
          </section>

          <section className="flex flex-wrap items-end gap-x-4 gap-y-3" aria-label="Filters">
            <div className="grid gap-1.5">
              <Label htmlFor="terra-adm">Administration</Label>
              <FilterInput id="terra-adm" value={search.adm} onCommit={commitAdm} placeholder="RUS, EST" className="w-32" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="terra-change">Change</Label>
              <Select
                value={search.change ?? ALL}
                onValueChange={(v) => patch({ change: v === ALL ? undefined : (v as TerraChangeFilter) })}
              >
                <SelectTrigger id="terra-change" className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All</SelectItem>
                  {TERRA_CHANGES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {CHANGE_LABEL[c]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="terra-status">Publication</Label>
              <Select
                value={search.status ?? ALL}
                onValueChange={(v) => patch({ status: v === ALL ? undefined : (v as TerraStatusFilter) })}
              >
                <SelectTrigger id="terra-status" className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All</SelectItem>
                  {TERRA_STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {PUB_STATUS_LABEL[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="terra-criterion">Criterion</Label>
              <Select value={search.criterion ?? ALL} onValueChange={(v) => patch({ criterion: v === ALL ? undefined : v })}>
                <SelectTrigger id="terra-criterion" className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All</SelectItem>
                  {/* A criterion id from a shared URL stays selectable even when the model does not list it. */}
                  {search.criterion && !model.data?.criteria.some((c) => c.id === search.criterion) && (
                    <SelectItem value={search.criterion}>{search.criterion}</SelectItem>
                  )}
                  {model.data?.criteria.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="terra-q">Search</Label>
              <FilterInput
                id="terra-q"
                value={search.q}
                onCommit={commitQ}
                placeholder="Ref, site or MHz"
                maxLength={MAX_Q}
                className="w-48"
              />
            </div>
            <div className="flex items-center gap-2 pb-2">
              <Switch
                id="terra-relevant"
                checked={search.relevant === 'all'}
                onCheckedChange={(checked) => patch({ relevant: checked ? 'all' : undefined })}
              />
              <Label htmlFor="terra-relevant">
                <TermHint hint={TERMS.relevant}>Include non-relevant</TermHint>
              </Label>
            </div>
            {filtered && (
              <Button
                variant="ghost"
                size="sm"
                className="mb-0.5"
                onClick={() =>
                  patch({
                    outcome: undefined,
                    adm: undefined,
                    change: undefined,
                    status: undefined,
                    relevant: undefined,
                    criterion: undefined,
                    q: undefined,
                  })
                }
              >
                <X aria-hidden /> Clear filters
              </Button>
            )}
          </section>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              value={tab}
              onValueChange={(v) => v && patch({ tab: v === 'findings' ? undefined : (v as Exclude<TerraTab, 'findings'>) })}
              aria-label="View"
            >
              {(['findings', 'map', 'trends'] as const).map((t) => (
                <ToggleGroupItem key={t} value={t}>
                  {TAB_LABEL[t]}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
            {tab !== 'trends' && assignments.data && (
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-xs text-muted-foreground">
                  {assignments.data.count} assignments, in the server's order (outcome, FIN coordination required, margin, change, publication status)
                </p>
                <Button variant="outline" size="sm" asChild disabled={assignments.data.count === 0}>
                  <a href={terraAssignmentsCsvUrl(issue.ific_no, filters)} download={`terra-${issue.ific_no}.csv`}>
                    <Download aria-hidden /> Download CSV
                  </a>
                </Button>
              </div>
            )}
          </div>

          {tab !== 'trends' && assignments.isError && !assignments.data ? (
            <Alert variant="destructive">
              <CircleAlert aria-hidden />
              <AlertTitle>Could not load the assessment of BR IFIC {issue.ific_no}</AlertTitle>
              <AlertDescription>{errorText(assignments.error)}</AlertDescription>
            </Alert>
          ) : tab === 'findings' ? (
            <TerraTable
              assignments={assignments.data?.assignments}
              isPending={assignments.isFetching}
              selected={search.ntc}
              onOpen={openAssignment}
              empty={filtered ? 'No assignment matches the filters.' : `BR IFIC ${issue.ific_no} has no relevant assignment.`}
            />
          ) : tab === 'map' ? (
            assignments.data ? (
              <TerraMap assignments={assignments.data.assignments} selected={search.ntc} onOpen={openAssignment} />
            ) : (
              <Skeleton className="h-[65svh] min-h-[420px]" />
            )
          ) : (
            <TerraTrends
              ificNo={issue.ific_no}
              assessedAt={assessedAt}
              otherIssues={otherIssues}
              trendIssues={trendIssues.filter((n) => n !== issue.ific_no)}
              onTrendIssuesChange={(next) => patch({ trend_issues: next.length ? next.join(',') : undefined })}
              onOpen={openAssignment}
            />
          )}

          <TerraSheet
            ificNo={issue.ific_no}
            terrakey={search.ntc}
            assessedAt={assessedAt}
            draftAdms={draftAdms}
            onOpenDraft={(adm) => patch({ draft: adm })}
            onClose={() => patch({ ntc: undefined })}
          />

          <Sheet open={search.draft != null} onOpenChange={(open) => !open && patch({ draft: undefined })}>
            <SheetContent className="w-full gap-0 data-[side=right]:sm:max-w-3xl">
              <SheetHeader className="border-b pr-12">
                <SheetTitle>Draft letter to {search.draft}</SheetTitle>
                <SheetDescription>BR IFIC {issue.ific_no} · built on demand from the stored results, never stored.</SheetDescription>
              </SheetHeader>
              <div className="flex-1 overflow-y-auto p-4">
                {search.draft && (
                  <TerraDraft key={`${issue.ific_no}:${search.draft}:${assessedAt}`} ificNo={issue.ific_no} adm={search.draft} assessedAt={assessedAt} />
                )}
              </div>
            </SheetContent>
          </Sheet>
        </>
      )}
    </>
  )
}
