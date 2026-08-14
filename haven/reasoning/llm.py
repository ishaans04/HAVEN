"""Reasoning-tier LLM adapters.

Three interchangeable providers behind one interface:

  ``MockGraniteLLM``    scripted stand-in. Runs offline, deterministically, and
                        is what the prototype ships on. It receives the same
                        prompts a real model would and returns the same shapes.
  ``OllamaGraniteLLM``  local Granite via Ollama -- free unlimited iteration.
  ``WatsonxGraniteLLM`` IBM watsonx.ai Granite -- integration and live demo.

The prompts below are the real prompts. The mock exists so the demo has no
external dependency, not to avoid writing them.

SAFETY: no adapter is ever asked for a number. ``assert_no_novel_numbers``
enforces that every numeral in a completion also appears in the deterministic
fact set injected into the prompt (PRD 6.1).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from haven.config import LLM

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


class LLMUnavailable(RuntimeError):
    """Raised when the provider is unreachable. Triggers degraded mode."""


class NumericIntegrityError(RuntimeError):
    """Raised when a completion contains a number the deterministic tier never supplied."""


def assert_no_novel_numbers(text: str, allowed: set[str]) -> None:
    """Hard rule 1: numbers are computed, never generated.

    Every numeral in ``text`` must appear in the injected fact set. A violation
    is a safety fault, not a formatting quirk, so it raises.
    """
    for found in _NUMBER.findall(text):
        normalised = found.rstrip("0").rstrip(".") if "." in found else found
        if found not in allowed and normalised not in allowed:
            raise NumericIntegrityError(
                f"Completion contains numeric value {found!r} not supplied by the deterministic tier"
            )


# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are the reasoning component of HAVEN, a flight-safety decision-support system. "
    "You interpret operating procedures. You never produce numbers: every figure is supplied "
    "to you by a deterministic engine and must be echoed exactly as given. You never invent, "
    "paraphrase, or extrapolate a procedure. You may only cite passages present in the "
    "candidate set. If no candidate passage actually governs the situation, you must say so "
    "rather than choose the closest one. Refusing is a correct answer."
)

SELECT_PROMPT = """TASK: SELECT

Identify which single candidate passage governs the situation below, or report that none do.
A passage governs only if the situation satisfies its stated preconditions. Topical similarity
is not sufficient: a passage about the same task type that governs a different domain (vehicle
state, suit systems, staffing) or a different mission phase (planning rather than execution)
does NOT govern.

SITUATION (deterministic tier; treat as fact):
{facts}

CANDIDATE PASSAGES:
{candidates}

Respond with JSON only:
{{"governing_passage_id": "<id or null>", "relevance": <0-1>, "rejected": [{{"passage_id": "..", "why": ".."}}]}}
"""

FUSE_PROMPT = """TASK: FUSE

Combine exactly three facts into one reasoned justification: the crew alertness state, the
task criticality, and the selected governing rule. Use only the numbers given below, written
exactly as given. Do not introduce any other figure. Two or three sentences.

DETERMINISTIC FACTS:
{facts}

GOVERNING PASSAGE ({passage_id}, {doc} section {section}):
{passage_text}

Respond with the justification text only.
"""

GENERATE_PROMPT = """TASK: GENERATE

Write the operator-facing recommendation. State the action the procedure prescribes, then the
justification. Cite the procedure by document and section. Use only the numbers given; do not
introduce any other figure.

PRESCRIBED ACTION: {action}
CITATION: {doc} section {section}
JUSTIFICATION: {justification}
DETERMINISTIC FACTS:
{facts}

Respond with the recommendation text only.
"""


@dataclass
class LLMCall:
    """One provider round-trip, recorded verbatim in the audit trail."""

    task: str
    prompt: str
    completion: str
    provider: str
    model_id: str
    latency_ms: float


class ReasoningLLM:
    """Provider interface."""

    provider = "base"

    @property
    def model_id(self) -> str:
        return LLM.model_id

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:
        raise NotImplementedError


# --------------------------------------------------------------------------
# Mock provider
# --------------------------------------------------------------------------
class MockGraniteLLM(ReasoningLLM):
    """Deterministic stand-in for Granite.

    The SELECT step is genuinely a decision, not a lookup: it evaluates each
    candidate's declared preconditions against the situation and rejects
    passages that are merely similar. That is the behaviour the real model is
    prompted to perform, reproduced deterministically so the demo cannot fail.
    """

    provider = "mock-granite"

    @property
    def model_id(self) -> str:
        return "granite-3-8b-instruct (scripted stand-in)"

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:
        if task == "SELECT":
            return json.dumps(self._select(context))
        if task == "FUSE":
            return self._fuse(context)
        if task == "GENERATE":
            return self._generate(context)
        raise ValueError(f"Unknown reasoning task {task!r}")

    # -- SELECT ----------------------------------------------------------
    @staticmethod
    def _unmet_conditions(applies_when: dict, facts: dict) -> list[str]:
        unmet: list[str] = []
        if "task_types" in applies_when and facts["task_type"] not in applies_when["task_types"]:
            unmet.append(
                f"passage is scoped to {', '.join(applies_when['task_types'])}; "
                f"situation task type is {facts['task_type']}"
            )
        if "criticality_in" in applies_when and facts["criticality"] not in applies_when["criticality_in"]:
            unmet.append(
                f"passage applies at {'/'.join(applies_when['criticality_in'])} criticality; "
                f"situation is {facts['criticality']}"
            )
        if "alertness_below" in applies_when and facts["alertness_score"] >= applies_when["alertness_below"]:
            unmet.append("passage requires alertness below its execution threshold; situation is above it")
        if applies_when.get("requires_circadian_flag") and not facts["circadian_flag"]:
            unmet.append("passage requires the task to fall in the operator's circadian trough; it does not")
        if "workload_above" in applies_when and facts["workload_score"] <= applies_when["workload_above"]:
            unmet.append("passage requires sustained duty load above its ceiling; situation is below it")
        if "phase" in applies_when and applies_when["phase"] != facts.get("phase", "execution"):
            unmet.append(
                f"passage governs the {applies_when['phase']} phase; situation is in {facts.get('phase', 'execution')}"
            )
        if "domain" in applies_when:
            unmet.append(f"passage governs {applies_when['domain'].replace('_', ' ')}, not crew alertness")
        return unmet

    def _select(self, context: dict[str, Any]) -> dict:
        facts = context["facts"]
        candidates = context["candidates"]

        governing: dict | None = None
        rejected: list[dict] = []

        for cand in candidates:
            unmet = self._unmet_conditions(cand["applies_when"], facts)
            if unmet or not cand["prescribes"]:
                reason = unmet[0] if unmet else "passage states no prescribed action for this condition"
                rejected.append(
                    {
                        "passage_id": cand["passage_id"],
                        "why": reason,
                        "relevance": round(cand["relevance"] * 0.55, 3),
                    }
                )
                continue
            judged = round(min(0.98, cand["relevance"] + 0.12), 3)
            if governing is None or judged > governing["relevance"]:
                if governing is not None:
                    rejected.append(
                        {
                            "passage_id": governing["governing_passage_id"],
                            "why": "governing but lower relevance than the selected passage",
                            "relevance": governing["relevance"],
                        }
                    )
                governing = {"governing_passage_id": cand["passage_id"], "relevance": judged}
            else:
                rejected.append(
                    {
                        "passage_id": cand["passage_id"],
                        "why": "governing but lower relevance than the selected passage",
                        "relevance": round(min(0.98, cand["relevance"] + 0.12), 3),
                    }
                )

        if governing is None:
            best = max((r["relevance"] for r in rejected), default=0.0)
            return {"governing_passage_id": None, "relevance": best, "rejected": rejected}
        return {**governing, "rejected": rejected}

    # -- FUSE ------------------------------------------------------------
    @staticmethod
    def _fuse(context: dict[str, Any]) -> str:
        f = context["facts"]
        passage = context["passage"]
        clauses = [
            f"Predicted alertness for {f['crew_name']} at the scheduled time is {f['alertness_score']} "
            f"on the normalised scale, after {f['hours_awake']} hours awake and a trailing sleep debt "
            f"of {f['sleep_debt_h']} hours"
        ]
        if f["circadian_flag"]:
            clauses.append("and the task falls inside the operator's circadian trough")
        clauses.append(
            f"against a {f['criticality']}-criticality {f['task_type'].replace('_', ' ')} carrying a "
            f"weighted NASA-TLX workload of {f['workload_score']}"
        )
        return (
            f"{', '.join(clauses)}. "
            f"{passage['doc']} section {passage['section']} governs this combination directly: it addresses "
            f"{passage['title'][0].lower()}{passage['title'][1:]} and its stated preconditions are all "
            f"satisfied by the current state."
        )

    # -- GENERATE --------------------------------------------------------
    @staticmethod
    def _generate(context: dict[str, Any]) -> str:
        action_text = {
            "second_operator_verify": (
                "Assign a second qualified operator to independently verify the task parameters before execution."
            ),
            "short_rest_then_proceed": (
                "Insert a protected rest period before the task and re-evaluate alertness prior to commencement."
            ),
            "duty_rotation": "Rotate the assignment to a qualified operator inside duty limits.",
            "task_deferral": "Defer the task to the next available execution window.",
            "no_action_required": "Proceed as scheduled; no procedural intervention is required.",
        }[context["action"]]
        return (
            f"{action_text} {context['justification']} "
            f"This recommendation is issued under {context['doc']} section {context['section']} and requires "
            f"operator approval before any change is made to the execution package."
        )


# --------------------------------------------------------------------------
# Real providers
# --------------------------------------------------------------------------
class OllamaGraniteLLM(ReasoningLLM):
    """Local Granite via Ollama. Free, unlimited, used for development."""

    provider = "ollama-granite"

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:  # pragma: no cover
        import httpx

        try:
            response = httpx.post(
                f"{LLM.ollama_url}/api/chat",
                json={
                    "model": LLM.model_id,
                    "stream": False,
                    "options": {"temperature": 0.0},
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=LLM.request_timeout_s,
            )
            response.raise_for_status()
        except Exception as exc:
            raise LLMUnavailable(f"Ollama unreachable: {exc}") from exc
        return response.json()["message"]["content"].strip()


class WatsonxGraniteLLM(ReasoningLLM):
    """IBM watsonx.ai Granite. Reserved for integration and the live demo.

    The Lite tier is token-limited, which is why development runs on the mock or
    on local Ollama (PRD section 3, cost constraints).
    """

    provider = "watsonx-granite"

    def __init__(self) -> None:  # pragma: no cover
        if not (LLM.watsonx_api_key and LLM.watsonx_project_id):
            raise LLMUnavailable("WATSONX_API_KEY and WATSONX_PROJECT_ID must be set")
        self._token: str | None = None

    def _access_token(self) -> str:  # pragma: no cover
        import httpx

        if self._token:
            return self._token
        response = httpx.post(
            "https://iam.cloud.ibm.com/identity/token",
            data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": LLM.watsonx_api_key},
            timeout=LLM.request_timeout_s,
        )
        response.raise_for_status()
        self._token = response.json()["access_token"]
        return self._token

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:  # pragma: no cover
        import httpx

        try:
            response = httpx.post(
                f"{LLM.watsonx_url}/ml/v1/text/chat?version=2024-10-10",
                headers={"Authorization": f"Bearer {self._access_token()}"},
                json={
                    "model_id": LLM.model_id,
                    "project_id": LLM.watsonx_project_id,
                    "temperature": 0.0,
                    "max_tokens": 500,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=LLM.request_timeout_s,
            )
            response.raise_for_status()
        except Exception as exc:
            raise LLMUnavailable(f"watsonx.ai unreachable: {exc}") from exc
        return response.json()["choices"][0]["message"]["content"].strip()


def build_llm() -> ReasoningLLM:
    if LLM.provider == "watsonx":
        return WatsonxGraniteLLM()
    if LLM.provider == "ollama":
        return OllamaGraniteLLM()
    return MockGraniteLLM()
