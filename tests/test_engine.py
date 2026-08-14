"""Deterministic-tier and scenario-outcome tests.

Covers the PRD's success metrics: correct rule selection including
discrimination against near-misses, correct refusal, and reproducibility of the
deterministic numbers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from haven import engine
from haven.api.main import UnavailableLLM
from haven.contracts import EvaluationRequest
from haven.data.scenarios import SCENARIOS
from haven.deterministic import nasa_tlx
from haven.deterministic.screens import CrewSnapshot, screen_schedule_impact
from haven.deterministic.three_process_model import (
    SleepEpisode,
    ThreeProcessModel,
    circadian,
    inertia,
    normalise,
)
from haven.reasoning.audit import AUDIT
from haven.reasoning.llm import MockGraniteLLM


def run(scenario_id: str):
    scenario = next(s for s in SCENARIOS if s.id == scenario_id)
    request = EvaluationRequest.model_validate(scenario.build())
    llm = UnavailableLLM() if scenario_id == "provider_outage" else MockGraniteLLM()
    return engine.evaluate(request, llm=llm)


def situation_for(response, task_id: str):
    return next(s for s in response.situations if s.task == task_id)


# --------------------------------------------------------------------------
# Three-Process Model
# --------------------------------------------------------------------------
def _episodes(nights: int, duration_h: float, bedtime_h: int = 22) -> list[SleepEpisode]:
    base = datetime(2026, 8, 14, tzinfo=timezone.utc)
    out = []
    for day in range(nights):
        sleep = base + timedelta(days=day, hours=bedtime_h)
        out.append(SleepEpisode(sleep=sleep, wake=sleep + timedelta(hours=duration_h)))
    return out


def test_alertness_declines_across_a_waking_day() -> None:
    model = ThreeProcessModel(_episodes(5, 8.0))
    morning = model.sample(datetime(2026, 8, 17, 8, tzinfo=timezone.utc))
    late = model.sample(datetime(2026, 8, 17, 22, tzinfo=timezone.utc))
    assert late.homeostatic < morning.homeostatic


def test_restricted_sleep_produces_lower_alertness_than_full_sleep() -> None:
    at = datetime(2026, 8, 17, 14, tzinfo=timezone.utc)
    rested = ThreeProcessModel(_episodes(5, 8.0)).sample(at)
    restricted = ThreeProcessModel(_episodes(5, 4.5)).sample(at)
    assert restricted.score < rested.score


def test_circadian_trough_is_below_circadian_peak() -> None:
    trough = circadian(datetime(2026, 8, 17, 4, tzinfo=timezone.utc))
    peak = circadian(datetime(2026, 8, 17, 17, tzinfo=timezone.utc))
    assert trough < 0 < peak


def test_sleep_inertia_is_negative_at_wake_and_decays() -> None:
    assert inertia(0.0) < inertia(1.0) < inertia(4.0) <= 0.0
    assert abs(inertia(6.0)) < 0.05


def test_normalisation_is_clamped_to_the_unit_interval() -> None:
    assert normalise(-5.0) == 0.0
    assert normalise(99.0) == 1.0


def test_sleep_debt_accumulates_under_restriction() -> None:
    model = ThreeProcessModel(_episodes(5, 5.0))
    debt = model.sleep_debt_h(datetime(2026, 8, 19, tzinfo=timezone.utc), nights=5)
    assert debt > 10.0


def test_identical_inputs_reproduce_identical_numbers() -> None:
    """PRD success metric: deterministic numbers reproducible across runs."""
    first, second = run("burn_fatigue"), run("burn_fatigue")
    for a, b in zip(first.situations, second.situations, strict=True):
        assert a.alertness_score == b.alertness_score
        assert a.workload_score == b.workload_score
        assert a.risk_level == b.risk_level
    for a, b in zip(first.readiness, second.readiness, strict=True):
        assert a.alertness_score == b.alertness_score
        assert a.sleep_debt_h == b.sleep_debt_h


# --------------------------------------------------------------------------
# NASA-TLX
# --------------------------------------------------------------------------
def test_tlx_weights_must_sum_to_fifteen() -> None:
    with pytest.raises(ValueError):
        nasa_tlx.TLXWeights(5, 5, 5, 5, 5, 5)


def test_tlx_weighted_score_matches_the_published_formula() -> None:
    ratings = nasa_tlx.TLXRatings(80, 20, 60, 40, 70, 30)
    # Weights restated by hand rather than read from TASK_WEIGHT_PROFILES: a test
    # that derives its expectation from the code under test proves nothing.
    expected = (80 * 4 + 20 * 1 + 60 * 4 + 40 * 3 + 70 * 2 + 30 * 1) / 15
    assert nasa_tlx.score(ratings, "orbital_burn").score == pytest.approx(expected)


def test_tlx_bands_are_ordered() -> None:
    assert nasa_tlx.band_for(10) == "low"
    assert nasa_tlx.band_for(50) == "moderate"
    assert nasa_tlx.band_for(70) == "high"
    assert nasa_tlx.band_for(90) == "very_high"


# --------------------------------------------------------------------------
# Schedule-impact screen
# --------------------------------------------------------------------------
def _snapshot(crew_id: str, alertness: float, qualified: list[str], tasks=()) -> CrewSnapshot:
    return CrewSnapshot(crew_id, crew_id, "flight_engineer", qualified, alertness, list(tasks))


def test_screen_blocks_when_no_alternate_is_qualified() -> None:
    at = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    result = screen_schedule_impact(
        "second_operator_verify",
        "docking",
        at,
        60,
        "CM-01",
        [_snapshot("CM-01", 0.6, ["docking"]), _snapshot("CM-02", 0.9, ["eva"])],
    )
    assert not result.roster_ok
    assert result.blocked_reason == "no_qualified_alternate"


def test_screen_blocks_when_alternates_are_below_the_alertness_floor() -> None:
    at = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    result = screen_schedule_impact(
        "second_operator_verify",
        "docking",
        at,
        60,
        "CM-01",
        [_snapshot("CM-01", 0.6, ["docking"]), _snapshot("CM-02", 0.5, ["docking"])],
    )
    assert not result.roster_ok
    assert result.blocked_reason == "alternate_below_alertness_floor"


def test_screen_blocks_when_the_alternate_is_committed_elsewhere() -> None:
    at = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    busy = _snapshot("CM-02", 0.9, ["docking"], [("T-999", "high", at, 90)])
    result = screen_schedule_impact(
        "second_operator_verify",
        "docking",
        at,
        60,
        "CM-01",
        [_snapshot("CM-01", 0.6, ["docking"]), busy],
    )
    assert not result.roster_ok
    assert result.blocked_reason == "alternate_committed_elsewhere"


def test_screen_passes_with_a_qualified_rested_uncommitted_alternate() -> None:
    at = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    result = screen_schedule_impact(
        "second_operator_verify",
        "docking",
        at,
        60,
        "CM-01",
        [_snapshot("CM-01", 0.6, ["docking"]), _snapshot("CM-02", 0.88, ["docking"])],
    )
    assert result.roster_ok
    assert result.alternate == "CM-02"


def test_deferral_needs_no_alternate() -> None:
    at = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    result = screen_schedule_impact("task_deferral", "docking", at, 60, "CM-01", [])
    assert result.roster_ok


# --------------------------------------------------------------------------
# Scenario outcomes -- the PRD success metrics
# --------------------------------------------------------------------------
def test_core_case_selects_the_fatigue_rule_and_staffs_a_second_operator() -> None:
    situation = situation_for(run("burn_fatigue"), "T-119")
    assert situation.outcome == "recommendation"
    assert situation.recommendation.action == "second_operator_verify"
    assert situation.recommendation.citation.doc == "OPS-FATIGUE-04"
    assert situation.recommendation.citation.section == "4.2"
    assert situation.recommendation.schedule_impact.roster_ok


def test_near_miss_is_retrieved_and_then_rejected_with_a_stated_reason() -> None:
    """The headline discrimination case.

    The pre-EVA sleep-shifting passage scores within a hair of the governing
    rule on similarity. Selection must reject it on its preconditions.
    """
    situation = situation_for(run("eva_near_miss"), "T-140")
    trail = AUDIT.get(situation.audit_ref)

    retrieved = next(e for e in trail.entries if e.step == "RETRIEVE")
    retrieved_ids = [c["passage_id"] for c in retrieved.outputs["candidates"]]
    assert "P-SLP-2.1" in retrieved_ids, "the near-miss must reach the candidate set"

    select = next(e for e in trail.entries if e.step == "SELECT")
    assert select.outputs["governing_passage_id"] == "P-FAT-4.4"
    rejected = {r["passage_id"]: r["why"] for r in select.outputs["rejected"]}
    assert "P-SLP-2.1" in rejected
    assert "planning" in rejected["P-SLP-2.1"]
    assert situation.recommendation.citation.doc == "OPS-FATIGUE-04"


def test_no_governing_procedure_produces_a_refusal_not_a_guess() -> None:
    """The primary demonstration of judgement."""
    situation = situation_for(run("no_procedure"), "T-160")
    assert situation.outcome == "refusal"
    assert situation.recommendation is None
    assert situation.refusal.reason == "no_governing_procedure"
    assert situation.refusal.escalate_to == "flight_director"
    assert len(situation.refusal.searched) >= 2


def test_schedule_impact_can_veto_a_well_formed_recommendation() -> None:
    situation = situation_for(run("roster_block"), "T-180")
    assert situation.outcome == "recommendation"
    assert not situation.recommendation.schedule_impact.roster_ok
    # The primary action was vetoed and downgraded to the fallback the same
    # cited passage prescribes.
    assert situation.recommendation.action == "task_deferral"
    assert situation.recommendation.citation.section == "4.2"
    trail = AUDIT.get(situation.audit_ref)
    assert any(e.step == "GENERATE_FALLBACK" for e in trail.entries)
    assert "Defer" in situation.recommendation.rationale


def test_circadian_term_catches_a_case_sleep_totals_would_clear() -> None:
    situation = situation_for(run("circadian_trap"), "T-201")
    assert situation.circadian_flag
    assert situation.recommendation.citation.section == "5.1"
    assert situation.recommendation.action == "task_deferral"


def test_thin_input_withholds_before_the_reasoning_tier_is_invoked() -> None:
    situation = situation_for(run("thin_data"), "T-190")
    assert situation.confidence == "insufficient"
    assert situation.outcome == "refusal"
    assert situation.refusal.reason == "insufficient_input"
    trail = AUDIT.get(situation.audit_ref)
    assert not any(e.tier == "reasoning" for e in trail.entries), (
        "the reasoning tier must not be consulted when the input cannot support a conclusion"
    )


def test_a_rested_crew_raises_nothing() -> None:
    response = run("nominal_ops")
    assert response.situations == []
    assert len(response.archived_low_risk) == 4


def test_provider_outage_degrades_loudly_rather_than_guessing() -> None:
    response = run("provider_outage")
    assert response.tier_status.degraded
    assert response.tier_status.degraded_reason
    situation = situation_for(response, "T-119")
    assert situation.outcome == "refusal"
    assert situation.refusal.reason == "provider_unavailable"
    # The deterministic evidence survives the outage intact.
    assert situation.alertness_score > 0
    assert situation.evidence.sleep_debt_h > 0


# --------------------------------------------------------------------------
# Audit trail
# --------------------------------------------------------------------------
def test_audit_chain_verifies_for_every_situation() -> None:
    for scenario in SCENARIOS:
        response = run(scenario.id)
        for situation in response.situations:
            trail = AUDIT.get(situation.audit_ref)
            assert trail is not None
            assert trail.verify(), f"{situation.audit_ref} chain does not verify"


def test_tampering_with_a_logged_step_breaks_the_chain() -> None:
    response = run("burn_fatigue")
    trail = AUDIT.get(response.situations[0].audit_ref)
    assert trail.verify()
    trail.entries[0].outputs["alertness_score"] = 0.99
    assert not trail.verify(), "an altered audit entry must not still verify"
