"""The state carried through HAVEN's two compiled graphs.

Two TypedDicts, one per graph. ``HavenState`` spans a whole evaluation;
``SituationState`` spans one raised Situation. Neither is persisted -- HAVEN's
audit ledger is the system of record, so the graphs run without a checkpointer
and the state is ordinary in-process Python objects, passed by reference.

The two frozen dataclasses below are the hand-offs between stages that are not
themselves contract types: ``ScoredTask`` is what SCORE produces for TRIGGER to
judge, and ``RaisedSituation`` is what TRIGGER hands to the situation graph.
They are declared here, with the state, because they *are* part of its shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict

from haven.contracts import (
    CrewMember,
    CrewReadiness,
    EvaluationRequest,
    EvaluationResponse,
    Evidence,
    Recommendation,
    Refusal,
    Situation,
    Task,
    TimelineTask,
)
from haven.deterministic.nasa_tlx import WorkloadResult
from haven.deterministic.screens import ConfidenceResult
from haven.deterministic.three_process_model import AlertnessSample, ThreeProcessModel
from haven.deterministic.triggers import TriggerResult
from haven.rag.retriever import ProcedureRetriever
from haven.reasoning.audit import AuditTrail
from haven.reasoning.llm import ReasoningLLM
from haven.reasoning.orchestrator import ReasoningFlow, ReasoningOutcome


@dataclass(frozen=True)
class ScoredTask:
    """One task with its deterministic scores, before the trigger has judged it.

    ``index`` is the 1-based position in the *sorted* task list and is retained
    rather than recomputed, because the Situation identifier is derived from it.
    """

    index: int
    task: Task
    member: CrewMember
    model: ThreeProcessModel
    sample: AlertnessSample
    workload: WorkloadResult


@dataclass(frozen=True)
class RaisedSituation:
    """A scored task the trigger raised, plus the identifier it was given."""

    scored: ScoredTask
    trigger: TriggerResult
    situation_id: str


class HavenState(TypedDict, total=False):
    """The seven-stage cycle's state: one evaluation, start to finish."""

    # -- bound by the caller ------------------------------------------------
    request: EvaluationRequest
    llm: ReasoningLLM
    retriever: ProcedureRetriever

    # -- INGEST -------------------------------------------------------------
    window_start: datetime
    window_end: datetime
    models: dict[str, ThreeProcessModel]
    by_id: dict[str, CrewMember]
    tasks: list[Task]

    # -- SCORE --------------------------------------------------------------
    readiness: list[CrewReadiness]
    scored: list[ScoredTask]

    # -- TRIGGER ------------------------------------------------------------
    timeline: list[TimelineTask]
    archived: list[str]
    raised: list[RaisedSituation]

    # -- SITUATIONS ---------------------------------------------------------
    situations: list[Situation]
    degraded: bool
    degraded_reason: str | None

    # -- PRESENT ------------------------------------------------------------
    response: EvaluationResponse


class SituationState(TypedDict, total=False):
    """One raised Situation, from the confidence gate to a Situation payload."""

    # -- bound by the evaluation graph --------------------------------------
    window_start: datetime
    request: EvaluationRequest
    models: dict[str, ThreeProcessModel]
    tasks: list[Task]
    retriever: ProcedureRetriever
    llm: ReasoningLLM
    member: CrewMember
    model: ThreeProcessModel
    task: Task
    sample: AlertnessSample
    workload: WorkloadResult
    trigger: TriggerResult
    situation_id: str

    # -- CONFIDENCE ---------------------------------------------------------
    audit_ref: str
    trail: AuditTrail
    confidence: ConfidenceResult
    evidence: Evidence

    # -- RETRIEVE / REASON --------------------------------------------------
    facts: dict[str, Any]
    flow: ReasoningFlow
    outcome: ReasoningOutcome
    degraded: bool
    degraded_reason: str | None

    # -- SCREEN / WITHHOLD --------------------------------------------------
    recommendation: Recommendation | None
    refusal: Refusal | None
    situation: Situation
