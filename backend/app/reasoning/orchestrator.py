"""The orchestration tier -- the IBM Bob reasoning flow (PRD 4.1).

RETRIEVE -> SELECT -> GATE -> (FUSE -> GENERATE) | REFUSE

Every step is timed and written to the hash-chained audit trail before the next
begins. The flow owns sequencing and logging. It does not own numbers, and it
does not make the final decision -- a human does.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.config import THRESHOLDS
from app.reasoning.audit import AuditTrail
from app.reasoning.llm import (
    FUSE_PROMPT,
    GENERATE_PROMPT,
    SELECT_PROMPT,
    LLMUnavailable,
    ReasoningLLM,
    assert_no_novel_numbers,
)
from app.retrieval.corpus import BY_ID
from app.retrieval.retriever import ProcedureRetriever, SituationQuery
from app.retrieval.vector_store import Candidate

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _allowed_numbers(facts: dict, extra: str = "") -> set[str]:
    """Numerals the reasoning tier is permitted to emit: exactly what it was given."""
    blob = json.dumps(facts, default=str) + " " + extra
    return set(_NUMBER.findall(blob))


class ReasoningFlow:
    """One evaluation of one Situation."""

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
    def _candidate_payload(c: Candidate) -> dict:
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

    # -- the flow --------------------------------------------------------
    def run(self, facts: dict) -> ReasoningOutcome:
        try:
            return self._run(facts)
        except LLMUnavailable as exc:
            return self._degraded(facts, str(exc))

    def _run(self, facts: dict) -> ReasoningOutcome:
        # ---- STEP 1: RETRIEVE (retrieval tier) --------------------------
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
        payloads = [self._candidate_payload(c) for c in candidates]
        self._payloads = payloads
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

        if not candidates:
            return self._refuse(facts, [], None, "retrieval returned no candidate passages")

        # ---- STEP 2: SELECT (reasoning tier) ----------------------------
        started_at = _now()
        prompt = SELECT_PROMPT.format(
            facts=json.dumps(facts, indent=2, default=str),
            candidates=json.dumps(
                [{k: v for k, v in p.items() if k != "near_miss_note"} for p in payloads],
                indent=2,
                default=str,
            ),
        )
        completion, latency = self._call("SELECT", prompt, {"facts": facts, "candidates": payloads})
        selection = json.loads(completion)
        governing_id = selection.get("governing_passage_id")
        judged_relevance = float(selection.get("relevance") or 0.0)
        rejected = selection.get("rejected", [])

        self.trail.append(
            step="SELECT",
            tier="reasoning",
            detail=(
                f"Model identified {governing_id} as the governing passage."
                if governing_id
                else "Model reported that no candidate passage governs this situation."
            ),
            inputs={"prompt": prompt, "provider": self.llm.provider, "model_id": self.llm.model_id},
            outputs={
                "governing_passage_id": governing_id,
                "relevance": judged_relevance,
                "rejected": rejected,
                "latency_ms": round(latency, 1),
            },
            duration_ms=latency,
            started_at=started_at,
        )

        # ---- STEP 3: GATE (deterministic branch) ------------------------
        started_at, t0 = _now(), time.perf_counter()
        passes = bool(governing_id) and judged_relevance >= THRESHOLDS.relevance_gate
        self.trail.append(
            step="GATE",
            tier="orchestration",
            detail=(
                f"Relevance {judged_relevance} {'meets' if passes else 'falls below'} the gate "
                f"of {THRESHOLDS.relevance_gate}."
            ),
            inputs={"relevance": judged_relevance, "gate": THRESHOLDS.relevance_gate},
            outputs={"branch": "FUSE" if passes else "REFUSE"},
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            started_at=started_at,
        )

        if not passes:
            best = None
            pool = rejected or []
            if pool:
                top = max(pool, key=lambda r: r.get("relevance", 0.0))
                passage = BY_ID.get(top["passage_id"])
                best = {
                    "doc": passage.doc if passage else top["passage_id"],
                    "section": passage.section if passage else "",
                    "relevance": round(float(top.get("relevance", 0.0)), 3),
                }
            reason = pool[0]["why"] if pool else "no retrieved passage stated preconditions matching this situation"
            return self._refuse(facts, payloads, best, reason, rejected=pool, candidates=payloads)

        passage = BY_ID[governing_id]
        allowed = _allowed_numbers(facts, f"{passage.doc} {passage.section} {passage.text}")

        # ---- STEP 4: FUSE ----------------------------------------------
        started_at = _now()
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
            detail="Fused crew alertness state, task criticality, and the selected rule into one justification.",
            inputs={"prompt": fuse_prompt},
            outputs={"justification": justification, "numeric_integrity": "verified", "latency_ms": round(latency, 1)},
            duration_ms=latency,
            started_at=started_at,
        )

        # ---- STEP 5: GENERATE ------------------------------------------
        started_at = _now()
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
            return self._refuse(facts, payloads, None, "cited passage did not resolve in the corpus")

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
        )

    # -- refusal ---------------------------------------------------------
    def _refuse(
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
    ) -> ReasoningOutcome:
        started_at, t0 = _now(), time.perf_counter()
        searched = sorted({p["doc"] for p in payloads}) or ["(no candidates returned)"]
        refusal = {
            "reason": reason,
            "reason_label": reason_label,
            "searched": searched,
            "best_candidate": best,
            "gate": THRESHOLDS.relevance_gate,
            "explanation": explanation
            or (
                f"The procedure store was searched across {len(searched)} documents. "
                f"The closest candidate was rejected because {reason_detail}. "
                f"No passage in the corpus states preconditions matching this situation, so no "
                f"recommendation can be grounded in procedure. Escalating rather than inferring one."
            ),
            "escalate_to": "flight_director",
        }
        self.trail.append(
            step="REFUSE",
            tier="orchestration",
            detail="No candidate cleared the relevance gate. Emitted a structured escalation instead of a recommendation.",
            inputs={"searched": searched, "gate": THRESHOLDS.relevance_gate},
            outputs=refusal,
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            started_at=started_at,
        )
        return ReasoningOutcome(
            outcome="refusal",
            refusal=refusal,
            candidates=candidates or payloads,
            rejected=rejected or [],
        )

    # -- degraded mode ---------------------------------------------------
    def _degraded(self, facts: dict, reason: str) -> ReasoningOutcome:
        """Provider outage or rate limit: fall back and say so, loudly.

        The fallback is the deterministic tier's own view plus the retrieved
        passage. It never fabricates reasoning -- it reports that reasoning is
        unavailable and hands the operator the raw evidence.
        """
        self.trail.append(
            step="DEGRADED",
            tier="orchestration",
            detail=f"Reasoning provider unavailable: {reason}. Fell back to the cached deterministic path.",
            inputs={"provider": self.llm.provider},
            outputs={"mode": "degraded"},
        )
        searched = sorted({p["doc"] for p in self._payloads})
        outcome = self._refuse(
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
