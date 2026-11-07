import { useQuery } from '@tanstack/react-query'
import { CircleAlert } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Toggle } from '@/components/ui/toggle'
import { errorText, terraTrendsQuery } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { DISTANCE_ORDER, TERMS, TREND_DIMENSIONS } from './terra-meta'
import { TermHint } from './term-hint'

/** Values shown per small multiple; the rest are summed into one row. */
const MAX_VALUES = 8

type TerraTrendsProps = {
  ificNo: number
  assessedAt: string | null
  /** Other assessed issues that can be summed in. */
  otherIssues: number[]
  trendIssues: number[]
  onTrendIssuesChange: (issues: number[]) => void
  onOpen: (terrakey: number) => void
}

function ordered(dimension: string, counts: Record<string, number>): [string, number][] {
  const entries = Object.entries(counts)
  if (dimension === 'distance')
    return entries.sort(([a], [b]) => DISTANCE_ORDER.indexOf(a) - DISTANCE_ORDER.indexOf(b))
  const sorted = entries.sort(([a, x], [b, y]) => y - x || a.localeCompare(b))
  if (sorted.length <= MAX_VALUES) return sorted
  const rest = sorted.slice(MAX_VALUES - 1).reduce((sum, [, n]) => sum + n, 0)
  return [...sorted.slice(0, MAX_VALUES - 1), [`${sorted.length - MAX_VALUES + 1} others`, rest]]
}

function SmallMultiple({ title, color, values }: { title: string; color: string; values: [string, number][] }) {
  const max = Math.max(1, ...values.map(([, n]) => n))
  return (
    <figure className="min-w-0 space-y-1.5">
      <figcaption className="text-xs font-medium text-muted-foreground">{title}</figcaption>
      {values.length ? (
        <ul className="space-y-1">
          {values.map(([value, n]) => (
            <li key={value} className="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-2 text-xs">
              <span className="truncate" title={value}>
                {value}
              </span>
              <span className="h-2.5 rounded-sm" style={{ width: `${(n / max) * 100}%`, background: color }} aria-hidden />
              <span className="text-right tabular-nums">{n}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">None</p>
      )}
    </figure>
  )
}

export function TerraTrends({ ificNo, assessedAt, otherIssues, trendIssues, onTrendIssuesChange, onOpen }: TerraTrendsProps) {
  const trends = useQuery(terraTrendsQuery(ificNo, trendIssues, assessedAt))
  const t = trends.data

  const toggleIssue = (n: number) =>
    onTrendIssuesChange(trendIssues.includes(n) ? trendIssues.filter((i) => i !== n) : [...trendIssues, n].sort((a, b) => a - b))

  // Administrations present in any dimension, in the API's neighbour order.
  const adms = t ? t.neighbours.filter((adm) => TREND_DIMENSIONS.some((d) => t.counts[d.id]?.[adm])) : []

  return (
    <div className={cn('space-y-6', trends.isFetching && !trends.isPending && 'opacity-80')}>
      <Card>
        <CardHeader>
          <CardTitle>Neighbour trends</CardTitle>
          <CardDescription>
            Notices of the neighbouring administrations first published (received, part 1) in the summed issues. A notice
            republished in a later issue is counted once.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Issues summed">
            <span className="mr-1 text-xs text-muted-foreground">Sum with</span>
            {otherIssues.length ? (
              otherIssues.map((n) => (
                <Toggle key={n} size="sm" variant="outline" pressed={trendIssues.includes(n)} onPressedChange={() => toggleIssue(n)}>
                  <span className="font-mono">{n}</span>
                </Toggle>
              ))
            ) : (
              <span className="text-xs text-muted-foreground">no other assessed issue</span>
            )}
          </div>
          {t && (
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {t.issues.map((n) => {
                const issue = t.per_issue[String(n)]
                return (
                  <li key={n}>
                    <span className="font-mono font-medium">{n}</span>: {issue?.received ?? 0} received
                    {issue && Object.keys(issue.by_adm).length > 0 && (
                      <span className="text-muted-foreground">
                        {' '}
                        ({Object.entries(issue.by_adm).map(([adm, c]) => `${adm} ${c}`).join(', ')})
                      </span>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      {trends.isPending ? (
        <Skeleton className="h-64" />
      ) : trends.isError && !t ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>Could not load the trends of BR IFIC {ificNo}</AlertTitle>
          <AlertDescription>{errorText(trends.error)}</AlertDescription>
        </Alert>
      ) : (
        t && (
          <>
            {adms.length ? (
              adms.map((adm) => (
                <Card key={adm}>
                  <CardHeader>
                    <CardTitle className="text-base">{adm}</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
                    {TREND_DIMENSIONS.map((d) => (
                      <SmallMultiple key={d.id} title={d.label} color={d.color} values={ordered(d.id, t.counts[d.id]?.[adm] ?? {})} />
                    ))}
                  </CardContent>
                </Card>
              ))
            ) : (
              <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
                No neighbour notice was first published in the summed issues.
              </p>
            )}

            <section className="space-y-3" aria-label="Anomalies">
              <h3 className="text-sm font-semibold">
                <TermHint hint={TERMS.anomaly}>Anomalies in BR IFIC {t.ific_no}</TermHint>
              </h3>
              {t.anomalies.map((rule) => (
                <Card key={rule.id} className="gap-3 py-4">
                  <CardHeader className="px-4">
                    <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-mono">{rule.id}</span>
                      <span className="font-normal">{rule.description}</span>
                      <span className="ml-auto text-xs font-normal text-muted-foreground tabular-nums">
                        {rule.matches.length} {rule.matches.length === 1 ? 'match' : 'matches'}
                      </span>
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Threshold: {rule.threshold} · {rule.citation}
                    </CardDescription>
                  </CardHeader>
                  {rule.matches.length > 0 && (
                    <CardContent className="px-4">
                      <ul className="divide-y text-sm">
                        {rule.matches.map((m) => (
                          <li key={m.terrakey} className="flex flex-wrap items-baseline gap-x-3 py-1.5">
                            <button
                              type="button"
                              onClick={() => onOpen(m.terrakey)}
                              className="rounded-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                            >
                              {m.adm} <span className="font-mono">{m.adm_ref_id ?? `#${m.terrakey}`}</span>
                            </button>
                            <span className="text-xs text-muted-foreground">{m.detail}</span>
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  )}
                </Card>
              ))}
            </section>
          </>
        )
      )}
    </div>
  )
}
