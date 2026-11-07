import type { Contour, NoContourReason, StationModel, StationProps, StationTimePct } from '@/lib/api'

export const DEFAULT_THRESHOLD = 30
export const THRESHOLD_RANGE = [-20, 120] as const
export const DEFAULT_EXAGGERATION = 20
export const EXAGGERATION_RANGE = [1, 50] as const

// TX-frequency bins; must match BAND_EDGES_HZ in backend/src/ific/stations.py.
export const BANDS = [
  { bin: 0, label: '< 30 MHz' },
  { bin: 1, label: '30–300 MHz' },
  { bin: 2, label: '300 MHz–1 GHz' },
  { bin: 3, label: '1–3 GHz' },
  { bin: 4, label: '3–10 GHz' },
  { bin: 5, label: '≥ 10 GHz' },
] as const

export const NO_CONTOUR_LABEL: Record<NoContourReason, string> = {
  missing_tx_frequency: 'No TX frequency in the data',
  outside_p1546_range: 'TX frequency outside the P.1546 range of 30–4000 MHz',
  no_power: 'No radiated power in the data',
  unsupported_power_type: 'Power is not given as e.r.p.',
  missing_antenna_height: 'No antenna height in the data',
  antenna_height_out_of_range: 'Antenna height above the P.1546 limit of 3000 m',
}

export const ASSUMPTION_LABEL: Record<string, string> = {
  h1_flat_terrain: 'Flat terrain: h1 is the antenna height above ground',
  path_assumed_land: 'All-land path; reach over sea is understated',
  omni_worst_case: 'Directional antenna drawn as a circle at maximum e.r.p.',
  power_type_assumed_erp: 'Power type missing; treated as e.r.p.',
  tca_not_applied: 'No terrain clearance angle correction',
  tropo_scatter_not_applied: 'No tropospheric scatter term',
  tr2508_time_differs: 'T/R 25-08 triggers are defined at 10% time',
}

const number = (digits: number) => new Intl.NumberFormat(undefined, { maximumFractionDigits: digits })
const n0 = number(0)
const n1 = number(1)
const n3 = number(3)

export function formatHz(hz: number | null | undefined): string {
  if (hz == null) return '—'
  if (hz >= 1e9) return `${n3.format(hz / 1e9)} GHz`
  if (hz >= 1e6) return `${n3.format(hz / 1e6)} MHz`
  if (hz >= 1e3) return `${n3.format(hz / 1e3)} kHz`
  return `${n0.format(hz)} Hz`
}

export const formatM = (m: number | null | undefined) => (m == null ? '—' : `${n1.format(m)} m`)

export function formatPower(dbw: number | null | undefined): string {
  if (dbw == null) return '—'
  const w = 10 ** (dbw / 10)
  const watts = w >= 1000 ? `${n1.format(w / 1000)} kW` : `${n1.format(w)} W`
  return `${n1.format(dbw)} dBW (${watts})`
}

export const formatDbuv = (v: number) => `${n1.format(v)} dBµV/m`

export function formatRadius(c: Contour): string {
  if (c.bound === 'below_1km') return '< 1 km'
  if (c.bound === 'at_least_1000km') return '≥ 1000 km'
  return `${c.radius_km < 10 ? n1.format(c.radius_km) : n0.format(c.radius_km)} km`
}

export const thresholdSourceLabel = (c: Contour) =>
  c.threshold_source === 'tr2508' ? 'T/R 25-08 trigger' : 'map threshold'

export const bandLabel = (p: Pick<StationProps, 'band_bin'>) =>
  p.band_bin == null ? 'No TX frequency' : BANDS[p.band_bin].label

export const modelStatement = (m: StationModel) =>
  `ITU-R P.1546-6, ${m.time_pct}% time, ${m.loc_pct}% locations, receiver ${m.h2_m} m, land path, flat terrain`

export type StationsSearch = {
  band?: string
  q?: string
  station?: number
  view?: '2d' | '3d'
  t?: StationTimePct
  thr?: number
  contours?: 'off'
  ex?: number
}
