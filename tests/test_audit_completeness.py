"""Every step the graph takes leaves a record, and the record matches the graph.

Phase 1A made the *sequence* of steps a property of a compiled object rather
than of the order of statements in a function (S9). This file closes the
matching gap on the other side: that the audit trail is a faithful account of
that sequence, and that a node cannot join the reasoning path without someone
deciding whether its work belongs in the record.

The enforcement is deliberately a test rather than a rewrite of the write path.
Each entry is written where its work happens, carrying detail only that step can
supply -- which candidates were retrieved, which clause failed, what the model
proposed. Hoisting those writes into a generic wrapper would buy a structural
guarantee at the cost of the detail that makes the trail worth reading. The
guarantee is what matters, so it is asserted here instead: the registry below
must account for every node in the compiled graph, and every scenario's trail
must match a legal path through it.
"""

from __future__ import annotations

import pytest

from haven.data.scenarios import SCENARIOS
from haven.graph.situation_graph import SITUATION_GRAPH
from haven.reasoning.audit import AUDIT
from tests.test_engine import run

ALL_SCENARIOS = [s.id for s in SCENARIOS]

# Every node of the situation graph, and the audit steps it may write.
#
# A committed decision, not a description. If a node appears in the graph and
# not here, `test_every_node_declares_whether_it_audits` fails, and whoever
# added it has to say whether its work belongs in the record.
NODE_STEPS: dict[str, tuple[str, ...]] = {
    # Writes TRIGGER as well as its own step: the deterministic scoring that
    # raised this Situation is recorded when the trail is opened, so a trail is
    # never missing the reason it exists.
    "CONFIDENCE": ("TRIGGER", "CONFIDENCE"),
    "WITHHOLD": ("WITHHOLD",),
    "RETRIEVE": ("RETRIEVE",),
    "ADMISSIBILITY": ("ADMISSIBILITY",),
    # DEGRADED replaces SELECT when the provider is unreachable, so the record
    # shows that no proposal was ever made rather than an empty one.
    "SELECT": ("SELECT", "DEGRADED"),
    "VERIFY": ("VERIFY",),
    "FUSE": ("FUSE",),
    "GENERATE": ("GENERATE",),
    "REFUSE": ("REFUSE",),
    # GENERATE_FALLBACK belongs to SCREEN: it is written when a deterministic
    # screen vetoes the primary action and the text is regenerated for the
    # fallback the same passage prescribes.
    "SCREEN": ("SCHEDULE_IMPACT", "GENERATE_FALLBACK"),
}

# Written by the API tier after the trail is sealed, when an operator records a
# decision. Never produced by the graph.
POST_HOC_STEPS = {"HUMAN_DECISION"}


def graph_nodes() -> set[str]:
    return {n for n in SITUATION_GRAPH.get_graph().nodes if not n.startswith("__")}


def topological_rank() -> dict[str, int]:
    """Rank nodes by distance from the start, for asserting step ordering."""
    graph = SITUATION_GRAPH.get_graph()
    successors: dict[str, list[str]] = {}
    for edge in graph.edges:
        successors.setdefault(edge.source, []).append(edge.target)

    rank: dict[str, int] = {}
    frontier, depth = ["__start__"], 0
    while frontier:
        following: list[str] = []
        for node in frontier:
            if node in rank:
                continue
            rank[node] = depth
            following.extend(successors.get(node, []))
        frontier, depth = following, depth + 1
    return rank


def step_owner() -> dict[str, str]:
    owners: dict[str, str] = {}
    for node, steps in NODE_STEPS.items():
        for step in steps:
            owners.setdefault(step, node)
    return owners


# --------------------------------------------------------------------------
# The registry must account for the graph
# --------------------------------------------------------------------------
def test_every_node_declares_whether_it_audits() -> None:
    """Adding a node to the reasoning path forces that decision."""
    assert graph_nodes() == set(NODE_STEPS), (
        "the situation graph and the audit registry disagree; a node was added or removed "
        "without deciding what it records"
    )


def test_no_declared_step_is_orphaned() -> None:
    """Every step the registry promises must actually be produced."""
    produced: set[str] = set()
    for scenario_id in ALL_SCENARIOS:
        for situation in run(scenario_id).situations:
            produced.update(e.step for e in AUDIT.get(situation.audit_ref).entries)

    declared = {step for steps in NODE_STEPS.values() for step in steps}
    assert produced <= declared, f"undeclared steps appeared: {sorted(produced - declared)}"
    assert not declared - produced, f"declared but never produced: {sorted(declared - produced)}"


# --------------------------------------------------------------------------
# The trail must match a legal path through the graph
# --------------------------------------------------------------------------
@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_every_audited_step_belongs_to_a_node_on_the_path(scenario_id: str) -> None:
    owners = step_owner()
    for situation in run(scenario_id).situations:
        for entry in AUDIT.get(situation.audit_ref).entries:
            assert entry.step in owners or entry.step in POST_HOC_STEPS, (
                f"{entry.step} was written by nothing the graph declares"
            )


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_steps_appear_in_graph_order(scenario_id: str) -> None:
    """A trail that reordered the flow would misrepresent what happened."""
    rank, owners = topological_rank(), step_owner()

    for situation in run(scenario_id).situations:
        steps = [e.step for e in AUDIT.get(situation.audit_ref).entries if e.step not in POST_HOC_STEPS]
        ranks = [rank[owners[s]] for s in steps]
        assert ranks == sorted(ranks), f"{scenario_id}: audit order {steps} contradicts the graph"


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_the_trail_has_no_gaps(scenario_id: str) -> None:
    """Contiguous from one, so a missing step cannot hide as absence."""
    for situation in run(scenario_id).situations:
        entries = AUDIT.get(situation.audit_ref).entries
        assert entries, "a raised Situation must never produce an empty trail"
        assert [e.seq for e in entries] == list(range(1, len(entries) + 1))


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_every_raised_situation_records_why_it_was_raised(scenario_id: str) -> None:
    """TRIGGER first, always: a trail must carry the reason it exists."""
    for situation in run(scenario_id).situations:
        entries = AUDIT.get(situation.audit_ref).entries
        assert entries[0].step == "TRIGGER"
        assert entries[1].step == "CONFIDENCE"


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_a_withheld_situation_never_reaches_the_reasoning_tier(scenario_id: str) -> None:
    """The confidence gate runs before a provider is consulted, not after."""
    for situation in run(scenario_id).situations:
        steps = [e.step for e in AUDIT.get(situation.audit_ref).entries]
        if "WITHHOLD" not in steps:
            continue
        assert steps == ["TRIGGER", "CONFIDENCE", "WITHHOLD"], (
            "withholding must terminate the flow, not merely annotate it"
        )
