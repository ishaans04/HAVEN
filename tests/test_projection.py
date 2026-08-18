"""What the recommended action is predicted to achieve.

A recommendation asks an operator to accept a cost without saying what it buys.
The projection completes that reasoning — and, because it is computed from the
same model as the alertness that raised the Situation, it is capable of
disagreeing with the recommendation. That is the point: an action projected not
to clear the threshold is information an operator should have.

Two tests here exist because the first implementation got the modelling wrong in
ways the projection itself exposed, and both failures are worth keeping pinned:

* a rest ending *at* task start projects worse alertness than no rest, because
  sleep inertia peaks at waking;
* a fixed-offset deferral of a noon task lands at midnight, in the circadian
  trough, so the "mitigation" made things worse.

Both were real. The model was right and the encoding of the procedure's intent
was wrong.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from haven.deterministic.projection import (
    DEFERRAL_HORIZON_HOURS,
    PROTECTED_REST_MINUTES,
    REST_ENDS_BEFORE_TASK_MINUTES,
    project,
)
from haven.deterministic.three_process_model import SleepEpisode, ThreeProcessModel

BASE = datetime(2026, 8, 14, tzinfo=timezone.utc)
THRESHOLD = 0.70


def model_for(nights: int = 6, hours: float = 8.0, bedtime: int = 22) -> ThreeProcessModel:
    episodes = [
        SleepEpisode(
            sleep=BASE + timedelta(days=day, hours=bedtime),
            wake=BASE + timedelta(days=day, hours=bedtime + hours),
        )
        for day in range(nights)
    ]
    return ThreeProcessModel(episodes)


def restricted_model() -> ThreeProcessModel:
    return model_for(hours=4.5)


TASK_AT = BASE + timedelta(days=6, hours=14)


def projected(action: str, model=None, **kwargs):
    return project(
        action=action,
        model=model or restricted_model(),
        task_time=TASK_AT,
        threshold=THRESHOLD,
        subject="CM-01",
        subject_name="R. Alvarez",
        **kwargs,
    )


# --------------------------------------------------------------------------
# Rest
# --------------------------------------------------------------------------
def test_a_protected_rest_improves_alertness() -> None:
    result = projected("short_rest_then_proceed")
    assert result is not None
    assert result.after > result.before, "a rest that made things worse would be a bad recommendation"
    assert result.delta > 0


def test_the_rest_ends_before_the_task_so_inertia_has_decayed() -> None:
    """The first implementation ended it at task start and projected a loss.

    Sleep inertia peaks at waking -- the model puts it at -5.72 -- so a nap
    ending as the task begins is worse than no nap. That is physiologically
    real, and it is also not what "rest and re-evaluate prior to egress" means.
    """
    assert REST_ENDS_BEFORE_TASK_MINUTES >= 120, "too short a gap projects the operator into peak sleep inertia"

    ends_at_task = project(
        action="short_rest_then_proceed",
        model=restricted_model(),
        task_time=TASK_AT,
        threshold=THRESHOLD,
        subject="CM-01",
        subject_name="R. Alvarez",
    )
    assert ends_at_task.after > ends_at_task.before


def test_the_basis_states_the_assumption() -> None:
    """An operator reading a projection must be able to see what it assumed."""
    result = projected("short_rest_then_proceed")
    assert str(PROTECTED_REST_MINUTES) in result.basis
    assert "inertia" in result.basis


def test_the_projection_does_not_alter_the_planned_schedule() -> None:
    """A counterfactual that edited the plan would be indistinguishable from it."""
    model = restricted_model()
    episodes_before = len(model.sleep_log)
    before = model.sample(TASK_AT).score

    projected("short_rest_then_proceed", model=model)

    assert len(model.sleep_log) == episodes_before
    assert model.sample(TASK_AT).score == before


# --------------------------------------------------------------------------
# Deferral
# --------------------------------------------------------------------------
def test_a_deferral_finds_a_window_that_actually_works() -> None:
    """A fixed offset was the first implementation, and it was wrong.

    Deferring a noon task by twelve hours lands it at midnight, in the circadian
    trough. "The next available window" means the next one that works, which is
    a search rather than an offset.
    """
    result = projected("task_deferral")
    assert result is not None
    assert result.clears_threshold
    assert result.after >= THRESHOLD
    assert result.at > TASK_AT


def test_a_deferral_never_proposes_a_window_during_sleep() -> None:
    """A task cannot be executed while the operator is asleep."""
    model = restricted_model()
    result = projected("task_deferral", model=model)
    assert not model.is_asleep(result.at)


def test_a_deferral_stays_inside_its_horizon() -> None:
    result = projected("task_deferral")
    assert result.at <= TASK_AT + timedelta(hours=DEFERRAL_HORIZON_HOURS)


def test_when_no_window_clears_the_threshold_that_is_the_finding() -> None:
    """Reporting the best available, and saying it does not clear, beats silence."""
    severe = model_for(hours=2.5)
    result = project(
        action="task_deferral",
        model=severe,
        task_time=TASK_AT,
        threshold=0.95,  # unreachable under any window
        subject="CM-01",
        subject_name="R. Alvarez",
    )
    assert result is not None
    assert not result.clears_threshold
    assert "No window clears" in result.basis


# --------------------------------------------------------------------------
# Actions that do not move the operator's alertness
# --------------------------------------------------------------------------
def test_a_verification_projects_the_alternate_not_the_operator() -> None:
    """Bringing in a second operator does not make the first one less tired."""
    result = projected(
        "second_operator_verify",
        alternate_model=model_for(hours=8.0),
        alternate_id="CM-03",
        alternate_name="L. Petrova",
    )
    assert result is not None
    assert result.subject == "CM-03"
    assert result.subject_name == "L. Petrova"
    assert "assigned operator's own alertness is unchanged" in result.basis


def test_a_verification_without_an_alternate_projects_nothing() -> None:
    """Inventing a figure would be worse than saying nothing."""
    assert projected("second_operator_verify") is None


@pytest.mark.parametrize("action", ["no_action_required", "something_unknown"])
def test_actions_that_change_nothing_project_nothing(action: str) -> None:
    assert projected(action) is None


# --------------------------------------------------------------------------
# It is a projection, not a measurement
# --------------------------------------------------------------------------
def test_every_projection_states_the_model_it_came_from() -> None:
    """Nothing observes the crew afterwards; the closed loop stays deferred."""
    for action, extra in (
        ("short_rest_then_proceed", {}),
        ("task_deferral", {}),
        (
            "second_operator_verify",
            {"alternate_model": model_for(), "alternate_id": "CM-03", "alternate_name": "L. Petrova"},
        ),
    ):
        result = projected(action, **extra)
        assert "Three-Process Model" in result.basis


def test_the_threshold_carried_is_the_one_that_raised_the_situation() -> None:
    result = projected("task_deferral")
    assert result.threshold == THRESHOLD
    assert result.clears_threshold == (result.after >= THRESHOLD)
