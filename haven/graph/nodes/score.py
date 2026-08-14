"""Stage 2: SCORE.

Two independent products, both purely deterministic:

  * Zone 1 crew readiness -- each crew member's current state against their own
    baseline, over the evaluation window.
  * Per-task scoring -- the alertness sample at the scheduled instant and the
    weighted NASA-TLX workload for that assignment.

No thresholds are applied here. Judging is stage 3's job.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from haven.contracts import CrewMember, CrewReadiness, CurvePoint
from haven.data.crew import duty_hours_24h
from haven.deterministic import nasa_tlx
from haven.deterministic.screens import assess_confidence
from haven.deterministic.three_process_model import ThreeProcessModel
from haven.graph.state import HavenState, ScoredTask


def mean_waking_alertness(model: ThreeProcessModel, start: datetime, end: datetime) -> float:
    samples = [s for s in model.curve(start, end, step_minutes=30) if not model.is_asleep(s.at)]
    if not samples:
        return 0.0
    return sum(s.score for s in samples) / len(samples)


def readiness_for(
    member: CrewMember, model: ThreeProcessModel, window_start: datetime, window_end: datetime
) -> CrewReadiness:
    """Zone 1: current state against the individual's own baseline."""
    history_start = max(model.origin, window_start - timedelta(days=5))
    baseline = mean_waking_alertness(model, history_start, window_start)

    # Sample at a moment the crew member is actually awake. Sleep inertia makes
    # a mid-sleep sample look like severe impairment, which it is not.
    asleep_now = model.is_asleep(window_start)
    reference_at = window_start
    if asleep_now:
        next_wake = min(
            (e.wake for e in model.sleep_log if e.wake > window_start),
            default=window_start,
        )
        # Three hours past wake, by which point sleep inertia has decayed to
        # near zero. Reading earlier would report inertia as if it were fatigue.
        reference_at = min(next_wake + timedelta(hours=3), window_end)
    now_sample = model.sample(reference_at)
    delta = now_sample.score - baseline

    waking = [s for s in model.curve(window_start, window_end, step_minutes=20) if not model.is_asleep(s.at)]
    worst = min(waking, key=lambda s: s.score) if waking else now_sample

    # Sustained-trend triage (PRD 8.2): compare the trailing two days against
    # the two before them, so a single short night does not raise a trend.
    recent = mean_waking_alertness(model, window_start - timedelta(days=2), window_start)
    prior = mean_waking_alertness(model, window_start - timedelta(days=4), window_start - timedelta(days=2))
    drift = recent - prior
    if drift > 0.02:
        trend = "improving"
    elif drift < -0.02:
        trend = "declining"
    else:
        trend = "stable"

    debt = model.sleep_debt_h(window_start)

    # Three independent signals, because no one of them is sufficient. Absolute
    # alertness misses someone whose baseline is already low; baseline delta
    # misses chronic restriction, because the baseline sinks with the person;
    # accumulated debt catches exactly that case.
    if now_sample.score < 0.55 or debt >= 10.0 or (delta <= -0.10 and trend == "declining"):
        status = "degraded"
    elif now_sample.score < 0.63 or debt >= 5.0 or delta <= -0.06:
        status = "watch"
    else:
        status = "nominal"

    coverage = assess_confidence(
        sleep_episodes=[(e.sleep, e.wake) for e in member.sleep_log],
        duty_entries=[(d.start, d.end) for d in member.duty_log],
        window_start=window_start,
    )

    duty_h = duty_hours_24h([{"start": d.start, "end": d.end} for d in member.duty_log], reference_at)
    ratings = nasa_tlx.from_duty_load(duty_h, concurrent_tasks=1, task_type="science_ops", criticality="medium")
    workload = nasa_tlx.score(ratings, "science_ops")

    curve = [
        CurvePoint(
            at=s.at,
            score=round(s.score, 3),
            homeostatic=round(s.homeostatic, 2),
            circadian=round(s.circadian, 2),
            inertia=round(s.inertia, 2),
            kss=round(s.kss, 1),
            in_circadian_low=s.in_circadian_low,
            asleep=model.is_asleep(s.at),
        )
        for s in model.curve(window_start, window_end, step_minutes=20)
    ]

    return CrewReadiness(
        crew_member=member.id,
        name=member.name or member.id,
        role=member.role,
        reference_at=reference_at,
        asleep_at_window_start=asleep_now,
        window_min_alertness=round(worst.score, 3),
        window_min_at=worst.at,
        data_coverage=coverage.coverage,
        confidence=coverage.level,
        alertness_score=round(now_sample.score, 3),
        baseline_alertness=round(baseline, 3),
        delta_vs_baseline=round(delta, 3),
        workload_score=round(workload.score, 1),
        sleep_debt_h=round(debt, 1),
        hours_awake=round(now_sample.hours_awake, 1),
        status=status,
        trend=trend,
        curve=curve,
    )


def score_node(state: HavenState) -> dict[str, Any]:
    request = state["request"]
    models = state["models"]
    by_id = state["by_id"]
    tasks = state["tasks"]

    readiness = [readiness_for(m, models[m.id], state["window_start"], state["window_end"]) for m in request.crew]

    scored: list[ScoredTask] = []
    for index, task in enumerate(tasks, start=1):
        member = by_id.get(task.assigned_to)
        # A task assigned to nobody on the roster is scored by nothing and
        # triggers nothing; it is dropped here and never reaches the timeline.
        if member is None:
            continue
        model = models[member.id]
        sample = model.sample(task.scheduled)

        duty_h = duty_hours_24h([{"start": d.start, "end": d.end} for d in member.duty_log], task.scheduled)
        concurrent = sum(
            1
            for other in tasks
            if other.assigned_to == member.id
            and other.id != task.id
            and abs((other.scheduled - task.scheduled).total_seconds()) < 6 * 3600
        )
        ratings = nasa_tlx.from_duty_load(duty_h, concurrent, task.type, task.criticality)
        workload = nasa_tlx.score(ratings, task.type)

        scored.append(ScoredTask(index=index, task=task, member=member, model=model, sample=sample, workload=workload))

    return {"readiness": readiness, "scored": scored}
