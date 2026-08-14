"""The contract's own guarantees, as executable tests (Phase 0).

Two classes of guarantee were documented in comments and enforced nowhere:

  ranges   ``alertness_score: float  # deterministic, 0-1`` was a promise to the
           reader, not to the caller. A value outside the range means the
           deterministic tier is broken, and the contract should refuse it
           rather than hand it to the console.

  tzinfo   A naive datetime submitted to ``POST /api/evaluate`` used to reach
           ``ThreeProcessModel.homeostatic`` and raise ``TypeError`` on the first
           comparison against an aware instant -- a 500 for a malformed request.

A constraint that never fires is decoration, so each is tested by asserting the
rejection, not merely the acceptance.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from haven.contracts import (
    AuditStep,
    CrewReadiness,
    DutyEntry,
    EvaluationRequest,
    EvaluationWindow,
    Evidence,
    SleepEntry,
    Task,
)
from haven.data.scenarios import BY_ID

NAIVE = datetime(2026, 8, 20, 12, 0, 0)
AWARE = NAIVE.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# UTC normalisation
# --------------------------------------------------------------------------
def test_naive_evaluation_window_is_coerced_to_utc() -> None:
    window = EvaluationWindow(start=NAIVE, end=NAIVE + timedelta(days=1))
    assert window.start.tzinfo is not None
    assert window.start == AWARE


def test_naive_sleep_and_duty_entries_are_coerced_to_utc() -> None:
    sleep = SleepEntry(sleep=NAIVE, wake=NAIVE + timedelta(hours=8))
    duty = DutyEntry(start=NAIVE, end=NAIVE + timedelta(hours=9))
    assert sleep.sleep.tzinfo is not None
    assert sleep.wake.tzinfo is not None
    assert duty.start.tzinfo is not None
    assert duty.end.tzinfo is not None


def test_naive_task_schedule_is_coerced_to_utc() -> None:
    task = Task(id="T-1", type="orbital_burn", criticality="high", scheduled=NAIVE, assigned_to="CM-01")
    assert task.scheduled == AWARE


def test_a_non_utc_offset_is_converted_not_merely_labelled() -> None:
    """+05:30 must become the same instant expressed in UTC, not be relabelled."""
    tokyo = timezone(timedelta(hours=9))
    task = Task(
        id="T-1",
        type="orbital_burn",
        criticality="high",
        scheduled=datetime(2026, 8, 20, 21, 0, 0, tzinfo=tokyo),
        assigned_to="CM-01",
    )
    assert task.scheduled == datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    assert task.scheduled.utcoffset() == timedelta(0)


def test_a_fully_naive_request_evaluates_without_raising() -> None:
    """The regression this guards: naive input used to 500 inside the model."""
    from haven import engine
    from haven.reasoning.llm import MockGraniteLLM

    payload = BY_ID["burn_fatigue"].build()

    def strip_tz(value):
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        if isinstance(value, dict):
            return {k: strip_tz(v) for k, v in value.items()}
        if isinstance(value, list):
            return [strip_tz(v) for v in value]
        return value

    request = EvaluationRequest.model_validate(strip_tz(payload))
    response = engine.evaluate(request, llm=MockGraniteLLM())
    assert response.situations, "a naive-datetime request should evaluate normally"


# --------------------------------------------------------------------------
# Range constraints
# --------------------------------------------------------------------------
def _readiness(**overrides):
    base = dict(
        crew_member="CM-01",
        name="R. Alvarez",
        role="commander",
        reference_at=AWARE,
        asleep_at_window_start=False,
        alertness_score=0.62,
        baseline_alertness=0.71,
        delta_vs_baseline=-0.09,
        workload_score=58.0,
        sleep_debt_h=11.4,
        hours_awake=6.2,
        window_min_alertness=0.41,
        window_min_at=AWARE,
        data_coverage=1.0,
        confidence="high",
        status="degraded",
        trend="declining",
    )
    return CrewReadiness(**{**base, **overrides})


def test_readiness_accepts_values_inside_the_documented_ranges() -> None:
    assert _readiness().alertness_score == 0.62


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("alertness_score", 1.4),
        ("alertness_score", -0.1),
        ("baseline_alertness", 1.01),
        ("window_min_alertness", -0.001),
        ("data_coverage", 1.5),
        ("workload_score", 140.0),
        ("workload_score", -1.0),
        ("delta_vs_baseline", -2.0),
        ("sleep_debt_h", -3.0),
        ("hours_awake", -1.0),
    ],
)
def test_readiness_rejects_values_outside_the_documented_ranges(field: str, value: float) -> None:
    with pytest.raises(ValidationError) as excinfo:
        _readiness(**{field: value})
    assert field in str(excinfo.value)


@pytest.mark.parametrize("kss", [0.5, 9.5])
def test_evidence_rejects_a_kss_outside_its_published_scale(kss: float) -> None:
    with pytest.raises(ValidationError):
        Evidence(
            hours_awake=6.0,
            sleep_debt_h=11.0,
            last_sleep_duration_h=4.3,
            kss=kss,
            homeostatic=8.1,
            circadian=-1.2,
            inertia=-0.01,
        )


def test_evidence_allows_signed_process_terms() -> None:
    """C oscillates about zero and W is strictly negative; neither may be clamped."""
    evidence = Evidence(
        hours_awake=6.0,
        sleep_debt_h=11.0,
        last_sleep_duration_h=4.3,
        kss=7.2,
        homeostatic=8.1,
        circadian=-2.4,
        inertia=-5.72,
    )
    assert evidence.circadian < 0
    assert evidence.inertia < 0


# --------------------------------------------------------------------------
# The dict widening that keeps the generated TypeScript usable
# --------------------------------------------------------------------------
def test_audit_step_dicts_carry_arbitrary_json_values() -> None:
    """`Record<string, never>` in the generated types would break Zone 3."""
    step = AuditStep(
        seq=1,
        step="RETRIEVE",
        tier="retrieval",
        detail="…",
        inputs={"top_k": 4},
        outputs={"candidates": [{"passage_id": "P-FAT-4.2", "relevance": 0.71}]},
        started_at=AWARE,
        duration_ms=1.5,
        entry_hash="a" * 64,
        prev_hash="0" * 64,
    )
    assert step.outputs["candidates"][0]["passage_id"] == "P-FAT-4.2"


def test_audit_step_schema_permits_additional_properties() -> None:
    """Asserted on the JSON schema, since that is what generates the TypeScript."""
    schema = AuditStep.model_json_schema()["properties"]["outputs"]
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is not False
