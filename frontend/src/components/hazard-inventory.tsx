import { ChevronRight, TriangleAlert } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { Assumption, Hazard, HazardInput } from '@/lib/api'
import { cn } from '@/lib/utils'
import { OutcomeBadge } from './outcome-badge'
import { HAZARD_MODE_META, TIER_META, formatBand, formatDb, formatShare, formatTimePct } from './risk-meta'
import { TermHint } from './term-hint'

const COLUMNS = ['Mode', 'Service', 'Band', 'Tier', 'Outcome', 'Share violating', 'Exceedance (median / P95)', 'Worst case']

export function SectionTitle({ children }: { children: string }) {
  return <h4 className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">{children}</h4>
}

export function CitationList({ citations }: { citations: string[] }) {
  if (!citations.length) return null
  return (
    <section>
      <SectionTitle>Citations</SectionTitle>
      <ul className="list-disc space-y-0.5 pl-4">
        {citations.map((cite) => (
          <li key={cite}>{cite}</li>
        ))}
      </ul>
    </section>
  )
}

export function AssumptionList({ assumptions, outcomeSensitive }: { assumptions: Assumption[]; outcomeSensitive: Set<string> }) {
  if (!assumptions.length) return null
  return (
    <section>
      <SectionTitle>Assumptions</SectionTitle>
      <ul className="space-y-1.5">
        {assumptions.map((a) => {
          const sensitive = a.sensitive || outcomeSensitive.has(a.id)
          return (
            <li key={a.id} className={cn('rounded-md px-2 py-1.5', sensitive ? 'bg-status-warning/15' : 'bg-muted/50')}>
              {sensitive && (
                <span className="mb-0.5 flex items-center gap-1 font-medium">
                  <TriangleAlert className="size-3" aria-hidden /> Outcome-sensitive
                </span>
              )}
              <code className="mr-1 font-mono text-[11px] text-muted-foreground">{a.id}</code>
              {a.text}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export function InputList({ inputs, empty }: { inputs: HazardInput[]; empty: string }) {
  return (
    <section className="min-w-0">
      <SectionTitle>Inputs</SectionTitle>
      {inputs.length ? (
        <ul className="divide-y rounded-md border">
          {inputs.map((input) => (
            <li key={input.name} className="space-y-0.5 px-2 py-1.5">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-medium">{input.name}</span>
                <span className="tabular-nums">
                  {input.value ?? '—'}
                  {input.unit ? ` ${input.unit}` : ''}
                </span>
                <Badge variant="outline" className="ml-auto h-4 px-1.5 font-mono text-[10px]">
                  {input.source}
                </Badge>
              </div>
              <div className="text-muted-foreground">{input.cite}</div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground">{empty}</p>
      )}
    </section>
  )
}

function HazardDetails({ hazard, outcomeSensitive }: { hazard: Hazard; outcomeSensitive: Set<string> }) {
  return (
    <div className="grid gap-4 py-2 text-xs md:grid-cols-2">
      <div className="space-y-4">
        <section>
          <SectionTitle>Population</SectionTitle>
          <p className="tabular-nums">
            {hazard.n_receivers.toLocaleString()} receivers · {hazard.n_samples.toLocaleString()} Monte Carlo samples
          </p>
        </section>
        {hazard.criteria.length > 0 && (
          <section>
            <SectionTitle>Protection criteria</SectionTitle>
            <ul className="space-y-1">
              {hazard.criteria.map((c) => (
                <li key={`${c.metric}-${c.time_pct}`}>
                  <span className="font-medium tabular-nums">
                    {c.metric} {formatDb(c.level_db)} for at most {formatTimePct(c.time_pct)}
                  </span>{' '}
                  <span className="text-muted-foreground">{c.cite}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
        <CitationList citations={hazard.citations} />
        <AssumptionList assumptions={hazard.assumptions} outcomeSensitive={outcomeSensitive} />
      </div>
      <InputList inputs={hazard.inputs} empty="No inputs recorded for this hazard." />
    </div>
  )
}

export function HazardInventory({ hazards, outcomeSensitive }: { hazards: Hazard[]; outcomeSensitive: Set<string> }) {
  const [open, setOpen] = useState<Set<string>>(() => new Set())
  const toggle = (id: string) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <div className="overflow-hidden rounded-lg border">
      <Table>
        <TableHeader className="bg-muted/40">
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-8">
              <span className="sr-only">Details</span>
            </TableHead>
            {COLUMNS.map((label) => (
              <TableHead key={label} className="whitespace-nowrap">
                {label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {hazards.length === 0 && (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={COLUMNS.length + 1} className="h-20 text-center text-muted-foreground">
                No hazards were inventoried for this notice.
              </TableCell>
            </TableRow>
          )}
          {hazards.map((hazard) => {
            const expanded = open.has(hazard.hazard_id)
            const mode = HAZARD_MODE_META[hazard.mode]
            return (
              <Fragment key={hazard.hazard_id}>
                <TableRow data-state={expanded ? 'selected' : undefined}>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => toggle(hazard.hazard_id)}
                      aria-expanded={expanded}
                      aria-label={`${expanded ? 'Hide' : 'Show'} inputs for ${mode.label} ${hazard.service_label ?? ''}`}
                    >
                      <ChevronRight className={cn('transition-transform', expanded && 'rotate-90')} />
                    </Button>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    <span className="flex items-center gap-2">
                      <span className="h-0.5 w-3 rounded-full" style={{ background: mode.color }} aria-hidden />
                      {mode.label}
                    </span>
                  </TableCell>
                  <TableCell>{hazard.service_label ?? hazard.service_class ?? '—'}</TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {hazard.bands_hz.length ? hazard.bands_hz.map((b) => <div key={b.join('-')}>{formatBand(b)}</div>) : '—'}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    <TermHint hint={TIER_META[hazard.tier].description}>
                      <span className="tabular-nums">{hazard.tier}</span> · {TIER_META[hazard.tier].label}
                    </TermHint>
                  </TableCell>
                  <TableCell className="min-w-40">
                    <OutcomeBadge outcome={hazard.outcome} />
                    {hazard.reason && <p className="mt-1 text-xs whitespace-normal text-muted-foreground">{hazard.reason}</p>}
                  </TableCell>
                  <TableCell className="tabular-nums">{formatShare(hazard.share_violating)}</TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {hazard.exceedance_db.length
                      ? hazard.exceedance_db.map((e) => (
                          <div key={`${e.level_db}-${e.time_pct}`}>
                            <span className="text-muted-foreground">{e.time_pct}%:</span> {formatDb(e.median_db)} /{' '}
                            {formatDb(e.p95_db)}
                          </div>
                        ))
                      : '—'}
                  </TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">{formatDb(hazard.worst_case_db)}</TableCell>
                </TableRow>
                {expanded && (
                  <TableRow className="bg-muted/20 hover:bg-muted/20">
                    <TableCell colSpan={COLUMNS.length + 1} className="whitespace-normal">
                      <HazardDetails hazard={hazard} outcomeSensitive={outcomeSensitive} />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
