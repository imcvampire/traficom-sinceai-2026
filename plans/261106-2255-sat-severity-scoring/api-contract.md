# `/api/risk/*` contract (riia-1)

This file pins the JSON shapes that phase 03 serves and phase 04 consumes, so the UI can be built against fixture
JSON while the engine is written. Field names are snake_case. Nullable fields are marked `| null`. No field anywhere
is a composite score.

## Shared enums

```ts
type Outcome = 'exceeds' | 'meets' | 'screened_out' | 'not_applicable' | 'not_assessed'
type HazardMode = 'cochannel' | 'adjacent' | 'es_terrestrial' | 'blocking_im' | 'aggregate_networks'
type OrbitType = 'gso' | 'ngso' | 'es'
type Stage = 'API/A' | 'CR/C' | 'Notification' | 'Res49'
type SourceTag = 'physics' | 'rr' | 'itu-r' | 'data' | 'assumption'
type JobStatus = 'idle' | 'running' | 'done' | 'failed'
```

Outcome order for sorting and badges: `exceeds`, `not_assessed`, `meets`, `screened_out`, `not_applicable`.

## `GET /api/risk/issues`

```ts
type Job = {
  status: JobStatus
  done: number
  total: number
  started_at: string | null      // ISO datetime
  finished_at: string | null
  error: string | null
}
type IssueOut = {
  ific_no: number
  path: string                   // display path, never absolute
  ingested: boolean
  assessed: boolean
  model_version: string | null
  receiver_source: 'generic-m4'
  notice_count: number | null
  outcome_counts: Record<Outcome, number> | null   // by notice worst outcome
  assessed_at: string | null
  as_of: string | null           // as_of the stored run used (YYYY-MM-DD)
  job: Job
}
// response: IssueOut[] sorted by ific_no desc
```

## `POST /api/risk/issues/{ific_no}`

Body: none. Query: `as_of` (optional, defaults to today on the server). Responses:

- `202 {accepted: true, job: Job}`
- `404 {detail}` unknown issue
- `409 {detail}` a job is already running for this issue
- `422 {detail}` ingest failed (`IngestError`)

## `GET /api/risk/issues/{ific_no}/notices?as_of=YYYY-MM-DD&view=technical|queue`

`404` if the issue is not assessed. `view=queue` filters to the work queue and orders by `days_left`, then the
technical order. Default `view=technical`.

```ts
type RegulatorySummary = {
  stage: Stage
  provision: string              // notice.prov, e.g. '9.6'
  d_wic: string | null           // YYYY-MM-DD
  window_end: string | null      // YYYY-MM-DD
  days_left: number | null       // null if no comment window for this stage
  window_open: boolean
  fin_identified: boolean
}
type NoticeSummary = {
  ntc_id: number
  sat_name: string | null
  adm: string
  prov: string
  ntc_type: 'G' | 'N' | 'S'
  orbit: OrbitType
  act_code: string | null
  worst_outcome: Outcome
  hazard_counts: Record<Outcome, number>
  services_exceeding: string[]   // service class ids with an `exceeds` hazard
  services_assessed: string[]    // service class ids with any quantified hazard
  max_share_violating: number | null      // 0..1
  max_median_exceedance_db: number | null
  max_worst_case_db: number | null        // Tier 1, dB relative to the class criterion level
  in_queue: boolean
  regulatory: RegulatorySummary
}
type NoticeListOut = {
  ific_no: number
  model_version: string
  receiver_source: 'generic-m4'
  as_of: string
  assessed_at: string
  view: 'technical' | 'queue'
  notices: NoticeSummary[]
}
```

## `GET /api/risk/issues/{ific_no}/notices/{ntc_id}?as_of=`

```ts
type Criterion = { metric: 'I/N' | 'spfd_margin'; level_db: number; time_pct: number; cite: string }
type Exceedance = {
  level_db: number
  time_pct: number
  median_db: number | null       // population median of X_r(p) − level
  p95_db: number | null
}
type RiskCurve = { time_pct: number; likelihood: number[] }   // L_p(x) on curve_grid_db, 0..1
type Input = { name: string; value: string | number | null; unit: string | null; source: SourceTag; cite: string }
type Assumption = { id: string; text: string; sensitive: boolean }
type Hazard = {
  hazard_id: string              // stable, e.g. 'cochannel:fixed'
  mode: HazardMode
  service_class: string | null   // e.g. 'fixed'; null for modes not tied to one class
  service_label: string | null
  bands_hz: [number, number][]   // Finnish receiver sub-bands in this hazard
  tier: 0 | 1 | 2
  outcome: Outcome
  reason: string | null          // always set for not_applicable / not_assessed / screened_out
  n_receivers: number
  n_samples: number
  share_violating: number | null // 0..1
  exceedance_db: Exceedance[]    // one per criterion point
  risk_curves: RiskCurve[]       // one per criterion time %
  worst_case_db: number | null   // Tier 1 consequence (I/N dB or spfd margin dB)
  criteria: Criterion[]
  inputs: Input[]
  citations: string[]
  assumptions: Assumption[]
}
type Finding = {
  source: 'provn' | 'tr_aff_ntw'
  coord_prov: string
  agree_st: string | null
  grp_id: number | null
  aff_ntc_id: number | null
  network: string | null         // affected Finnish network (tr_aff_ntw.sat_name)
}
type NoticeDetail = NoticeSummary & {
  model_version: string
  receiver_source: 'generic-m4'
  as_of: string
  assessed_at: string
  curve_grid_db: { start: number; stop: number; step: number }   // -40, 40, 1
  hazards: Hazard[]
  regulatory: RegulatorySummary & {
    window_cite: string | null
    findings: Finding[]
    citations: string[]
  }
}
```

## `GET /api/risk/model`

```ts
type ModelOut = {
  model_version: string
  receiver_source: 'generic-m4'
  curve_grid_db: { start: number; stop: number; step: number }
  method_steps: { step: number; source_wording: string; what: string; cite: string }[]
  references: { title: string; url: string; supports: string }[]
  receiver_classes: {
    id: string
    label: string
    keywords: string[]
    pattern: string
    gain_dbi: number
    nf_db: number
    bw_hz: number
    criteria: Criterion[]
    distributions: { param: string; kind: string; low: number; high: number; source: 'assumption'; cite: string }[]
  }[]
  inputs: { name: string; source: SourceTag; cite: string }[]
  outcome_sensitive: string[]    // assumption ids flagged by the latest sensitivity report
  doc_path: 'docs/interference-risk-assessment.md'
}
```

## Health

`GET /api/health` gains `risk: {issues_assessed: number, model_version: string, running_jobs: number}`.
