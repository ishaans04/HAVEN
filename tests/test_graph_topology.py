"""S9: the graph must be provably static.

HAVEN is a state machine, not an agent, and that is the safety property -- the
step sequence is fixed, auditable, and identical on every run. An agent that
could choose its own next step could choose to skip the confidence gate, or the
schedule-impact screen, or the audit write between them.

So the shape is asserted against the *compiled* graphs rather than against the
builder source: node set, edge set, absence of model-directed routing, absence
of any prebuilt agent node, and acyclicity. The node and edge sets are committed
literals. They are meant to be annoying to change -- a diff to one of them is a
change to the audited sequence of a safety decision, and should be read as such
in review.

The two ``*_probe_itself_fires`` tests exist because a guard nobody has seen
fail is not evidence of anything.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import haven.graph
from haven.graph import EVALUATION_GRAPH, SITUATION_GRAPH
from haven.reasoning.llm import ReasoningLLM
from haven.reasoning.orchestrator import ReasoningFlow

GRAPH_PACKAGE = Path(inspect.getfile(haven.graph)).parent

GRAPHS = {"evaluation": EVALUATION_GRAPH, "situation": SITUATION_GRAPH}


# --------------------------------------------------------------------------
# 1 + 2: the committed topology
# --------------------------------------------------------------------------
EVALUATION_NODES = {"__start__", "INGEST", "SCORE", "TRIGGER", "SITUATIONS", "PRESENT", "__end__"}

# (source, target, conditional). The flag is part of the snapshot: turning an
# unconditional edge into a routed one is exactly the change this must catch.
EVALUATION_EDGES = {
    ("__start__", "INGEST", False),
    ("INGEST", "SCORE", False),
    ("SCORE", "TRIGGER", False),
    ("TRIGGER", "SITUATIONS", False),
    ("SITUATIONS", "PRESENT", False),
    ("PRESENT", "__end__", False),
}

SITUATION_NODES = {
    "__start__",
    "CONFIDENCE",
    "WITHHOLD",
    "RETRIEVE",
    "ADMISSIBILITY",
    "SELECT",
    "VERIFY",
    "FUSE",
    "GENERATE",
    "REFUSE",
    "SCREEN",
    "__end__",
}

SITUATION_EDGES = {
    ("__start__", "CONFIDENCE", False),
    # Branch 1: is the input good enough to reason about at all?
    ("CONFIDENCE", "WITHHOLD", True),
    ("CONFIDENCE", "RETRIEVE", True),
    ("RETRIEVE", "ADMISSIBILITY", False),
    ("ADMISSIBILITY", "SELECT", False),
    ("SELECT", "VERIFY", False),
    # Branch 2: did the deterministic checker confirm what the model proposed?
    # The model proposes; this edge is where the checker disposes.
    ("VERIFY", "FUSE", True),
    ("VERIFY", "REFUSE", True),
    ("FUSE", "GENERATE", False),
    ("GENERATE", "SCREEN", False),
    ("REFUSE", "SCREEN", False),
    ("SCREEN", "__end__", False),
    ("WITHHOLD", "__end__", False),
}

EXPECTED = {
    "evaluation": (EVALUATION_NODES, EVALUATION_EDGES),
    "situation": (SITUATION_NODES, SITUATION_EDGES),
}


def _nodes(compiled) -> set[str]:
    return set(compiled.get_graph().nodes)


def _edges(compiled) -> set[tuple[str, str, bool]]:
    return {(e.source, e.target, bool(e.conditional)) for e in compiled.get_graph().edges}


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_node_set_matches_the_committed_snapshot(name: str) -> None:
    assert _nodes(GRAPHS[name]) == EXPECTED[name][0]


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_edge_set_matches_the_committed_snapshot(name: str) -> None:
    assert _edges(GRAPHS[name]) == EXPECTED[name][1]


def test_the_withhold_branch_bypasses_retrieval_and_reasoning() -> None:
    """The confidence gate's refusal path must not touch the reasoning tier.

    Asserted on the topology as well as on behaviour: WITHHOLD is reachable only
    from CONFIDENCE, and leads only to the end of the graph.
    """
    edges = _edges(SITUATION_GRAPH)
    into = {source for source, target, _ in edges if target == "WITHHOLD"}
    out_of = {target for source, target, _ in edges if source == "WITHHOLD"}
    assert into == {"CONFIDENCE"}
    assert out_of == {"__end__"}


def test_operator_facing_prose_is_reachable_only_through_verification() -> None:
    """The propose/dispose invariant, asserted on the topology.

    FUSE and GENERATE are the two nodes that write text an operator will read
    and act on. Neither may be reached except through VERIFY, and the refusal
    branch may not double back into them -- otherwise a selection the checker
    rejected could still be written up, and the check would be advisory.
    """
    edges = _edges(SITUATION_GRAPH)
    assert {source for source, target, _ in edges if target == "FUSE"} == {"VERIFY"}
    assert {source for source, target, _ in edges if target == "GENERATE"} == {"FUSE"}
    assert {source for source, target, _ in edges if target == "REFUSE"} == {"VERIFY"}
    assert {target for source, target, _ in edges if source == "REFUSE"} == {"SCREEN"}


def test_the_checker_runs_before_the_reasoning_tier_is_consulted() -> None:
    """ADMISSIBILITY is upstream of SELECT, on every path that reaches SELECT.

    Committed as topology rather than left to node code: the checker's verdict
    has to be a position taken independently and *first*, or "the checker
    agreed" means only that it was asked afterwards.
    """
    edges = _edges(SITUATION_GRAPH)
    assert {source for source, target, _ in edges if target == "SELECT"} == {"ADMISSIBILITY"}
    assert {source for source, target, _ in edges if target == "ADMISSIBILITY"} == {"RETRIEVE"}
    assert {source for source, target, _ in edges if target == "VERIFY"} == {"SELECT"}


# --------------------------------------------------------------------------
# 3: no conditional-edge router may consult a provider
# --------------------------------------------------------------------------
# Committed inventory of every routed decision in the system: (graph, source
# node, router function). Adding a conditional edge anywhere fails this before
# any of the content checks below run, which is the point -- a new route into
# the control flow gets read by a human.
ROUTERS = {
    ("situation", "CONFIDENCE", "route_after_confidence"),
    ("situation", "VERIFY", "route_after_verify"),
}

# Matched against lowercased source, so provider class names (ReasoningLLM,
# MockGraniteLLM, WatsonxGraniteLLM, UnavailableLLM, ...) are all covered by
# "llm", and `build_llm` with them.
FORBIDDEN_SOURCE_FRAGMENTS = (
    "llm",
    "complete(",
    ".invoke(",
    ".run(",
    "reasoningflow",
    "retriever",
    "get_relevant_documents",
)

# A router may not import the reasoning or retrieval tiers at all, directly or
# through a provider SDK.
FORBIDDEN_IMPORT_PREFIXES = (
    "haven.reasoning.llm",
    "haven.reasoning.orchestrator",
    "haven.rag",
    "langchain_ollama",
    "langchain_ibm",
    "langchain_openai",
    "httpx",
    "openai",
)

FORBIDDEN_IMPORT_NAMES = {"build_llm", "ReasoningFlow", "get_retriever", "ReasoningLLM"}


def _routers() -> list[tuple[str, str, Any]]:
    """Every conditional-edge router, read off the compiled graphs."""
    found: list[tuple[str, str, Any]] = []
    for name, compiled in GRAPHS.items():
        for source, branches in compiled.builder.branches.items():
            for spec in branches.values():
                fn = getattr(spec.path, "func", None)
                assert fn is not None, f"{name}/{source}: router is not a plain function; cannot be inspected"
                found.append((name, source, fn))
    return found


def _source_violations(source: str) -> list[str]:
    lowered = source.lower()
    return [fragment for fragment in FORBIDDEN_SOURCE_FRAGMENTS if fragment in lowered]


def _import_violations(source: str) -> list[str]:
    bad: list[str] = []
    for node in ast.walk(ast.parse(textwrap.dedent(source))):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
            names = [alias.asname or alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
            names = [alias.name for alias in node.names]
        else:
            continue
        for module in modules:
            if any(module == p or module.startswith(p + ".") for p in FORBIDDEN_IMPORT_PREFIXES):
                bad.append(f"imports {module}")
        for imported in names:
            if imported in FORBIDDEN_IMPORT_NAMES or "llm" in imported.lower():
                bad.append(f"imports the name {imported}")
    return bad


def _namespace_violations(module: ModuleType) -> list[str]:
    """Anything provider-shaped already bound in the router's module globals."""
    bad: list[str] = []
    for name, value in vars(module).items():
        if name.startswith("__"):
            continue
        if isinstance(value, ReasoningLLM):
            bad.append(f"{name} is a provider instance")
        if isinstance(value, type) and issubclass(value, (ReasoningLLM, ReasoningFlow)):
            bad.append(f"{name} is a provider class")
        if callable(value) and getattr(value, "__module__", "").startswith(FORBIDDEN_IMPORT_PREFIXES):
            bad.append(f"{name} comes from {value.__module__}")
    return bad


def test_the_router_inventory_is_exactly_the_committed_one() -> None:
    assert {(graph, source, fn.__name__) for graph, source, fn in _routers()} == ROUTERS


def test_no_router_source_references_a_provider() -> None:
    for graph, source, fn in _routers():
        violations = _source_violations(inspect.getsource(fn))
        assert not violations, f"{graph}/{source}: router {fn.__name__} references {violations}"


def test_no_router_module_imports_a_provider() -> None:
    for graph, source, fn in _routers():
        module = inspect.getmodule(fn)
        assert module is not None
        violations = _import_violations(inspect.getsource(module))
        assert not violations, f"{graph}/{source}: {module.__name__} {violations}"


def test_no_router_module_has_a_provider_in_its_namespace() -> None:
    for graph, source, fn in _routers():
        module = inspect.getmodule(fn)
        assert module is not None
        violations = _namespace_violations(module)
        assert not violations, f"{graph}/{source}: {module.__name__} {violations}"


def test_the_router_probe_itself_fires() -> None:
    """A router that consulted a model must be caught by both checks."""
    hostile = """
        from haven.reasoning.llm import build_llm

        def route(state):
            llm = build_llm()
            return llm.complete("SELECT", "which way?", {}).strip()
        """
    assert _source_violations(hostile)
    assert _import_violations(hostile)


# --------------------------------------------------------------------------
# 4: no prebuilt agent, no tool node
# --------------------------------------------------------------------------
PREBUILT_MARKERS = (
    "langgraph.prebuilt",
    "ToolNode",
    "tools_condition",
    "create_react_agent",
    "create_agent",
    "ToolExecutor",
    "bind_tools",
)

GRAPH_MODULE_SOURCES = sorted(GRAPH_PACKAGE.rglob("*.py"))


def test_the_graph_package_was_actually_found() -> None:
    """Guards the two file-scanning tests below against scanning nothing."""
    names = {path.name for path in GRAPH_MODULE_SOURCES}
    assert {"evaluation_graph.py", "situation_graph.py", "state.py"} <= names


@pytest.mark.parametrize("path", GRAPH_MODULE_SOURCES, ids=lambda p: p.name)
def test_no_graph_module_mentions_a_prebuilt_agent(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    found = [marker for marker in PREBUILT_MARKERS if marker in source]
    assert not found, f"{path.name} mentions {found}"


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_every_node_is_havens_own_code(name: str) -> None:
    """No node may be a prebuilt agent or tool executor supplied by the library."""
    for node_id, node in GRAPHS[name].get_graph().nodes.items():
        if node_id in ("__start__", "__end__"):
            continue
        assert type(node.data).__name__ != "ToolNode", f"{name}/{node_id} is a ToolNode"
        fn = getattr(node.data, "func", None)
        assert fn is not None, f"{name}/{node_id} is not a plain function node"
        assert fn.__module__.startswith("haven.graph.nodes"), (
            f"{name}/{node_id} is implemented by {fn.__module__}, not by HAVEN"
        )


# --------------------------------------------------------------------------
# 5: acyclic, so no unbounded loop exists
# --------------------------------------------------------------------------
def _reachable(edges: set[tuple[str, str, bool]], start: str) -> set[str]:
    seen: set[str] = set()
    stack = [target for source, target, _ in edges if source == start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(target for source, target, _ in edges if source == node)
    return seen


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_no_node_is_reachable_from_itself(name: str) -> None:
    edges = _edges(GRAPHS[name])
    for node in _nodes(GRAPHS[name]):
        assert node not in _reachable(edges, node), f"{name}: {node} is reachable from itself"


def test_the_cycle_probe_itself_fires() -> None:
    cyclic = {("A", "B", False), ("B", "A", False)}
    assert "A" in _reachable(cyclic, "A")
