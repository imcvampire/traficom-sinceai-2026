import { useQuery } from '@tanstack/react-query'
import { BookOpen, ExternalLink, TriangleAlert } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import type { ModelOut, ReceiverClass } from '@/lib/api'
import { errorText, riskModelQuery } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { SectionTitle } from './hazard-inventory'
import { formatDb, formatTimePct } from './risk-meta'

function formatBandwidth(hz: number): string {
  if (hz >= 1e9) return `${Number((hz / 1e9).toFixed(3))} GHz`
  if (hz >= 1e6) return `${Number((hz / 1e6).toFixed(3))} MHz`
  return `${Number((hz / 1e3).toFixed(3))} kHz`
}

const UNIT_SUFFIX: [string, string][] = [
  ['_deg', '°'],
  ['_m', ' m'],
  ['_db', ' dB'],
  ['_dbi', ' dBi'],
]

function formatRange(param: string, low: number, high: number): string {
  const unit = UNIT_SUFFIX.find(([suffix]) => param.endsWith(suffix))?.[1] ?? ''
  return `${low}–${high}${unit}`
}

function ClassCard({ cls }: { cls: ReceiverClass }) {
  const characteristics: { key: string; label: string; value: string }[] = [
    { key: 'pattern', label: 'Antenna pattern', value: cls.pattern },
    { key: 'gain_dbi', label: 'Gain', value: `${cls.gain_dbi} dBi` },
    { key: 'nf_db', label: 'Noise figure', value: `${cls.nf_db} dB` },
    { key: 'bw_hz', label: 'Bandwidth', value: formatBandwidth(cls.bw_hz) },
    { key: 'acs_db', label: 'Adjacent-channel selectivity', value: `${cls.acs_db} dB` },
    { key: 'min_elev_deg', label: 'Minimum elevation', value: `${cls.min_elev_deg}°` },
  ]
  return (
    <li className="space-y-3 rounded-lg border p-3">
      <div>
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-sm font-medium">{cls.label}</span>
          <code className="font-mono text-[11px] text-muted-foreground">{cls.id}</code>
        </div>
        {cls.keywords.length > 0 && (
          <p className="text-muted-foreground">Matched from M4 services: {cls.keywords.join('; ')}</p>
        )}
      </div>
      <dl className="divide-y rounded-md border">
        {characteristics.map((c) => (
          <div key={c.key} className="space-y-0.5 px-2 py-1.5">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <dt className="font-medium">{c.label}</dt>
              <dd className="tabular-nums">{c.value}</dd>
            </div>
            {cls.cites[c.key] && <dd className="text-muted-foreground">{cls.cites[c.key]}</dd>}
          </div>
        ))}
      </dl>
      {cls.criteria.length > 0 && (
        <section>
          <SectionTitle>Protection criteria</SectionTitle>
          <ul className="space-y-1">
            {cls.criteria.map((c) => (
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
      {cls.distributions.length > 0 && (
        <section>
          <SectionTitle>Monte Carlo distributions</SectionTitle>
          <ul className="space-y-1">
            {cls.distributions.map((d) => (
              <li key={d.param}>
                <code className="font-mono">{d.param}</code>{' '}
                <span className="tabular-nums">
                  {d.kind} {formatRange(d.param, d.low, d.high)}
                </span>{' '}
                <span className="text-muted-foreground">{d.cite}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </li>
  )
}

function ModelBody({ model }: { model: ModelOut }) {
  const sensitive = new Set(model.outcome_sensitive)
  const assumptions = model.inputs.filter((i) => i.source === 'assumption')
  const sources = model.inputs.filter((i) => i.source !== 'assumption')
  const grid = model.curve_grid_db

  return (
    <div className="space-y-6 px-4 pb-6 text-xs">
      <section className="space-y-3">
        <SectionTitle>Method</SectionTitle>
        <ol className="space-y-3">
          {model.method_steps.map((step) => (
            <li key={step.step} className="space-y-1">
              <div className="text-sm font-medium">
                Step {step.step}: {step.what}
              </div>
              <blockquote className="border-l-2 pl-2 text-muted-foreground italic">“{step.source_wording}”</blockquote>
              <div className="text-muted-foreground">{step.cite}</div>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <SectionTitle>Model settings</SectionTitle>
        <dl className="divide-y rounded-md border">
          <div className="flex flex-wrap gap-x-2 px-2 py-1.5">
            <dt className="font-medium">Model version</dt>
            <dd className="font-mono">{model.model_version}</dd>
            <dd className="w-full text-muted-foreground">Also seeds the Monte Carlo generator, with the issue, notice and hazard.</dd>
          </div>
          <div className="flex flex-wrap gap-x-2 px-2 py-1.5">
            <dt className="font-medium">Receiver population</dt>
            <dd className="font-mono">{model.receiver_source}</dd>
          </div>
          <div className="flex flex-wrap gap-x-2 px-2 py-1.5">
            <dt className="font-medium">Likelihood-curve grid</dt>
            <dd className="tabular-nums">
              {formatDb(grid.start)} to {formatDb(grid.stop)} in {grid.step} dB steps
            </dd>
          </div>
        </dl>
      </section>

      <section>
        <SectionTitle>Assumptions</SectionTitle>
        <p className="mb-2 text-muted-foreground">
          Highlighted assumptions can change an outcome in the stored results (sensitivity report).
        </p>
        <ul className="space-y-1.5">
          {assumptions.map((a) => {
            const flagged = sensitive.has(a.name)
            return (
              <li key={a.name} className={cn('rounded-md px-2 py-1.5', flagged ? 'bg-status-warning/15' : 'bg-muted/50')}>
                {flagged && (
                  <span className="mb-0.5 flex items-center gap-1 font-medium">
                    <TriangleAlert className="size-3" aria-hidden /> Outcome-sensitive
                  </span>
                )}
                <code className="mr-1 font-mono text-[11px] text-muted-foreground">{a.name}</code>
                {a.cite}
              </li>
            )
          })}
        </ul>
      </section>

      <section>
        <SectionTitle>Receiver classes</SectionTitle>
        <ul className="space-y-3">
          {model.receiver_classes.map((cls) => (
            <ClassCard key={cls.id} cls={cls} />
          ))}
        </ul>
      </section>

      <section>
        <SectionTitle>Input sources</SectionTitle>
        <ul className="divide-y rounded-md border">
          {sources.map((input) => (
            <li key={input.name} className="space-y-0.5 px-2 py-1.5">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-medium">{input.name}</span>
                <Badge variant="outline" className="ml-auto h-4 px-1.5 font-mono text-[10px]">
                  {input.source}
                </Badge>
              </div>
              <div className="text-muted-foreground">{input.cite}</div>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <SectionTitle>References</SectionTitle>
        <ul className="space-y-1.5">
          {model.references.map((ref) => (
            <li key={ref.url}>
              <a
                href={ref.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 font-medium text-primary underline-offset-4 hover:underline"
              >
                {ref.title} <ExternalLink className="size-3" aria-hidden />
              </a>
              <div className="text-muted-foreground">{ref.supports}</div>
            </li>
          ))}
        </ul>
      </section>

      <p className="border-t pt-3 text-muted-foreground">
        Full method, inputs and known weaknesses: <code className="font-mono text-foreground">{model.doc_path}</code>
      </p>
    </div>
  )
}

/** The model as it runs: method steps, settings, assumptions, receiver-class parameters and input sources. */
export function MethodSheet() {
  const model = useQuery(riskModelQuery)
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm">
          <BookOpen aria-hidden /> Method &amp; parameters
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full gap-0 overflow-y-auto data-[side=right]:sm:max-w-2xl">
        <SheetHeader className="pr-12">
          <SheetTitle>Risk-informed assessment{model.data ? `, ${model.data.model_version}` : ''}</SheetTitle>
          <SheetDescription>
            Four steps, each grounded in its source. No step combines results into a score.
          </SheetDescription>
        </SheetHeader>
        {model.isPending ? (
          <div className="space-y-2 px-4">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </div>
        ) : model.isError ? (
          <p className="px-4 text-sm text-status-critical-foreground">Could not load the method: {errorText(model.error)}</p>
        ) : (
          <ModelBody model={model.data} />
        )}
      </SheetContent>
    </Sheet>
  )
}
