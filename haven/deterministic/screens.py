"""Stage 6: the deterministic screens.

Two independent vetoes applied *after* the reasoning tier has produced a
recommendation:

  confidence gate     is the input data good enough to assert this at all?
  schedule-impact     does the proposed change leave a safety-critical role
                      unstaffed by someone qualified and rested?

Either can downgrade or block a recommendation. Neither can create one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from haven.config import THRESHOLDS


# --------------------------------------------------------------------------
# Confidence gate
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ConfidenceResult:
    level: str  # high | moderate | low | insufficient
    coverage: float  # 0-1, fraction of the lookback covered by sleep/duty data
    notes: list[str]
    withhold: bool  # True -> do not show a recommendation


def assess_confidence(
    sleep_episodes: list[tuple[datetime, datetime]],
    duty_entries: list[tuple[datetime, datetime]],
    window_start: datetime,
    lookback_days: int = 3,
) -> ConfidenceResult:
    """Data sufficiency over the trailing lookback window.

    Coverage measures *record completeness*, not hours occupied: for each of the
    trailing days, is there a sleep record and a duty record? Measuring occupied
    hours would penalise a crew member simply for having time off.
    """
    notes: list[str] = []
    expected_slots = lookback_days * 2  # one sleep + one duty record per day
    present = 0
    missing_sleep_days: list[int] = []

    for day_back in range(1, lookback_days + 1):
        day_start = window_start - timedelta(days=day_back)
        day_end = day_start + timedelta(days=1)
        has_sleep = any(e > day_start and s < day_end for s, e in sleep_episodes)
        has_duty = any(e > day_start and s < day_end for s, e in duty_entries)
        present += int(has_sleep) + int(has_duty)
        if not has_sleep:
            missing_sleep_days.append(day_back)

    coverage = present / expected_slots if expected_slots else 0.0

    nights = lookback_days - len(missing_sleep_days)
    if missing_sleep_days:
        notes.append(f"only {nights} of {lookback_days} expected sleep periods present in the record")
    if present < expected_slots:
        notes.append("sleep or duty records are missing from the trailing window")

    if coverage >= THRESHOLDS.confidence_full_coverage and not missing_sleep_days:
        level, withhold = "high", False
    elif coverage >= THRESHOLDS.confidence_low_coverage:
        level, withhold = "moderate", False
    elif coverage >= THRESHOLDS.confidence_minimum:
        level, withhold = "low", False
    else:
        level, withhold = "insufficient", True
        notes.append("input is insufficient to model alertness, so no recommendation is issued")

    return ConfidenceResult(level=level, coverage=round(coverage, 3), notes=notes, withhold=withhold)


# --------------------------------------------------------------------------
# Schedule-impact screen
# --------------------------------------------------------------------------
@dataclass
class CrewSnapshot:
    """What the screen needs to know about a potential alternate operator."""

    crew_id: str
    name: str
    role: str
    qualified_for: list[str]
    alertness_at_task: float
    assigned_tasks: list[tuple[str, str, datetime, int]]  # (task_id, criticality, scheduled, duration_min)


@dataclass(frozen=True)
class ScheduleImpactResult:
    roster_ok: bool
    checked_roles: list[str]
    alternate: str | None
    alternate_name: str
    note: str
    blocked_reason: str | None


ACTIONS_NEEDING_ANOTHER_OPERATOR = {"second_operator_verify", "duty_rotation"}


def _busy_at(snapshot: CrewSnapshot, at: datetime, duration_min: int) -> bool:
    task_end = at + timedelta(minutes=duration_min)
    for _, criticality, scheduled, dur in snapshot.assigned_tasks:
        other_end = scheduled + timedelta(minutes=dur)
        overlaps = scheduled < task_end and at < other_end
        if overlaps and criticality in ("high", "medium"):
            return True
    return False


def screen_schedule_impact(
    action: str,
    task_type: str,
    task_time: datetime,
    task_duration_min: int,
    assigned_crew_id: str,
    crew: list[CrewSnapshot],
    safety_critical_roles: tuple[str, ...] = ("commander", "flight_engineer"),
) -> ScheduleImpactResult:
    """Confirm the proposed change leaves every safety-critical role staffed."""
    checked = [c.role for c in crew if c.role in safety_critical_roles]

    if action not in ACTIONS_NEEDING_ANOTHER_OPERATOR:
        if action == "task_deferral":
            note = "Deferral removes the task from this window; no role is left unstaffed by the change."
        elif action == "short_rest_then_proceed":
            note = "Rest period sits inside the existing window; the assignment is unchanged."
        else:
            note = "No staffing change proposed."
        return ScheduleImpactResult(True, checked, None, "", note, None)

    qualified = [c for c in crew if c.crew_id != assigned_crew_id and task_type in c.qualified_for]
    if not qualified:
        return ScheduleImpactResult(
            False,
            checked,
            None,
            "",
            "No other crew member holds the qualification for this task type.",
            "no_qualified_alternate",
        )

    rested = [c for c in qualified if c.alertness_at_task >= THRESHOLDS.alternate_min_alertness]
    if not rested:
        best = max(qualified, key=lambda c: c.alertness_at_task)
        return ScheduleImpactResult(
            False,
            checked,
            None,
            "",
            (
                f"Qualified crew are available but none meet the alertness floor for verification duty; "
                f"the best available is {best.name}."
            ),
            "alternate_below_alertness_floor",
        )

    available = [c for c in rested if not _busy_at(c, task_time, task_duration_min)]
    if not available:
        return ScheduleImpactResult(
            False,
            checked,
            None,
            "",
            "Every qualified and rested alternate is committed to another safety-critical task in this window.",
            "alternate_committed_elsewhere",
        )

    pick = max(available, key=lambda c: c.alertness_at_task)
    return ScheduleImpactResult(
        True,
        checked,
        pick.crew_id,
        pick.name,
        (
            f"{pick.name} ({pick.role.replace('_', ' ')}) is qualified, above the alertness floor, and "
            f"uncommitted for the task window. Safety-critical roles remain staffed."
        ),
        None,
    )
