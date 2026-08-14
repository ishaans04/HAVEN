"""Stage 3: the trigger. Deterministic decision to raise a Situation.

No language, no model. Thresholds in, booleans and a risk band out.
"""

from __future__ import annotations

from dataclasses import dataclass

from haven.config import THRESHOLDS


@dataclass(frozen=True)
class TriggerResult:
    raises_situation: bool
    risk_score: float
    risk_level: str
    reasons: list[str]
    alertness_threshold: float


def threshold_for(criticality: str) -> float:
    return {
        "high": THRESHOLDS.alertness_trigger_high,
        "medium": THRESHOLDS.alertness_trigger_medium,
        "low": THRESHOLDS.alertness_trigger_low,
    }.get(criticality, THRESHOLDS.alertness_trigger_medium)


def evaluate(
    alertness_score: float,
    workload_score: float,
    circadian_flag: bool,
    criticality: str,
) -> TriggerResult:
    threshold = threshold_for(criticality)
    reasons: list[str] = []

    alertness_deficit = max(0.0, threshold - alertness_score) / threshold

    if alertness_score <= threshold:
        reasons.append("predicted alertness at or below the execution threshold for this criticality")
    if workload_score >= THRESHOLDS.workload_trigger:
        reasons.append("weighted NASA-TLX workload at or above the sustained-duty ceiling")
    if circadian_flag:
        reasons.append("task falls within the operator's circadian trough")

    criticality_weight = {"high": 1.0, "medium": 0.78, "low": 0.45}.get(criticality, 0.78)
    # Absolute alertness dominates: how far below the threshold someone sits
    # matters less than how impaired they are in absolute terms. Workload enters
    # absolutely too, for the same reason -- deliberately not as excess above the
    # trigger, which would make a heavily-loaded operator read as unloaded until
    # the ceiling is crossed.
    risk_score = (
        0.50 * (1.0 - alertness_score)
        + 0.25 * alertness_deficit
        + 0.15 * (workload_score / 100.0)
        + (0.10 if circadian_flag else 0.0)
    ) * criticality_weight

    if risk_score >= THRESHOLDS.risk_critical_at:
        risk_level = "critical"
    elif risk_score >= THRESHOLDS.risk_elevated_at:
        risk_level = "elevated"
    else:
        risk_level = "nominal"

    # A low-criticality task is archived regardless: HAVEN exists to protect
    # irreversible operations, and firing on routine work causes alert fatigue.
    raises = bool(reasons) and criticality in ("high", "medium")

    # A raised Situation is never labelled nominal. If it cleared a threshold it
    # is at least elevated, whatever the composite says.
    if raises and risk_level == "nominal":
        risk_level = "elevated"

    return TriggerResult(
        raises_situation=raises,
        risk_score=round(risk_score, 3),
        risk_level=risk_level if raises else "nominal",
        reasons=reasons,
        alertness_threshold=threshold,
    )
