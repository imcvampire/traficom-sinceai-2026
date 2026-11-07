import { Ban, CircleCheck, CircleHelp, OctagonAlert, ShieldCheck, type LucideIcon } from 'lucide-react'
import type {
  CurveGrid,
  DraftKind,
  Hazard,
  HazardMode,
  NoticeDetail,
  NoticeSummary,
  OrbitType,
  Outcome,
  RegulatorySummary,
  Stage,
} from '@/lib/api'

const MONTE_CARLO =
  'the Monte Carlo method: a simulation that draws thousands of random receiver positions, antenna pointings and, for non-GSO systems, satellite positions, computes the interference for each draw and counts how often it is above the protection level'

export const TIER_META: Record<Hazard['tier'], { label: string; description: string }> = {
  0: {
    label: 'Inventory',
    description:
      'Tier 0 checks frequency overlap and visibility only. A hazard stops here when there is no overlap or the satellite is never above the horizon in Finland.',
  },
  1: {
    label: 'Worst case',
    description:
      'Tier 1 is one deterministic calculation with every input at its worst value: closest geometry, receiver main beam on the satellite, peak satellite gain. A hazard stops here when even that stays below every protection level.',
  },
  2: { label: 'Monte Carlo', description: `Tier 2 uses ${MONTE_CARLO}.` },
}

export const BR_DESCRIPTION =
  'BR is the ITU Radiocommunication Bureau, which examines each notice and publishes the IFIC. "BR identified Finland" means its findings for this notice name Finland: as an administration whose coordination is required (provn, e.g. RR No. 9.11, 9.14, 9.21) or as the owner of an affected network (tr_aff_ntw).'

export const OPEN_WINDOW_DESCRIPTION =
  'Notices whose comment window has not closed on the "As of" date: the window is still open, or the notice is at a stage without a comment window (Notification, Res. 49). Notices with a closed window are hidden.'

export const WORK_QUEUE_DESCRIPTION =
  'Notices with an exceeding hazard whose comment window has not closed (still open, or no comment window at this stage). Click to show them, soonest deadline first.'

/** The comment window is open on the as-of date, or the notice is at a stage that has none. Mirrors the API's
 * `window_not_closed`, which decides `in_queue` together with an `exceeds` outcome. */
export const windowNotClosed = ({ regulatory: r }: NoticeSummary) => r.days_left == null || r.days_left >= 0

export const WORK_QUEUE_FILTER = { outcome: 'exceeds', open: true, br: undefined, sort: 'days_left.asc' } as const

export const OUTCOME_ORDER: Outcome[] = ['exceeds', 'not_assessed', 'meets', 'screened_out', 'not_applicable']

export const OUTCOME_META: Record<
  Outcome,
  { label: string; description: string; icon: LucideIcon; swatch: string; badge: string }
> = {
  exceeds: {
    label: 'Exceeds',
    description:
      `At least one Finnish receiver violates an ITU-R protection criterion: interference above the protection level for longer than the allowed % of time. Found with ${MONTE_CARLO}.`,
    icon: OctagonAlert,
    swatch: 'bg-status-critical',
    badge: 'bg-status-critical/12 text-status-critical-foreground',
  },
  not_assessed: {
    label: 'Not assessed',
    description:
      'The hazard is relevant but the Monte Carlo simulation could not run, for example because orbit data is missing. Only the worst case is known, so this is not a clean result.',
    icon: CircleHelp,
    swatch: 'bg-status-warning',
    badge: 'bg-status-warning/15 text-foreground',
  },
  meets: {
    label: 'Meets',
    description:
      `No Finnish receiver violates any protection criterion. Checked with ${MONTE_CARLO}.`,
    icon: CircleCheck,
    swatch: 'bg-status-good',
    badge: 'bg-status-good/12 text-status-good-foreground',
  },
  screened_out: {
    label: 'Screened out',
    description:
      'Even the worst case (closest geometry, receiver main beam on the satellite, peak satellite gain) stays below every protection level, so the Monte Carlo simulation was not needed.',
    icon: ShieldCheck,
    swatch: 'bg-status-neutral',
    badge: 'bg-muted text-muted-foreground',
  },
  not_applicable: {
    label: 'Not applicable',
    description:
      'Nothing to assess: no frequency overlap with a Finnish service, the satellite is never above the horizon in Finland, or the notice is a suppression.',
    icon: Ban,
    swatch: 'bg-status-neutral',
    badge: 'bg-muted text-muted-foreground',
  },
}

export const HAZARD_MODE_META: Record<HazardMode, { label: string; color: string }> = {
  cochannel: { label: 'Co-channel', color: 'var(--series-1)' },
  adjacent: { label: 'Adjacent band', color: 'var(--series-2)' },
  es_terrestrial: { label: 'Earth station → terrestrial', color: 'var(--series-3)' },
  blocking_im: { label: 'Blocking / intermodulation', color: 'var(--series-4)' },
  aggregate_networks: { label: 'Aggregate of networks', color: 'var(--series-5)' },
}

export const SERIES_COLORS = [1, 2, 3, 4, 5].map((i) => `var(--series-${i})`)

export const ORBIT_LABEL: Record<OrbitType, string> = { gso: 'GSO', ngso: 'NGSO', es: 'Earth station' }

export const STAGE_SHORT: Record<Stage, string> = { 'API/A': 'API', 'CR/C': 'CR', Notification: 'N', Res49: 'Res49' }

export const DRAFT_BANNER = 'DRAFT – for expert review, not sent'

/** Letter kinds of the draft correspondence; the API picks one from the stage, the open window and the BR findings. */
export const DRAFT_KIND_META: Record<DraftKind, { label: string; description: string }> = {
  comment_9_52: {
    label: 'Comment under RR No. 9.52',
    description:
      'The BR identified Finland on this coordination request (CR/C) and the comment window is open: Finland informs the notifying administration that it does not agree and asks for coordination. Without a reply in time, RR No. 9.52C lets Finland be treated as not affected.',
  },
  inclusion_9_41: {
    label: 'Request for inclusion under RR No. 9.41',
    description:
      'The BR did not identify Finland on this coordination request (CR/C) and the comment window is open: Finland asks to be included in the coordination procedure and comments under RR No. 9.52.',
  },
  comment_9_3: {
    label: 'Comment under RR No. 9.3',
    description:
      'Advance publication (API/A) with the comment window open: Finland informs the notifying administration of the interference it anticipates.',
  },
  enquiry: {
    label: 'Informal technical enquiry',
    description:
      'No RR comment window applies: the notice is at Notification or Resolution 49 stage, or its window has closed. The letter asks for technical information and claims no RR basis.',
  },
}

export const RECEIVER_SOURCE_LABEL = 'Generic population (M4 × grid over Finland)'

export function todayIso(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function formatShare(share: number | null | undefined): string {
  if (share == null) return '—'
  const pct = share * 100
  if (pct === 0) return '0%'
  if (pct < 0.1) return '<0.1%'
  return `${pct < 10 ? pct.toFixed(1) : pct.toFixed(0)}%`
}

export function formatDb(db: number | null | undefined): string {
  if (db == null) return '—'
  const sign = db > 0 ? '+' : db < 0 ? '−' : ''
  return `${sign}${Math.abs(db).toFixed(1)} dB`
}

export const formatTimePct = (pct: number) => `${pct}% of time`

function formatHz(hz: number, unit: 'GHz' | 'MHz'): string {
  const value = unit === 'GHz' ? hz / 1e9 : hz / 1e6
  return String(Number(value.toFixed(3)))
}

export function formatBand([low, high]: [number, number]): string {
  const unit = low >= 10e9 ? 'GHz' : 'MHz'
  return `${formatHz(low, unit)}–${formatHz(high, unit)} ${unit}`
}

export function daysLeftText(reg: RegulatorySummary): { text: string; closed: boolean } {
  if (reg.days_left == null) return { text: '—', closed: false }
  if (!reg.window_open || reg.days_left < 0) return { text: 'closed', closed: true }
  return { text: `${reg.days_left} d`, closed: false }
}

export const gridXs = (grid: CurveGrid): number[] => {
  const n = Math.round((grid.stop - grid.start) / grid.step) + 1
  return Array.from({ length: n }, (_, i) => grid.start + i * grid.step)
}

/** L_p(x) read off a curve on the grid, linearly interpolated between grid points. */
export function likelihoodAt(likelihood: number[], grid: CurveGrid, x: number): number | null {
  if (!likelihood.length) return null
  const pos = (x - grid.start) / grid.step
  if (pos <= 0) return likelihood[0]
  if (pos >= likelihood.length - 1) return likelihood[likelihood.length - 1]
  const i = Math.floor(pos)
  const t = pos - i
  return likelihood[i] * (1 - t) + likelihood[i + 1] * t
}

/** The hazard's criterion for a given time %, matching the curve it belongs to. */
export const criterionFor = (hazard: Hazard, timePct: number) => hazard.criteria.find((c) => c.time_pct === timePct)

export const compareOutcomes = (a: Outcome, b: Outcome) => OUTCOME_ORDER.indexOf(a) - OUTCOME_ORDER.indexOf(b)

/**
 * The curve that represents a notice in the compare view: the worst quantified hazard (outcome order, then share
 * violating, then median exceedance), at the criterion time % with the largest share violating.
 */
export function mainCurve(detail: NoticeDetail): { hazard: Hazard; timePct: number; likelihood: number[] } | null {
  const quantified = detail.hazards.filter((h) => h.risk_curves.length > 0)
  if (!quantified.length) return null
  const medianOf = (h: Hazard) => Math.max(-Infinity, ...h.exceedance_db.map((e) => e.median_db ?? -Infinity))
  const [hazard] = [...quantified].sort(
    (a, b) =>
      compareOutcomes(a.outcome, b.outcome) ||
      (b.share_violating ?? -1) - (a.share_violating ?? -1) ||
      medianOf(b) - medianOf(a),
  )
  let best = hazard.risk_curves[0]
  let bestShare = -1
  for (const curve of hazard.risk_curves) {
    const criterion = criterionFor(hazard, curve.time_pct)
    const share = criterion ? (likelihoodAt(curve.likelihood, detail.curve_grid_db, criterion.level_db) ?? -1) : -1
    if (share > bestShare) {
      best = curve
      bestShare = share
    }
  }
  return { hazard, timePct: best.time_pct, likelihood: best.likelihood }
}

/** True when one curve lies on or above every other curve at every grid point. */
export function hasDominantCurve(curves: number[][]): boolean {
  const EPS = 1e-9
  return curves.some((upper, i) =>
    curves.every((other, j) => i === j || other.every((value, k) => (upper[k] ?? 0) + EPS >= value)),
  )
}
