"""The hard rules, as executable tests.

S1-S3 are PRD section 6.1 and date from v1. S4-S6 arrive with propose/dispose
and are asserted at the bottom of this file.

These are the tests that matter. If one of them fails, the system is unsafe
regardless of how well anything else works.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

import pytest

from haven import engine
from haven.api.main import UnavailableLLM
from haven.config import THRESHOLDS
from haven.contracts import EvaluationRequest
from haven.data.scenarios import SCENARIOS
from haven.deterministic.preconditions import check
from haven.rag.corpus import BY_ID, CORPUS
from haven.reasoning.audit import AUDIT
from haven.reasoning.llm import (
    MockGraniteLLM,
    NumericIntegrityError,
    ReasoningLLM,
    assert_no_novel_numbers,
)
from haven.reasoning.orchestrator import PROSE_KEYS

NUMBER = re.compile(r"\d+(?:\.\d+)?")


def build_llm_for(scenario_id: str) -> ReasoningLLM:
    return UnavailableLLM() if scenario_id == "provider_outage" else MockGraniteLLM()


def run(scenario_id: str):
    scenario = next(s for s in SCENARIOS if s.id == scenario_id)
    request = EvaluationRequest.model_validate(scenario.build())
    return engine.evaluate(request, llm=build_llm_for(scenario_id))


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
    from haven.rag.corpus import BY_ID

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


# --------------------------------------------------------------------------
# S4: the reasoning tier never receives compiled preconditions
#
# The moment a model can see ``applies_when``, it stops reading procedure prose
# and starts pattern-matching an answer key -- which is precisely the behaviour
# v2 exists to remove, and a skill that would transfer to no real procedure
# library. This is also the invariant most easily lost in a later refactor: the
# leak is a one-word change at a call site and nothing else fails. So it is
# asserted three ways -- on what the provider was actually handed, on the
# rendered prompt in the sealed audit trail, and on the shape of the payload.
# --------------------------------------------------------------------------
# Withheld from every provider prompt. ``phase`` is a clause name too, but it is
# also a legitimate deterministic fact ("phase": "execution") that the model is
# meant to reason with, so it is not in this list; the payload-shape assertion
# below is what covers it.
REDACTED_KEYS = (
    "applies_when",
    "prescribes",
    "near_miss_note",
    "task_types",
    "criticality_in",
    "alertness_below",
    "requires_circadian_flag",
    "workload_above",
)

NEAR_MISS_NOTES = tuple(p.near_miss_note for p in CORPUS if p.near_miss_note)


class RecordingLLM(ReasoningLLM):
    """Wraps a provider and keeps every call it was handed, verbatim.

    Asserting on the audit trail alone would not be enough: the trail records
    the *prompt*, and the mock is handed a structured ``context`` beside it.
    v1's mock read its answer key from exactly that second channel while the
    prompt looked clean, so both are captured here.
    """

    def __init__(self, inner: ReasoningLLM) -> None:
        self.inner = inner
        self.calls: list[dict[str, Any]] = []

    @property
    def provider(self) -> str:  # type: ignore[override]
        return self.inner.provider

    @property
    def model_id(self) -> str:
        return self.inner.model_id

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:
        self.calls.append({"task": task, "prompt": prompt, "context": copy.deepcopy(context)})
        return self.inner.complete(task, prompt, context)


def run_recorded(scenario_id: str) -> tuple[Any, RecordingLLM]:
    scenario = next(s for s in SCENARIOS if s.id == scenario_id)
    request = EvaluationRequest.model_validate(scenario.build())
    recorder = RecordingLLM(build_llm_for(scenario_id))
    return engine.evaluate(request, llm=recorder), recorder


def leaks(blob: str) -> list[str]:
    return [key for key in REDACTED_KEYS if key in blob] + [n for n in NEAR_MISS_NOTES if n and n in blob]


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_no_compiled_precondition_reaches_a_provider_by_any_path(scenario_id: str) -> None:
    """S4, asserted on what the provider was actually given -- prompt and context."""
    _, recorder = run_recorded(scenario_id)
    for call in recorder.calls:
        assert not leaks(call["prompt"]), f"{scenario_id}/{call['task']}: prompt leaked {leaks(call['prompt'])}"
        blob = json.dumps(call["context"], default=str)
        assert not leaks(blob), f"{scenario_id}/{call['task']}: context leaked {leaks(blob)}"


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_no_compiled_precondition_appears_in_a_recorded_reasoning_prompt(scenario_id: str) -> None:
    """S4 again, from the sealed audit trail rather than from an injected spy.

    A refactor that stopped routing prompts through the recorder would still be
    caught here, and vice versa.
    """
    response = run(scenario_id)
    for situation in response.situations:
        record = AUDIT.get(situation.audit_ref)
        if record is None:
            continue
        for step in record.entries:
            if step.tier != "reasoning":
                continue
            prompt = str(step.inputs.get("prompt", ""))
            assert not leaks(prompt), f"{scenario_id}/{step.step}: prompt leaked {leaks(prompt)}"


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_the_select_candidate_payload_is_exactly_prose(scenario_id: str) -> None:
    """The structural half of S4: not "no forbidden words" but "only these keys".

    A substring assertion only catches the leaks somebody thought of. This
    catches every field the corpus grows in future, including ones nobody has
    written yet.
    """
    _, recorder = run_recorded(scenario_id)
    select_calls = [c for c in recorder.calls if c["task"] == "SELECT"]
    for call in select_calls:
        for candidate in call["context"]["candidates"]:
            assert set(candidate) == set(PROSE_KEYS), f"{scenario_id}: SELECT saw {sorted(candidate)}"


def test_the_redaction_probe_itself_fires() -> None:
    """A guard nobody has seen fail is not evidence of anything."""
    passage = BY_ID["P-SLP-2.1"]
    leaky = json.dumps([{"passage_id": passage.passage_id, "text": passage.text, "applies_when": passage.applies_when}])
    assert "applies_when" in leaks(leaky)
    assert leaks(passage.near_miss_note)
    assert not leaks(json.dumps([{k: getattr(passage, k) for k in PROSE_KEYS}]))


# --------------------------------------------------------------------------
# S5: no citation without independent checker confirmation
# --------------------------------------------------------------------------
class SimilarityMatchingLLM(MockGraniteLLM):
    """A provider that names the top-ranked candidate whatever it says.

    The mock agrees with the checker on all eight shipped scenarios, which means
    S5 has nothing to catch there and would pass on a system with no checker at
    all. This adversary is what gives the invariant teeth: it is exactly the
    failure mode v1's design made structural -- reasoning replaced by
    similarity -- and on ``no_procedure`` it proposes a passage whose
    preconditions do not hold.
    """

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:
        if task != "SELECT":
            return super().complete(task, prompt, context)
        candidates = context["candidates"]
        return json.dumps(
            {
                "governing_passage_id": candidates[0]["passage_id"] if candidates else None,
                "reason": "highest ranked candidate",
                "rejected": [{"passage_id": c["passage_id"], "why": "lower ranked"} for c in candidates[1:]],
            }
        )


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
@pytest.mark.parametrize("adversarial", [False, True], ids=["mock", "similarity-matcher"])
def test_no_recommendation_cites_a_passage_the_checker_would_reject(scenario_id: str, adversarial: bool) -> None:
    """S5, re-derived from the response the operator sees.

    Deliberately not read out of the audit trail: this reconstructs the fact set
    from the ``Situation`` payload and runs the checker again from scratch, so a
    recommendation whose recorded verdict was fabricated somewhere between the
    checker and the contract would still be caught here.
    """
    scenario = next(s for s in SCENARIOS if s.id == scenario_id)
    request = EvaluationRequest.model_validate(scenario.build())
    llm = SimilarityMatchingLLM() if adversarial else build_llm_for(scenario_id)

    for situation in engine.evaluate(request, llm=llm).situations:
        if situation.recommendation is None:
            continue
        passage = BY_ID[situation.recommendation.citation.passage_id]
        facts = {
            "task_type": situation.task_type,
            "criticality": situation.task_criticality,
            "phase": "execution",
            "alertness_score": situation.alertness_score,
            "workload_score": situation.workload_score,
            "circadian_flag": situation.circadian_flag,
        }
        verdict = check(passage.applies_when, passage.prescribes, facts)
        assert verdict.admissible, (
            f"{situation.situation_id} cites {passage.passage_id}, which fails {[c.clause for c in verdict.unmet]}"
        )


def test_the_similarity_matcher_really_does_propose_something_inadmissible() -> None:
    """Confirms the adversary above is adversarial, rather than accidentally correct.

    Without this, a later corpus change could quietly make the matcher right on
    every scenario and S5 would go back to proving nothing.
    """
    scenario = next(s for s in SCENARIOS if s.id == "no_procedure")
    request = EvaluationRequest.model_validate(scenario.build())
    response = engine.evaluate(request, llm=SimilarityMatchingLLM())
    situation = next(s for s in response.situations if s.task == "T-160")
    assert situation.outcome == "refusal"
    assert situation.refusal.reason == "precondition_unmet"
    assert situation.refusal.model_selected == "P-FAT-4.2"
    assert "task_types" in [c.clause for c in situation.refusal.failed_clauses]


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_every_recommendation_carries_the_checkers_verdict(scenario_id: str) -> None:
    """The verdict travels with the recommendation, so an operator can audit the
    citation rather than trust it."""
    for situation in run(scenario_id).situations:
        if situation.recommendation is None:
            continue
        clauses = situation.recommendation.verified_clauses
        assert clauses, f"{situation.situation_id}: recommendation issued with no recorded verification"
        assert all(c.satisfied for c in clauses)
        assert all(c.explanation for c in clauses)


# --------------------------------------------------------------------------
# S6: model/checker disagreement fails closed, both directions
#
# The forced-disagreement cases live in tests/test_propose_dispose.py, where the
# stub providers are. What is asserted here is the property over the shipped
# behaviour: wherever the two tiers disagreed, the outcome is a refusal.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_a_recorded_disagreement_is_never_a_recommendation(scenario_id: str) -> None:
    for situation in run(scenario_id).situations:
        record = AUDIT.get(situation.audit_ref)
        verify = next((e for e in record.entries if e.step == "VERIFY"), None)
        if verify is None:
            continue
        if verify.outputs["checker_disagreed"]:
            assert situation.outcome == "refusal"
            assert situation.recommendation is None
        if situation.recommendation is not None:
            assert verify.outputs["verified"] is True
