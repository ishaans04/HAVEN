"""Propose / dispose: the model reads prose, the checker decides.

v1's reasoning tier was a rules engine wearing a model's clothes. The SELECT
prompt carried each candidate's compiled ``applies_when`` and the mock evaluated
it with Python conditionals, so the "AI" was handed the answer key; and the gate
that produced HAVEN's headline refusal was a TF-IDF-derived float compared
against a configured threshold, which is a similarity score wearing a decision's
clothes.

What replaces both is asserted here:

  * the mock judges from passage text alone, and the corpus is written so that
    text is sufficient -- every near-miss states its own limit in plain language;
  * the deterministic checker reaches its own verdict on every candidate
    *before* the model is asked;
  * VERIFY disposes, and both directions of disagreement fail closed;
  * nothing anywhere branches on the relevance gate.

The stubs below force the branches a mock that happens to be right cannot reach.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

import haven
from haven import engine
from haven.api.main import UnavailableLLM
from haven.contracts import EvaluationRequest
from haven.data.scenarios import SCENARIOS
from haven.deterministic.preconditions import check
from haven.rag.corpus import BY_ID
from haven.reasoning.audit import AUDIT
from haven.reasoning.llm import MockGraniteLLM
from haven.reasoning.orchestrator import PROSE_KEYS, ReasoningFlow

ALL_SCENARIOS = [s.id for s in SCENARIOS]


def run(scenario_id: str, llm=None):
    scenario = next(s for s in SCENARIOS if s.id == scenario_id)
    request = EvaluationRequest.model_validate(scenario.build())
    if llm is None:
        llm = UnavailableLLM() if scenario_id == "provider_outage" else MockGraniteLLM()
    return engine.evaluate(request, llm=llm)


def situation_for(response, task_id: str):
    return next(s for s in response.situations if s.task == task_id)


def steps_of(situation) -> list[str]:
    return [e.step for e in AUDIT.get(situation.audit_ref).entries]


def entry(situation, step: str):
    return next(e for e in AUDIT.get(situation.audit_ref).entries if e.step == step)


def prose(*passage_ids: str) -> list[dict]:
    """A candidate payload redacted exactly as the flow redacts it."""
    return [{k: getattr(BY_ID[pid], k) for k in PROSE_KEYS} for pid in passage_ids]


BURN_FACTS: dict[str, Any] = {
    "crew_name": "R. Alvarez",
    "task_type": "orbital_burn",
    "criticality": "high",
    "phase": "execution",
    "alertness_score": 0.61,
    "alertness_threshold": 0.70,
    "workload_score": 58.0,
    "circadian_flag": False,
    "hours_awake": 15.0,
    "sleep_debt_h": 9.0,
    "kss": 6.0,
}


def select(facts: dict, *passage_ids: str) -> dict:
    return json.loads(MockGraniteLLM().complete("SELECT", "", {"facts": facts, "candidates": prose(*passage_ids)}))


# --------------------------------------------------------------------------
# 1. The mock reads prose
# --------------------------------------------------------------------------
def test_the_mock_selects_the_fatigue_rule_over_the_vehicle_state_near_miss() -> None:
    result = select(BURN_FACTS, "P-DCK-3.2", "P-FAT-4.2")
    assert result["governing_passage_id"] == "P-FAT-4.2"
    rejected = {r["passage_id"]: r["why"] for r in result["rejected"]}
    assert "vehicle state" in rejected["P-DCK-3.2"]


def test_the_mock_rejects_the_planning_phase_passage_from_its_own_text() -> None:
    """OPS-SLEEP-02 2.1 says "Sleep shifting is a planning activity". That
    sentence is the whole basis for rejecting it, and it is in the prose."""
    facts = {**BURN_FACTS, "task_type": "eva", "alertness_score": 0.55}
    result = select(facts, "P-SLP-2.1", "P-FAT-4.4")
    assert result["governing_passage_id"] == "P-FAT-4.4"
    rejected = {r["passage_id"]: r["why"] for r in result["rejected"]}
    assert "planning" in rejected["P-SLP-2.1"].lower()


def test_the_mock_rejects_a_passage_that_never_mentions_the_operator() -> None:
    facts = {**BURN_FACTS, "task_type": "robotics_capture", "circadian_flag": True}
    result = select(facts, "P-ROBO-9.1", "P-FAT-5.1")
    assert result["governing_passage_id"] == "P-FAT-5.1"
    rejected = {r["passage_id"]: r["why"] for r in result["rejected"]}
    assert "does not address operator" in rejected["P-ROBO-9.1"]


def test_the_mock_reports_none_when_no_candidate_addresses_this_situation() -> None:
    facts = {**BURN_FACTS, "task_type": "medical_contingency"}
    result = select(facts, "P-DCK-3.2", "P-EVA-11.3", "P-FAT-4.2")
    assert result["governing_passage_id"] is None
    assert len(result["rejected"]) == 3


def test_the_mock_recognises_an_operation_by_the_words_procedure_uses_for_it() -> None:
    """A rulebook does not say "orbital_burn". It says "propulsive manoeuvre"."""
    assert "orbital burn" not in BY_ID["P-FAT-4.2"].text.lower()
    assert select(BURN_FACTS, "P-FAT-4.2")["governing_passage_id"] == "P-FAT-4.2"


def test_the_mock_cannot_read_compiled_preconditions_because_it_is_not_given_any() -> None:
    """If the mock works without them, the redaction cannot silently regress."""
    candidates = prose("P-FAT-4.2")
    assert all(set(c) == set(PROSE_KEYS) for c in candidates)
    result = json.loads(MockGraniteLLM().complete("SELECT", "", {"facts": BURN_FACTS, "candidates": candidates}))
    assert result["governing_passage_id"] == "P-FAT-4.2"


def test_the_mock_is_fallible_and_the_checker_is_what_makes_that_safe() -> None:
    """The point of the exercise, stated as a test.

    Reading prose, "below the nominal execution threshold" names no number and
    "medium or high criticality" is not in the sentence the model is looking at.
    So the mock proposes a passage that the compiled rule excludes -- and that
    is *correct behaviour for a reader*. VERIFY is what makes it safe.
    """
    facts = {**BURN_FACTS, "criticality": "low", "alertness_score": 0.93}
    assert select(facts, "P-FAT-4.2")["governing_passage_id"] == "P-FAT-4.2"

    passage = BY_ID["P-FAT-4.2"]
    verdict = check(passage.applies_when, passage.prescribes, facts)
    assert not verdict.admissible
    assert {"criticality_in", "alertness_below"} <= {c.clause for c in verdict.unmet}


# --------------------------------------------------------------------------
# 2. S4 at the payload level: the redaction is one function, and it is exact
# --------------------------------------------------------------------------
def test_the_redacted_payload_is_exactly_the_prose_keys() -> None:
    full = {
        "passage_id": "P-FAT-4.2",
        "doc": "OPS-FATIGUE-04",
        "section": "4.2",
        "title": "t",
        "text": "x",
        "task_types": ["orbital_burn"],
        "applies_when": {"alertness_below": 0.7},
        "prescribes": "second_operator_verify",
        "relevance": 0.8,
        "lexical": 0.4,
        "near_miss_note": "note",
    }
    assert set(ReasoningFlow._payload_redacted(full)) == set(PROSE_KEYS)
    assert PROSE_KEYS == ("passage_id", "doc", "section", "title", "text")


# --------------------------------------------------------------------------
# 3. ADMISSIBILITY: an independent verdict, taken first, on every candidate
# --------------------------------------------------------------------------
@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_the_checker_judges_every_candidate_and_filters_none(scenario_id: str) -> None:
    """Filtering here would delete the discrimination case entirely.

    A near-miss is inadmissible by construction. Dropping the inadmissible
    candidates before SELECT would hand the model a pre-cleaned set and its
    "rejection" of the near-miss would be a tautology.
    """
    for situation in run(scenario_id).situations:
        if "ADMISSIBILITY" not in steps_of(situation):
            continue
        retrieved = {c["passage_id"] for c in entry(situation, "RETRIEVE").outputs["candidates"]}
        judged = set(entry(situation, "ADMISSIBILITY").outputs["clauses"])
        assert judged == retrieved
        assert len(retrieved) > 1


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_the_checker_speaks_before_the_model_and_disposes_after(scenario_id: str) -> None:
    for situation in run(scenario_id).situations:
        steps = steps_of(situation)
        if "SELECT" not in steps:
            continue
        assert steps.index("ADMISSIBILITY") < steps.index("SELECT") < steps.index("VERIFY")


def test_the_admissibility_entry_records_the_whole_verdict_not_only_failures() -> None:
    situation = situation_for(run("burn_fatigue"), "T-119")
    clauses = entry(situation, "ADMISSIBILITY").outputs["clauses"]["P-FAT-4.2"]
    assert [c["clause"] for c in clauses] == [
        "authority",
        "task_types",
        "criticality_in",
        "alertness_below",
    ]
    assert all(c["satisfied"] for c in clauses)


# --------------------------------------------------------------------------
# 4. VERIFY: the disposition table, all four rows
# --------------------------------------------------------------------------
class StubSelectLLM(MockGraniteLLM):
    """Forces a SELECT answer so VERIFY's branches can be exercised.

    A mock that happens to agree with the checker on all eight scenarios cannot
    demonstrate what happens when it does not, and "fails closed" is a claim
    about the disagreement.
    """

    def __init__(self, governing: str | None) -> None:
        self._governing = governing

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:
        if task == "SELECT":
            return json.dumps({"governing_passage_id": self._governing, "reason": "stubbed", "rejected": []})
        return super().complete(task, prompt, context)


def test_agreement_produces_a_recommendation_carrying_the_verified_clauses() -> None:
    situation = situation_for(run("burn_fatigue", StubSelectLLM("P-FAT-4.2")), "T-119")
    assert situation.outcome == "recommendation"
    assert situation.recommendation.citation.passage_id == "P-FAT-4.2"
    assert situation.recommendation.verified_clauses
    assert all(c.satisfied for c in situation.recommendation.verified_clauses)


def test_the_checker_rejects_an_inadmissible_selection_and_names_the_clause() -> None:
    """S6, direction one: the model proposes a planning-phase passage during
    execution. The checker disposes, and the refusal says which clause failed."""
    situation = situation_for(run("eva_near_miss", StubSelectLLM("P-SLP-2.1")), "T-140")
    assert situation.outcome == "refusal"
    assert situation.recommendation is None
    assert situation.refusal.reason == "precondition_unmet"
    assert situation.refusal.model_selected == "P-SLP-2.1"
    assert situation.refusal.checker_disagreed is True
    assert "phase" in [c.clause for c in situation.refusal.failed_clauses]
    assert "planning" in situation.refusal.explanation


def test_a_model_refusal_is_never_overridden_upward() -> None:
    """S6, direction two, and the one that matters most.

    A passage was admissible, but the model said none govern. HAVEN never
    promotes a passage the reasoning tier did not select -- a checker that could
    hand back a rule nobody read would be the same system with the tiers
    swapped, not a safer one.
    """
    situation = situation_for(run("burn_fatigue", StubSelectLLM(None)), "T-119")
    assert situation.outcome == "refusal"
    assert situation.recommendation is None
    assert situation.refusal.reason == "checker_model_disagreement"
    assert situation.refusal.checker_disagreed is True
    assert situation.refusal.model_selected is None
    # The checker did find something, said so, and was still not allowed to act.
    verify = entry(situation, "VERIFY")
    assert verify.inputs["checker_admissible"] == ["P-FAT-4.2"]
    assert "P-FAT-4.2" in situation.refusal.explanation


@pytest.mark.parametrize("hallucinated", ["P-HAT-5.2", "P-NOT-A-REAL-ID"])
def test_a_selection_outside_the_candidate_set_is_refused_structurally(hallucinated: str) -> None:
    """A real provider can emit an identifier it invented, including a real one
    that was never retrieved. Hard rule 3 has to hold by construction rather
    than by trusting the completion."""
    situation = situation_for(run("burn_fatigue", StubSelectLLM(hallucinated)), "T-119")
    assert situation.outcome == "refusal"
    assert situation.refusal.reason == "checker_model_disagreement"
    assert situation.refusal.model_selected == hallucinated
    assert situation.refusal.checker_disagreed is True


def test_both_tiers_finding_nothing_is_an_ordinary_refusal_not_a_disagreement() -> None:
    situation = situation_for(run("no_procedure"), "T-160")
    assert situation.refusal.reason == "no_governing_procedure"
    assert situation.refusal.checker_disagreed is False
    assert situation.refusal.failed_clauses == []


def test_the_verify_entry_is_written_on_every_path_through_the_reasoning_tier() -> None:
    for scenario_id in ALL_SCENARIOS:
        for situation in run(scenario_id).situations:
            steps = steps_of(situation)
            if "SELECT" in steps:
                assert "VERIFY" in steps, f"{scenario_id}: SELECT ran without a recorded disposition"


# --------------------------------------------------------------------------
# 5. The eva_near_miss regression, end to end
# --------------------------------------------------------------------------
def test_the_near_miss_is_retrieved_judged_inadmissible_and_not_cited() -> None:
    """The headline discrimination case, now with three independent checks.

    The near-miss must reach the candidate set (retrieval does not hide it), the
    checker must judge it rather than skip it, and the citation must still land
    on the rule that governs.
    """
    situation = situation_for(run("eva_near_miss"), "T-140")

    retrieved = [c["passage_id"] for c in entry(situation, "RETRIEVE").outputs["candidates"]]
    assert "P-SLP-2.1" in retrieved, "the near-miss must reach the candidate set"

    admissibility = entry(situation, "ADMISSIBILITY").outputs
    assert "P-SLP-2.1" in admissibility["clauses"], "the checker must judge the near-miss, not skip it"
    assert "P-SLP-2.1" not in admissibility["admissible"]
    unmet = [c["clause"] for c in admissibility["clauses"]["P-SLP-2.1"] if not c["satisfied"]]
    assert "phase" in unmet

    select_step = entry(situation, "SELECT")
    assert select_step.outputs["governing_passage_id"] == "P-FAT-4.4"
    rejected = {r["passage_id"]: r["why"] for r in select_step.outputs["rejected"]}
    assert "planning" in rejected["P-SLP-2.1"]

    assert situation.recommendation.citation.passage_id == "P-FAT-4.4"
    assert situation.recommendation.citation.doc == "OPS-FATIGUE-04"


# --------------------------------------------------------------------------
# 6. The float gate is gone from the decision path
# --------------------------------------------------------------------------
GATE_NAME = "relevance_gate"
HAVEN_SOURCES = sorted(Path(inspect.getfile(haven)).parent.rglob("*.py"))


def _mentions_gate(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr == GATE_NAME:
            return True
        if isinstance(child, ast.Name) and child.id == GATE_NAME:
            return True
    return False


def _gate_decisions(source: str) -> list[str]:
    """Every place a value named ``relevance_gate`` steers control flow.

    Only the *test* expression of a branch is inspected, never its body -- an
    ``if`` whose body happens to build a payload containing the gate is not a
    decision about the gate.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Compare):
            tests: list[ast.AST] = [node]
        elif isinstance(node, (ast.If, ast.IfExp, ast.While, ast.Assert)):
            tests = [node.test]
        else:
            continue
        found.extend(ast.dump(t)[:120] for t in tests if _mentions_gate(t))
    return found


def test_the_source_scan_actually_found_the_package() -> None:
    names = {p.name for p in HAVEN_SOURCES}
    assert {"config.py", "contracts.py", "engine.py"} <= names


@pytest.mark.parametrize("path", HAVEN_SOURCES, ids=lambda p: p.name)
def test_no_decision_branches_on_the_relevance_gate(path: Path) -> None:
    """The gate is display-only, and that has to be structural, not a habit.

    v1 compared a TF-IDF-derived similarity float against this threshold and
    called the comparison a decision about whether a rule applies. It is not one:
    similarity is a property of wording, and admissibility is a property of the
    rule. The threshold survives on the contract so the console can still show
    an operator what the closest candidate scored -- but nothing may read it and
    branch.
    """
    violations = _gate_decisions(path.read_text(encoding="utf-8"))
    assert not violations, f"{path.name} branches on {GATE_NAME}: {violations}"


def test_the_gate_probe_itself_fires() -> None:
    """A guard nobody has seen fail is not evidence of anything.

    This is v1's GATE step, verbatim in shape.
    """
    hostile = """
        passes = bool(governing_id) and judged_relevance >= THRESHOLDS.relevance_gate
        branch = "FUSE" if passes else "REFUSE"
        """
    assert _gate_decisions(inspect.cleandoc(hostile))
    # ... and a payload field carrying the same value is not a decision.
    assert not _gate_decisions('refusal = {"gate": THRESHOLDS.relevance_gate}')


def test_the_select_step_no_longer_reports_a_relevance_score() -> None:
    """The mock's ``+0.12`` fudge produced a number that looked like a judgement
    and was arithmetic on a similarity score. Nothing downstream may resurrect it."""
    situation = situation_for(run("burn_fatigue"), "T-119")
    outputs = entry(situation, "SELECT").outputs
    assert "relevance" not in outputs
    assert all("relevance" not in r for r in outputs["rejected"])
