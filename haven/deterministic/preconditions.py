"""Deterministic rule admissibility -- the "disposes" half of the v2 invariant.

The reasoning tier proposes a governing passage by reading prose. This module
independently decides whether that passage's *compiled* preconditions are
actually satisfied by the Situation. It is the only place in HAVEN that may
answer the question "does this rule govern?", and it is deliberately unreachable
from the reasoning tier: the clause vocabulary below is exactly what is redacted
out of every provider prompt (safety requirement S4).

In v1 this logic lived inside ``MockGraniteLLM._unmet_conditions``, which meant
the model was handed the answer key and the "AI reasoning tier" was a rules
engine in a model's clothes. Moving it here makes it a safety component with its
own tests, and leaves the reasoning tier with nothing to match against.

Four properties matter, and each is tested:

  * **Every clause is reported, satisfied or not.** The console renders the full
    verdict. A single reason invites the assumption that fixing it would change
    the answer, and an operator deciding whether to override needs all of them.
  * **It is total.** No input shape raises. A checker that can throw is a
    checker that can be skipped, and the exception would surface as a 500 where
    a refusal belongs.
  * **It is pure.** Same clauses, same facts, same verdict -- so a
    recommendation can be re-derived from the audit trail years later.
  * **It fails closed.** A clause the checker does not recognise cannot be
    confirmed, so it counts against admissibility rather than being skipped.
    Phase 4's compiler will author ``applies_when`` from real documents; the day
    it emits a clause this module has never seen, the answer must be "I cannot
    confirm that", not silent assent.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from haven.contracts import ClauseDetail

# The clause vocabulary this checker understands, in the order clauses are
# reported. Evaluating in a fixed order rather than in ``applies_when`` order
# keeps the audit trail stable across corpus edits.
CLAUSE_VOCABULARY: tuple[str, ...] = (
    "task_types",
    "criticality_in",
    "alertness_below",
    "requires_circadian_flag",
    "workload_above",
    "phase",
    "domain",
)

# What a Situation raised by HAVEN's deterministic tier is *about*. A passage
# that declares any other domain is out of scope by its own declaration -- see
# the ``domain`` clause below.
SITUATION_DOMAIN = "crew_alertness"

# The phase a Situation is in when it reaches the reasoning tier. Stated here so
# the default is one named constant rather than a literal repeated per clause.
DEFAULT_PHASE = "execution"

_MISSING = "(not reported by the deterministic tier)"


@dataclass(frozen=True)
class AdmissibilityResult:
    """Whether one passage may lawfully be cited for one Situation."""

    admissible: bool
    clauses: list[ClauseDetail]
    prescribes: str | None

    @property
    def unmet(self) -> list[ClauseDetail]:
        return [c for c in self.clauses if not c.satisfied]

    def as_dicts(self) -> list[dict]:
        """Clause detail in the shape the audit trail and the contract carry."""
        return [c.model_dump() for c in self.clauses]


# --------------------------------------------------------------------------
# Coercion helpers
#
# Every one of these returns a value rather than raising. Corpus data reaches
# this module unvalidated -- Phase 4 generates it from documents -- and a
# malformed clause must produce an inadmissible verdict, never an exception out
# of the middle of an evaluation.
# --------------------------------------------------------------------------
def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(v) for v in value]
    return [str(value)]


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_text(value: Any) -> str:
    return _MISSING if value is None else str(value)


def _clause(clause: str, satisfied: bool, expected: str, actual: str, explanation: str) -> ClauseDetail:
    return ClauseDetail(
        clause=clause,
        satisfied=satisfied,
        expected=expected,
        actual=actual,
        explanation=explanation,
    )


def _uncomparable(clause: str, expected: str, actual: str) -> ClauseDetail:
    """A clause whose operands are not numbers. Fails closed, and says why."""
    return _clause(
        clause,
        False,
        expected,
        actual,
        f"clause {clause} could not be evaluated numerically ({expected} against {actual}); "
        f"an unevaluable precondition is treated as unsatisfied",
    )


# --------------------------------------------------------------------------
# The clause evaluators
# --------------------------------------------------------------------------
def _task_types(declared: Any, facts: Mapping[str, Any]) -> ClauseDetail:
    allowed = _as_list(declared)
    actual = _as_text(facts.get("task_type"))
    return _clause(
        "task_types",
        actual in allowed,
        ", ".join(allowed),
        actual,
        f"passage is scoped to {', '.join(allowed)}; situation task type is {actual}",
    )


def _criticality_in(declared: Any, facts: Mapping[str, Any]) -> ClauseDetail:
    allowed = _as_list(declared)
    actual = _as_text(facts.get("criticality"))
    return _clause(
        "criticality_in",
        actual in allowed,
        "/".join(allowed),
        actual,
        f"passage applies at {'/'.join(allowed)} criticality; situation is {actual}",
    )


def _alertness_below(declared: Any, facts: Mapping[str, Any]) -> ClauseDetail:
    limit = _as_number(declared)
    score = _as_number(facts.get("alertness_score"))
    if limit is None or score is None:
        return _uncomparable("alertness_below", f"below {_as_text(declared)}", _as_text(facts.get("alertness_score")))
    return _clause(
        "alertness_below",
        score < limit,
        f"below {limit}",
        str(score),
        f"passage requires predicted alertness below {limit}; situation is {score}",
    )


def _requires_circadian_flag(declared: Any, facts: Mapping[str, Any]) -> ClauseDetail:
    inside = bool(facts.get("circadian_flag"))
    return _clause(
        "requires_circadian_flag",
        inside,
        "task inside the operator's circadian trough",
        "inside trough" if inside else "outside trough",
        "passage requires the task to fall in the operator's circadian trough; it does not",
    )


def _workload_above(declared: Any, facts: Mapping[str, Any]) -> ClauseDetail:
    limit = _as_number(declared)
    score = _as_number(facts.get("workload_score"))
    if limit is None or score is None:
        return _uncomparable("workload_above", f"above {_as_text(declared)}", _as_text(facts.get("workload_score")))
    return _clause(
        "workload_above",
        score > limit,
        f"above {limit}",
        str(score),
        f"passage requires sustained duty load above {limit}; situation is {score}",
    )


def _phase(declared: Any, facts: Mapping[str, Any]) -> ClauseDetail:
    expected = _as_text(declared)
    actual = str(facts.get("phase") or DEFAULT_PHASE)
    return _clause(
        "phase",
        expected == actual,
        expected,
        actual,
        f"passage governs the {expected} phase; situation is in {actual}",
    )


def _domain(declared: Any, facts: Mapping[str, Any]) -> ClauseDetail:
    """A declared domain is a scope declaration, and it is always disqualifying.

    v1 buried this: ``_unmet_conditions`` appended an unmet condition for *any*
    ``domain`` key without ever comparing it, which read like an oversight. It
    is not. Every Situation HAVEN raises is a crew-alertness Situation, and a
    passage that declares a domain is declaring it governs something else --
    vehicle geometry, suit systems, staffing. Modelling it as a comparison
    against ``SITUATION_DOMAIN`` makes that an explicit, readable verdict rather
    than an unexplained side effect.
    """
    declared_domain = _as_text(declared)
    return _clause(
        "domain",
        declared_domain == SITUATION_DOMAIN,
        SITUATION_DOMAIN,
        declared_domain,
        f"passage governs {declared_domain.replace('_', ' ')}, not crew alertness",
    )


_EVALUATORS = {
    "task_types": _task_types,
    "criticality_in": _criticality_in,
    "alertness_below": _alertness_below,
    "requires_circadian_flag": _requires_circadian_flag,
    "workload_above": _workload_above,
    "phase": _phase,
    "domain": _domain,
}


def evaluate_clauses(applies_when: Any, facts: Any) -> list[ClauseDetail]:
    """Evaluate every declared precondition against the Situation.

    Returns a verdict for each clause -- satisfied ones included -- because the
    operator-facing record of a safety decision is the whole test, not the part
    that failed.

    An *empty* ``applies_when`` yields no clauses and is therefore vacuously
    satisfied: a passage that declares no preconditions has declared that it
    always applies, and that is the corpus author's call to make. A *malformed*
    one has declared nothing at all, and fails closed.
    """
    if not isinstance(applies_when, Mapping):
        return [
            _clause(
                "applies_when",
                False,
                "a mapping of precondition clauses",
                type(applies_when).__name__,
                "preconditions are not a clause mapping, so none of them can be evaluated; "
                "an unevaluable declaration is treated as unsatisfied",
            )
        ]

    declared = applies_when
    situation = _mapping(facts)
    results: list[ClauseDetail] = []

    for name in CLAUSE_VOCABULARY:
        if name not in declared:
            continue
        # ``requires_circadian_flag: False`` declares no requirement at all, so
        # it is not a clause. Only a truthy value constrains anything.
        if name == "requires_circadian_flag" and not declared[name]:
            continue
        results.append(_EVALUATORS[name](declared[name], situation))

    for name in sorted(k for k in declared if k not in CLAUSE_VOCABULARY):
        results.append(
            _clause(
                str(name),
                False,
                "a clause in the checker's vocabulary",
                f"{name}={declared[name]!r}",
                f"precondition {name!r} is not in the deterministic checker's vocabulary, so it cannot be "
                f"confirmed; an unconfirmable precondition is treated as unsatisfied",
            )
        )

    return results


def check(applies_when: Any, prescribes: str | None, facts: Any) -> AdmissibilityResult:
    """Can a passage with these preconditions lawfully be cited for this Situation?

    Admissible means every declared precondition is satisfied **and** the
    passage prescribes an action. The second half is a real clause, not a
    footnote: a passage that governs but states no prescribed action cannot
    ground a recommendation, which is hard rule 3 ("no citation, no
    recommendation") seen from the other side. v1 checked it as an afterthought
    inside the mock's ``_select``, where it was invisible to the audit trail.
    """
    clauses = evaluate_clauses(applies_when, facts)
    if prescribes is None:
        clauses.append(
            _clause(
                "prescribes",
                False,
                "a prescribed action",
                "none",
                "passage states no prescribed action for this condition, so it cannot ground a recommendation",
            )
        )
    return AdmissibilityResult(
        admissible=all(c.satisfied for c in clauses),
        clauses=clauses,
        prescribes=prescribes,
    )
