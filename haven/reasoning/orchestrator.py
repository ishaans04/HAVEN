"""The orchestration tier -- the IBM Bob reasoning flow (PRD 4.1).

    RETRIEVE -> ADMISSIBILITY -> SELECT -> VERIFY -> (FUSE -> GENERATE) | REFUSE

Sequencing is no longer this module's job: the compiled situation graph owns it,
one node per step (``haven/graph/situation_graph.py``). What lives here is what
each step *does*, and what it writes to the hash-chained audit trail before the
next begins.

The shape of that sequence is the v2 invariant made executable:

  **ADMISSIBILITY** runs the deterministic checker over *every* retrieved
  candidate, before the model has spoken. It does **not** filter the candidate
  set -- filtering would delete the near-miss discrimination case entirely,
  since a near-miss is inadmissible by construction and the whole point is that
  the model must reject it from prose. Its purpose is to put on the record what
  the checker independently believes, so that agreement or disagreement with the
  model is a recorded fact rather than a later inference.

  **SELECT** is the model's proposal, made from redacted prose only.

  **VERIFY** is the disposition, and it is deterministic:

      model said | checker says          | result
      -----------|-----------------------|--------------------------------------
      passage P  | P admissible          | proceed to FUSE
      passage P  | P inadmissible        | refuse, naming the unmet clause
      none       | something admissible  | refuse, logging the disagreement
      none       | nothing admissible    | refuse, no governing procedure

  Both disagreement directions fail closed, and a passage the model did not
  select is **never** promoted. A ``governing_passage_id`` outside the candidate
  set is rejected structurally rather than trusted, because a real provider can
  hallucinate an identifier and hard rule 3 must hold by construction.

There is no relevance gate on this path. v1 compared a TF-IDF-derived float
against ``THRESHOLDS.relevance_gate`` and called the result a decision; a
similarity score is not a judgement about whether a rule applies. Relevance now
ranks candidates and is displayed, and nothing branches on it.

The flow owns sequencing and logging. It does not own numbers, and it does not
make the final decision -- a human does.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from haven.config import THRESHOLDS
from haven.deterministic.preconditions import AdmissibilityResult, check
from haven.rag.corpus import BY_ID
from haven.rag.retriever import ProcedureRetriever, SituationQuery
from haven.rag.vector_store import Candidate
from haven.reasoning.audit import AuditTrail
from haven.reasoning.llm import (
    FUSE_PROMPT,
    GENERATE_PROMPT,
    SELECT_PROMPT,
    LLMUnavailable,
    ReasoningLLM,
    assert_no_novel_numbers,
)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")

# The only keys a provider may see about a candidate passage. Everything else --
# the compiled preconditions, the prescribed action, the corpus author's
# near-miss note -- is the answer key, and handing it over turns reading into
# matching (safety requirement S4).
PROSE_KEYS: tuple[str, ...] = ("passage_id", "doc", "section", "title", "text")


@dataclass
class ReasoningOutcome:
    """What the flow produced. Exactly one of ``recommendation`` / ``refusal``."""

    outcome: str  # "recommendation" | "refusal"
    action: str | None = None
    citation: dict | None = None
    rationale: str = ""
    justification: str = ""
    refusal: dict | None = None
    candidates: list[dict] | None = None
    rejected: list[dict] | None = None
    degraded: bool = False
    degraded_reason: str | None = None
    # The checker's verdict on the cited passage, clause by clause. Non-empty on
    # every recommendation: no citation survives without one (S5).
    verified_clauses: list[dict] = field(default_factory=list)
    failed_clauses: list[dict] = field(default_factory=list)
    model_selected: str | None = None
    checker_disagreed: bool = False


@dataclass(frozen=True)
class Verdict:
    """VERIFY's disposition of the model's proposal. Deterministic, and logged."""

    verified: bool
    passage_id: str | None
    model_selected: str | None
    checker_disagreed: bool
    admissible_ids: list[str]
    clauses: list[dict]
    reason: str
    reason_label: str
    detail: str
    explanation: str

    @property
    def unmet(self) -> list[dict]:
        return [c for c in self.clauses if not c["satisfied"]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _allowed_numbers(facts: dict, extra: str = "") -> set[str]:
    """Numerals the reasoning tier is permitted to emit: exactly what it was given."""
    blob = json.dumps(facts, default=str) + " " + extra
    return set(_NUMBER.findall(blob))


class ReasoningFlow:
    """One evaluation of one Situation, as a set of individually audited steps.

    Each public method below is exactly one graph node's worth of work: it does
    the thing, writes its audit entry, and returns. Nothing here decides what
    runs next -- the compiled graph does, and it cannot be persuaded otherwise.
    """

    def __init__(self, retriever: ProcedureRetriever, llm: ReasoningLLM, trail: AuditTrail) -> None:
        self.retriever = retriever
        self.llm = llm
        self.trail = trail
        self.trail.provider = llm.provider
        self.trail.model_id = llm.model_id
        # Retained so a mid-flow provider failure can still report what was searched.
        self._payloads: list[dict] = []

    # -- helpers ---------------------------------------------------------
    def _call(self, task: str, prompt: str, context: dict[str, Any]) -> tuple[str, float]:
        started = time.perf_counter()
        completion = self.llm.complete(task, prompt, context)
        return completion, (time.perf_counter() - started) * 1000.0

    @staticmethod
    def _payload_full(c: Candidate) -> dict:
        """Everything known about a candidate: for ADMISSIBILITY, the audit, the UI.

        None of these three is the reasoning tier. The console shows the
        relevance breakdown and the corpus author's near-miss note so a reviewer
        can see what retrieval did; the checker needs the compiled clauses to do
        its job. Neither is a provider.
        """
        p = c.passage
        return {
            "passage_id": p.passage_id,
            "doc": p.doc,
            "section": p.section,
            "title": p.title,
            "text": p.text,
            "task_types": p.task_types,
            "applies_when": p.applies_when,
            "prescribes": p.prescribes,
            "relevance": c.relevance,
            "lexical": round(c.lexical, 3),
            "near_miss_note": p.near_miss_note,
        }

    @staticmethod
    def _payload_redacted(payload: dict) -> dict:
        """The passage as written, and nothing else. The only thing a provider sees.

        A model given ``applies_when`` is matching a key, not reading a rule,
        and would carry none of that skill to a real procedure library. Applied
        inside :meth:`select` rather than at the call site, so there is exactly
        one construction of a provider-bound candidate payload in the system and
        no caller can pass the unredacted one by mistake.
        """
        return {k: payload[k] for k in PROSE_KEYS}

    @staticmethod
    def _best(payloads: list[dict], passage_id: str | None = None) -> dict | None:
        """The closest candidate, for display on a refusal. Decides nothing."""
        if passage_id is not None:
            chosen = next((p for p in payloads if p["passage_id"] == passage_id), None)
        else:
            chosen = max(payloads, key=lambda p: p["relevance"], default=None)
        if chosen is None:
            return None
        return {
            "doc": chosen["doc"],
            "section": chosen["section"],
            "relevance": round(float(chosen["relevance"]), 3),
        }

    # -- STEP 1: RETRIEVE (retrieval tier) --------------------------------
    def retrieve(self, facts: dict) -> list[dict]:
        started_at, t0 = _now(), time.perf_counter()
        query = SituationQuery(
            task_type=facts["task_type"],
            criticality=facts["criticality"],
            alertness_score=float(facts["alertness_score"]),
            workload_score=float(facts["workload_score"]),
            circadian_flag=bool(facts["circadian_flag"]),
            phase=facts.get("phase", "execution"),
        )
        candidates = self.retriever.get_relevant_documents(query)
        self._payloads = [self._payload_full(c) for c in candidates]
        self.trail.append(
            step="RETRIEVE",
            tier="retrieval",
            detail=(
                f"Embedded the Situation and queried the procedure store via "
                f"{self.retriever.backend_name}; returned top-{len(candidates)} candidates "
                f"including topical near-misses."
            ),
            inputs={"query_text": query.to_text(), "top_k": THRESHOLDS.retrieval_top_k},
            outputs={"candidates": [c.as_dict() for c in candidates]},
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            started_at=started_at,
        )
        return self._payloads

    # -- STEP 2: ADMISSIBILITY (deterministic, every candidate) -----------
    def admissibility(self, facts: dict, payloads: list[dict]) -> dict[str, AdmissibilityResult]:
        """Check every candidate's compiled preconditions, before the model speaks.

        Does not filter. A near-miss is inadmissible by construction, and
        dropping it here would hand the model a pre-cleaned candidate set --
        which is the same mistake as showing it ``applies_when``, arrived at
        from the other direction.
        """
        started_at, t0 = _now(), time.perf_counter()
        results = {p["passage_id"]: check(p["applies_when"], p["prescribes"], facts) for p in payloads}
        admissible = sorted(pid for pid, r in results.items() if r.admissible)
        self.trail.append(
            step="ADMISSIBILITY",
            tier="deterministic",
            detail=(
                f"Evaluated the compiled preconditions of all {len(results)} retrieved candidates "
                f"independently of the reasoning tier. "
                + (f"Admissible: {', '.join(admissible)}." if admissible else "None admissible.")
            ),
            inputs={"checked": sorted(results), "situation_domain": "crew_alertness"},
            outputs={
                "admissible": admissible,
                "clauses": {pid: r.as_dicts() for pid, r in results.items()},
            },
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            started_at=started_at,
        )
        return results

    # -- STEP 3: SELECT (reasoning tier, prose only) ----------------------
    def select(self, facts: dict, payloads: list[dict]) -> dict:
        """Ask the model which passage governs, giving it nothing but the prose."""
        started_at = _now()
        redacted = [self._payload_redacted(p) for p in payloads]
        prompt = SELECT_PROMPT.format(
            facts=json.dumps(facts, indent=2, default=str),
            candidates=json.dumps(redacted, indent=2, default=str),
        )
        completion, latency = self._call("SELECT", prompt, {"facts": facts, "candidates": redacted})
        selection = json.loads(completion)
        governing_id = selection.get("governing_passage_id")
        rejected = selection.get("rejected", [])

        self.trail.append(
            step="SELECT",
            tier="reasoning",
            detail=(
                f"Model read {len(redacted)} passages as prose and proposed {governing_id} as governing."
                if governing_id
                else "Model read the candidate passages as prose and reported that none govern this situation."
            ),
            inputs={"prompt": prompt, "provider": self.llm.provider, "model_id": self.llm.model_id},
            outputs={
                "governing_passage_id": governing_id,
                "reason": selection.get("reason", ""),
                "rejected": rejected,
                "latency_ms": round(latency, 1),
            },
            duration_ms=latency,
            started_at=started_at,
        )
        return {"governing_passage_id": governing_id, "rejected": rejected}

    # -- STEP 4: VERIFY (deterministic; the checker disposes) -------------
    def verify(self, admissibility: dict[str, AdmissibilityResult], selection: dict) -> Verdict:
        governing_id = selection.get("governing_passage_id")
        admissible_ids = sorted(pid for pid, r in admissibility.items() if r.admissible)
        # Structural check first: a passage outside the candidate set was never
        # retrieved, so the checker has no verdict on it and never will. A real
        # provider can emit an identifier it invented, and hard rule 3 has to
        # hold by construction rather than by trusting the completion.
        in_candidate_set = governing_id in admissibility
        selected = admissibility.get(governing_id) if governing_id else None

        if governing_id and not in_candidate_set:
            verdict = Verdict(
                verified=False,
                passage_id=None,
                model_selected=governing_id,
                checker_disagreed=True,
                admissible_ids=admissible_ids,
                clauses=[],
                reason="checker_model_disagreement",
                reason_label="Selection outside the candidate set",
                detail=f"the reasoning tier named {governing_id}, which was not among the retrieved candidates",
                explanation=(
                    f"The reasoning tier proposed {governing_id} as the governing passage, but no passage "
                    f"with that identifier was retrieved for this Situation. The deterministic checker "
                    f"therefore holds no verdict on it and HAVEN will not cite a passage it did not read. "
                    f"The decision is escalated."
                ),
            )
        elif governing_id and selected is not None and not selected.admissible:
            unmet = [c.model_dump() for c in selected.unmet]
            detail = "; ".join(c["explanation"] for c in unmet)
            verdict = Verdict(
                verified=False,
                passage_id=None,
                model_selected=governing_id,
                checker_disagreed=True,
                admissible_ids=admissible_ids,
                clauses=selected.as_dicts(),
                reason="precondition_unmet",
                reason_label="Precondition not satisfied",
                detail=detail,
                explanation=(
                    f"The reasoning tier proposed {governing_id} as the governing passage. The "
                    f"deterministic checker independently evaluated that passage's compiled "
                    f"preconditions and found {len(unmet)} of them unsatisfied: {detail}. A passage may "
                    f"not be cited unless every precondition holds, so the decision is escalated rather "
                    f"than issued."
                ),
            )
        elif governing_id and selected is not None:
            verdict = Verdict(
                verified=True,
                passage_id=governing_id,
                model_selected=governing_id,
                checker_disagreed=False,
                admissible_ids=admissible_ids,
                clauses=selected.as_dicts(),
                reason="",
                reason_label="",
                detail="",
                explanation="",
            )
        elif admissible_ids:
            # The model found nothing; the checker found something. HAVEN never
            # promotes a passage the model did not select, and it does not
            # proceed on a disagreement either. Both directions fail closed.
            verdict = Verdict(
                verified=False,
                passage_id=None,
                model_selected=None,
                checker_disagreed=True,
                admissible_ids=admissible_ids,
                clauses=[],
                reason="checker_model_disagreement",
                reason_label="Checker and reasoning tier disagree",
                detail=(
                    f"the reasoning tier read no governing passage, while the checker found "
                    f"{', '.join(admissible_ids)} admissible"
                ),
                explanation=(
                    f"The reasoning tier read the candidate passages and reported that none govern this "
                    f"Situation. The deterministic checker independently found {', '.join(admissible_ids)} "
                    f"admissible. HAVEN does not promote a passage the reasoning tier did not select, and "
                    f"it does not issue a recommendation the two tiers disagree about. The disagreement "
                    f"itself is the finding, and the decision is escalated with both views recorded."
                ),
            )
        else:
            # Both tiers agree there is nothing here. The refusal keeps the
            # model's own stated reason for the closest candidate, because
            # "nothing governs" is more useful to an operator with the reading
            # attached than without it.
            stated = [r.get("why", "") for r in selection.get("rejected", []) if r.get("why")]
            verdict = Verdict(
                verified=False,
                passage_id=None,
                model_selected=None,
                checker_disagreed=False,
                admissible_ids=[],
                clauses=[],
                reason="no_governing_procedure",
                reason_label="No governing procedure",
                detail=stated[0] if stated else "no retrieved passage states preconditions matching this situation",
                explanation="",
            )

        started_at, t0 = _now(), time.perf_counter()
        self.trail.append(
            step="VERIFY",
            tier="deterministic",
            detail=(
                f"Checker confirmed every compiled precondition of {verdict.passage_id}; the model's selection stands."
                if verdict.verified
                else f"Checker did not confirm the reasoning tier's selection ({verdict.detail}). Failing closed."
            ),
            inputs={"model_selected": governing_id, "checker_admissible": admissible_ids},
            outputs={
                "verified": verdict.verified,
                "checker_disagreed": verdict.checker_disagreed,
                "refusal_reason": verdict.reason or None,
                "clauses": verdict.clauses,
            },
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            started_at=started_at,
        )
        return verdict

    # -- STEP 5: FUSE -----------------------------------------------------
    def fuse(self, facts: dict, passage) -> str:
        started_at = _now()
        allowed = _allowed_numbers(facts, f"{passage.doc} {passage.section} {passage.text}")
        fuse_prompt = FUSE_PROMPT.format(
            facts=json.dumps(facts, indent=2, default=str),
            passage_id=passage.passage_id,
            doc=passage.doc,
            section=passage.section,
            passage_text=passage.text,
        )
        justification, latency = self._call(
            "FUSE",
            fuse_prompt,
            {
                "facts": facts,
                "passage": {
                    "doc": passage.doc,
                    "section": passage.section,
                    "title": passage.title,
                    "text": passage.text,
                },
            },
        )
        assert_no_novel_numbers(justification, allowed)
        self.trail.append(
            step="FUSE",
            tier="reasoning",
            detail="Fused crew alertness state, task criticality, and the verified rule into one justification.",
            inputs={"prompt": fuse_prompt},
            outputs={"justification": justification, "numeric_integrity": "verified", "latency_ms": round(latency, 1)},
            duration_ms=latency,
            started_at=started_at,
        )
        return justification

    # -- STEP 6: GENERATE -------------------------------------------------
    def generate(
        self,
        facts: dict,
        passage,
        justification: str,
        verdict: Verdict,
        payloads: list[dict],
        rejected: list[dict],
    ) -> ReasoningOutcome:
        started_at = _now()
        allowed = _allowed_numbers(facts, f"{passage.doc} {passage.section} {passage.text}")
        gen_prompt = GENERATE_PROMPT.format(
            action=passage.prescribes,
            doc=passage.doc,
            section=passage.section,
            justification=justification,
            facts=json.dumps(facts, indent=2, default=str),
        )
        rationale, latency = self._call(
            "GENERATE",
            gen_prompt,
            {
                "action": passage.prescribes,
                "doc": passage.doc,
                "section": passage.section,
                "justification": justification,
            },
        )
        assert_no_novel_numbers(rationale, allowed)

        citation = {
            "doc": passage.doc,
            "section": passage.section,
            "title": passage.title,
            "passage_id": passage.passage_id,
        }
        # Hard rule 3: no citation, no recommendation.
        if passage.passage_id not in BY_ID:
            return self.refuse(facts, payloads, None, "cited passage did not resolve in the corpus")

        self.trail.append(
            step="GENERATE",
            tier="reasoning",
            detail=f"Produced the operator-facing recommendation cited to {passage.doc} section {passage.section}.",
            inputs={"prompt": gen_prompt},
            outputs={
                "recommendation": rationale,
                "citation": citation,
                "numeric_integrity": "verified",
                "latency_ms": round(latency, 1),
            },
            duration_ms=latency,
            started_at=started_at,
        )

        return ReasoningOutcome(
            outcome="recommendation",
            action=passage.prescribes,
            citation=citation,
            rationale=rationale,
            justification=justification,
            candidates=payloads,
            rejected=rejected,
            verified_clauses=verdict.clauses,
            model_selected=verdict.model_selected,
        )

    # -- refusal ---------------------------------------------------------
    def refuse_verdict(
        self,
        facts: dict,
        payloads: list[dict],
        verdict: Verdict,
        rejected: list[dict],
    ) -> ReasoningOutcome:
        """Turn VERIFY's disposition into the structured escalation it implies."""
        return self.refuse(
            facts,
            payloads,
            self._best(payloads, verdict.model_selected),
            verdict.detail,
            rejected=rejected,
            candidates=payloads,
            reason=verdict.reason,
            reason_label=verdict.reason_label,
            explanation=verdict.explanation or None,
            failed_clauses=verdict.unmet,
            model_selected=verdict.model_selected,
            checker_disagreed=verdict.checker_disagreed,
        )

    def refuse(
        self,
        facts: dict,
        payloads: list[dict],
        best: dict | None,
        reason_detail: str,
        rejected: list[dict] | None = None,
        candidates: list[dict] | None = None,
        reason: str = "no_governing_procedure",
        reason_label: str = "No governing procedure",
        explanation: str | None = None,
        failed_clauses: list[dict] | None = None,
        model_selected: str | None = None,
        checker_disagreed: bool = False,
    ) -> ReasoningOutcome:
        started_at, t0 = _now(), time.perf_counter()
        searched = sorted({p["doc"] for p in payloads}) or ["(no candidates returned)"]
        refusal = {
            "reason": reason,
            "reason_label": reason_label,
            "searched": searched,
            "best_candidate": best,
            # Display-only. Nothing above branches on it; it is here so the
            # console can still show what similarity the closest candidate
            # scored, next to the clause that actually decided the outcome.
            "gate": THRESHOLDS.relevance_gate,
            "explanation": explanation
            or (
                f"The procedure store was searched across {len(searched)} documents. "
                f"The closest candidate was rejected because {reason_detail}. "
                f"No passage in the corpus states preconditions matching this situation, so no "
                f"recommendation can be grounded in procedure. Escalating rather than inferring one."
            ),
            "escalate_to": "flight_director",
            "failed_clauses": failed_clauses or [],
            "model_selected": model_selected,
            "checker_disagreed": checker_disagreed,
        }
        self.trail.append(
            step="REFUSE",
            tier="orchestration",
            detail=(
                f"No passage survived verification ({reason}). Emitted a structured escalation instead "
                f"of a recommendation."
            ),
            inputs={"searched": searched, "model_selected": model_selected},
            outputs=refusal,
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            started_at=started_at,
        )
        return ReasoningOutcome(
            outcome="refusal",
            refusal=refusal,
            candidates=candidates or payloads,
            rejected=rejected or [],
            failed_clauses=failed_clauses or [],
            model_selected=model_selected,
            checker_disagreed=checker_disagreed,
        )

    # -- degraded mode ---------------------------------------------------
    def degrade(self, facts: dict, reason: str) -> ReasoningOutcome:
        """Provider outage or rate limit: fall back and say so, loudly.

        The fallback is the deterministic tier's own view plus the retrieved
        passages. It never fabricates reasoning -- it reports that reasoning is
        unavailable and hands the operator the raw evidence. Called from
        whichever reasoning node the provider died in; every node after it is
        inert once an outcome exists.
        """
        self.trail.append(
            step="DEGRADED",
            tier="orchestration",
            detail=f"Reasoning provider unavailable: {reason}. Fell back to the cached deterministic path.",
            inputs={"provider": self.llm.provider},
            outputs={"mode": "degraded"},
        )
        searched = sorted({p["doc"] for p in self._payloads})
        outcome = self.refuse(
            facts,
            self._payloads,
            None,
            "the reasoning provider was unavailable",
            reason="provider_unavailable",
            reason_label="Reasoning tier unavailable",
            explanation=(
                f"Retrieval completed and returned candidates across {len(searched)} documents, but the "
                f"reasoning provider could not be reached ({reason}). No cached reasoning path exists for "
                f"this Situation. The deterministic evidence below is unaffected and remains valid; what "
                f"is missing is the procedure interpretation. HAVEN will not select a rule without the "
                f"reasoning tier, so the decision is escalated with the evidence attached."
            ),
        )
        outcome.degraded = True
        outcome.degraded_reason = reason
        return outcome

    # -- regeneration after a deterministic downgrade --------------------
    def regenerate(self, facts: dict, passage, action: str, justification: str) -> str:
        """Re-run GENERATE when a deterministic screen changes the action.

        The screen may veto the primary action, but the operator-facing text
        must then describe what is actually being recommended. Rewriting it in
        the engine would put generated prose outside the audited flow, so the
        regeneration is a logged reasoning step like any other.
        """
        started_at = _now()
        allowed = _allowed_numbers(facts, f"{passage.doc} {passage.section} {passage.text}")
        prompt = GENERATE_PROMPT.format(
            action=action,
            doc=passage.doc,
            section=passage.section,
            justification=justification,
            facts=json.dumps(facts, indent=2, default=str),
        )
        rationale, latency = self._call(
            "GENERATE",
            prompt,
            {
                "action": action,
                "doc": passage.doc,
                "section": passage.section,
                "justification": justification,
            },
        )
        assert_no_novel_numbers(rationale, allowed)
        self.trail.append(
            step="GENERATE_FALLBACK",
            tier="reasoning",
            detail=(
                f"Schedule-impact screen vetoed the primary action; regenerated the recommendation for "
                f"the fallback action prescribed by the same passage ({action})."
            ),
            inputs={"prompt": prompt, "action": action},
            outputs={"recommendation": rationale, "numeric_integrity": "verified", "latency_ms": round(latency, 1)},
            duration_ms=latency,
            started_at=started_at,
        )
        return rationale


__all__ = ["LLMUnavailable", "ReasoningFlow", "ReasoningOutcome", "Verdict"]
