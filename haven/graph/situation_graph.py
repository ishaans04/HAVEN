"""The per-Situation graph: CONFIDENCE -> RETRIEVE -> REASON -> SCREEN.

One raised Situation, from the input-sufficiency gate to a ``Situation`` payload
and a sealed audit trail. The single branch is at the gate: an input too thin to
model alertness routes to WITHHOLD and terminates there, without retrieval and
without the reasoning tier ever being reached.

The topology is fixed and acyclic. There is no step the reasoning tier can add,
skip, or repeat -- that fixed sequence is the safety property, and
``tests/test_graph_topology.py`` asserts it against this compiled graph.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from haven.graph.nodes.confidence import confidence_node, route_after_confidence
from haven.graph.nodes.reason import reason_node
from haven.graph.nodes.retrieve import retrieve_node
from haven.graph.nodes.screen import screen_node
from haven.graph.nodes.withhold import withhold_node
from haven.graph.state import SituationState


def build_situation_graph() -> StateGraph:
    graph = StateGraph(SituationState)

    graph.add_node("CONFIDENCE", confidence_node)
    graph.add_node("WITHHOLD", withhold_node)
    graph.add_node("RETRIEVE", retrieve_node)
    graph.add_node("REASON", reason_node)
    graph.add_node("SCREEN", screen_node)

    graph.add_edge(START, "CONFIDENCE")
    # The only branch in the graph, and it is decided by a deterministic screen
    # that has already been written to the audit trail.
    graph.add_conditional_edges(
        "CONFIDENCE",
        route_after_confidence,
        {"WITHHOLD": "WITHHOLD", "RETRIEVE": "RETRIEVE"},
    )
    graph.add_edge("RETRIEVE", "REASON")
    graph.add_edge("REASON", "SCREEN")
    graph.add_edge("SCREEN", END)
    graph.add_edge("WITHHOLD", END)

    return graph


# Compiled once, at import. The graph is a static artefact of the program, not
# something rebuilt per request; no checkpointer, because HAVEN's audit ledger
# is the system of record and graph state is deliberately not persisted.
SITUATION_GRAPH = build_situation_graph().compile()
