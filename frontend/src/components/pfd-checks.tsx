import { ChevronRight, CircleAlert } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { NoticeDetail, PfdCheck } from '@/lib/api'
import { cn } from '@/lib/utils'
import { AssumptionList, CitationList, InputList, SectionTitle } from './hazard-inventory'
import { OutcomeBadge } from './outcome-badge'
import { PFD_TERMS, compareOutcomes, formatBand, formatDb } from './risk-meta'
import { TermHint } from './term-hint'

const COLUMNS: { label: string; hint?: string }[] = [
  { label: 'Group' },
  { label: 'Band' },
  { label: 'Service' },
  { label: 'Table 21-4 row' },
  { label: 'B_ref', hint: PFD_TERMS.refBw },
  { label: 'pfd', hint: PFD_TERMS.pfd },
  { label: 'Limit' },
  { label: 'δ', hint: PFD_TERMS.delta },
  { label: 'Margin', hint: PFD_TERMS.margin },
  { label: 'Source' },
  { label: 'Outcome' },
]

const formatLevel = (v: number | null) => (v == null ? '—' : `${v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}`)

function formatRefBw(hz: number | null): string {
  if (hz == null) return '—'
  return hz >= 1e6 ? `${Number((hz / 1e6).toFixed(3))} MHz` : `${Number((hz / 1e3).toFixed(3))} kHz`
}

const byOutcomeThenMargin = (a: PfdCheck, b: PfdCheck) =>
  compareOutcomes(a.outcome, b.outcome) || (b.margin_db ?? -Infinity) - (a.margin_db ?? -Infinity)

function CheckDetails({ check, outcomeSensitive }: { check: PfdCheck; outcomeSensitive: Set<string> }) {
  return (
    <div className="grid gap-4 py-2 text-xs md:grid-cols-2">
      <div className="space-y-4">
        <section>
          <SectionTitle>Groups</SectionTitle>
          <p className="tabular-nums">
            Worst of {check.n_groups} group{check.n_groups === 1 ? '' : 's'} sharing this row and outcome
            {check.n_groups_exceeding > 0 && `; ${check.n_groups_exceeding} exceed the limit`}.
          </p>
        </section>
        <CitationList citations={check.citations} />
        <AssumptionList assumptions={check.assumptions} outcomeSensitive={outcomeSensitive} />
      </div>
      <InputList inputs={check.inputs} empty="No inputs: this row was not evaluated." />
    </div>
  )
}

export function PfdChecks({ detail, outcomeSensitive }: { detail: NoticeDetail; outcomeSensitive: Set<string> }) {
  const [open, setOpen] = useState<Set<string>>(() => new Set())
  const checks = detail.pfd_checks
  if (checks == null) {
    return (
      <p className="rounded-lg border border-dashed px-3 py-4 text-sm text-muted-foreground">
        This notice was assessed before the pfd check existed. Re-assess the issue to compute it.
      </p>
    )
  }
  const toggle = (id: string) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const sorted = [...checks].sort(byOutcomeThenMargin)

  return (
    <div className="space-y-3">
      {detail.pfd_limits_review === 'pending' && (
        <Alert>
          <CircleAlert aria-hidden />
          <AlertTitle>Table 21-4 transcription: review pending</AlertTitle>
          <AlertDescription>{PFD_TERMS.review}</AlertDescription>
        </Alert>
      )}
      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-8">
                <span className="sr-only">Details</span>
              </TableHead>
              {COLUMNS.map((c) => (
                <TableHead key={c.label} className="whitespace-nowrap">
                  {c.hint ? <TermHint hint={c.hint}>{c.label}</TermHint> : c.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={COLUMNS.length + 1} className="h-20 text-center text-muted-foreground">
                  No space-to-Earth groups, so no Table 21-4 limit applies.
                </TableCell>
              </TableRow>
            )}
            {sorted.map((check) => {
              const expanded = open.has(check.check_id)
              const evaluated = check.margin_db != null
              return (
                <Fragment key={check.check_id}>
                  <TableRow
                    data-state={expanded ? 'selected' : undefined}
                    className={cn(check.outcome === 'not_applicable' && 'text-muted-foreground')}
                  >
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={() => toggle(check.check_id)}
                        aria-expanded={expanded}
                        aria-label={`${expanded ? 'Hide' : 'Show'} inputs for pfd check ${check.check_id}`}
                      >
                        <ChevronRight className={cn('transition-transform', expanded && 'rotate-90')} />
                      </Button>
                    </TableCell>
                    <TableCell className="font-mono text-xs whitespace-nowrap">
                      {check.grp_id ?? '—'}
                      {check.n_groups > 1 && <span className="text-muted-foreground"> +{check.n_groups - 1}</span>}
                    </TableCell>
                    <TableCell className="whitespace-nowrap tabular-nums">
                      {check.band_hz ? formatBand(check.band_hz) : '—'}
                    </TableCell>
                    <TableCell>{check.service ?? '—'}</TableCell>
                    <TableCell className="font-mono text-xs">{check.row_id ?? '—'}</TableCell>
                    <TableCell className="whitespace-nowrap tabular-nums">{formatRefBw(check.ref_bw_hz)}</TableCell>
                    <TableCell className="whitespace-nowrap tabular-nums">{formatLevel(check.pfd_dbw_m2)}</TableCell>
                    <TableCell className="whitespace-nowrap tabular-nums">{formatLevel(check.limit_dbw_m2)}</TableCell>
                    <TableCell className="whitespace-nowrap tabular-nums">
                      {check.delta_deg == null ? '—' : `${check.delta_deg.toFixed(1)}°`}
                    </TableCell>
                    <TableCell
                      className={cn(
                        'whitespace-nowrap tabular-nums',
                        check.outcome === 'exceeds' && 'font-medium text-status-critical-foreground',
                      )}
                    >
                      {evaluated ? formatDb(check.margin_db) : '—'}
                      {check.near_limit && (
                        <Badge variant="outline" className="ml-1.5 h-4 px-1.5 text-[10px]">
                          near
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{check.source ?? '—'}</TableCell>
                    <TableCell className="min-w-40">
                      <OutcomeBadge outcome={check.outcome} />
                      {check.reason && <p className="mt-1 text-xs whitespace-normal text-muted-foreground">{check.reason}</p>}
                    </TableCell>
                  </TableRow>
                  {expanded && (
                    <TableRow className="bg-muted/20 hover:bg-muted/20">
                      <TableCell colSpan={COLUMNS.length + 1} className="whitespace-normal">
                        <CheckDetails check={check} outcomeSensitive={outcomeSensitive} />
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              )
            })}
          </TableBody>
        </Table>
      </div>
      {detail.pfd_check_version && (
        <p className="text-xs text-muted-foreground">
          pfd check {detail.pfd_check_version}; dB(W/m²) in the reference bandwidth. Not part of the hazard outcomes.
        </p>
      )}
    </div>
  )
}
