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

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function errorFrom(res: Response): Promise<ApiError> {
  let detail = `HTTP ${res.status}`
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') detail = body.detail
  } catch {
    // non-JSON error body; keep the status text
  }
  return new ApiError(res.status, detail)
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

export const listFiles = () => request<WatcherFile[]>('/api/watcher/files')

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

export type NoticeDetail = NoticeSummary & {
  model_version: string
  receiver_source: ReceiverSource
  as_of: string
  assessed_at: string
  curve_grid_db: CurveGrid
  hazards: Hazard[]
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
