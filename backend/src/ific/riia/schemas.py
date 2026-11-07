"""Response models of `/api/risk/*` (contract: plans/261106-2255-sat-severity-scoring/api-contract.md)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Outcome = Literal["exceeds", "meets", "screened_out", "not_applicable", "not_assessed"]


class JobOut(BaseModel):
    status: Literal["idle", "running", "done", "failed"]
    done: int
    total: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None


class IssueOut(BaseModel):
    ific_no: int
    path: str
    ingested: bool
    assessed: bool
    model_version: str | None
    receiver_source: str
    notice_count: int | None
    outcome_counts: dict[Outcome, int] | None
    assessed_at: datetime | None
    as_of: str | None
    job: JobOut


class AcceptedOut(BaseModel):
    accepted: bool
    job: JobOut


class FindingOut(BaseModel):
    source: Literal["provn", "tr_aff_ntw"]
    coord_prov: str
    agree_st: str | None
    grp_id: int | None
    aff_ntc_id: int | None
    network: str | None


class RegulatorySummaryOut(BaseModel):
    stage: str
    provision: str
    d_wic: str | None
    window_end: str | None
    days_left: int | None
    window_open: bool
    fin_identified: bool


class RegulatoryOut(RegulatorySummaryOut):
    window_cite: str | None
    findings: list[FindingOut]
    citations: list[str]


class NoticeSummaryOut(BaseModel):
    ntc_id: int
    sat_name: str | None
    adm: str
    prov: str
    ntc_type: str
    orbit: Literal["gso", "ngso", "es"]
    act_code: str | None
    worst_outcome: Outcome
    hazard_counts: dict[Outcome, int]
    services_exceeding: list[str]
    services_assessed: list[str]
    max_share_violating: float | None
    max_median_exceedance_db: float | None
    max_worst_case_db: float | None
    in_queue: bool
    regulatory: RegulatorySummaryOut


class NoticeListOut(BaseModel):
    ific_no: int
    model_version: str
    receiver_source: str
    as_of: str
    assessed_at: datetime
    view: Literal["technical", "queue"]
    notices: list[NoticeSummaryOut]


class CriterionOut(BaseModel):
    metric: str
    level_db: float
    time_pct: float
    cite: str


class ExceedanceOut(BaseModel):
    level_db: float
    time_pct: float
    median_db: float | None
    p95_db: float | None


class RiskCurveOut(BaseModel):
    time_pct: float
    likelihood: list[float]


class InputOut(BaseModel):
    name: str
    value: str | float | int | None
    unit: str | None
    source: Literal["physics", "rr", "itu-r", "data", "assumption"]
    cite: str


class AssumptionOut(BaseModel):
    id: str
    text: str
    sensitive: bool


class HazardOut(BaseModel):
    hazard_id: str
    mode: Literal["cochannel", "adjacent", "es_terrestrial", "blocking_im", "aggregate_networks"]
    service_class: str | None
    service_label: str | None
    bands_hz: list[tuple[float, float]]
    tier: Literal[0, 1, 2]
    outcome: Outcome
    reason: str | None
    n_receivers: int
    n_samples: int
    share_violating: float | None
    exceedance_db: list[ExceedanceOut]
    risk_curves: list[RiskCurveOut]
    worst_case_db: float | None
    criteria: list[CriterionOut]
    inputs: list[InputOut]
    citations: list[str]
    assumptions: list[AssumptionOut]


class GridOut(BaseModel):
    start: float
    stop: float
    step: float


class NoticeDetailOut(NoticeSummaryOut):
    model_version: str
    receiver_source: str
    as_of: str
    assessed_at: datetime
    curve_grid_db: GridOut
    hazards: list[HazardOut]
    regulatory: RegulatoryOut


class DistributionOut(BaseModel):
    param: str
    kind: str
    low: float
    high: float
    source: Literal["assumption"]
    cite: str


class ReceiverClassOut(BaseModel):
    id: str
    label: str
    keywords: list[str]
    pattern: str
    gain_dbi: float
    nf_db: float
    bw_hz: float
    criteria: list[CriterionOut]
    distributions: list[DistributionOut]


class MethodStepOut(BaseModel):
    step: int
    source_wording: str
    what: str
    cite: str


class ReferenceOut(BaseModel):
    title: str
    url: str
    supports: str


class ModelInputOut(BaseModel):
    name: str
    source: Literal["physics", "rr", "itu-r", "data", "assumption"]
    cite: str


class ModelOut(BaseModel):
    model_version: str
    receiver_source: str
    curve_grid_db: GridOut
    method_steps: list[MethodStepOut]
    references: list[ReferenceOut]
    receiver_classes: list[ReceiverClassOut]
    inputs: list[ModelInputOut]
    outcome_sensitive: list[str]
    doc_path: str
