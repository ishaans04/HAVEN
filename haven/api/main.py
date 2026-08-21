"""HAVEN API tier.

Thin by design: it validates against the locked contract, sequences nothing, and
decides nothing. All logic lives in the engine and the tiers beneath it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from haven import engine
from haven.config import BUILD_MODE, LLM, THRESHOLDS
from haven.contracts import (
    AuditRecord,
    DecisionRecord,
    DecisionRequest,
    EvaluationRequest,
    EvaluationResponse,
    ProcedureSummary,
    ScenarioSummary,
)
from haven.data.scenarios import BY_ID as SCENARIO_BY_ID
from haven.data.scenarios import SCENARIOS
from haven.rag.corpus import CORPUS, DOCS
from haven.rag.retriever import get_retriever
from haven.reasoning.audit import AUDIT
from haven.reasoning.chain import build_chain, configured_chain
from haven.reasoning.llm import LLMUnavailable, ReasoningLLM

app = FastAPI(
    title="HAVEN",
    description=(
        "Human Adaptation & Vitality Enhancement Network -- a fatigue-aware safety co-pilot. "
        "The deterministic tier owns every safety-critical number; the reasoning tier reads, "
        "selects, explains, or refuses; the human owns every decision."
    ),
    version="1.0.0",
)

# Only needed in development, where the console runs on its own port. In the
# shipped container both are served from one origin and no request is
# cross-origin at all.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class UnavailableLLM(ReasoningLLM):
    """Forces the degraded path, for the provider-outage scenario."""

    provider = "watsonx-granite (unreachable)"

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:
        raise LLMUnavailable("watsonx.ai returned 429: token quota exhausted for the current period")


@app.get("/api/health")
def health() -> dict:
    """What this process is actually configured to do.

    Both tier fields used to report something other than what runs. Reasoning
    reported ``LLM.provider`` -- the *single*-provider setting, which is still
    ``mock`` on any deployment configured with ``HAVEN_LLM_CHAIN``, so a server
    genuinely calling watsonx announced itself as running the offline stand-in.
    Retrieval reported ``RETRIEVAL.backend``, a v1 field describing a vector
    store Phase 5 replaced; the running tier is BM25, optionally fused with
    dense retrieval.

    Both were wrong in the same direction and in the worst possible place. The
    one question this endpoint exists to answer is "is this thing real, or is it
    the mock?", and it was answering it incorrectly for a correctly configured
    system. The values now come from the same places the evaluation response
    takes them from, so health and TierStatus cannot disagree.
    """
    return {
        "status": "ok",
        "build_mode": BUILD_MODE,
        "tiers": {
            "deterministic": "Three-Process Model of Alertness + NASA-TLX",
            "retrieval": get_retriever().backend_name,
            # The chain, not the single provider: which link answers is decided
            # per request and reported by TierStatus.served_by.
            "reasoning_provider": " -> ".join(configured_chain()),
            "reasoning_model": LLM.model_id,
        },
        "thresholds": {
            "alertness_trigger_high": THRESHOLDS.alertness_trigger_high,
            "workload_trigger": THRESHOLDS.workload_trigger,
            "relevance_gate": THRESHOLDS.relevance_gate,
            "alternate_min_alertness": THRESHOLDS.alternate_min_alertness,
        },
    }


@app.get("/api/scenarios", response_model=list[ScenarioSummary])
def list_scenarios() -> list[ScenarioSummary]:
    return [
        ScenarioSummary(
            id=s.id,
            title=s.title,
            subtitle=s.subtitle,
            note=s.note,
            demonstrates=s.demonstrates,
        )
        for s in SCENARIOS
    ]


@app.get("/api/procedures", response_model=list[ProcedureSummary])
def list_procedures() -> list[ProcedureSummary]:
    return [
        ProcedureSummary(
            passage_id=p.passage_id,
            doc=p.doc,
            section=p.section,
            title=p.title,
            task_types=p.task_types,
            source=f"{DOCS.get(p.doc, p.doc)} -- {p.source}",
            text=p.text,
            provenance=p.provenance,
            authority=p.authority,
            reviewed_by=p.reviewed_by,
            prescribes=p.prescribes,
            near_miss_note=p.near_miss_note,
        )
        for p in CORPUS
    ]


@app.post("/api/evaluate", response_model=EvaluationResponse)
def post_evaluate(request: EvaluationRequest) -> EvaluationResponse:
    # The chain rather than a single provider, so a watsonx outage falls through
    # to local Granite and then to the offline stand-in -- loudly, with
    # TierStatus naming the link that answered. The outage scenario keeps its
    # own unreachable provider, since demonstrating the degraded path is the
    # entire point of it.
    llm = UnavailableLLM() if request.scenario_id == "provider_outage" else build_chain()
    response = engine.evaluate(request, llm=llm)
    scenario = SCENARIO_BY_ID.get(request.scenario_id or "")
    if scenario:
        response.scenario_title = scenario.title
        response.scenario_note = scenario.note
    return response


@app.get("/api/scenarios/{scenario_id}/evaluate", response_model=EvaluationResponse)
def evaluate_scenario(scenario_id: str) -> EvaluationResponse:
    scenario = SCENARIO_BY_ID.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Unknown scenario {scenario_id!r}")
    request = EvaluationRequest.model_validate(scenario.build())
    return post_evaluate(request)


@app.get("/api/audit/{audit_ref}", response_model=AuditRecord)
def get_audit(audit_ref: str) -> AuditRecord:
    trail = AUDIT.get(audit_ref)
    if trail is None:
        raise HTTPException(status_code=404, detail=f"No audit record {audit_ref!r}")
    return AuditRecord.model_validate(trail.as_dict())


@app.post("/api/decisions", response_model=DecisionRecord)
def record_decision(request: DecisionRequest) -> DecisionRecord:
    """Stage 7: capture the human decision.

    HAVEN never actions anything itself. This endpoint records what the operator
    chose and why, which is also the input to the decision-learning loop.
    """
    record = DecisionRecord(
        decision_id=f"DEC-{uuid.uuid4().hex[:8].upper()}",
        situation_id=request.situation_id,
        audit_ref=request.audit_ref,
        decision=request.decision,
        operator=request.operator,
        reason=request.reason,
        recorded_at=datetime.now(timezone.utc),
    )
    AUDIT.record_decision(record.model_dump())
    trail = AUDIT.get(request.audit_ref)
    if trail is not None:
        trail.append(
            step="HUMAN_DECISION",
            tier="human",
            detail=f"Operator {request.decision} the recommendation.",
            inputs={"operator": request.operator},
            outputs={"decision": request.decision, "reason": request.reason, "decision_id": record.decision_id},
        )
        # The trail was sealed when the Situation was raised; this entry is
        # appended afterwards, so it needs flushing. put() inserts only what is
        # not already stored, so re-storing the trail rewrites nothing.
        AUDIT.put(trail)
    return record


@app.get("/api/decisions", response_model=list[DecisionRecord])
def list_decisions() -> list[DecisionRecord]:
    return [DecisionRecord.model_validate(d) for d in AUDIT.decisions()]


# --------------------------------------------------------------------------
# The console, served from the same origin as the API
# --------------------------------------------------------------------------
#
# Mounted last, and only if it has been built. Two consequences worth stating:
#
# * The mount is at "/" and would otherwise shadow every API route, so it has to
#   come after them. FastAPI matches in declaration order.
# * A missing export is not an error. Development runs the console on its own
#   port with `npm run dev`, and an API that refused to start without a built
#   frontend would make that workflow impossible.
CONSOLE_DIR = Path(__file__).resolve().parents[2] / "web" / "out"

if CONSOLE_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(CONSOLE_DIR), html=True), name="console")
