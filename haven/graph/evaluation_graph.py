"""The seven-stage evaluation cycle (PRD section 4) as a compiled state machine.

    INGEST -> SCORE -> TRIGGER -> SITUATIONS -> PRESENT

Stages 4, 5 and 6 live inside SITUATIONS, which runs the situation graph once
per raised Situation.

This is a state machine, not an agent, and the distinction is the whole point:
the step sequence is fixed at compile time and can be read off the compiled
object. No model chooses what happens next, nothing loops, and nothing can be
skipped. ``tests/test_graph_topology.py`` asserts exactly that against this
graph, so a later change that made the control flow model-driven would fail a
test rather than pass unnoticed.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from haven.graph.nodes.ingest import ingest_node
from haven.graph.nodes.present import present_node
from haven.graph.nodes.score import score_node
from haven.graph.nodes.situations import situations_node
from haven.graph.nodes.trigger import trigger_node
from haven.graph.state import HavenState


def build_evaluation_graph() -> StateGraph:
    graph = StateGraph(HavenState)

    graph.add_node("INGEST", ingest_node)
    graph.add_node("SCORE", score_node)
    graph.add_node("TRIGGER", trigger_node)
    graph.add_node("SITUATIONS", situations_node)
    graph.add_node("PRESENT", present_node)

    # Unconditional throughout: every evaluation runs every stage, in this
    # order. A run with no raised Situation still passes through SITUATIONS and
    # still reports its tier status.
    graph.add_edge(START, "INGEST")
    graph.add_edge("INGEST", "SCORE")
    graph.add_edge("SCORE", "TRIGGER")
    graph.add_edge("TRIGGER", "SITUATIONS")
    graph.add_edge("SITUATIONS", "PRESENT")
    graph.add_edge("PRESENT", END)

    return graph


# Compiled once, at import; see ``situation_graph`` for why there is no
# checkpointer.
EVALUATION_GRAPH = build_evaluation_graph().compile()
