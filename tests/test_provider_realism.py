"""The whole flow, against providers that behave like real ones.

Everything upstream of this file tests HAVEN against a mock that answers
perfectly. These stubs misbehave in the specific ways instruction-tuned models
do — fenced JSON, prose instead of an object, an invented figure — and drive the
full graph, so what is asserted is the *outcome*: what an operator would see.

Two shapes of correct behaviour, and the difference matters.

**Recovered.** The first response was unusable, the second was fine, and the
recommendation stands — with the repair recorded, so a provider that needs
correcting is visible rather than quietly tolerated.

**Withheld.** The second response failed too. There is no recommendation, there
is a refusal naming what went wrong, and the deterministic evidence survives
intact. This is the system working, not the system breaking.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from haven import engine
from haven.contracts import EvaluationRequest
from haven.data.scenarios import SCENARIOS
from haven.reasoning.audit import AUDIT
from haven.reasoning.llm import MockGraniteLLM, ReasoningLLM


def run(scenario_id: str, llm: ReasoningLLM):
    """Evaluate a scenario against a chosen provider, through the whole graph."""
    scenario = next(s for s in SCENARIOS if s.id == scenario_id)
    request = EvaluationRequest.model_validate(scenario.build())
    return engine.evaluate(request, llm=llm)


def situation_for(response, task_id: str):
    return next(s for s in response.situations if s.task == task_id)


class ScriptedLLM(ReasoningLLM):
    """A provider whose SELECT answers are scripted, in order, per call."""

    provider = "stub-granite"

    def __init__(self, *select_responses: str, delegate: ReasoningLLM | None = None) -> None:
        self._responses = list(select_responses)
        self._delegate = delegate or MockGraniteLLM()
        self.select_calls = 0

    @property
    def model_id(self) -> str:
        return "granite-stub"

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:
        if task != "SELECT":
            return self._delegate.complete(task, prompt, context)
        self.select_calls += 1
        if self._responses:
            return self._responses.pop(0)
        return self._delegate.complete(task, prompt, context)


def governing_json(passage_id: str) -> str:
    return json.dumps({"governing_passage_id": passage_id, "reason": "governs", "rejected": []})


def steps(situation) -> list[str]:
    return [e.step for e in AUDIT.get(situation.audit_ref).entries]


def select_entry(situation) -> dict:
    return next(e for e in AUDIT.get(situation.audit_ref).entries if e.step == "SELECT").outputs


# --------------------------------------------------------------------------
# Wrapping the model adds
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("label", "wrapper"),
    [
        ("fenced", "```json\n{body}\n```"),
        ("preamble", "Certainly! Here is my analysis:\n\n{body}"),
        ("postamble", "{body}\n\nI hope this is helpful."),
    ],
)
def test_a_wrapped_selection_still_produces_the_recommendation(label: str, wrapper: str) -> None:
    """None of this is misbehaviour, and none of it should cost a recommendation."""
    llm = ScriptedLLM(wrapper.format(body=governing_json("P-FAT-4.2")))
    situation = situation_for(run("burn_fatigue", llm), "T-119")

    assert situation.outcome == "recommendation"
    assert situation.recommendation.citation.section == "4.2"
    assert llm.select_calls == 1, "wrapping should not have needed a repair"


# --------------------------------------------------------------------------
# Recovered
# --------------------------------------------------------------------------
def test_prose_then_json_recovers_and_records_the_repair() -> None:
    llm = ScriptedLLM(
        "I think section 4.2 is the relevant one here.",
        governing_json("P-FAT-4.2"),
    )
    situation = situation_for(run("burn_fatigue", llm), "T-119")

    assert situation.outcome == "recommendation"
    assert llm.select_calls == 2, "the repair attempt should have been made"

    outputs = select_entry(situation)
    assert outputs["attempts"] == 2
    assert outputs["repaired_after"], "a provider that needed repairing must be visible in the record"


def test_an_empty_response_is_repaired_rather_than_fatal() -> None:
    llm = ScriptedLLM("", governing_json("P-FAT-4.2"))
    situation = situation_for(run("burn_fatigue", llm), "T-119")
    assert situation.outcome == "recommendation"
    assert llm.select_calls == 2


# --------------------------------------------------------------------------
# Withheld
# --------------------------------------------------------------------------
def test_two_unreadable_responses_refuse_rather_than_guess() -> None:
    """Not knowing which rule governs is an answer, and it is this one."""
    llm = ScriptedLLM(
        "Section 4.2 applies.",
        "As I said, section 4.2.",
    )
    situation = situation_for(run("burn_fatigue", llm), "T-119")

    assert situation.outcome == "refusal"
    assert situation.recommendation is None
    assert llm.select_calls == 2, "exactly one repair, then stop"


def test_an_unreadable_selection_leaves_the_evidence_intact() -> None:
    """The deterministic tier is unaffected by the provider failing to answer."""
    llm = ScriptedLLM("nonsense", "still nonsense")
    situation = situation_for(run("burn_fatigue", llm), "T-119")

    assert situation.outcome == "refusal"
    assert situation.alertness_score > 0
    assert situation.evidence.sleep_debt_h > 0
    assert situation.evidence.workload_band


def test_the_trail_records_what_could_not_be_read() -> None:
    """A reviewer must be able to see the provider's actual words."""
    llm = ScriptedLLM("Section 4.2 applies, obviously.", "It is 4.2.")
    situation = situation_for(run("burn_fatigue", llm), "T-119")

    outputs = select_entry(situation)
    assert outputs["governing_passage_id"] is None
    assert outputs["attempts"] == 2
    assert "parse_failure" in outputs
    assert "Section 4.2 applies, obviously." in outputs["raw_completion"]


def test_an_unreadable_selection_is_still_a_complete_situation() -> None:
    """S2: exactly one of recommendation or refusal, whatever the provider did."""
    llm = ScriptedLLM("nope", "nope again")
    situation = situation_for(run("burn_fatigue", llm), "T-119")
    assert (situation.recommendation is None) != (situation.refusal is None)
    assert situation.audit_ref
    assert AUDIT.get(situation.audit_ref).verify()


def test_a_model_that_invents_an_identifier_is_recorded_as_having_invented_it() -> None:
    """Failing closed is not enough; the record must show what happened."""
    llm = ScriptedLLM(governing_json("P-NOT-REAL"))
    situation = situation_for(run("burn_fatigue", llm), "T-119")

    assert situation.outcome == "refusal"
    assert situation.refusal.model_selected == "P-NOT-REAL", (
        "the trail must name the invented identifier, not merely report an absent selection"
    )
    assert "VERIFY" in steps(situation)


# --------------------------------------------------------------------------
# The numeric guard, against a model that invents a figure
# --------------------------------------------------------------------------
class InventsNumbersLLM(ReasoningLLM):
    """Writes a figure nobody computed, for a given number of attempts.

    Not a contrived failure. A model asked to write about an alertness of 0.61
    will sooner or later round it, restate a threshold from the passage, or add
    "within 30 minutes" because the prose mentioned it.
    """

    provider = "stub-granite"

    def __init__(self, bad_attempts: int, *, stage: str = "FUSE") -> None:
        self.bad_attempts = bad_attempts
        self.stage = stage
        self._delegate = MockGraniteLLM()
        self.calls: dict[str, int] = {}

    @property
    def model_id(self) -> str:
        return "granite-stub"

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:
        self.calls[task] = self.calls.get(task, 0) + 1
        if task == self.stage and self.calls[task] <= self.bad_attempts:
            # 8675309 appears in no fact set, no threshold, and no passage.
            return "Alertness stands at 8675309 on the normalised scale."
        return self._delegate.complete(task, prompt, context)


def test_an_invented_figure_is_repaired_and_the_recommendation_stands() -> None:
    """The fault is usually incidental, and the model corrects it when told."""
    llm = InventsNumbersLLM(bad_attempts=1)
    situation = situation_for(run("burn_fatigue", llm), "T-119")

    assert situation.outcome == "recommendation"
    assert llm.calls["FUSE"] == 2, "one repair attempt should have been made"

    fuse = next(e for e in AUDIT.get(situation.audit_ref).entries if e.step == "FUSE")
    assert fuse.outputs["attempts"] == 2
    assert fuse.outputs["repaired_after"], "the repair must be recorded, not absorbed"
    assert "8675309" not in situation.recommendation.rationale


def test_an_invented_figure_twice_withholds_the_recommendation() -> None:
    """The harm this system exists to prevent: a fabricated safety figure."""
    llm = InventsNumbersLLM(bad_attempts=2)
    situation = situation_for(run("burn_fatigue", llm), "T-119")

    assert situation.outcome == "refusal"
    assert situation.recommendation is None
    assert situation.refusal.reason == "numeric_integrity_failure"
    assert llm.calls["FUSE"] == 2, "exactly one repair, then withhold"


def test_a_withheld_recommendation_keeps_its_evidence() -> None:
    """A refusal here is the system working; the numbers were never in doubt."""
    situation = situation_for(run("burn_fatigue", InventsNumbersLLM(bad_attempts=2)), "T-119")

    assert situation.alertness_score > 0
    assert situation.evidence.sleep_debt_h > 0
    assert situation.evidence.kss > 0
    # The explanation names the offending figure on purpose: a reviewer needs to
    # see what the model tried to publish, not merely that something was wrong.
    assert "8675309" in situation.refusal.explanation
    assert "deterministic evidence below is unaffected" in situation.refusal.explanation


def test_the_numeric_failure_is_recorded_as_its_own_step() -> None:
    situation = situation_for(run("burn_fatigue", InventsNumbersLLM(bad_attempts=2)), "T-119")
    assert "NUMERIC_INTEGRITY_FAILURE" in steps(situation)
    assert AUDIT.get(situation.audit_ref).verify()


def test_the_guard_also_covers_the_generate_stage() -> None:
    """S1 applies to every piece of operator-facing text, not just the first."""
    llm = InventsNumbersLLM(bad_attempts=2, stage="GENERATE")
    situation = situation_for(run("burn_fatigue", llm), "T-119")

    assert situation.outcome == "refusal"
    assert situation.refusal.reason == "numeric_integrity_failure"
