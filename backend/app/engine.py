"""The seven-stage evaluation cycle (PRD section 4).

  1 ingest -> 2 score -> 3 trigger -> 4 retrieve -> 5 reason -> 6 screen -> 7 present

Stages 1-3 and 6 are deterministic and live here. Stages 4-5 are delegated to
the retrieval and orchestration tiers. Stage 7 is the UI's job; this module
produces the payload it renders.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import BUILD_MODE, THRESHOLDS
from app.contracts import (
    Citation,
    CrewReadiness,
    CurvePoint,
    EvaluationRequest,
    EvaluationResponse,
    Evidence,
    Recommendation,
    Refusal,
    ScheduleImpact,
    Situation,
    TierStatus,
    TimelineTask,
)
from app.data.crew import SAFETY_CRITICAL_ROLES, duty_hours_24h
from app.deterministic import nasa_tlx, triggers
from app.deterministic.screens import CrewSnapshot, assess_confidence, screen_schedule_impact
from app.deterministic.three_process_model import SleepEpisode, ThreeProcessModel
from app.reasoning.audit import AUDIT, AuditTrail
from app.reasoning.llm import ReasoningLLM, build_llm
from app.reasoning.orchestrator import ReasoningFlow
from app.retrieval.corpus import BY_ID
from app.retrieval.retriever import get_retriever

ACTION_LABELS = {
    "second_operator_verify": "Second-operator verification",
    "short_rest_then_proceed": "Protected rest, then re-evaluate",
    "duty_rotation": "Duty rotation",
    "task_deferral": "Defer to next execution window",
    "no_action_required": "Proceed as scheduled",
}

RESOURCE_COST = {
    "second_operator_verify": "One additional crew-hour. No schedule slip.",
    "short_rest_then_proceed": "Protected rest before execution. Task slips inside the current window.",
    "duty_rotation": "Assignment moves to another qualified operator; originating operator released to rest.",
    "task_deferral": "Task slips to the next execution window. No crew-hours consumed now.",
    "no_action_required": "None.",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _model_for(member) -> ThreeProcessModel:
    episodes = [SleepEpisode(sleep=e.sleep, wake=e.wake) for e in member.sleep_log]
    return ThreeProcessModel(episodes, acrophase_offset_h=member.circadian_offset_h)


def _mean_waking_alertness(model: ThreeProcessModel, start: datetime, end: datetime) -> float:
    samples = [s for s in model.curve(start, end, step_minutes=30) if not model.is_asleep(s.at)]
    if not samples:
        return 0.0
    return sum(s.score for s in samples) / len(samples)


def _readiness_for(member, model: ThreeProcessModel, window_start: datetime, window_end: datetime) -> CrewReadiness:
    """Zone 1: current state against the individual's own baseline."""
    history_start = max(model.origin, window_start - timedelta(days=5))
    baseline = _mean_waking_alertness(model, history_start, window_start)

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
    recent = _mean_waking_alertness(model, window_start - timedelta(days=2), window_start)
    prior = _mean_waking_alertness(model, window_start - timedelta(days=4), window_start - timedelta(days=2))
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


def evaluate(request: EvaluationRequest, llm: ReasoningLLM | None = None) -> EvaluationResponse:
    window_start = request.evaluation_window.start
    window_end = request.evaluation_window.end
    llm = llm or build_llm()
    retriever = get_retriever()

    # ---- Stage 1-2: ingest and score ----------------------------------
    models = {m.id: _model_for(m) for m in request.crew}
    by_id = {m.id: m for m in request.crew}
    readiness = [_readiness_for(m, models[m.id], window_start, window_end) for m in request.crew]

    timeline: list[TimelineTask] = []
    situations: list[Situation] = []
    archived: list[str] = []
    degraded = False
    degraded_reason: str | None = None

    tasks = sorted(request.tasks, key=lambda t: t.scheduled)

    for index, task in enumerate(tasks, start=1):
        member = by_id.get(task.assigned_to)
        if member is None:
            continue
        model = models[member.id]
        sample = model.sample(task.scheduled)

        # ---- Stage 2: NASA-TLX -----------------------------------------
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

        # ---- Stage 3: trigger ------------------------------------------
        trigger = triggers.evaluate(
            alertness_score=sample.score,
            workload_score=workload.score,
            circadian_flag=sample.in_circadian_low,
            criticality=task.criticality,
        )

        situation_id = f"S-{window_start.strftime('%Y%m%d')}-{index:02d}"
        timeline.append(
            TimelineTask(
                task_id=task.id,
                label=task.label or task.type.replace("_", " ").title(),
                type=task.type,
                criticality=task.criticality,
                scheduled=task.scheduled,
                assigned_to=member.id,
                assigned_name=member.name or member.id,
                predicted_alertness=round(sample.score, 3),
                circadian_low=sample.in_circadian_low,
                raises_situation=trigger.raises_situation,
                situation_id=situation_id if trigger.raises_situation else None,
                risk_level=trigger.risk_level,
            )
        )

        if not trigger.raises_situation:
            archived.append(task.id)
            continue

        # ---- Stage 6a: confidence gate (runs before reasoning) ----------
        confidence = assess_confidence(
            sleep_episodes=[(e.sleep, e.wake) for e in member.sleep_log],
            duty_entries=[(d.start, d.end) for d in member.duty_log],
            window_start=window_start,
        )

        last_sleep = max(
            (e for e in member.sleep_log if e.wake <= task.scheduled),
            key=lambda e: e.wake,
            default=None,
        )
        evidence = Evidence(
            hours_awake=round(sample.hours_awake, 1),
            sleep_debt_h=round(model.sleep_debt_h(task.scheduled), 1),
            last_sleep_duration_h=round((last_sleep.wake - last_sleep.sleep).total_seconds() / 3600.0, 1)
            if last_sleep
            else 0.0,
            kss=round(sample.kss, 1),
            homeostatic=round(sample.homeostatic, 2),
            circadian=round(sample.circadian, 2),
            inertia=round(sample.inertia, 2),
            workload_subscales={k: round(v, 1) for k, v in workload.subscales.items()},
            workload_band=workload.band,
            data_coverage=confidence.coverage,
        )

        audit_ref = f"LOG-{situation_id}"
        trail = AuditTrail(audit_ref=audit_ref, situation_id=situation_id)
        trail.append(
            step="TRIGGER",
            tier="deterministic",
            detail=(
                f"Three-Process Model and NASA-TLX evaluated for {member.name} against {task.id}. "
                + "; ".join(trigger.reasons)
                + "."
            ),
            inputs={
                "alertness_threshold": trigger.alertness_threshold,
                "workload_trigger": THRESHOLDS.workload_trigger,
                "criticality": task.criticality,
            },
            outputs={
                "alertness_score": round(sample.score, 3),
                "workload_score": round(workload.score, 1),
                "circadian_flag": sample.in_circadian_low,
                "risk_score": trigger.risk_score,
                "risk_level": trigger.risk_level,
            },
        )
        trail.append(
            step="CONFIDENCE",
            tier="deterministic",
            detail=(
                f"Input sufficiency assessed as {confidence.level}"
                + (f": {'; '.join(confidence.notes)}." if confidence.notes else ".")
            ),
            inputs={"lookback_days": 3, "full_coverage_threshold": THRESHOLDS.confidence_full_coverage},
            outputs={"level": confidence.level, "coverage": confidence.coverage, "withhold": confidence.withhold},
        )

        # Insufficient input withholds before any model is consulted: there is
        # nothing to reason about, and asserting anything here would be false
        # certainty.
        if confidence.withhold:
            refusal = Refusal(
                reason="insufficient_input",
                reason_label="Input insufficient",
                searched=[],
                best_candidate=None,
                gate=THRESHOLDS.relevance_gate,
                explanation=(
                    "The sleep and duty record for this operator does not cover enough of the trailing "
                    "window to model alertness. "
                    + " ".join(n.capitalize() + "." for n in confidence.notes)
                    + " No recommendation is issued; the gap itself is the finding."
                ),
                escalate_to="flight_surgeon",
            )
            trail.append(
                step="WITHHOLD",
                tier="deterministic",
                detail="Confidence gate withheld the recommendation before the reasoning tier was invoked.",
                outputs=refusal.model_dump(),
            )
            AUDIT.put(trail)
            situations.append(
                Situation(
                    situation_id=situation_id,
                    crew_member=member.id,
                    crew_member_name=member.name or member.id,
                    crew_role=member.role,
                    task=task.id,
                    task_type=task.type,
                    task_label=task.label,
                    task_scheduled=task.scheduled,
                    task_criticality=task.criticality,
                    alertness_score=round(sample.score, 3),
                    workload_score=round(workload.score, 1),
                    circadian_flag=sample.in_circadian_low,
                    risk_level=trigger.risk_level,
                    confidence=confidence.level,
                    outcome="refusal",
                    refusal=refusal,
                    evidence=evidence,
                    audit_ref=audit_ref,
                )
            )
            continue

        # ---- Stages 4-5: retrieval and orchestrated reasoning -----------
        facts = {
            "crew_name": member.name or member.id,
            "crew_role": member.role,
            "task_id": task.id,
            "task_type": task.type,
            "criticality": task.criticality,
            "phase": "execution",
            "alertness_score": round(sample.score, 2),
            "alertness_threshold": trigger.alertness_threshold,
            "workload_score": round(workload.score, 1),
            "circadian_flag": sample.in_circadian_low,
            "hours_awake": round(sample.hours_awake, 1),
            "sleep_debt_h": round(model.sleep_debt_h(task.scheduled), 1),
            "kss": round(sample.kss, 1),
        }
        flow = ReasoningFlow(retriever, llm, trail)
        outcome = flow.run(facts)
        if outcome.degraded:
            degraded = True
            degraded_reason = outcome.degraded_reason

        recommendation: Recommendation | None = None
        refusal_obj: Refusal | None = None

        if outcome.outcome == "refusal":
            refusal_obj = Refusal(
                reason=outcome.refusal["reason"],
                reason_label=outcome.refusal["reason_label"],
                searched=outcome.refusal["searched"],
                best_candidate=outcome.refusal["best_candidate"],
                gate=outcome.refusal["gate"],
                explanation=outcome.refusal["explanation"],
                escalate_to=outcome.refusal["escalate_to"],
            )
        else:
            # ---- Stage 6b: schedule-impact screen -----------------------
            snapshots = [
                CrewSnapshot(
                    crew_id=other.id,
                    name=other.name or other.id,
                    role=other.role,
                    qualified_for=other.qualified_for,
                    alertness_at_task=models[other.id].sample(task.scheduled).score,
                    assigned_tasks=[
                        (t.id, t.criticality, t.scheduled, t.duration_min) for t in tasks if t.assigned_to == other.id
                    ],
                )
                for other in request.crew
            ]
            action = outcome.action
            impact = screen_schedule_impact(
                action=action,
                task_type=task.type,
                task_time=task.scheduled,
                task_duration_min=task.duration_min,
                assigned_crew_id=member.id,
                crew=snapshots,
                safety_critical_roles=SAFETY_CRITICAL_ROLES,
            )

            passage = BY_ID[outcome.citation["passage_id"]]
            downgrade_note = ""
            rationale = outcome.rationale
            if not impact.roster_ok and passage.fallback_action:
                downgrade_note = (
                    f" Primary action ({ACTION_LABELS[action]}) was blocked by the schedule-impact screen; "
                    f"{passage.doc} section {passage.section} prescribes this fallback where the primary "
                    f"cannot be staffed."
                )
                action = passage.fallback_action
                rationale = flow.regenerate(facts, passage, action, outcome.justification)

            trail.append(
                step="SCHEDULE_IMPACT",
                tier="deterministic",
                detail=(impact.note + downgrade_note if impact.roster_ok or passage.fallback_action else impact.note),
                inputs={
                    "proposed_action": outcome.action,
                    "safety_critical_roles": list(SAFETY_CRITICAL_ROLES),
                    "alternate_min_alertness": THRESHOLDS.alternate_min_alertness,
                },
                outputs={
                    "roster_ok": impact.roster_ok,
                    "alternate": impact.alternate,
                    "blocked_reason": impact.blocked_reason,
                    "final_action": action,
                },
            )

            if not impact.roster_ok and not passage.fallback_action:
                refusal_obj = Refusal(
                    reason="roster_conflict",
                    reason_label="No workable staffing",
                    searched=[c["doc"] for c in (outcome.candidates or [])],
                    best_candidate=None,
                    gate=THRESHOLDS.relevance_gate,
                    explanation=(
                        f"{passage.doc} section {passage.section} governs and prescribes "
                        f"{ACTION_LABELS[outcome.action].lower()}, but the schedule-impact screen "
                        f"cannot staff it: {impact.note} The procedure states no alternative for this "
                        f"case, so the decision is escalated rather than downgraded."
                    ),
                    escalate_to="flight_director",
                )
            else:
                recommendation = Recommendation(
                    action=action,
                    action_label=ACTION_LABELS[action],
                    citation=Citation(**outcome.citation),
                    rationale=rationale + downgrade_note,
                    resource_cost=RESOURCE_COST[action],
                    schedule_impact=ScheduleImpact(
                        roster_ok=impact.roster_ok,
                        checked_roles=sorted(set(impact.checked_roles)),
                        alternate=impact.alternate,
                        alternate_name=impact.alternate_name,
                        note=impact.note,
                        blocked_reason=impact.blocked_reason,
                    ),
                )

        AUDIT.put(trail)
        situations.append(
            Situation(
                situation_id=situation_id,
                crew_member=member.id,
                crew_member_name=member.name or member.id,
                crew_role=member.role,
                task=task.id,
                task_type=task.type,
                task_label=task.label,
                task_scheduled=task.scheduled,
                task_criticality=task.criticality,
                alertness_score=round(sample.score, 3),
                workload_score=round(workload.score, 1),
                circadian_flag=sample.in_circadian_low,
                risk_level=trigger.risk_level,
                confidence=confidence.level,
                outcome="refusal" if refusal_obj else "recommendation",
                recommendation=recommendation,
                refusal=refusal_obj,
                evidence=evidence,
                audit_ref=audit_ref,
            )
        )

    return EvaluationResponse(
        evaluation_id=f"EVAL-{window_start.strftime('%Y%m%d')}-{_now().strftime('%H%M%S')}",
        generated_at=_now(),
        scenario_id=request.scenario_id,
        window=request.evaluation_window,
        readiness=readiness,
        timeline=timeline,
        situations=situations,
        archived_low_risk=archived,
        tier_status=TierStatus(
            deterministic="Three-Process Model + NASA-TLX (live)",
            retrieval=retriever.backend_name,
            reasoning=f"{llm.provider} / {llm.model_id}",
            orchestration=f"Bob reasoning flow, hash-chained audit ({BUILD_MODE})",
            degraded=degraded,
            degraded_reason=degraded_reason,
        ),
    )
