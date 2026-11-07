import { useLayoutEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import type { CurveGrid } from '@/lib/api'
import { formatDb, formatShare, gridXs } from './risk-meta'

export type ChartCurve = { id: string; label: string; color: string; likelihood: number[]; dotted?: boolean }
export type ChartCriterion = {
  id: string
  label: string
  color: string
  levelDb: number
  share: number | null
  shade?: boolean
  point?: boolean
}
export type ChartWorstCase = { id: string; label: string; color: string; db: number }

type RiskChartProps = {
  grid: CurveGrid
  curves: ChartCurve[]
  criteria?: ChartCriterion[]
  worstCases?: ChartWorstCase[]
  ariaLabel: string
  height?: number
}

const FLOOR = 1e-4
const DECADES = Math.log10(1 / FLOOR)
const Y_TICKS = [1e-4, 1e-3, 1e-2, 1e-1, 1]
const MARGIN = { top: 20, right: 16, bottom: 44, left: 60 }
const MIN_WIDTH = 520
const DOTTED = '1.5 3'
const DASHED = '6 4'

function useWidth() {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(MIN_WIDTH)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => setWidth(Math.max(MIN_WIDTH, Math.floor(el.clientWidth)))
    update()
    const observer = new ResizeObserver(update)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}

export function RiskChart({ grid, curves, criteria = [], worstCases = [], ariaLabel, height = 320 }: RiskChartProps) {
  const [ref, width] = useWidth()
  const [hover, setHover] = useState<number | null>(null)
  const xs = useMemo(() => gridXs(grid), [grid])
  const innerW = width - MARGIN.left - MARGIN.right
  const innerH = height - MARGIN.top - MARGIN.bottom
  const bottom = MARGIN.top + innerH
  const right = MARGIN.left + innerW

  const xOf = (db: number) => {
    const clamped = Math.min(grid.stop, Math.max(grid.start, db))
    return MARGIN.left + ((clamped - grid.start) / (grid.stop - grid.start)) * innerW
  }
  const yOf = (share: number) => MARGIN.top + (-Math.log10(Math.max(share, FLOOR)) / DECADES) * innerH

  const paths = curves.map((curve) => {
    let d = ''
    let pen = false
    curve.likelihood.forEach((value, i) => {
      const x = xOf(xs[i]).toFixed(1)
      if (value >= FLOOR) {
        d += `${pen ? 'L' : 'M'}${x},${yOf(value).toFixed(1)}`
        pen = true
      } else if (pen) {
        d += `L${x},${bottom.toFixed(1)}`
        pen = false
      }
    })
    return { ...curve, d }
  })

  const shadeLevels = [...new Set(criteria.filter((c) => c.shade).map((c) => c.levelDb))]
  const shadeStart = shadeLevels.length ? Math.min(...shadeLevels) : null
  const xTicks = xs.filter((x) => x % 10 === 0)

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.getBoundingClientRect()
    const ratio = (e.clientX - box.left) / box.width
    setHover(Math.min(xs.length - 1, Math.max(0, Math.round(ratio * (xs.length - 1)))))
  }

  const hoverRows =
    hover == null
      ? []
      : curves
          .map((c) => ({ id: c.id, label: c.label, color: c.color, value: c.likelihood[hover] ?? 0 }))
          .sort((a, b) => b.value - a.value)
  const hoverX = hover == null ? 0 : xOf(xs[hover])

  return (
    <div className="overflow-x-auto">
      <div ref={ref} className="relative min-w-[520px]">
        <svg width={width} height={height} role="img" aria-label={ariaLabel} className="block select-none">
          {shadeLevels.map((level) => (
            <rect
              key={level}
              x={xOf(level)}
              y={MARGIN.top}
              width={Math.max(0, right - xOf(level))}
              height={innerH}
              fill="var(--status-critical)"
              opacity={0.07}
            />
          ))}

          {Y_TICKS.map((tick) => (
            <g key={tick}>
              <line x1={MARGIN.left} x2={right} y1={yOf(tick)} y2={yOf(tick)} stroke="var(--border)" />
              <text
                x={MARGIN.left - 8}
                y={yOf(tick)}
                dy="0.32em"
                textAnchor="end"
                className="fill-muted-foreground text-[11px] tabular-nums"
              >
                {tick >= 0.01 ? `${tick * 100}%` : `${Number((tick * 100).toPrecision(1))}%`}
              </text>
            </g>
          ))}
          {xTicks.map((tick) => (
            <g key={tick}>
              <line
                x1={xOf(tick)}
                x2={xOf(tick)}
                y1={MARGIN.top}
                y2={bottom}
                stroke="var(--border)"
                strokeWidth={tick === 0 ? 1.5 : 1}
              />
              <text x={xOf(tick)} y={bottom + 16} textAnchor="middle" className="fill-muted-foreground text-[11px] tabular-nums">
                {tick > 0 ? `+${tick}` : tick < 0 ? `−${-tick}` : '0'}
              </text>
            </g>
          ))}
          <text x={MARGIN.left + innerW / 2} y={height - 6} textAnchor="middle" className="fill-muted-foreground text-[11px]">
            Consequence x (dB, I/N or pfd margin)
          </text>
          <text
            transform={`translate(14 ${MARGIN.top + innerH / 2}) rotate(-90)`}
            textAnchor="middle"
            className="fill-muted-foreground text-[11px]"
          >
            Share of receivers above x
          </text>

          {shadeStart != null && (
            <text
              x={Math.min(xOf(shadeStart) + 4, right - 4)}
              y={MARGIN.top - 6}
              textAnchor={xOf(shadeStart) + 100 > right ? 'end' : 'start'}
              className="fill-status-critical-foreground text-[10px] font-medium"
            >
              exceeds criterion →
            </text>
          )}

          {criteria.map((c) => (
            <line
              key={`level-${c.id}`}
              x1={xOf(c.levelDb)}
              x2={xOf(c.levelDb)}
              y1={MARGIN.top}
              y2={bottom}
              stroke={c.color}
              strokeOpacity={0.55}
            />
          ))}

          {worstCases.map((w) => (
            <line
              key={w.id}
              x1={xOf(w.db)}
              x2={xOf(w.db)}
              y1={MARGIN.top}
              y2={bottom}
              stroke={w.color}
              strokeWidth={1.5}
              strokeDasharray={DASHED}
            >
              <title>{`${w.label}: Tier 1 worst case ${formatDb(w.db)}`}</title>
            </line>
          ))}

          {paths.map((p) => (
            <path
              key={p.id}
              d={p.d}
              fill="none"
              stroke={p.color}
              strokeWidth={2}
              strokeDasharray={p.dotted ? DOTTED : undefined}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ))}

          {criteria.map((c) => {
            if (c.point === false) return null
            const below = c.share == null || c.share < FLOOR
            return (
              <circle
                key={`point-${c.id}`}
                cx={xOf(c.levelDb)}
                cy={below ? bottom : yOf(c.share ?? FLOOR)}
                r={4.5}
                fill={below ? 'var(--card)' : c.color}
                stroke={below ? c.color : 'var(--card)'}
                strokeWidth={below ? 2 : 1.5}
              >
                <title>{`${c.label}: ${formatShare(c.share)} of receivers violate`}</title>
              </circle>
            )
          })}

          {hover != null && (
            <line x1={hoverX} x2={hoverX} y1={MARGIN.top} y2={bottom} stroke="var(--foreground)" strokeOpacity={0.35} />
          )}
          <rect
            x={MARGIN.left}
            y={MARGIN.top}
            width={innerW}
            height={innerH}
            fill="transparent"
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          />
        </svg>

        {hover != null && hoverRows.length > 0 && (
          <div
            className="pointer-events-none absolute top-6 z-10 w-max max-w-64 rounded-md border bg-popover px-2.5 py-2 text-xs text-popover-foreground shadow-md"
            style={hoverX > width / 2 ? { right: width - hoverX + 8 } : { left: hoverX + 8 }}
          >
            <div className="mb-1 font-medium tabular-nums">x = {formatDb(xs[hover])}</div>
            <ul className="space-y-0.5">
              {hoverRows.map((row) => (
                <li key={row.id} className="flex items-center gap-2">
                  <span className="h-0.5 w-3 shrink-0 rounded-full" style={{ background: row.color }} aria-hidden />
                  <span className="truncate">{row.label}</span>
                  <span className="ml-auto pl-2 tabular-nums">{formatShare(row.value)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

export function ChartLegend({
  curves,
  showCriteria = true,
  showWorstCase = false,
}: {
  curves: ChartCurve[]
  showCriteria?: boolean
  showWorstCase?: boolean
}) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
      {curves.map((c) => (
        <li key={c.id} className="flex items-center gap-1.5">
          <svg width="18" height="6" aria-hidden>
            <line
              x1="1"
              x2="17"
              y1="3"
              y2="3"
              stroke={c.color}
              strokeWidth="2"
              strokeLinecap="round"
              strokeDasharray={c.dotted ? DOTTED : undefined}
            />
          </svg>
          {c.label}
        </li>
      ))}
      {showCriteria && (
        <>
          <li className="flex items-center gap-1.5">
            <svg width="10" height="10" aria-hidden>
              <circle cx="5" cy="5" r="4" fill="currentColor" />
            </svg>
            Criterion point: share violating
          </li>
          <li className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-xs bg-status-critical/20" aria-hidden />
            Exceeds criterion region
          </li>
        </>
      )}
      {showWorstCase && (
        <li className="flex items-center gap-1.5">
          <svg width="6" height="14" aria-hidden>
            <line x1="3" x2="3" y1="0" y2="14" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 2" />
          </svg>
          Tier 1 worst case
        </li>
      )}
    </ul>
  )
}
