"""Stage 3: TRIGGER.

Applies the deterministic thresholds to every scored task, builds the Zone 2
timeline, and splits the tasks into the ones that raise a Situation and the ones
archived as low risk. Thresholds in, booleans out; no language, no model.
"""

from __future__ import annotations

from typing import Any

from haven.contracts import TimelineTask
from haven.deterministic import triggers
from haven.graph.state import HavenState, RaisedSituation


def trigger_node(state: HavenState) -> dict[str, Any]:
    window_start = state["window_start"]

    timeline: list[TimelineTask] = []
    archived: list[str] = []
    raised: list[RaisedSituation] = []

    for entry in state["scored"]:
        task, member, sample, workload = entry.task, entry.member, entry.sample, entry.workload

        trigger = triggers.evaluate(
            alertness_score=sample.score,
            workload_score=workload.score,
            circadian_flag=sample.in_circadian_low,
            criticality=task.criticality,
        )

        situation_id = f"S-{window_start.strftime('%Y%m%d')}-{entry.index:02d}"
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

        raised.append(RaisedSituation(scored=entry, trigger=trigger, situation_id=situation_id))

    return {"timeline": timeline, "archived": archived, "raised": raised}
