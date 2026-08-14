"""The seven-stage evaluation cycle (PRD section 4).

  1 ingest -> 2 score -> 3 trigger -> 4 retrieve -> 5 reason -> 6 screen -> 7 present

The cycle itself is a compiled LangGraph state machine and lives in
``haven.graph``; stages 4-6 run in the per-Situation graph nested inside stage 3's
successor. What remains here is the entry point: bind the reasoning and retrieval
adapters for this run, invoke the graph, and hand back the payload the UI renders.

Binding the adapters here rather than inside a node is deliberate. The graph then
constructs no provider of its own, which is what lets the topology tests assert
that nothing on the control path can reach one.
"""

from __future__ import annotations

from haven.contracts import EvaluationRequest, EvaluationResponse
from haven.graph import EVALUATION_GRAPH
from haven.rag.retriever import get_retriever
from haven.reasoning.llm import ReasoningLLM, build_llm


def evaluate(request: EvaluationRequest, llm: ReasoningLLM | None = None) -> EvaluationResponse:
    final = EVALUATION_GRAPH.invoke(
        {
            "request": request,
            "llm": llm or build_llm(),
            "retriever": get_retriever(),
        }
    )
    return final["response"]
