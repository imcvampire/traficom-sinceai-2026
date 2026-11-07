import { useQuery } from '@tanstack/react-query'
import { CircleAlert, FileText, Flag, MessageSquare } from 'lucide-react'
import { useMemo, type ReactNode } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { Hazard, NoticeDetail } from '@/lib/api'
import { formatDate, formatDateTime } from '@/lib/format'
import { errorText, riskModelQuery, riskNoticeQuery } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { HazardInventory } from './hazard-inventory'
import { NoticeDraft } from './notice-draft'
import { PfdChecks } from './pfd-checks'
import { TermHint } from './term-hint'
import { OutcomeBadge } from './outcome-badge'
import { ChartLegend, RiskChart, type ChartCriterion, type ChartCurve, type ChartWorstCase } from './risk-chart'
import {
  BR_DESCRIPTION,
  HAZARD_MODE_META,
  ORBIT_LABEL,
  RECEIVER_SOURCE_LABEL,
  compareOutcomes,
  daysLeftText,
  formatBand,
  formatDb,
  formatShare,
  likelihoodAt,
} from './risk-meta'

function hazardName(h: Hazard): string {
  return [HAZARD_MODE_META[h.mode].label, h.service_label ?? h.service_class].filter(Boolean).join(' · ')
}

function chartSeries(detail: NoticeDetail) {
  const curves: ChartCurve[] = []
  const criteria: ChartCriterion[] = []
  const worstCases: ChartWorstCase[] = []
  for (const h of detail.hazards) {
    const color = HAZARD_MODE_META[h.mode].color
    const name = hazardName(h)
    const sorted = [...h.risk_curves].sort((a, b) => b.time_pct - a.time_pct)
    sorted.forEach((curve, i) =>
      curves.push({
        id: `${h.hazard_id}@${curve.time_pct}`,
        label: `${name} · ${curve.time_pct}% of time`,
        color,
        likelihood: curve.likelihood,
        dotted: i > 0,
      }),
    )
    if (h.risk_curves.length || h.worst_case_db != null)
      for (const c of h.criteria) {
        const curve = h.risk_curves.find((rc) => rc.time_pct === c.time_pct)
        criteria.push({
          id: `${h.hazard_id}@${c.time_pct}@${c.level_db}`,
          label: `${name} · ${c.metric} ${formatDb(c.level_db)} at ${c.time_pct}% of time`,
          color,
          levelDb: c.level_db,
          share: curve ? likelihoodAt(curve.likelihood, detail.curve_grid_db, c.level_db) : null,
          shade: true,
          point: Boolean(curve),
        })
      }
    if (h.worst_case_db != null) worstCases.push({ id: h.hazard_id, label: name, color, db: h.worst_case_db })
  }
  return { curves, criteria, worstCases }
}

function hazardSentence(h: Hazard): string {
  const parts = [h.service_label ?? h.service_class ?? HAZARD_MODE_META[h.mode].label]
  if (h.bands_hz.length) {
    const shown = h.bands_hz.slice(0, 3).map(formatBand).join(', ')
    const more = h.bands_hz.length > 3 ? ` +${h.bands_hz.length - 3} more` : ''
    parts[0] += ` (${shown}${more})`
  }
  if (h.share_violating != null) parts.push(`${formatShare(h.share_violating)} of receivers`)
  const worst = [...h.exceedance_db].sort((a, b) => (b.median_db ?? -Infinity) - (a.median_db ?? -Infinity))[0]
  if (worst?.median_db != null) parts.push(`${formatDb(worst.median_db)} at ${worst.time_pct}% of time`)
  return parts.join(', ')
}

function OutcomeSet({ hazards }: { hazards: Hazard[] }) {
  const groups = useMemo(() => {
    const sorted = [...hazards].sort((a, b) => compareOutcomes(a.outcome, b.outcome))
    const map = new Map<Hazard['outcome'], Hazard[]>()
    for (const h of sorted) map.set(h.outcome, [...(map.get(h.outcome) ?? []), h])
    return [...map.entries()]
  }, [hazards])
  return (
    <ul className="space-y-1.5 text-sm">
      {groups.map(([outcome, list]) => (
        <li key={outcome} className="flex flex-wrap items-start gap-2">
          <OutcomeBadge outcome={outcome} />
          <span className="min-w-0 flex-1">{list.map(hazardSentence).join('; ')}</span>
        </li>
      ))}
    </ul>
  )
}

function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{hint ? <TermHint hint={hint}>{label}</TermHint> : label}</dt>
      <dd className="mt-0.5 text-sm font-medium break-words">{children}</dd>
    </div>
  )
}

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="min-w-0 space-y-3">
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      {children}
    </section>
  )
}

function Regulatory({ detail }: { detail: NoticeDetail }) {
  const reg = detail.regulatory
  const days = daysLeftText(reg)
  return (
    <Section title="Regulatory context" description="Shown next to the technical result, never multiplied into it.">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="Stage">{reg.stage}</Field>
        <Field label="Provision">RR No. {reg.provision}</Field>
        <Field label="Published (d_wic)">{formatDate(reg.d_wic)}</Field>
        <Field label="Comment window ends">{formatDate(reg.window_end)}</Field>
        <Field label="Days left">
          <span className={cn(days.closed && 'text-muted-foreground')}>
            {reg.days_left == null ? 'No comment window at this stage' : days.text}
          </span>
          {reg.window_cite && <span className="block text-xs font-normal text-muted-foreground">{reg.window_cite}</span>}
        </Field>
        <Field label="BR identified Finland" hint={BR_DESCRIPTION}>
          {reg.fin_identified ? (
            <span className="flex items-center gap-1">
              <Flag className="size-3.5 text-primary" aria-hidden /> Yes
            </span>
          ) : (
            <>
              No
              <span className="block text-xs font-normal text-muted-foreground">
                Finland may request inclusion under RR No. 9.41
              </span>
            </>
          )}
        </Field>
      </dl>
      {reg.findings.length > 0 && (
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow className="hover:bg-transparent">
                <TableHead>Source</TableHead>
                <TableHead>Provision</TableHead>
                <TableHead>Agreement</TableHead>
                <TableHead>Group</TableHead>
                <TableHead>Affected notice</TableHead>
                <TableHead>Finnish network</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {reg.findings.map((f, i) => (
                <TableRow key={i}>
                  <TableCell className="font-mono text-xs">{f.source}</TableCell>
                  <TableCell>{f.coord_prov}</TableCell>
                  <TableCell>{f.agree_st ?? '—'}</TableCell>
                  <TableCell className="tabular-nums">{f.grp_id ?? '—'}</TableCell>
                  <TableCell className="font-mono text-xs">{f.aff_ntc_id ?? '—'}</TableCell>
                  <TableCell>{f.network ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {reg.citations.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
          {reg.citations.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      )}
    </Section>
  )
}

function NoticeBody({ detail, outcomeSensitive }: { detail: NoticeDetail; outcomeSensitive: Set<string> }) {
  const series = useMemo(() => chartSeries(detail), [detail])
  const hazards = useMemo(
    () => [...detail.hazards].sort((a, b) => compareOutcomes(a.outcome, b.outcome)),
    [detail.hazards],
  )
  const exceeding = detail.hazards.filter((h) => h.outcome === 'exceeds').length

  return (
    <div className="space-y-6 px-4 pb-6">
      <Section title="Outcome per hazard" description="The notice result is this set of outcomes, not a combined score.">
        <OutcomeSet hazards={detail.hazards} />
      </Section>

      <Section
        title="Likelihood–consequence"
        description="One curve per hazard and criterion time %. A point marks the share of receivers violating that criterion."
      >
        <div className="rounded-lg border p-3">
          {series.curves.length || series.worstCases.length ? (
            <div className="space-y-3">
              <RiskChart
                grid={detail.curve_grid_db}
                curves={series.curves}
                criteria={series.criteria}
                worstCases={series.worstCases}
                ariaLabel={`Likelihood–consequence curves for notice ${detail.ntc_id}: ${series.curves.length} curves, ${exceeding} hazards exceed their criterion`}
              />
              <ChartLegend curves={series.curves} showWorstCase={series.worstCases.length > 0} />
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No hazard was quantified for this notice, so there is no curve to draw.
            </p>
          )}
        </div>
      </Section>

      <Section
        title="pfd limits (RR Art. 21, Table 21-4)"
        description="Worst pfd on Finnish territory per Table 21-4 row. A limit on the transmitter, kept apart from the receiver hazards below."
      >
        <PfdChecks detail={detail} outcomeSensitive={outcomeSensitive} />
      </Section>

      <Section
        title="Hazard inventory"
        description="Every interference mode, including those not assessed or screened out. Expand a row for its inputs."
      >
        <HazardInventory hazards={hazards} outcomeSensitive={outcomeSensitive} />
      </Section>

      <Regulatory detail={detail} />

      <dl className="grid grid-cols-2 gap-3 border-t pt-4 sm:grid-cols-4">
        <Field label="Model">{detail.model_version}</Field>
        <Field label="As of">{formatDate(detail.as_of)}</Field>
        <Field label="Assessed">{formatDateTime(detail.assessed_at)}</Field>
        <Field label="Receivers">{RECEIVER_SOURCE_LABEL}</Field>
      </dl>
    </div>
  )
}

type NoticeSheetProps = {
  ificNo: number
  ntcId: number | undefined
  asOf: string
  assessedAt: string | null
  onClose: () => void
  chatOpen: boolean
  onChatOpenChange: (open: boolean) => void
  /** Rendered as a column beside the details while `chatOpen`. */
  chat: ReactNode
  draftOpen: boolean
  onDraftOpenChange: (open: boolean) => void
}

export function NoticeSheet({
  ificNo,
  ntcId,
  asOf,
  assessedAt,
  onClose,
  chatOpen,
  onChatOpenChange,
  chat,
  draftOpen,
  onDraftOpenChange,
}: NoticeSheetProps) {
  const notice = useQuery({ ...riskNoticeQuery(ificNo, ntcId ?? 0, asOf, assessedAt), enabled: ntcId != null })
  const model = useQuery(riskModelQuery)
  const outcomeSensitive = useMemo(() => new Set(model.data?.outcome_sensitive ?? []), [model.data])
  const detail = notice.data

  return (
    <Sheet open={ntcId != null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        className={cn(
          'w-full gap-0 overflow-y-auto',
          chatOpen ? 'data-[side=right]:sm:max-w-7xl lg:overflow-hidden' : 'data-[side=right]:sm:max-w-3xl',
        )}
      >
        <SheetHeader className="gap-2 pr-12">
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button
              variant={draftOpen ? 'secondary' : 'outline'}
              size="sm"
              aria-pressed={draftOpen}
              onClick={() => onDraftOpenChange(!draftOpen)}
            >
              <FileText aria-hidden /> Draft letter
            </Button>
            <Button
              variant={chatOpen ? 'secondary' : 'outline'}
              size="sm"
              aria-pressed={chatOpen}
              onClick={() => onChatOpenChange(!chatOpen)}
            >
              <MessageSquare aria-hidden /> Ask
            </Button>
          </div>
          <SheetTitle className="text-lg">
            {detail ? (detail.sat_name ?? 'Unnamed network') : `Notice ${ntcId ?? ''}`}
          </SheetTitle>
          <SheetDescription asChild>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="font-mono">{ntcId}</span>
              {detail && (
                <>
                  <span>{detail.adm}</span>
                  <span>
                    {detail.regulatory.stage} · RR No. {detail.prov}
                  </span>
                  <span>{ORBIT_LABEL[detail.orbit]}</span>
                  <OutcomeBadge outcome={detail.worst_outcome} />
                </>
              )}
            </div>
          </SheetDescription>
        </SheetHeader>
        <div className={cn(chatOpen && 'flex flex-col lg:min-h-0 lg:flex-1 lg:flex-row')}>
          {chatOpen && (
            <div className="order-first h-[28rem] shrink-0 border-y lg:order-last lg:h-auto lg:w-[28rem] lg:border-y-0 lg:border-l">
              {chat}
            </div>
          )}
          <div className={cn('min-w-0', chatOpen && 'pt-4 lg:flex-1 lg:overflow-y-auto lg:pt-0')}>
            {notice.isPending ? (
              <div className="space-y-4 px-4 pb-6">
                <Skeleton className="h-16" />
                <Skeleton className="h-80" />
                <Skeleton className="h-40" />
              </div>
            ) : notice.isError ? (
              <div className="px-4">
                <Alert variant="destructive">
                  <CircleAlert aria-hidden />
                  <AlertTitle>Could not load notice {ntcId}</AlertTitle>
                  <AlertDescription>{errorText(notice.error)}</AlertDescription>
                </Alert>
              </div>
            ) : (
              detail && (
                <>
                  {draftOpen && (
                    <div className="px-4 pb-6">
                      <Section
                        title="Draft letter"
                        description="A letter to the notifying administration, built from the stored results for an expert to review and edit. Nothing is stored or sent."
                      >
                        <NoticeDraft
                          key={`${detail.ntc_id}:${asOf}`}
                          ificNo={ificNo}
                          ntcId={detail.ntc_id}
                          asOf={asOf}
                          assessedAt={assessedAt}
                        />
                      </Section>
                    </div>
                  )}
                  <NoticeBody detail={detail} outcomeSensitive={outcomeSensitive} />
                </>
              )
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
