"""The locked JSON contract between the engine and the UI (PRD section 5).

This module is the single source of truth for the interface. Both halves of the
team build against it; if it holds, the halves snap together.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field


def _ensure_utc(value: datetime) -> datetime:
    """Normalise an instant to timezone-aware UTC.

    Without this, a naive datetime submitted to ``POST /api/evaluate`` reaches
    ``ThreeProcessModel.homeostatic`` and raises ``TypeError`` on the first
    comparison against an aware instant -- a 500 from the API tier for what is
    really a malformed request. Coercing at the boundary keeps every datetime
    below the contract aware, which the deterministic tier already assumes.

    ``three_process_model.utc`` is the sibling of this function for ISO strings;
    Pydantic has already parsed to ``datetime`` by the time a validator runs, so
    the two cannot be the same helper.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# Every instant crossing the contract is aware and in UTC.
UTCDateTime = Annotated[datetime, AfterValidator(_ensure_utc)]

# Normalised 0-1 alertness, and 0-100 weighted NASA-TLX. These ranges were
# documented in comments and enforced nowhere; a value outside them means the
# deterministic tier is broken, and the contract should say so rather than pass
# it to the UI.
UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]
WorkloadScore = Annotated[float, Field(ge=0.0, le=100.0)]

Criticality = Literal["low", "medium", "high"]
RiskLevel = Literal["nominal", "elevated", "critical"]
Confidence = Literal["high", "moderate", "low", "insufficient"]
Outcome = Literal["recommendation", "refusal"]
ActionType = Literal[
    "second_operator_verify",
    "short_rest_then_proceed",
    "duty_rotation",
    "task_deferral",
    "no_action_required",
]


# --------------------------------------------------------------------------
# Request  (PRD 5.1)
# --------------------------------------------------------------------------
class EvaluationWindow(BaseModel):
    start: UTCDateTime
    end: UTCDateTime


class SleepEntry(BaseModel):
    sleep: UTCDateTime
    wake: UTCDateTime


class DutyEntry(BaseModel):
    start: UTCDateTime
    end: UTCDateTime
    task_type: str = "science_ops"


class CrewMember(BaseModel):
    id: str = Field(examples=["CM-01"])
    name: str = ""
    role: str = Field(examples=["commander"])
    sleep_log: list[SleepEntry] = []
    duty_log: list[DutyEntry] = []
    qualified_for: list[str] = []
    # Hours the individual's biological day is shifted from UTC. Slam-shifted
    # crew are represented here rather than by faking their clock times.
    circadian_offset_h: float = 0.0


class Task(BaseModel):
    id: str = Field(examples=["T-119"])
    type: str = Field(examples=["orbital_burn"])
    criticality: Criticality
    scheduled: UTCDateTime
    assigned_to: str
    duration_min: int = 60
    label: str = ""


class EvaluationRequest(BaseModel):
    evaluation_window: EvaluationWindow
    crew: list[CrewMember]
    tasks: list[Task]
    scenario_id: str | None = None


# --------------------------------------------------------------------------
# Response  (PRD 5.2 / 5.3)
# --------------------------------------------------------------------------
class ClauseDetail(BaseModel):
    """One compiled precondition, as the deterministic checker evaluated it.

    Present on both outcomes, because both are claims about the same test: on a
    recommendation these clauses are the evidence the citation was lawful; on a
    refusal they are the reason it was not. The reasoning tier never sees this
    shape -- it is produced by ``haven.deterministic.preconditions`` after the
    model has already spoken (safety requirement S4).
    """

    clause: str
    satisfied: bool
    expected: str
    actual: str
    explanation: str


class Citation(BaseModel):
    doc: str
    section: str
    title: str = ""
    passage_id: str = ""


class ScheduleImpact(BaseModel):
    roster_ok: bool
    checked_roles: list[str] = []
    alternate: str | None = None
    alternate_name: str = ""
    note: str = ""
    blocked_reason: str | None = None


class Recommendation(BaseModel):
    action: ActionType
    action_label: str
    citation: Citation
    rationale: str
    resource_cost: str = ""
    schedule_impact: ScheduleImpact
    # Every precondition of the cited passage, as the deterministic checker
    # evaluated it *after* the model proposed the citation. Non-empty and
    # all-satisfied on every recommendation HAVEN issues (safety requirement
    # S5); the console shows it so an operator can audit the citation rather
    # than trust it.
    verified_clauses: list[ClauseDetail] = []


class BestCandidate(BaseModel):
    doc: str
    section: str = ""
    relevance: float


class Refusal(BaseModel):
    reason: Literal[
        "no_governing_procedure",
        "insufficient_input",
        "roster_conflict",
        "provider_unavailable",
        # The reasoning tier named a passage; the deterministic checker found a
        # precondition of that passage unsatisfied. ``failed_clauses`` names it.
        "precondition_unmet",
        # The reasoning tier and the checker reached different conclusions about
        # whether anything governs. Both directions fail closed (S6).
        "checker_model_disagreement",
        "numeric_integrity_failure",
    ]
    reason_label: str
    searched: list[str]
    best_candidate: BestCandidate | None = None
    # Retrieval relevance floor. Display-only since v2: no decision anywhere in
    # HAVEN branches on it (``tests/test_propose_dispose.py`` asserts that).
    # Retained on the contract so the console can keep showing the operator what
    # similarity the closest candidate actually scored.
    gate: float
    explanation: str
    escalate_to: str
    # Which preconditions the checker found unsatisfied, and what the model had
    # proposed when it did. Empty when the refusal never reached a selection.
    failed_clauses: list[ClauseDetail] = []
    model_selected: str | None = None
    checker_disagreed: bool = False


class Evidence(BaseModel):
    """The deterministic facts handed to the reasoning tier, echoed verbatim.

    Present in the response so an operator can confirm that every number in the
    recommendation text came from here and not from the model.
    """

    hours_awake: float = Field(ge=0.0)
    sleep_debt_h: float = Field(ge=0.0)
    last_sleep_duration_h: float = Field(ge=0.0)
    # Karolinska Sleepiness Scale, clamped to its published 1-9 range by
    # ``three_process_model.to_kss``.
    kss: float = Field(ge=1.0, le=9.0)
    # S, C and W on the model's native scale. Signed and unbounded by design:
    # C oscillates about zero and W is strictly negative.
    homeostatic: float
    circadian: float
    inertia: float
    workload_subscales: dict[str, float] = {}
    workload_band: str = ""
    data_coverage: UnitInterval = 1.0


class Situation(BaseModel):
    situation_id: str
    crew_member: str
    crew_member_name: str = ""
    crew_role: str = ""
    task: str
    task_type: str
    task_label: str = ""
    task_scheduled: UTCDateTime
    task_criticality: Criticality
    alertness_score: UnitInterval  # deterministic, Three-Process Model
    workload_score: WorkloadScore  # weighted NASA-TLX
    circadian_flag: bool
    risk_level: RiskLevel
    confidence: Confidence
    outcome: Outcome
    recommendation: Recommendation | None = None
    refusal: Refusal | None = None
    evidence: Evidence
    audit_ref: str
    # The exact rulebook this decision was made under. Two evaluations that
    # disagree are only comparable if they were reasoning over the same corpus,
    # and after Phase 4 the corpus is compiled and versioned rather than fixed.
    corpus_manifest: str = ""


class CurvePoint(BaseModel):
    at: UTCDateTime
    score: UnitInterval
    homeostatic: float
    circadian: float
    inertia: float
    kss: float = Field(ge=1.0, le=9.0)
    in_circadian_low: bool
    asleep: bool


class CrewReadiness(BaseModel):
    """Zone 1 payload: per-crew state at the moment of evaluation."""

    crew_member: str
    name: str
    role: str
    # State at ``reference_at``: the window start if the crew member is awake
    # then, otherwise their next wake time. Reporting alertness mid-sleep would
    # read as impairment when it is simply sleep.
    reference_at: UTCDateTime
    asleep_at_window_start: bool
    alertness_score: UnitInterval
    baseline_alertness: UnitInterval
    # A difference of two unit-interval scores, so signed and spanning -1 to 1.
    delta_vs_baseline: float = Field(ge=-1.0, le=1.0)
    workload_score: WorkloadScore
    sleep_debt_h: float = Field(ge=0.0)
    hours_awake: float = Field(ge=0.0)
    window_min_alertness: UnitInterval
    window_min_at: UTCDateTime
    data_coverage: UnitInterval
    confidence: Confidence
    status: Literal["nominal", "watch", "degraded"]
    trend: Literal["improving", "stable", "declining"]
    curve: list[CurvePoint] = []


class TimelineTask(BaseModel):
    """Zone 2 payload: a task plotted against predicted alertness."""

    task_id: str
    label: str
    type: str
    criticality: Criticality
    scheduled: UTCDateTime
    assigned_to: str
    assigned_name: str
    predicted_alertness: UnitInterval
    circadian_low: bool
    raises_situation: bool
    situation_id: str | None = None
    risk_level: RiskLevel


class TierStatus(BaseModel):
    """Zone 6 payload: which tier is live, which is mocked, which is degraded."""

    deterministic: str
    retrieval: str
    reasoning: str
    orchestration: str
    degraded: bool = False
    degraded_reason: str | None = None
    corpus_manifest: str = ""


class EvaluationResponse(BaseModel):
    evaluation_id: str
    generated_at: UTCDateTime
    scenario_id: str | None = None
    scenario_title: str = ""
    scenario_note: str = ""
    window: EvaluationWindow
    readiness: list[CrewReadiness]
    timeline: list[TimelineTask]
    situations: list[Situation]
    archived_low_risk: list[str] = []
    tier_status: TierStatus


# --------------------------------------------------------------------------
# Audit + human decision capture
# --------------------------------------------------------------------------
class AuditStep(BaseModel):
    seq: int
    step: str
    tier: str
    detail: str
    # Parameterised rather than bare ``dict``: an unparameterised dict renders in
    # OpenAPI as an object with no additional properties, which openapi-typescript
    # emits as ``Record<string, never>``. The console reads
    # ``retrieveStep.outputs.candidates``, so that type would be a compile error.
    inputs: dict[str, Any] = {}
    outputs: dict[str, Any] = {}
    started_at: UTCDateTime
    duration_ms: float = Field(ge=0.0)
    entry_hash: str
    prev_hash: str


class AuditRecord(BaseModel):
    audit_ref: str
    situation_id: str
    created_at: UTCDateTime
    steps: list[AuditStep]
    chain_valid: bool
    model_id: str
    provider: str


class DecisionRequest(BaseModel):
    situation_id: str
    audit_ref: str
    decision: Literal["approved", "overridden"]
    operator: str = "flight_surgeon_console"
    reason: str = ""


class DecisionRecord(BaseModel):
    decision_id: str
    situation_id: str
    audit_ref: str
    decision: str
    operator: str
    reason: str
    recorded_at: UTCDateTime


class ScenarioSummary(BaseModel):
    """One demo scenario, as listed by ``GET /api/scenarios``.

    Declared here rather than returned as a bare ``list[dict]`` so the console's
    type for it is generated from the contract like everything else, instead of
    being hand-maintained and free to drift.
    """

    id: str
    title: str
    subtitle: str
    note: str
    demonstrates: str


class ProcedureSummary(BaseModel):
    passage_id: str
    doc: str
    section: str
    title: str
    task_types: list[str]
    source: str
    text: str
