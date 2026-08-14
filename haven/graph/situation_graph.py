"""The per-Situation graph, from the input-sufficiency gate to a sealed record.

    CONFIDENCE -> RETRIEVE -> ADMISSIBILITY -> SELECT -> VERIFY -> FUSE -> GENERATE -> SCREEN
         |                                                   |                            |
         +-> WITHHOLD -> END                                 +-> REFUSE ------------------+

Two branches, and both are decided by deterministic code that has already
written its reasoning to the audit trail:

  * **CONFIDENCE** -- an input too thin to model alertness routes to WITHHOLD and
    terminates there, without retrieval and without the reasoning tier ever
    being reached.
  * **VERIFY** -- the model's proposed passage is checked against the compiled
    rule. Confirmed, it is written up. Anything else -- an unsatisfied
    precondition, a disagreement in either direction, an identifier that was
    never in the candidate set -- becomes a structured escalation.

Both terminal paths converge on SCREEN, which applies the schedule-impact veto
to a recommendation, passes a refusal through untouched, and seals the trail.
One exit means the closing sequence cannot drift between the two.

The topology is fixed and acyclic. There is no step the reasoning tier can add,
skip, or repeat -- that fixed sequence is the safety property, and
``tests/test_graph_topology.py`` asserts it against this compiled graph.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from haven.graph.nodes.admissibility import admissibility_node
from haven.graph.nodes.confidence import confidence_node, route_after_confidence
from haven.graph.nodes.fuse import fuse_node
from haven.graph.nodes.generate import generate_node
from haven.graph.nodes.refuse import refuse_node
from haven.graph.nodes.retrieve import retrieve_node
from haven.graph.nodes.screen import screen_node
from haven.graph.nodes.select import select_node
from haven.graph.nodes.verify import route_after_verify, verify_node
from haven.graph.nodes.withhold import withhold_node
from haven.graph.state import SituationState


def build_situation_graph() -> StateGraph:
    graph = StateGraph(SituationState)

    graph.add_node("CONFIDENCE", confidence_node)
    graph.add_node("WITHHOLD", withhold_node)
    graph.add_node("RETRIEVE", retrieve_node)
    graph.add_node("ADMISSIBILITY", admissibility_node)
    graph.add_node("SELECT", select_node)
    graph.add_node("VERIFY", verify_node)
    graph.add_node("FUSE", fuse_node)
    graph.add_node("GENERATE", generate_node)
    graph.add_node("REFUSE", refuse_node)
    graph.add_node("SCREEN", screen_node)

    graph.add_edge(START, "CONFIDENCE")
    # Branch 1: is the input good enough to reason about at all?
    graph.add_conditional_edges(
        "CONFIDENCE",
        route_after_confidence,
        {"WITHHOLD": "WITHHOLD", "RETRIEVE": "RETRIEVE"},
    )
    graph.add_edge("RETRIEVE", "ADMISSIBILITY")
    graph.add_edge("ADMISSIBILITY", "SELECT")
    graph.add_edge("SELECT", "VERIFY")
    # Branch 2: did the checker confirm what the model proposed?
    graph.add_conditional_edges(
        "VERIFY",
        route_after_verify,
        {"FUSE": "FUSE", "REFUSE": "REFUSE"},
    )
    graph.add_edge("FUSE", "GENERATE")
    graph.add_edge("GENERATE", "SCREEN")
    graph.add_edge("REFUSE", "SCREEN")
    graph.add_edge("SCREEN", END)
    graph.add_edge("WITHHOLD", END)

    return graph


# Compiled once, at import. The graph is a static artefact of the program, not
# something rebuilt per request; no checkpointer, because HAVEN's audit ledger
# is the system of record and graph state is deliberately not persisted.
SITUATION_GRAPH = build_situation_graph().compile()
