import type {
  Outcome,
  TerraAssignment,
  TerraAssignmentFilters,
  TerraChange,
  TerraLetterKind,
  TerraPubStatus,
  TerraSegmentKind,
  TerraSignalId,
} from '@/lib/api'

export type TerraTab = 'findings' | 'map' | 'trends'
export type TerraChangeFilter = Exclude<TerraChange, 'unknown'>
export type TerraStatusFilter = Exclude<TerraPubStatus, 'unknown'>

/** `/terrestrial` URL search params; list params are comma-separated, already validated and normalised. */
export type TerraSearch = {
  issue?: number
  outcome?: string
  adm?: string
  change?: TerraChangeFilter
  status?: TerraStatusFilter
  relevant?: 'all'
  criterion?: string
  q?: string
  ntc?: number
  tab?: Exclude<TerraTab, 'findings'>
  trend_issues?: string
  draft?: string
}

export const TERRA_OUTCOMES: readonly Outcome[] = ['exceeds', 'not_assessed', 'meets', 'screened_out', 'not_applicable']
export const TERRA_CHANGES: readonly TerraChangeFilter[] = ['new', 'modified', 'withdrawn']
export const TERRA_STATUSES: readonly TerraStatusFilter[] = ['received', 'recorded', 'returned']
export const TERRA_TABS: readonly TerraTab[] = ['findings', 'map', 'trends']
export const ADM_RE = /^[A-Z]{1,3}$/
export const CRITERION_RE = /^[a-z0-9][a-z0-9-]{0,39}$/
/** The API caps `adm` at 8 values and `q` at 80 characters. */
export const MAX_ADMS = 8
export const MAX_Q = 80

export const splitList = (value: string | undefined): string[] => (value ? value.split(',') : [])
export const splitIds = (value: string | undefined): number[] => splitList(value).map(Number)

/** The URL params that are API filters, in the API's shape. */
export function terraFilters(search: TerraSearch): TerraAssignmentFilters {
  return {
    outcome: splitList(search.outcome) as Outcome[],
    adm: splitList(search.adm),
    change: search.change,
    pub_status: search.status,
    relevant: search.relevant === 'all' ? 'all' : 'true',
    criterion: search.criterion,
    q: search.q,
  }
}

export const TERRA_OUTCOME_DESCRIPTION: Record<Outcome, string> = {
  exceeds:
    'The P.1546 field strength at the worst Finnish border point is above the criterion trigger: coordination with Finland is indicated.',
  not_assessed:
    'Relevant to Finland, but the field strength could not be computed: a missing site, power, antenna height or notice type, a frequency or distance outside P.1546, or no criterion for the frequency. The reason is given per row.',
  meets: 'The P.1546 field strength at every evaluated Finnish border point stays at or below the trigger.',
  screened_out:
    'The Tier 1 upper bound (all-sea path to the nearest Finnish point, maximum e.r.p.) stays at least 3 dB below the trigger.',
  not_applicable: 'Nothing to assess: not relevant to Finland, withdrawn, or a receiving station.',
}

export const CHANGE_LABEL: Record<TerraChange, string> = {
  new: 'New',
  modified: 'Modified',
  withdrawn: 'Withdrawn',
  unknown: 'Unknown',
}

export const PUB_STATUS_LABEL: Record<TerraPubStatus, string> = {
  received: 'Received',
  recorded: 'Recorded',
  returned: 'Returned',
  unknown: 'Unknown',
}

export const SIGNAL_META: Record<TerraSignalId, { label: string; description: string }> = {
  fin_coordination: {
    label: 'Finland in coordination',
    description: 'The notice lists FIN in its coordination records (fxm_coord). Sufficient on its own for relevance.',
  },
  ge06_affected: {
    label: 'GE06 affected',
    description: 'Finland is an affected administration under the GE06 Agreement. Sufficient on its own for relevance.',
  },
  within_range: {
    label: 'Within range',
    description: 'The site is within the screening range (1000 km) of the nearest sampled Finnish border or coast point.',
  },
  freq_overlap_m4: {
    label: 'Overlaps M4',
    description: 'The frequency overlaps a Finnish M4 allocation row. Recorded as context, it never decides relevance.',
  },
}

export const SEGMENT_META: Record<TerraSegmentKind, { label: string; color: string }> = {
  land: { label: 'Land', color: 'var(--series-1)' },
  sea_cold: { label: 'Cold sea', color: 'var(--series-2)' },
  sea_warm: { label: 'Warm sea', color: 'var(--series-3)' },
}

export const LETTER_KIND_META: Record<TerraLetterKind, { label: string; description: string }> = {
  coordination_request: {
    label: 'Coordination request',
    description:
      'FIN coordination is COORD REQUIRED, or the field strength exceeds the trigger and no FIN coordination is recorded: Finland asks that the assignments be coordinated before they are brought into use.',
  },
  enquiry: {
    label: 'Technical enquiry',
    description:
      'The field strength exceeds the trigger while FIN coordination is recorded as COORD COMPLETED: Finland asks to confirm the notified characteristics match those coordinated. Not a reply under an RR comment provision.',
  },
}

/** Trend dimensions drawn as small multiples, with the order their values are shown in. */
export const TREND_DIMENSIONS = [
  { id: 'band', label: 'Band', color: 'var(--series-1)' },
  { id: 'distance', label: 'Distance to Finland', color: 'var(--series-2)' },
  { id: 'stn_cls', label: 'Station class', color: 'var(--series-3)' },
  { id: 'bw_code', label: 'Bandwidth', color: 'var(--series-4)' },
] as const

export const DISTANCE_ORDER = ['<50 km', '50-150 km', '150-300 km', '300-1000 km', '≥1000 km', 'unknown']

export const TERMS = {
  margin: 'Field strength E at the worst Finnish point minus the criterion trigger. Above 0 dB the trigger is exceeded.',
  erp: 'Effective radiated power of the assessed antenna row, in dBW: transmitter power plus antenna gain relative to a half-wave dipole.',
  h1: 'Transmitting antenna height above ground (m), used as P.1546 h1 on flat terrain.',
  trigger:
    'The field strength (dBµV/m) at the Finnish border above which the criterion calls for coordination, corrected for bandwidth.',
  indicative:
    'The criterion is a CEPT/ECC recommendation the administration is not bound by (for example RUS, with CEPT membership suspended). The result is indicative; the bilateral agreement governs.',
  finCoord: 'Coordination records of the notice that name FIN: the provision and its status.',
  distance: 'Great-circle distance from the site to the nearest sampled Finnish border or coast point.',
  relevant:
    'An assignment is relevant when Finland is in its coordination records, is GE06-affected, or the site is within range. Show all to review the rest for false negatives.',
  tier1:
    'Tier 1: one deterministic upper bound, an all-sea path to the nearest Finnish point at maximum e.r.p. If it stays at least 3 dB below the trigger the assignment is screened out.',
  tier2:
    'Tier 2: ITU-R P.1546 on mixed land/sea paths to the nearest Finnish points, with antenna discrimination; the worst point is reported.',
  p1546: 'The intermediate values of the ITU-R P.1546 calculation at the worst point, as the backend computed them.',
  sources: 'Every value comes from a source row: issue:table:key. The tags name the BR IFIC tables the fields were read from.',
  anomaly: 'Rules that flag notices worth a second look within this issue. A match is a prompt to review, not a finding.',
}

export const fixed = (value: number | null | undefined, digits: number, unit = '') =>
  value == null ? '—' : `${Number(value.toFixed(digits))}${unit ? ` ${unit}` : ''}`

export const formatMhz = (mhz: number | null | undefined) => fixed(mhz, 4, 'MHz')
export const formatKhz = (khz: number | null | undefined) => fixed(khz, 1, 'kHz')
export const formatDbw = (dbw: number | null | undefined) => fixed(dbw, 1, 'dBW')
export const formatM = (m: number | null | undefined) => fixed(m, 0, 'm')
export const formatKm = (km: number | null | undefined) => fixed(km, 1, 'km')
export const formatDbuv = (e: number | null | undefined) => fixed(e, 1, 'dBµV/m')
export const formatLatLon = (lat: number, lon: number) => `${lat.toFixed(4)}°, ${lon.toFixed(4)}°`

export const finCoordText = (a: Pick<TerraAssignment, 'relevance'>) =>
  a.relevance.fin_coordination.map((c) => [c.coord_prov, c.coord_st].filter(Boolean).join(' ')).join('; ')

/** The Finnish point the result is read at: the Tier 2 worst point, else the Tier 1 nearest point. */
export const worstPoint = (a: Pick<TerraAssignment, 'hazard'>) => a.hazard.tier2?.worst_point ?? a.hazard.tier1?.point ?? null
