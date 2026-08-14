"""The retrieval tier (PRD stage 4).

Mirrors the LangChain retriever shape (``get_relevant_documents``) so the real
LangChain + Chroma pipeline can be dropped in without touching the orchestrator.
LangChain is deliberately confined to this file's job: load, chunk, embed,
retrieve. It makes no decision about which candidate governs.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import THRESHOLDS
from app.retrieval.vector_store import Candidate, build_store


@dataclass(frozen=True)
class SituationQuery:
    """The Situation, rendered as a retrieval query (state + task + criticality)."""

    task_type: str
    criticality: str
    alertness_score: float
    workload_score: float
    circadian_flag: bool
    phase: str = "execution"

    def to_text(self) -> str:
        state = []
        if self.alertness_score < THRESHOLDS.alertness_trigger_high:
            state.append("reduced crew alertness below execution threshold")
        if self.circadian_flag:
            state.append("task scheduled during operator circadian trough")
        if self.workload_score >= THRESHOLDS.workload_trigger:
            state.append("sustained high duty workload")
        state_text = "; ".join(state) or "nominal crew state"
        return (
            f"{self.task_type.replace('_', ' ')} of {self.criticality} criticality "
            f"during {self.phase}. Crew condition: {state_text}. "
            f"Governing rule for whether the task may proceed as assigned."
        )


class ProcedureRetriever:
    """Top-k retrieval over the procedure corpus."""

    def __init__(self) -> None:
        self.store = build_store()

    @property
    def backend_name(self) -> str:
        return self.store.backend_name

    def get_relevant_documents(self, query: SituationQuery, top_k: int | None = None) -> list[Candidate]:
        k = top_k or THRESHOLDS.retrieval_top_k
        return self.store.query(
            query_text=query.to_text(),
            task_type=query.task_type,
            criticality=query.criticality,
            top_k=k,
        )


_retriever: ProcedureRetriever | None = None


def get_retriever() -> ProcedureRetriever:
    global _retriever
    if _retriever is None:
        _retriever = ProcedureRetriever()
    return _retriever
