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

Read the candidate passages below and identify which single passage governs the situation, or
report that none do.

A passage governs only if its own text establishes that it applies to this operation, in this
mission phase, and to the operator's alertness state. Topical similarity is not sufficient.
Passages frequently disclaim jurisdiction in their own wording -- a passage that says it covers
a planning activity, vehicle state, suit systems, or that crew rest is assessed elsewhere, does
not govern an execution-phase crew-alertness situation. Read for those limits.

You are given no structured metadata and no precondition table. Judge from the text.
Your selection is a proposal: it is checked against the compiled rule independently before
anything is issued, so name the passage you can defend from its wording, and name none if none
fits. Refusing is a correct answer.

SITUATION (deterministic tier; treat as fact):
{facts}

CANDIDATE PASSAGES:
{candidates}

Respond with JSON only:
{{"governing_passage_id": "<id or null>", "reason": "<one sentence>", "rejected": [{{"passage_id": "..", "why": ".."}}]}}
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

Write the operator-facing recommendation. State the action the procedure requires, then the
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
    """Deterministic stand-in for Granite, reasoning from prose.

    In v1 the SELECT step read each candidate's compiled ``applies_when`` and
    evaluated it with Python conditionals. That made the "reasoning tier" a
    rules engine wearing a model's clothes: it was handed the answer key, and
    the skill it demonstrated would transfer to no real procedure library. Since
    v2 the candidate payload reaching any provider is redacted to prose
    (``passage_id``, ``doc``, ``section``, ``title``, ``text``) and this mock
    judges from the text, as the model it stands in for must.

    The corpus was written to make that possible. Every near-miss states its own
    limit in plain language -- "Sleep shifting is a planning activity", "This
    section governs vehicle state and approach geometry only", "is not assessed
    by this section" -- because a real rulebook does the same.

    **It is deliberately fallible.** Reading prose, it cannot evaluate a
    threshold the passage does not quantify: "below the nominal execution
    threshold" names no number, so nothing here can confirm it. That is exactly
    the class of judgement the deterministic checker owns, and VERIFY is what
    makes a wrong proposal safe. A mock that could not be wrong would hide the
    mechanism this system exists to demonstrate.
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
    # Phrases by which a passage disclaims jurisdiction over crew alertness
    # during execution. Checked first, and before anything else, because a
    # passage that has already said "not me" has settled the question -- and
    # because several near-misses would otherwise pass the later checks on
    # vocabulary they use while disclaiming it (OPS-DUTY-03 3.5 talks about
    # recovery periods in the same breath as declining to gate execution).
    _DISCLAIMERS: tuple[tuple[str, str], ...] = (
        ("planning activity", "passage governs the planning phase, not execution"),
        ("completed before the execution period", "passage governs the planning phase, not execution"),
        ("does not itself gate task execution", "passage sets planning limits and does not gate execution"),
        ("defines planning limits", "passage sets planning limits and does not gate execution"),
        ("governs vehicle state", "passage governs vehicle state, not crew alertness"),
        ("approach geometry only", "passage governs vehicle state, not crew alertness"),
        ("is not assessed by this section", "passage defers crew rest status to another section"),
        ("verified separately", "passage defers crew rest status to another section"),
    )

    # Vocabulary that marks a passage as actually addressing operator condition.
    # Matched on word boundaries: "restarted" is not "rest".
    _CREW_STATE_TERMS: tuple[str, ...] = (
        "alertness",
        "alert phase",
        "fatigue",
        "sleep",
        "sleepiness",
        "circadian",
        "rest",
        "duty ceiling",
        "duty load",
        "recovery period",
    )

    # How each operation is named in procedure prose. A rulebook does not say
    # "orbital_burn"; it says "propulsive manoeuvre". Reading the corpus means
    # recognising the operation from the words it is written in.
    _OPERATION_TERMS: dict[str, tuple[str, ...]] = {
        "orbital_burn": ("propulsive", "burn", "manoeuvre", "reboost"),
        "docking": ("docking", "proximity operation", "approach corridor", "range gate"),
        "eva": ("extravehicular", "egress", "suited", "pre-breathe"),
        "robotics_capture": ("robotic", "capture"),
        "hatch_operation": ("hatch",),
        "science_ops": ("payload", "science"),
        "maintenance": ("maintenance",),
        "medical_contingency": ("medical",),
    }

    # A passage may scope itself by class rather than by operation. Only counts
    # where the situation is in that class.
    _SAFETY_CRITICAL_SCOPE = "safety-critical task"

    @staticmethod
    def _mentions(text: str, term: str) -> bool:
        return re.search(rf"\b{re.escape(term)}", text) is not None

    @classmethod
    def _disclaims(cls, text: str) -> str | None:
        for phrase, why in cls._DISCLAIMERS:
            if phrase in text:
                return why
        return None

    @classmethod
    def _addresses_crew_state(cls, text: str) -> bool:
        return any(cls._mentions(text, term) for term in cls._CREW_STATE_TERMS)

    @classmethod
    def _covers_operation(cls, text: str, task_type: str, criticality: str) -> bool:
        if criticality == "high" and cls._SAFETY_CRITICAL_SCOPE in text:
            return True
        return any(cls._mentions(text, term) for term in cls._OPERATION_TERMS.get(task_type, ()))

    def _select(self, context: dict[str, Any]) -> dict:
        """Judge each candidate from its text, as the real model is prompted to.

        Four readings, in order, on the passage's own words plus the
        deterministic fact set -- never on compiled preconditions, which this
        method is not given:

          1. does the passage disclaim jurisdiction?
          2. does it address the operator's condition at all, or only hardware?
          3. does it name this operation, or scope itself to tasks of this class?
          4. does it condition itself on a crew state the facts report absent?

        Step 4 is limited to conditions a reader can actually settle: the
        circadian trough is stated categorically in prose and reported
        categorically in the facts, so the two can be compared. A threshold the
        passage does not quantify ("below the nominal execution threshold")
        cannot be, and is deliberately left to the deterministic checker.

        The first survivor is the proposal. Later survivors are reported as
        rejected in favour of it -- the prompt asks for a single governing
        passage, and retrieval order is the model's only ranking signal.
        """
        facts = context["facts"]
        task_type = str(facts.get("task_type", "")).replace("_", " ")
        criticality = str(facts.get("criticality", ""))
        in_circadian_trough = bool(facts.get("circadian_flag"))

        governing: str | None = None
        rejected: list[dict] = []

        def reject(passage_id: str, why: str) -> None:
            rejected.append({"passage_id": passage_id, "why": why})

        for cand in context["candidates"]:
            passage_id = cand["passage_id"]
            text = f"{cand.get('title', '')}. {cand['text']}".lower()

            disclaimer = self._disclaims(text)
            if disclaimer:
                reject(passage_id, disclaimer)
                continue
            if not self._addresses_crew_state(text):
                reject(passage_id, "passage does not address operator alertness, fatigue or rest state")
                continue
            if not self._covers_operation(text, str(facts.get("task_type", "")), criticality):
                reject(passage_id, f"passage does not name {task_type} among the operations it covers")
                continue
            if "circadian trough" in text and not in_circadian_trough:
                reject(
                    passage_id,
                    "passage applies where the task falls inside the operator's circadian trough; this one does not",
                )
                continue
            if governing is None:
                governing = passage_id
            else:
                reject(passage_id, "also addresses this condition, but the selected passage is more specific")

        return {
            "governing_passage_id": governing,
            "reason": (
                f"passage addresses operator alertness for {task_type} during execution and disclaims nothing"
                if governing
                else f"no candidate passage addresses operator alertness for {task_type} during execution"
            ),
            "rejected": rejected,
        }

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
            f"{passage['title'][0].lower()}{passage['title'][1:]} and the situation falls inside the "
            f"conditions its text states."
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


PROVIDERS: dict[str, type[ReasoningLLM]] = {
    "watsonx": WatsonxGraniteLLM,
    "ollama": OllamaGraniteLLM,
    "mock": MockGraniteLLM,
}


def build_llm(provider: str | None = None) -> ReasoningLLM:
    """The configured provider, or a named one.

    The override exists so the evaluation harness can measure a provider without
    mutating process configuration, and so the provider chain can construct each
    link by name. An unknown name falls back to the mock rather than raising:
    the offline stand-in is always a safe answer to "which provider?", and
    failing to start over a typo in an environment variable would be worse.
    """
    name = (provider or LLM.provider or "mock").strip().lower()
    return PROVIDERS.get(name, MockGraniteLLM)()
