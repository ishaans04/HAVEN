"""What the recommended action would do to the operator's alertness.

A recommendation currently asks an operator to accept a cost — a crew-hour, a
slipped task, a reassignment — without saying what it buys. "Insert a protected
rest period" is a weaker case than "insert a protected rest period, and
predicted alertness at the task rises from 0.61 to 0.74, above the 0.70
execution threshold". The second is the same recommendation with its reasoning
completed.

**This is a projection, not a verification.** The Three-Process Model says what
alertness would be under a stated sleep schedule; it cannot say what actually
happened, because nothing here observes the crew afterwards. The closed
verification loop — confirming after the fact that alertness and coverage really
improved — is named as deferred in the architecture design and stays deferred.
Presenting a projection as a measurement would be exactly the false confidence
this system exists to avoid, so the contract calls it `projected` and the console
says "predicted".

Deterministic tier, and necessarily so: it produces a number, so the reasoning
tier may not.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from haven.deterministic.three_process_model import SleepEpisode, ThreeProcessModel

#: A protected rest period, per OPS-FATIGUE-04 4.4: "no less than ninety
#: minutes". The figure comes from the corpus rather than from here.
PROTECTED_REST_MINUTES = 90

#: How long before the task the rest ends.
#:
#: This is not padding. Sleep inertia peaks at the moment of waking -- the model
#: puts it at -5.72 on a 1-16 scale -- so a rest ending exactly at task start
#: projects *worse* alertness than no rest at all. That is physiologically real
#: and it is also not what 4.4 describes: "a protected rest period ... may be
#: taken and alertness re-evaluated prior to egress" only makes sense with time
#: to wake up in between.
#:
#: Three hours, matching the figure the scoring node already uses for exactly
#: this question -- "by which point sleep inertia has decayed to near zero.
#: Reading earlier would report inertia as if it were fatigue." Deliberately
#: taken from the existing precedent rather than chosen: a constant picked to
#: make a recommendation project well would be tuning the evidence to fit the
#: conclusion, which is the opposite of what this module is for.
#:
#: The first version omitted the gap entirely and duly projected a 90-minute
#: rest making an EVA operator markedly worse. Worth keeping the reason written
#: down: the model was right and the encoding of the intent was wrong.
REST_ENDS_BEFORE_TASK_MINUTES = 180

#: How far ahead a deferral may look for a workable window, and how finely.
DEFERRAL_HORIZON_HOURS = 24
DEFERRAL_STEP_MINUTES = 30


@dataclass(frozen=True)
class Projection:
    """Alertness before and after, under the recommended action."""

    action: str
    #: Whose alertness is being projected. For a rotation or a verification that
    #: is a different person from the one the Situation is about, which is the
    #: whole point of the action.
    subject: str
    subject_name: str
    at: datetime
    before: float
    after: float
    threshold: float
    basis: str

    @property
    def delta(self) -> float:
        return round(self.after - self.before, 3)

    @property
    def clears_threshold(self) -> bool:
        return self.after >= self.threshold

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "subject": self.subject,
            "subject_name": self.subject_name,
            "at": self.at,
            "before": round(self.before, 3),
            "after": round(self.after, 3),
            "delta": self.delta,
            "threshold": self.threshold,
            "clears_threshold": self.clears_threshold,
            "basis": self.basis,
        }


def _with_rest(model: ThreeProcessModel, before: datetime, minutes: int) -> ThreeProcessModel:
    """The same operator, with a rest period inserted before the task.

    A new model rather than a mutated one: the original is the record of what is
    actually planned, and a projection that edited it would make the counterfactual
    indistinguishable from the plan.
    """
    rest = SleepEpisode(sleep=before - timedelta(minutes=minutes), wake=before)
    return ThreeProcessModel(
        [*model.sleep_log, rest],
        acrophase_offset_h=model.acrophase_offset_h,
        initial_s=model.initial_s,
    )


def _sweep(model: ThreeProcessModel, start: datetime):
    """Alertness at each candidate window across the deferral horizon.

    Windows where the operator would be asleep are skipped: a task cannot be
    executed then, and reporting a sleeping operator's alertness as a workable
    option would be nonsense.
    """
    steps = int(DEFERRAL_HORIZON_HOURS * 60 / DEFERRAL_STEP_MINUTES)
    for step in range(1, steps + 1):
        at = start + timedelta(minutes=DEFERRAL_STEP_MINUTES * step)
        if model.is_asleep(at):
            continue
        yield at, model.sample(at).score


def _next_workable_window(model: ThreeProcessModel, start: datetime, threshold: float):
    """The first window clearing the threshold, or ``(None, 0.0)``.

    A fixed offset was the first implementation and it was wrong: deferring a
    noon task by twelve hours lands it at midnight, in the circadian trough, and
    the projection duly reported a recommendation making things worse. "The next
    available window" means the next window that *works*, which is a search.
    """
    for at, score in _sweep(model, start):
        if score >= threshold:
            return at, score
    return None, 0.0


def _best_window(model: ThreeProcessModel, start: datetime):
    """The best the horizon offers, for when nothing in it clears the threshold."""
    candidates = list(_sweep(model, start))
    if not candidates:
        return start + timedelta(hours=DEFERRAL_HORIZON_HOURS), 0.0
    return max(candidates, key=lambda pair: pair[1])


def project(
    *,
    action: str,
    model: ThreeProcessModel,
    task_time: datetime,
    threshold: float,
    subject: str,
    subject_name: str,
    alternate_model: ThreeProcessModel | None = None,
    alternate_id: str = "",
    alternate_name: str = "",
) -> Projection | None:
    """What the action would achieve, or ``None`` where the question is meaningless.

    Not every action moves alertness, and inventing a number for the ones that
    do not would be worse than saying nothing. `no_action_required` changes
    nothing by definition; a verification or a rotation does not improve the
    *assigned* operator at all — it brings in someone else, so the honest figure
    is the alternate's alertness, and without an alternate there is nothing to
    project.
    """
    before = model.sample(task_time).score

    if action == "short_rest_then_proceed":
        ends_at = task_time - timedelta(minutes=REST_ENDS_BEFORE_TASK_MINUTES)
        rested = _with_rest(model, ends_at, PROTECTED_REST_MINUTES)
        return Projection(
            action=action,
            subject=subject,
            subject_name=subject_name,
            at=task_time,
            before=before,
            after=rested.sample(task_time).score,
            threshold=threshold,
            basis=(
                f"Three-Process Model, with a {PROTECTED_REST_MINUTES}-minute protected rest "
                f"ending {REST_ENDS_BEFORE_TASK_MINUTES} minutes before the task, so sleep "
                f"inertia has decayed by the time it starts"
            ),
        )

    if action == "task_deferral":
        window, score = _next_workable_window(model, task_time, threshold)
        if window is None:
            best_at, best_score = _best_window(model, task_time)
            return Projection(
                action=action,
                subject=subject,
                subject_name=subject_name,
                at=best_at,
                before=before,
                after=best_score,
                threshold=threshold,
                basis=(
                    f"Three-Process Model swept over the next {DEFERRAL_HORIZON_HOURS} hours. "
                    f"No window clears the execution threshold; this is the best available, "
                    f"which is itself a finding."
                ),
            )
        return Projection(
            action=action,
            subject=subject,
            subject_name=subject_name,
            at=window,
            before=before,
            after=score,
            threshold=threshold,
            basis=(
                f"Three-Process Model swept forward to the first window clearing the execution "
                f"threshold, within {DEFERRAL_HORIZON_HOURS} hours. The actual window is a "
                f"scheduling decision HAVEN does not make."
            ),
        )

    if action in ("second_operator_verify", "duty_rotation"):
        if alternate_model is None:
            return None
        return Projection(
            action=action,
            subject=alternate_id,
            subject_name=alternate_name,
            at=task_time,
            before=before,
            after=alternate_model.sample(task_time).score,
            threshold=threshold,
            basis=(
                "Three-Process Model for the proposed alternate at the scheduled time. "
                "The assigned operator's own alertness is unchanged by this action."
            ),
        )

    return None
