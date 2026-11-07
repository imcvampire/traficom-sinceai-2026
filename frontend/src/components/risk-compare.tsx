import { useQueries } from '@tanstack/react-query'
import { CircleAlert, GitCompareArrows, Shuffle, X } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { CurveGrid, NoticeDetail } from '@/lib/api'
import { errorText, riskNoticeQuery } from '@/lib/queries'
import { ChartLegend, RiskChart, type ChartCriterion, type ChartCurve } from './risk-chart'
import { HAZARD_MODE_META, SERIES_COLORS, criterionFor, hasDominantCurve, likelihoodAt, mainCurve } from './risk-meta'

function buildCompare(details: (NoticeDetail | undefined)[]) {
  const curves: ChartCurve[] = []
  const criteria: ChartCriterion[] = []
  const unquantified: number[] = []
  let grid: CurveGrid | undefined
  for (const [i, detail] of details.entries()) {
    if (!detail) continue
    grid ??= detail.curve_grid_db
    const main = mainCurve(detail)
    if (!main) {
      unquantified.push(detail.ntc_id)
      continue
    }
    const color = SERIES_COLORS[i % SERIES_COLORS.length]
    const service = main.hazard.service_label ?? main.hazard.service_class
    const name = `${detail.sat_name ?? detail.ntc_id} · ${HAZARD_MODE_META[main.hazard.mode].label}${service ? ` · ${service}` : ''} · ${main.timePct}%`
    curves.push({
      id: String(detail.ntc_id),
      label: name,
      color,
      likelihood: main.likelihood,
      dotted: i >= SERIES_COLORS.length,
    })
    const criterion = criterionFor(main.hazard, main.timePct)
    if (criterion)
      criteria.push({
        id: String(detail.ntc_id),
        label: name,
        color,
        levelDb: criterion.level_db,
        share: likelihoodAt(main.likelihood, detail.curve_grid_db, criterion.level_db),
      })
  }
  const crossing = curves.length > 1 && !hasDominantCurve(curves.map((c) => c.likelihood))
  return { curves, criteria, grid, unquantified, crossing }
}

type RiskCompareProps = {
  ificNo: number
  ids: number[]
  asOf: string
  assessedAt: string | null
  onRemove: (id: number) => void
  onClear: () => void
}

export function RiskCompare({ ificNo, ids, asOf, assessedAt, onRemove, onClear }: RiskCompareProps) {
  const results = useQueries({ queries: ids.map((id) => riskNoticeQuery(ificNo, id, asOf, assessedAt)) })
  const pending = results.some((r) => r.isPending)
  const failed = results.flatMap((r, i) => (r.isError ? [{ id: ids[i], error: r.error }] : []))
  const { curves, criteria, grid, unquantified, crossing } = buildCompare(results.map((r) => r.data))

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GitCompareArrows className="size-4 text-primary" aria-hidden /> Compare notices
        </CardTitle>
        <CardDescription>
          The main curve of each selected notice: its worst quantified hazard, at the criterion time % with the largest
          share violating.
        </CardDescription>
        <CardAction>
          <Button variant="ghost" size="sm" onClick={onClear}>
            <X aria-hidden /> Clear
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        {ids.length < 2 && (
          <p className="text-sm text-muted-foreground">Select at least one more notice in the table to compare.</p>
        )}
        {failed.map(({ id, error }) => (
          <Alert key={id} variant="destructive">
            <CircleAlert aria-hidden />
            <AlertTitle>Could not load notice {id}</AlertTitle>
            <AlertDescription className="flex flex-wrap items-center gap-2">
              {errorText(error)}
              <Button variant="outline" size="xs" onClick={() => onRemove(id)}>
                Remove
              </Button>
            </AlertDescription>
          </Alert>
        ))}
        {pending && !curves.length ? (
          <Skeleton className="h-80" />
        ) : grid && curves.length ? (
          <>
            {crossing && (
              <Alert>
                <Shuffle aria-hidden />
                <AlertTitle>Curves cross</AlertTitle>
                <AlertDescription>
                  No curve lies above all the others everywhere, so none of these notices is riskier than the others
                  across the whole consequence range. Read them at the criterion points instead.
                </AlertDescription>
              </Alert>
            )}
            <RiskChart
              grid={grid}
              curves={curves}
              criteria={criteria}
              ariaLabel={`Comparison of ${curves.length} notices${crossing ? '; the curves cross' : ''}`}
            />
            <ChartLegend curves={curves} />
          </>
        ) : (
          !pending &&
          ids.length > 0 && <p className="text-sm text-muted-foreground">None of the selected notices has a quantified hazard.</p>
        )}
        {unquantified.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Not drawn, no quantified hazard: {unquantified.join(', ')}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
