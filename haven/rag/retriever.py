"""The retrieval tier (PRD stage 4).

v1 mirrored the LangChain retriever shape so the real pipeline could be dropped
in without touching the orchestrator. This is that drop-in: BM25 over the corpus,
optionally fused with dense retrieval from a Chroma collection, and the
orchestrator above is unchanged.

LangChain stays confined to this tier's job -- index, embed, retrieve. It makes
no decision about which candidate governs, and the relevance figure it produces
decides nothing either: the float gate was removed in Phase 1B precisely because
a similarity score was standing in for a judgement. What retrieval owes the
reasoning tier is a candidate set that *contains* the governing rule, with its
confusable neighbours included on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass

from haven.config import THRESHOLDS
from haven.rag.backends import HybridRetrieval
from haven.rag.fusion import display_relevance
from haven.rag.vector_store import Candidate


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
    """Top-k retrieval over the procedure corpus.

    Returns ``Candidate`` objects, unchanged from v1, so the orchestrator, the
    audit trail and Zone 3 all keep working across the backend swap. What the
    fields now mean:

    ``relevance``  the fused rank expressed 0-1, for drawing a bar. Nothing
                   branches on it.
    ``lexical``    BM25's own score, so a reviewer can see the lexical view that
                   ranked a near-miss beside the rule it imitates.
    ``tag_match``  1.0 when the passage declares this task type.
    """

    def __init__(self) -> None:
        self.store = HybridRetrieval()

    @property
    def backend_name(self) -> str:
        return self.store.backend_name

    @property
    def degraded_reason(self) -> str:
        return self.store.degraded_reason

    def get_relevant_documents(self, query: SituationQuery, top_k: int | None = None) -> list[Candidate]:
        k = top_k or THRESHOLDS.retrieval_top_k
        fused, views = self.store.rank(query.to_text(), k)
        lexical_scores = views["bm25"].scores if "bm25" in views else {}

        candidates: list[Candidate] = []
        for entry in fused:
            passage = self.store.passage(entry.passage_id)
            candidates.append(
                Candidate(
                    passage=passage,
                    lexical=float(lexical_scores.get(entry.passage_id, 0.0)),
                    tag_match=1.0 if query.task_type in passage.task_types else 0.0,
                    criticality_match=1.0
                    if query.criticality in passage.applies_when.get("criticality_in", [query.criticality])
                    else 0.3,
                    relevance=round(display_relevance(entry, len(fused)), 4),
                    ranked_by=dict(entry.contributions),
                )
            )
        return candidates


_retriever: ProcedureRetriever | None = None


def get_retriever() -> ProcedureRetriever:
    global _retriever
    if _retriever is None:
        _retriever = ProcedureRetriever()
    return _retriever


def reset_retriever() -> None:
    """Drop the cached retriever. For tests that change the corpus or the mode."""
    global _retriever
    _retriever = None
