"""The deterministic checker, on its own.

This module is the "disposes" half of the v2 invariant: the model proposes a
governing passage from prose, and this code independently decides whether the
passage's compiled preconditions are actually satisfied. In v1 the same logic
lived inside ``MockGraniteLLM``, where it was mock scaffolding rather than a
safety component and had no tests of its own.

Two classes of property are asserted here. The first is that it gets the corpus
right. The second, and the reason for the Hypothesis section at the bottom, is
that it is **total and fail-closed**: no input shape raises, and anything it
cannot evaluate counts against admissibility. A checker that can throw is a
checker that can be skipped, and the exception would surface as a 500 where a
refusal belongs.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from haven.deterministic.preconditions import (
    CLAUSE_VOCABULARY,
    SITUATION_DOMAIN,
    AdmissibilityResult,
    check,
)
from haven.rag.corpus import BY_ID, CORPUS

BURN_FACTS = {
    "task_type": "orbital_burn",
    "criticality": "high",
    "phase": "execution",
    "alertness_score": 0.61,
    "workload_score": 58.0,
    "circadian_flag": False,
}


def check_passage(passage_id: str, facts: dict) -> AdmissibilityResult:
    """Check a corpus passage the way the flow does: clauses + prescribed action."""
    passage = BY_ID[passage_id]
    return check(passage.applies_when, passage.prescribes, facts)


def clauses_of(result: AdmissibilityResult) -> list[str]:
    return [c.clause for c in result.clauses]


def unmet_of(result: AdmissibilityResult) -> list[str]:
    return [c.clause for c in result.unmet]


# --------------------------------------------------------------------------
# The corpus, clause by clause
# --------------------------------------------------------------------------
def test_the_governing_passage_is_admissible() -> None:
    result = check_passage("P-FAT-4.2", BURN_FACTS)
    assert result.admissible
    assert result.unmet == []
    assert result.prescribes == "second_operator_verify"
    assert all(c.satisfied for c in result.clauses)


def test_satisfied_clauses_are_reported_not_only_failures() -> None:
    """The console renders the whole verdict, so the whole verdict is produced."""
    result = check_passage("P-FAT-4.2", BURN_FACTS)
    assert clauses_of(result) == ["task_types", "criticality_in", "alertness_below"]
    alertness = next(c for c in result.clauses if c.clause == "alertness_below")
    assert alertness.expected == "below 0.7"
    assert alertness.actual == "0.61"


def test_a_planning_phase_passage_is_inadmissible_during_execution() -> None:
    facts = {**BURN_FACTS, "task_type": "eva", "alertness_score": 0.55}
    result = check_passage("P-SLP-2.1", facts)
    assert not result.admissible
    assert "phase" in unmet_of(result)
    phase = next(c for c in result.clauses if c.clause == "phase")
    assert phase.expected == "planning"
    assert phase.actual == "execution"


def test_a_declared_domain_is_a_scope_declaration_and_always_disqualifies() -> None:
    """``domain`` is honest about being a scope declaration, not a comparison.

    Every Situation HAVEN raises is a crew-alertness Situation. A passage that
    declares any other domain has said it governs something else.
    """
    result = check_passage("P-DCK-3.2", {**BURN_FACTS, "task_type": "docking"})
    assert not result.admissible
    domain = next(c for c in result.clauses if c.clause == "domain")
    assert domain.satisfied is False
    assert domain.expected == SITUATION_DOMAIN
    assert domain.actual == "vehicle_state"


def test_a_passage_prescribing_nothing_cannot_ground_a_recommendation() -> None:
    """Hard rule 3, seen from the corpus side, as a real clause rather than a footnote."""
    facts = {**BURN_FACTS, "task_type": "eva", "alertness_score": 0.55}
    result = check_passage("P-EVA-11.3", facts)
    assert not result.admissible
    assert result.prescribes is None
    assert "prescribes" in unmet_of(result)


def test_the_circadian_rule_requires_the_flag() -> None:
    result = check_passage("P-FAT-5.1", BURN_FACTS)
    assert not result.admissible
    assert unmet_of(result) == ["requires_circadian_flag"]

    in_trough = check_passage("P-FAT-5.1", {**BURN_FACTS, "circadian_flag": True})
    assert in_trough.admissible


def test_the_workload_clause_is_strict() -> None:
    """``workload_above: 65`` means above, not at. A boundary read either way is a
    different rule, so it is pinned."""
    facts = {**BURN_FACTS, "task_type": "maintenance", "criticality": "high"}
    assert not check_passage("P-FAT-6.3", {**facts, "workload_score": 65.0}).admissible
    assert check_passage("P-FAT-6.3", {**facts, "workload_score": 65.1}).admissible


def test_every_unmet_clause_is_reported_not_just_the_first() -> None:
    """An operator deciding whether to override needs all of the reasons.

    One reason invites the assumption that fixing it would change the answer.
    """
    facts = {**BURN_FACTS, "task_type": "science_ops", "criticality": "low"}
    result = check_passage("P-FAT-4.2", facts)
    assert not result.admissible
    assert {"task_types", "criticality_in"} <= set(unmet_of(result))
    assert len(result.unmet) >= 2


@pytest.mark.parametrize("passage_id", sorted(BY_ID))
def test_no_passage_is_admissible_against_an_empty_fact_set(passage_id: str) -> None:
    """Fail closed: an absent fact never satisfies a precondition by default."""
    assert not check_passage(passage_id, {}).admissible


def test_the_verdict_is_pure() -> None:
    """Same clauses, same facts, same answer -- so a citation can be re-derived
    from the audit trail years later."""
    first = check_passage("P-FAT-4.2", BURN_FACTS)
    second = check_passage("P-FAT-4.2", dict(BURN_FACTS))
    assert first == second


# --------------------------------------------------------------------------
# Fail-closed on anything the checker does not understand
# --------------------------------------------------------------------------
def test_an_unrecognised_clause_counts_against_admissibility() -> None:
    """Phase 4's compiler will author ``applies_when`` from real documents.

    The day it emits a clause this module has never seen, the answer must be
    "I cannot confirm that", not silent assent.
    """
    result = check({"task_types": ["orbital_burn"], "solar_beta_below": 60}, "task_deferral", BURN_FACTS)
    assert not result.admissible
    assert "solar_beta_below" in unmet_of(result)


def test_a_clause_whose_operands_are_not_numbers_is_unsatisfied() -> None:
    result = check({"alertness_below": "quite low"}, "task_deferral", BURN_FACTS)
    assert not result.admissible
    assert unmet_of(result) == ["alertness_below"]


def test_a_malformed_precondition_declaration_fails_closed() -> None:
    result = check(["task_types"], "task_deferral", BURN_FACTS)
    assert not result.admissible
    assert unmet_of(result) == ["applies_when"]


def test_a_passage_declaring_no_preconditions_is_vacuously_admissible() -> None:
    """Documented deliberately: an empty declaration is still a declaration.

    Inventing "no clauses means inadmissible" here would contradict the
    all-clauses-satisfied semantics and would surprise the Phase 4 compiler. A
    rule that should not always apply is a corpus bug, not a checker bug.
    """
    assert check({}, "task_deferral", BURN_FACTS).admissible
    assert not check({}, None, BURN_FACTS).admissible


# --------------------------------------------------------------------------
# Property: the checker is total
# --------------------------------------------------------------------------
_LEAVES = (
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=True, allow_infinity=True) | st.text(max_size=8)
)

_VALUES = st.recursive(
    _LEAVES,
    lambda children: st.lists(children, max_size=3) | st.dictionaries(st.text(max_size=5), children, max_size=3),
    max_leaves=5,
)

_CLAUSE_KEYS = st.sampled_from(CLAUSE_VOCABULARY) | st.text(max_size=8)
_FACT_KEYS = st.sampled_from(
    ["task_type", "criticality", "phase", "alertness_score", "workload_score", "circadian_flag"]
) | st.text(max_size=8)

PROPERTY_SETTINGS = settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@PROPERTY_SETTINGS
@given(
    applies_when=st.dictionaries(_CLAUSE_KEYS, _VALUES, max_size=6),
    prescribes=st.none() | st.text(max_size=12),
    facts=st.dictionaries(_FACT_KEYS, _VALUES, max_size=8),
)
def test_check_never_raises_on_arbitrary_shapes(applies_when: dict, prescribes: str | None, facts: dict) -> None:
    result = check(applies_when, prescribes, facts)
    assert isinstance(result.admissible, bool)
    # The verdict is exactly the conjunction of its clauses -- never a shortcut
    # taken somewhere else.
    assert result.admissible == all(c.satisfied for c in result.clauses)
    assert result.unmet == [c for c in result.clauses if not c.satisfied]
    for clause in result.clauses:
        assert isinstance(clause.explanation, str) and clause.explanation


@PROPERTY_SETTINGS
@given(value=_VALUES)
def test_check_never_raises_on_non_mapping_inputs(value: object) -> None:
    assert isinstance(check(value, None, value), AdmissibilityResult)
    assert isinstance(check(value, "task_deferral", value), AdmissibilityResult)


@PROPERTY_SETTINGS
@given(
    alertness=st.floats(min_value=0.0, max_value=1.0),
    limit=st.floats(min_value=0.0, max_value=1.0),
)
def test_the_alertness_clause_is_exactly_the_comparison_it_claims(alertness: float, limit: float) -> None:
    result = check({"alertness_below": limit}, "task_deferral", {**BURN_FACTS, "alertness_score": alertness})
    assert result.admissible == (alertness < limit)


def test_a_nan_score_does_not_satisfy_a_threshold() -> None:
    """Not an academic case: a malformed downlink is how NaN reaches a threshold."""
    result = check({"alertness_below": 0.7}, "task_deferral", {**BURN_FACTS, "alertness_score": math.nan})
    assert not result.admissible


def test_the_clause_vocabulary_covers_every_clause_the_corpus_uses() -> None:
    """The corpus may not quietly grow a clause the checker treats as unknown.

    It would still fail closed, so nothing unsafe happens -- but every passage
    using it would become permanently uncitable, which is a corpus outage
    presenting as a run of refusals.
    """
    used = {key for passage in CORPUS for key in passage.applies_when}
    assert used <= set(CLAUSE_VOCABULARY), (
        f"corpus uses clauses the checker does not model: {used - set(CLAUSE_VOCABULARY)}"
    )
