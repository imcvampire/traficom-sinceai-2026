"""Response models of `/api/terrestrial/*` (mirrored in frontend/src/lib/api.ts as `Terra*`)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from ific.riia.schemas import JobOut, Outcome

Change = Literal["new", "modified", "withdrawn", "unknown"]
PubStatus = Literal["received", "recorded", "returned", "unknown"]
Applicability = Literal["applicable", "indicative", "unknown"]


class TerraIssueOut(BaseModel):
    ific_no: int
    path: str
    ingested: bool
    assessed: bool
    model_version: str | None
    assignment_count: int | None
    relevant_count: int | None
    outcome_counts: dict[Outcome, int] | None
    assessed_at: datetime | None
    job: JobOut


class TerraAcceptedOut(BaseModel):
    accepted: bool
    job: JobOut


class SiteOut(BaseModel):
    geo_key: int
    geo_type: str | None
    ctry: str | None
    name: str | None
    lat: float
    lon: float
    alt_m: float | None


class DiagramPointOut(BaseModel):
    azm: float
    attn: float


class AntennaOut(BaseModel):
    ant_key: int
    pwr_dbw: float | None
    pwr_eiv: str | None
    pwr_xyz: str | None
    erp_dbw: float | None
    hgt_agl_m: float | None
    ant_dir: str | None
    azm_max_e: float | None
    gain_max: float | None
    diagram: list[DiagramPointOut]
    rows: int


class TargetOut(BaseModel):
    terrakey: int
    action: str | None
    intent: str | None


class DiffOut(BaseModel):
    table: str
    field: str
    ant_key: int | None = None
    before: str | float | int | None
    after: str | float | int | None


class FindingOut(BaseModel):
    fdg_type: str | None
    fdg_status: str | None
    is_favorbl: bool


class PubHistOut(BaseModel):
    pub_no: int | None
    part: str


class PubStatusOut(BaseModel):
    status: PubStatus
    part: str | None
    pub_no: int | None
    first_published_in: int | None
    history: list[PubHistOut]
    finding: FindingOut | None
    findings: list[FindingOut]


class CoordinationOut(BaseModel):
    adm: str | None
    coord_prov: str | None
    coord_st: str | None


class SignalOut(BaseModel):
    id: Literal["fin_coordination", "ge06_affected", "within_range", "freq_overlap_m4"]
    sufficient: bool
    detail: str
    source: str


class RelevanceOut(BaseModel):
    relevant: bool
    signals: list[SignalOut]
    distance_km: float | None
    fin_coordination: list[CoordinationOut]
    fin_coord_required: bool


class RrProvisionOut(BaseModel):
    code: str | None
    label: str | None


class Ge06Out(BaseModel):
    applies: bool
    cite: str | None


class M4RowOut(BaseModel):
    id: int
    services: str | None


class TerraRegulatoryOut(BaseModel):
    rr_provision: RrProvisionOut
    ge06: Ge06Out
    criterion_id: str | None
    criterion_applicability: Applicability | None
    applicability_reason: str | None
    governing: str | None
    m4_rows: list[M4RowOut]
    m4_cite: str
    citations: list[str]


class CriterionRefOut(BaseModel):
    id: str
    title: str
    citation: str
    verified: bool
    verified_by: str | None
    applicability: Applicability | None


class TriggerOut(BaseModel):
    base_dbuv_m: float
    bandwidth_correction_db: float
    e_dbuv_m: float
    evaluation_km: float
    note: str


class ParametersOut(BaseModel):
    f_mhz: float
    bw_khz: float | None
    h1_m: float
    h2_m: float
    time_pct: float
    loc_pct: float
    erp_dbw: float
    rx_env: str
    bw_correction_db: float


class PointOut(BaseModel):
    lat: float
    lon: float
    distance_km: float
    bearing_deg: float


class SegmentOut(BaseModel):
    kind: Literal["land", "sea_cold", "sea_warm"]
    length_km: float


class Tier1Out(BaseModel):
    point: PointOut
    path: list[SegmentOut]
    e_upper_dbuv: float
    margin_upper_db: float


class P1546Out(BaseModel):
    version: str
    inputs: dict[str, float | str]
    steps: dict[str, float]
    assumptions: list[str]


class OtherLevelOut(BaseModel):
    trigger_dbuv_m: float
    case: str
    margin_db: float


class Tier2Out(BaseModel):
    worst_point: PointOut
    path: list[SegmentOut]
    e_p1546_dbuv: float
    antenna_attenuation_db: float
    e_dbuv: float
    margin_db: float
    points_evaluated: int
    e_all_land_dbuv: float
    e_all_sea_dbuv: float
    p1546: P1546Out | None = None
    other_levels: list[OtherLevelOut]


class HazardOut(BaseModel):
    hazard_id: str
    outcome: Outcome
    reason: str | None
    tier: int
    detail: str | None = None
    criterion_id: str | None = None
    trigger: TriggerOut | None = None
    parameters: ParametersOut | None = None
    tier1: Tier1Out | None = None
    tier2: Tier2Out | None = None


class AssignmentOut(BaseModel):
    model_version: str
    ific_no: int
    terrakey: int
    adm: str
    adm_ref_id: str | None
    stn_cls: str
    stn_cls_description: str | None
    notice_typ: str | None
    notice_typ_description: str | None
    role: Literal["tx", "rx", "unknown"]
    intent: str
    prov: str | None
    f_mhz: float | None
    freq_min_mhz: float | None
    freq_max_mhz: float | None
    bw_khz: float | None
    bw_code: str | None
    emi_cls: str | None
    d_rcv: str | None
    site: SiteOut | None
    antenna: AntennaOut | None
    change: Change
    target: TargetOut | None
    diff: list[DiffOut] | None
    diff_reason: str | None
    pub_status: PubStatusOut
    coordination: list[CoordinationOut]
    sources: list[str]
    relevance: RelevanceOut
    regulatory: TerraRegulatoryOut
    criterion: CriterionRefOut | None
    hazard: HazardOut
    outcome: Outcome
    reason: str | None
    e_dbuv: float | None
    trigger_dbuv: float | None
    margin_db: float | None
    assumptions: list[str]
    sort_key: list[float]


class AssignmentListOut(BaseModel):
    ific_no: int
    model_version: str
    assessed_at: datetime
    count: int
    assignments: list[AssignmentOut]


class CriterionBandOut(BaseModel):
    f_min_mhz: float
    f_max_mhz: float
    trigger_dbuv_m: float
    evaluation_km: float
    quote: str


class CriterionOut(BaseModel):
    id: str
    title: str
    citation: str
    doc_url: str
    doc_sha256: str
    f_min_mhz: float
    f_max_mhz: float
    time_pct: float
    loc_pct: float
    rx_height_m: float
    reference_bw_khz: float
    bw_correction: str
    evaluation: str
    bands: list[CriterionBandOut]
    verified: bool
    verified_by: str | None


class AssumptionOut(BaseModel):
    id: str
    text: str


class TerraModelOut(BaseModel):
    model_version: str
    p1546_version: str
    criteria: list[CriterionOut]
    assumptions: list[AssumptionOut]
    frameworks: list[str]
    neighbours: list[str]
    method_doc: str


class AnomalyMatchOut(BaseModel):
    terrakey: int
    adm: str
    adm_ref_id: str | None
    detail: str


class AnomalyRuleOut(BaseModel):
    id: str
    description: str
    threshold: str
    citation: str
    matches: list[AnomalyMatchOut]


class IssueCountsOut(BaseModel):
    received: int
    by_adm: dict[str, int]


class TrendsOut(BaseModel):
    ific_no: int
    issues: list[int]
    neighbours: list[str]
    dimensions: list[str]
    per_issue: dict[int, IssueCountsOut]
    # dimension -> administration -> value -> count
    counts: dict[str, dict[str, dict[str, int]]]
    anomalies: list[AnomalyRuleOut]


LetterKindOut = Literal["coordination_request", "enquiry"]


class TerraDraftAnnexRowOut(BaseModel):
    adm_ref_id: str | None
    kind: LetterKindOut
    f_mhz: float | None
    bw_khz: float | None
    erp_dbw: float | None
    h1_m: float | None
    criterion_id: str | None
    applicability: str | None
    trigger_dbuv: float | None
    e_dbuv: float | None
    margin_db: float | None
    fin_coord: str | None
    outcome: Outcome


class TerraDraftOut(BaseModel):
    kind: LetterKindOut
    ific_no: int
    adm: str
    adm_name: str | None
    annex: list[TerraDraftAnnexRowOut]
    basis: list[str]
    warnings: list[str]
    reviewer_notes: list[str]
    prose_paragraphs: list[str]
    model_version: str
    letter_md: str


class TerraDraftPolishOut(BaseModel):
    letter_md: str
    polished: bool
    model: str | None


class DraftAdmOut(BaseModel):
    adm: str
    adm_name: str | None
    assignments: int
