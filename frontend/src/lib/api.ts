export type Health = {
  status: string
  version: string
  db: {
    m4_edition: string
    tables: { m4_allocation: number; m4_page: number }
  }
}

export type RunOutcome = 'ok' | 'error' | 'skipped'
export type FileStatus = 'new' | 'downloading' | 'downloaded' | 'failed'
/** `space` is the Space IFIC; `terrestrial` is the BR IFIC extract with the same issue number. */
export type FileKind = 'space' | 'terrestrial'

export type WatcherRun = {
  started_at: string
  finished_at: string
  trigger: 'schedule' | 'manual' | 'cli'
  outcome: RunOutcome
  new_count: number
  downloaded_count: number
  failed_count: number
  error: string | null
}

export type WatcherState = {
  enabled: boolean
  locked: boolean
  ui_enabled: boolean | null
  interval_seconds: number
  running: boolean
  source_url: string
  terrestrial_enabled: boolean
  terrestrial_source_url: string
  last_run: WatcherRun | null
  next_run_at: string | null
}

export type WatcherFile = {
  ific_no: number
  published_on: string | null
  zip_url: string
  status: FileStatus
  size_bytes: number | null
  local_path: string | null
  error: string | null
  attempts: number
  discovered_at: string
  downloaded_at: string | null
}

export class ApiError extends Error {
  readonly status: number
  /** The parsed JSON error body, for routes that return more than `detail`. */
  readonly body: unknown

  constructor(status: number, message: string, body?: unknown) {
    super(message)
    this.status = status
    this.body = body
  }
}

async function errorFrom(res: Response): Promise<ApiError> {
  let detail = `HTTP ${res.status}`
  let body: unknown
  try {
    body = await res.json()
    const text = (body as { detail?: unknown }).detail
    if (typeof text === 'string') detail = text
  } catch {
    // non-JSON error body; keep the status text
  }
  return new ApiError(res.status, detail, body)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
  })
  if (!res.ok) throw await errorFrom(res)
  return (await res.json()) as T
}

export const getHealth = () => request<Health>('/api/health')

export const getWatcher = () => request<WatcherState>('/api/watcher')

export const setWatcherEnabled = (enabled: boolean) =>
  request<WatcherState>('/api/watcher', { method: 'PATCH', body: JSON.stringify({ enabled }) })

export const checkNow = () => request<{ accepted: boolean }>('/api/watcher/check', { method: 'POST' })

export const listFiles = (kind: FileKind = 'space') => request<WatcherFile[]>(`/api/watcher/files?kind=${kind}`)

export type Outcome = 'exceeds' | 'meets' | 'screened_out' | 'not_applicable' | 'not_assessed'
export type HazardMode = 'cochannel' | 'adjacent' | 'es_terrestrial' | 'blocking_im' | 'aggregate_networks'
export type OrbitType = 'gso' | 'ngso' | 'es'
export type Stage = 'API/A' | 'CR/C' | 'Notification' | 'Res49'
export type SourceTag = 'physics' | 'rr' | 'itu-r' | 'data' | 'assumption'
export type JobStatus = 'idle' | 'running' | 'done' | 'failed'
export type NoticeView = 'technical' | 'queue'
export type ReceiverSource = 'generic-m4'

export type Job = {
  status: JobStatus
  done: number
  total: number
  started_at: string | null
  finished_at: string | null
  error: string | null
}

export type IssueOut = {
  ific_no: number
  path: string
  ingested: boolean
  assessed: boolean
  model_version: string | null
  receiver_source: ReceiverSource
  notice_count: number | null
  outcome_counts: Record<Outcome, number> | null
  assessed_at: string | null
  as_of: string | null
  job: Job
}

export type AssessAccepted = { accepted: true; job: Job }

export type RegulatorySummary = {
  stage: Stage
  provision: string
  d_wic: string | null
  window_end: string | null
  days_left: number | null
  window_open: boolean
  fin_identified: boolean
}

export type NoticeSummary = {
  ntc_id: number
  sat_name: string | null
  adm: string
  prov: string
  ntc_type: 'G' | 'N' | 'S'
  orbit: OrbitType
  act_code: string | null
  worst_outcome: Outcome
  hazard_counts: Record<Outcome, number>
  services_exceeding: string[]
  services_assessed: string[]
  max_share_violating: number | null
  max_median_exceedance_db: number | null
  max_worst_case_db: number | null
  /** RR Table 21-4 check; null on results stored before it existed (re-assess to compute). */
  pfd_outcome?: Outcome | null
  max_pfd_margin_db?: number | null
  pfd_near_limit?: boolean | null
  in_queue: boolean
  regulatory: RegulatorySummary
}

export type NoticeListOut = {
  ific_no: number
  model_version: string
  receiver_source: ReceiverSource
  as_of: string
  assessed_at: string
  view: NoticeView
  notices: NoticeSummary[]
}

export type Criterion = { metric: 'I/N' | 'spfd_margin'; level_db: number; time_pct: number; cite: string }

export type Exceedance = {
  level_db: number
  time_pct: number
  median_db: number | null
  p95_db: number | null
}

export type RiskCurve = { time_pct: number; likelihood: number[] }

export type HazardInput = {
  name: string
  value: string | number | null
  unit: string | null
  source: SourceTag
  cite: string
}

export type Assumption = { id: string; text: string; sensitive: boolean }

export type Hazard = {
  hazard_id: string
  mode: HazardMode
  service_class: string | null
  service_label: string | null
  bands_hz: [number, number][]
  tier: 0 | 1 | 2
  outcome: Outcome
  reason: string | null
  n_receivers: number
  n_samples: number
  share_violating: number | null
  exceedance_db: Exceedance[]
  risk_curves: RiskCurve[]
  worst_case_db: number | null
  criteria: Criterion[]
  inputs: HazardInput[]
  citations: string[]
  assumptions: Assumption[]
}

export type Finding = {
  source: 'provn' | 'tr_aff_ntw'
  coord_prov: string
  agree_st: string | null
  grp_id: number | null
  aff_ntc_id: number | null
  network: string | null
}

export type CurveGrid = { start: number; stop: number; step: number }

export type PfdCheck = {
  check_id: string
  grp_id: number | null
  n_groups: number
  n_groups_exceeding: number
  row_id: string | null
  band_hz: [number, number] | null
  service: string | null
  orbit: OrbitType
  ref_bw_hz: number | null
  source: 'calculated' | 'notified' | null
  pfd_dbw_m2: number | null
  limit_dbw_m2: number | null
  delta_deg: number | null
  margin_db: number | null
  outcome: Outcome
  near_limit: boolean
  reason: string | null
  inputs: HazardInput[]
  citations: string[]
  assumptions: Assumption[]
}

export type NoticeDetail = NoticeSummary & {
  model_version: string
  receiver_source: ReceiverSource
  as_of: string
  assessed_at: string
  curve_grid_db: CurveGrid
  hazards: Hazard[]
  pfd_checks?: PfdCheck[] | null
  pfd_check_version?: string | null
  pfd_limits_sha256?: string | null
  pfd_limits_review?: string | null
  regulatory: RegulatorySummary & {
    window_cite: string | null
    findings: Finding[]
    citations: string[]
  }
}

export type ReceiverClass = {
  id: string
  label: string
  keywords: string[]
  pattern: string
  gain_dbi: number
  nf_db: number
  bw_hz: number
  acs_db: number
  min_elev_deg: number
  /** Citation per characteristic, keyed by field name (pattern, gain_dbi, nf_db, bw_hz, acs_db, min_elev_deg). */
  cites: Record<string, string>
  criteria: Criterion[]
  distributions: { param: string; kind: string; low: number; high: number; source: 'assumption'; cite: string }[]
}

export type ModelOut = {
  model_version: string
  receiver_source: ReceiverSource
  curve_grid_db: CurveGrid
  method_steps: { step: number; source_wording: string; what: string; cite: string }[]
  references: { title: string; url: string; supports: string }[]
  receiver_classes: ReceiverClass[]
  inputs: { name: string; source: SourceTag; cite: string }[]
  outcome_sensitive: string[]
  doc_path: 'docs/interference-risk-assessment.md'
}

const query = (params: Record<string, string | undefined>) => {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value) search.set(key, value)
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const listRiskIssues = () => request<IssueOut[]>('/api/risk/issues')

export const assessIssue = (ificNo: number, asOf?: string) =>
  request<AssessAccepted>(`/api/risk/issues/${ificNo}${query({ as_of: asOf })}`, { method: 'POST' })

export const listRiskNotices = (ificNo: number, asOf: string, view: NoticeView) =>
  request<NoticeListOut>(`/api/risk/issues/${ificNo}/notices${query({ as_of: asOf, view })}`)

export const getRiskNotice = (ificNo: number, ntcId: number, asOf: string) =>
  request<NoticeDetail>(`/api/risk/issues/${ificNo}/notices/${ntcId}${query({ as_of: asOf })}`)

export const getRiskModel = () => request<ModelOut>('/api/risk/model')

// Mirrors DraftOut, DraftAnnexRowOut and DraftPolishOut in backend/src/ific/riia/schemas.py.
export type DraftKind = 'comment_9_52' | 'inclusion_9_41' | 'comment_9_3' | 'enquiry'
export type DraftReading = 'exceeds' | 'main_beam' | 'near_limit'

export type DraftAnnexRow = {
  source: string
  hazard_id: string
  reading: DraftReading
  service_label: string | null
  bands_hz: [number, number][]
  share_violating: number | null
  worst_p95_db: number | null
  worst_case_db: number | null
  metric: string | null
  level_db: number | null
  time_pct: number | null
  cite: string | null
}

export type Draft = {
  kind: DraftKind
  ific_no: number
  ntc_id: number
  sat_name: string | null
  adm: string
  adm_name: string | null
  stage: Stage
  provision: string
  d_wic: string | null
  window_end: string | null
  days_left: number | null
  fin_identified: boolean
  br_provisions: string[]
  annex: DraftAnnexRow[]
  warnings: string[]
  reviewer_notes: string[]
  prose_paragraphs: string[]
  model_version: string
  as_of: string
  letter_md: string
}

export type DraftPolish = { letter_md: string; polished: boolean; model: string }
/** 422 body of a rejected polish: the protected tokens the rewrite dropped or introduced. */
export type DraftPolishRejection = { detail: string; missing: string[]; added: string[] }

const draftPath = (ificNo: number, ntcId: number) => `/api/risk/issues/${ificNo}/notices/${ntcId}/draft`

export const getDraft = (ificNo: number, ntcId: number, asOf: string) =>
  request<Draft>(`${draftPath(ificNo, ntcId)}${query({ as_of: asOf })}`)

export const polishDraft = (ificNo: number, ntcId: number, asOf: string) =>
  request<DraftPolish>(`${draftPath(ificNo, ntcId)}/polish${query({ as_of: asOf })}`, { method: 'POST' })

export type ChatMessage = { role: 'user' | 'assistant'; content: string }
export type ChatRequest = {
  messages: ChatMessage[]
  ntc_ids?: number[]
  ntc_id?: number
  filters?: Record<string, string>
}
export type ChatStatus = { enabled: boolean; model: string | null; reason: string | null }
export type ChatUsage = { prompt_tokens: number | null; completion_tokens: number | null }

export const getChatStatus = () => request<ChatStatus>('/api/risk/chat')

/** Streams one answer over SSE (`delta`, `done`, `error` events); resolves with the provider's usage. */
export async function streamRiskChat(
  ificNo: number,
  asOf: string,
  body: ChatRequest,
  { signal, onDelta }: { signal?: AbortSignal; onDelta: (text: string) => void },
): Promise<{ usage: ChatUsage | null }> {
  const res = await fetch(`/api/risk/issues/${ificNo}/chat${query({ as_of: asOf })}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) throw await errorFrom(res)
  if (!res.body) throw new ApiError(res.status, 'The response has no body')
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value.replace(/\r\n/g, '\n')
    let end: number
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      let event = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trimStart()
      }
      if (!data) continue
      const payload = JSON.parse(data) as { text?: string; usage?: ChatUsage | null; detail?: string }
      if (event === 'delta' && payload.text) onDelta(payload.text)
      else if (event === 'error') throw new ApiError(502, payload.detail ?? 'The answer stopped with an error')
      else if (event === 'done') return { usage: payload.usage ?? null }
    }
  }
  throw new ApiError(502, 'The answer ended before it was complete')
}

export type ContourBound = 'exact' | 'below_1km' | 'at_least_1000km'
export type NoContourReason =
  | 'missing_tx_frequency'
  | 'outside_p1546_range'
  | 'no_power'
  | 'unsupported_power_type'
  | 'missing_antenna_height'
  | 'antenna_height_out_of_range'
export type StationTimePct = 1 | 10 | 50

export type Contour = {
  radius_km: number
  bound: ContourBound
  threshold_dbuv: number
  threshold_source: 'tr2508' | 'user'
  threshold_citation: string | null
  threshold_note: string | null
  time_pct: number
  loc_pct: number
  h1_m: number
  h2_m: number
  erp_dbw: number
  f_mhz: number
  assumptions: string[]
}

export type StationProps = {
  source_row: number
  station_no: number
  licence_class: string | null
  tx_hz: number | null
  rx_hz: number | null
  bandwidth_hz: number | null
  effective_agl_m: number | null
  effective_asl_m: number | null
  ground_height_m: number | null
  azimuth_deg: number | null
  directivity: string | null
  ant_gain_db: number | null
  polarisation: string | null
  emission_class: string | null
  radiated_power_dbw: number | null
  band_bin: number | null
  m4_services: string[]
  quality_flags: string[]
  contour: Contour | null
  no_contour_reason: NoContourReason | null
}

export type StationFeature = {
  type: 'Feature'
  id: number
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: StationProps
}

export type StationModel = {
  p1546_version: string
  p1546_reference: string
  tr2508_citation: string
  tr2508_range_mhz: [number, number]
  time_pct: number
  loc_pct: number
  h2_m: number
  rx_env: string
  path: string
  terrain: string
  antenna: string
  user_threshold_dbuv: number
  radius_range_km: [number, number]
}

export type StationCollection = { type: 'FeatureCollection'; model: StationModel; features: StationFeature[] }

export type StationOverlap = {
  side: 'tx' | 'rx'
  m4_id: number
  overlap_lower_hz: number
  overlap_upper_hz: number
  services_in_finland: string | null
  sub_band_usage: string | null
  class_of_station: string | null
  direction: string | null
}

export type StationDetail = StationFeature & {
  raw: Record<string, string | number | null>
  m4_overlaps: StationOverlap[]
  p1546_steps: Record<string, number> | null
  model: StationModel
}

const stationParams = (timePct: StationTimePct, threshold: number) =>
  query({ time_pct: String(timePct), threshold_dbuv: String(threshold) })

export const listStations = (timePct: StationTimePct, threshold: number) =>
  request<StationCollection>(`/api/stations${stationParams(timePct, threshold)}`)

export const getStation = (sourceRow: number, timePct: StationTimePct, threshold: number) =>
  request<StationDetail>(`/api/stations/${sourceRow}${stationParams(timePct, threshold)}`)

// Mirrors backend/src/ific/terra/schemas.py: `/api/terrestrial/*` (BR IFIC terrestrial land mobile).
export type TerraChange = 'new' | 'modified' | 'withdrawn' | 'unknown'
export type TerraPubStatus = 'received' | 'recorded' | 'returned' | 'unknown'
export type TerraApplicability = 'applicable' | 'indicative' | 'unknown'
export type TerraSignalId = 'fin_coordination' | 'ge06_affected' | 'within_range' | 'freq_overlap_m4'
export type TerraSegmentKind = 'land' | 'sea_cold' | 'sea_warm'
export type TerraLetterKind = 'coordination_request' | 'enquiry'

export type TerraIssueOut = {
  ific_no: number
  path: string
  ingested: boolean
  assessed: boolean
  model_version: string | null
  assignment_count: number | null
  relevant_count: number | null
  outcome_counts: Record<Outcome, number> | null
  assessed_at: string | null
  job: Job
}

export type TerraAcceptedOut = { accepted: boolean; job: Job }

export type TerraSite = {
  geo_key: number
  geo_type: string | null
  ctry: string | null
  name: string | null
  lat: number
  lon: number
  alt_m: number | null
}

export type TerraAntenna = {
  ant_key: number
  pwr_dbw: number | null
  pwr_eiv: string | null
  pwr_xyz: string | null
  erp_dbw: number | null
  hgt_agl_m: number | null
  ant_dir: string | null
  azm_max_e: number | null
  gain_max: number | null
  diagram: { azm: number; attn: number }[]
  rows: number
}

export type TerraTarget = { terrakey: number; action: string | null; intent: string | null }

export type TerraDiff = {
  table: string
  field: string
  ant_key?: number | null
  before: string | number | null
  after: string | number | null
}

export type TerraFinding = { fdg_type: string | null; fdg_status: string | null; is_favorbl: boolean }

export type TerraPubStatusOut = {
  status: TerraPubStatus
  part: string | null
  pub_no: number | null
  first_published_in: number | null
  history: { pub_no: number | null; part: string }[]
  finding: TerraFinding | null
  findings: TerraFinding[]
}

export type TerraCoordination = { adm: string | null; coord_prov: string | null; coord_st: string | null }

export type TerraSignal = { id: TerraSignalId; sufficient: boolean; detail: string; source: string }

export type TerraRelevance = {
  relevant: boolean
  signals: TerraSignal[]
  distance_km: number | null
  fin_coordination: TerraCoordination[]
  fin_coord_required: boolean
}

export type TerraRegulatory = {
  rr_provision: { code: string | null; label: string | null }
  ge06: { applies: boolean; cite: string | null }
  criterion_id: string | null
  criterion_applicability: TerraApplicability | null
  applicability_reason: string | null
  governing: string | null
  m4_rows: { id: number; services: string | null }[]
  m4_cite: string
  citations: string[]
}

export type TerraCriterionRef = {
  id: string
  title: string
  citation: string
  verified: boolean
  verified_by: string | null
  applicability: TerraApplicability | null
}

export type TerraTrigger = {
  base_dbuv_m: number
  bandwidth_correction_db: number
  e_dbuv_m: number
  evaluation_km: number
  note: string
}

export type TerraParameters = {
  f_mhz: number
  bw_khz: number | null
  h1_m: number
  h2_m: number
  time_pct: number
  loc_pct: number
  erp_dbw: number
  rx_env: string
  bw_correction_db: number
}

export type TerraPoint = { lat: number; lon: number; distance_km: number; bearing_deg: number }

export type TerraSegment = { kind: TerraSegmentKind; length_km: number }

export type TerraTier1 = { point: TerraPoint; path: TerraSegment[]; e_upper_dbuv: number; margin_upper_db: number }

export type TerraP1546 = {
  version: string
  inputs: Record<string, number | string>
  steps: Record<string, number>
  assumptions: string[]
}

export type TerraTier2 = {
  worst_point: TerraPoint
  path: TerraSegment[]
  e_p1546_dbuv: number
  antenna_attenuation_db: number
  e_dbuv: number
  margin_db: number
  points_evaluated: number
  e_all_land_dbuv: number
  e_all_sea_dbuv: number
  /** Omitted (null) in the assignment list; present on the single-assignment route. */
  p1546?: TerraP1546 | null
  other_levels: { trigger_dbuv_m: number; case: string; margin_db: number }[]
}

export type TerraHazard = {
  hazard_id: string
  outcome: Outcome
  reason: string | null
  tier: number
  detail?: string | null
  criterion_id?: string | null
  trigger?: TerraTrigger | null
  parameters?: TerraParameters | null
  tier1?: TerraTier1 | null
  tier2?: TerraTier2 | null
}

export type TerraAssignment = {
  model_version: string
  ific_no: number
  terrakey: number
  adm: string
  adm_ref_id: string | null
  stn_cls: string
  stn_cls_description: string | null
  notice_typ: string | null
  notice_typ_description: string | null
  role: 'tx' | 'rx' | 'unknown'
  intent: string
  prov: string | null
  f_mhz: number | null
  freq_min_mhz: number | null
  freq_max_mhz: number | null
  bw_khz: number | null
  bw_code: string | null
  emi_cls: string | null
  d_rcv: string | null
  site: TerraSite | null
  antenna: TerraAntenna | null
  change: TerraChange
  target: TerraTarget | null
  diff: TerraDiff[] | null
  diff_reason: string | null
  pub_status: TerraPubStatusOut
  coordination: TerraCoordination[]
  sources: string[]
  relevance: TerraRelevance
  regulatory: TerraRegulatory
  criterion: TerraCriterionRef | null
  hazard: TerraHazard
  outcome: Outcome
  reason: string | null
  e_dbuv: number | null
  trigger_dbuv: number | null
  margin_db: number | null
  assumptions: string[]
  sort_key: number[]
}

export type TerraAssignmentList = {
  ific_no: number
  model_version: string
  assessed_at: string
  count: number
  assignments: TerraAssignment[]
}

export type TerraCriterion = {
  id: string
  title: string
  citation: string
  doc_url: string
  doc_sha256: string
  f_min_mhz: number
  f_max_mhz: number
  time_pct: number
  loc_pct: number
  rx_height_m: number
  reference_bw_khz: number
  bw_correction: string
  evaluation: string
  bands: { f_min_mhz: number; f_max_mhz: number; trigger_dbuv_m: number; evaluation_km: number; quote: string }[]
  verified: boolean
  verified_by: string | null
}

export type TerraModel = {
  model_version: string
  p1546_version: string
  criteria: TerraCriterion[]
  assumptions: { id: string; text: string }[]
  frameworks: string[]
  neighbours: string[]
  method_doc: string
}

export type TerraAnomalyRule = {
  id: string
  description: string
  threshold: string
  citation: string
  matches: { terrakey: number; adm: string; adm_ref_id: string | null; detail: string }[]
}

export type TerraTrends = {
  ific_no: number
  issues: number[]
  neighbours: string[]
  dimensions: string[]
  /** Keyed by issue number (a string once JSON-encoded). */
  per_issue: Record<string, { received: number; by_adm: Record<string, number> }>
  /** dimension -> administration -> value -> count */
  counts: Record<string, Record<string, Record<string, number>>>
  anomalies: TerraAnomalyRule[]
}

export type TerraDraftAnnexRow = {
  adm_ref_id: string | null
  kind: TerraLetterKind
  f_mhz: number | null
  bw_khz: number | null
  erp_dbw: number | null
  h1_m: number | null
  criterion_id: string | null
  applicability: string | null
  trigger_dbuv: number | null
  e_dbuv: number | null
  margin_db: number | null
  fin_coord: string | null
  outcome: Outcome
}

export type TerraDraft = {
  kind: TerraLetterKind
  ific_no: number
  adm: string
  adm_name: string | null
  annex: TerraDraftAnnexRow[]
  basis: string[]
  warnings: string[]
  reviewer_notes: string[]
  prose_paragraphs: string[]
  model_version: string
  letter_md: string
}

export type TerraDraftPolish = { letter_md: string; polished: boolean; model: string | null }

export type TerraDraftAdm = { adm: string; adm_name: string | null; assignments: number }

/** Server-side filters of the assignment list; list values become repeated query params. */
export type TerraAssignmentFilters = {
  outcome?: Outcome[]
  adm?: string[]
  change?: TerraChange
  pub_status?: TerraPubStatus
  relevant?: 'true' | 'false' | 'all'
  criterion?: string
  q?: string
}

function listQuery(params: Record<string, string | readonly string[] | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === 'string') {
      if (value) search.set(key, value)
    } else for (const item of value ?? []) search.append(key, item)
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

const terraIssuePath = (ificNo: number) => `/api/terrestrial/issues/${ificNo}`

export const listTerraIssues = () => request<TerraIssueOut[]>('/api/terrestrial/issues')

export const assessTerraIssue = (ificNo: number) => request<TerraAcceptedOut>(terraIssuePath(ificNo), { method: 'POST' })

export const listTerraAssignments = (ificNo: number, filters: TerraAssignmentFilters) =>
  request<TerraAssignmentList>(`${terraIssuePath(ificNo)}/assignments${listQuery(filters)}`)

/** Same filters and order as the list; the browser downloads it as `terra-<no>.csv`. */
export const terraAssignmentsCsvUrl = (ificNo: number, filters: TerraAssignmentFilters) =>
  `${terraIssuePath(ificNo)}/assignments.csv${listQuery(filters)}`

export const getTerraAssignment = (ificNo: number, terrakey: number) =>
  request<TerraAssignment>(`${terraIssuePath(ificNo)}/assignments/${terrakey}`)

export const getTerraTrends = (ificNo: number, issues: readonly number[]) =>
  request<TerraTrends>(`${terraIssuePath(ificNo)}/trends${listQuery({ issues: issues.join(',') })}`)

export const listTerraDrafts = (ificNo: number) => request<TerraDraftAdm[]>(`${terraIssuePath(ificNo)}/drafts`)

export const getTerraDraft = (ificNo: number, adm: string) =>
  request<TerraDraft>(`${terraIssuePath(ificNo)}/drafts/${encodeURIComponent(adm)}`)

export const polishTerraDraft = (ificNo: number, adm: string) =>
  request<TerraDraftPolish>(`${terraIssuePath(ificNo)}/drafts/${encodeURIComponent(adm)}/polish`, { method: 'POST' })

export const getTerraModel = () => request<TerraModel>('/api/terrestrial/model')
