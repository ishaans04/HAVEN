"""The three hard rules from PRD section 6.1, as executable tests.

These are the tests that matter. If one of them fails, the system is unsafe
regardless of how well anything else works.
"""

from __future__ import annotations

import re

import pytest

from app import engine
from app.config import THRESHOLDS
from app.contracts import EvaluationRequest
from app.data.scenarios import SCENARIOS
from app.main import UnavailableLLM
from app.reasoning.audit import AUDIT
from app.reasoning.llm import MockGraniteLLM, NumericIntegrityError, assert_no_novel_numbers

NUMBER = re.compile(r"\d+(?:\.\d+)?")


def run(scenario_id: str):
    scenario = next(s for s in SCENARIOS if s.id == scenario_id)
    request = EvaluationRequest.model_validate(scenario.build())
    llm = UnavailableLLM() if scenario_id == "provider_outage" else MockGraniteLLM()
    return engine.evaluate(request, llm=llm)


ALL_SCENARIOS = [s.id for s in SCENARIOS]


# --------------------------------------------------------------------------
# Hard rule 1: numbers are computed, never generated
# --------------------------------------------------------------------------
@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_no_number_in_generated_text_originates_from_the_model(scenario_id: str) -> None:
    """Every numeral in operator-facing text must trace to the deterministic tier."""
    response = run(scenario_id)
    for situation in response.situations:
        if not situation.recommendation:
            continue
        trail = AUDIT.get(situation.audit_ref)
        assert trail is not None

        # The fact set the reasoning tier was given, plus the cited passage.
        supplied: set[str] = set()
        for entry in trail.entries:
            if entry.step in ("TRIGGER", "CONFIDENCE"):
                supplied |= set(NUMBER.findall(str(entry.outputs)))
            if entry.step == "SELECT":
                supplied |= set(NUMBER.findall(str(entry.inputs.get("prompt", ""))))
        supplied |= set(NUMBER.findall(situation.recommendation.citation.doc))
        supplied |= set(NUMBER.findall(situation.recommendation.citation.section))

        for found in NUMBER.findall(situation.recommendation.rationale):
            assert found in supplied, (
                f"{situation.situation_id}: recommendation contains {found!r}, which was never "
                f"supplied by the deterministic tier"
            )


def test_numeric_guard_rejects_an_invented_figure() -> None:
    """The guard itself must actually fire -- not just be present."""
    with pytest.raises(NumericIntegrityError):
        assert_no_novel_numbers("Alertness is 0.42 and rest for 90 minutes.", {"0.42"})


def test_numeric_guard_accepts_only_supplied_figures() -> None:
    assert_no_novel_numbers("Alertness is 0.42.", {"0.42", "4"})


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_safety_numbers_come_from_the_deterministic_tier(scenario_id: str) -> None:
    """Scores in the response must equal what the deterministic tier logged."""
    response = run(scenario_id)
    for situation in response.situations:
        trail = AUDIT.get(situation.audit_ref)
        trigger = next((e for e in trail.entries if e.step == "TRIGGER"), None)
        if trigger is None:
            continue
        assert situation.alertness_score == trigger.outputs["alertness_score"]
        assert situation.workload_score == trigger.outputs["workload_score"]
        assert situation.circadian_flag == trigger.outputs["circadian_flag"]


# --------------------------------------------------------------------------
# Hard rule 2: HAVEN flags risk; it never decides or acts
# --------------------------------------------------------------------------
@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_output_is_always_a_recommendation_or_a_refusal(scenario_id: str) -> None:
    response = run(scenario_id)
    for situation in response.situations:
        assert situation.outcome in ("recommendation", "refusal")
        # Exactly one is populated; there is no third, self-actioning state.
        assert (situation.recommendation is None) != (situation.refusal is None)


def test_no_decision_is_recorded_without_a_human() -> None:
    """Decisions exist only where an operator supplied one."""
    run("burn_fatigue")
    assert AUDIT.decisions() == [] or all(d["operator"] for d in AUDIT.decisions())


# --------------------------------------------------------------------------
# Hard rule 3: no citation, no recommendation
# --------------------------------------------------------------------------
@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_every_recommendation_carries_a_resolvable_citation(scenario_id: str) -> None:
    from app.retrieval.corpus import BY_ID

    response = run(scenario_id)
    for situation in response.situations:
        if situation.recommendation is None:
            continue
        citation = situation.recommendation.citation
        assert citation.passage_id in BY_ID, f"{citation.passage_id} does not resolve in the corpus"
        passage = BY_ID[citation.passage_id]
        assert citation.doc == passage.doc
        assert citation.section == passage.section


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_refusals_record_what_was_searched(scenario_id: str) -> None:
    """A refusal is auditable, not silent."""
    response = run(scenario_id)
    for situation in response.situations:
        if situation.refusal is None:
            continue
        refusal = situation.refusal
        assert refusal.escalate_to
        assert refusal.explanation
        if refusal.reason == "no_governing_procedure":
            assert refusal.searched, "a procedure refusal must record the searched set"
            if refusal.best_candidate:
                assert refusal.best_candidate.relevance < THRESHOLDS.relevance_gate
