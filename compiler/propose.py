"""A model proposes preconditions. A human approves them. Neither happens live.

This is the one place in HAVEN where a model is asked to author something the
deterministic checker will later treat as ground truth, and the whole design
turns on that being an *offline* act with a person in the middle.

Live, it would defeat the architecture entirely. The checker's authority comes
from preconditions being fixed, reviewable, and signed off before any Situation
is evaluated; a model writing them at request time would be the model marking its
own homework with extra steps. Offline, with review, it is just a drafting aid —
the model reads a rule and suggests how to encode it, a human decides.

What the model may propose is deliberately narrow: only clauses in the checker's
own vocabulary, since a precondition the checker cannot evaluate is one it must
treat as unsatisfied, and a corpus full of those fails everything closed for no
useful reason.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from langchain_core.documents import Document

from haven.deterministic.preconditions import CLAUSE_VOCABULARY
from haven.reasoning.llm import ReasoningLLM
from haven.reasoning.parsing import ParseFailure, extract_json

#: Actions the corpus may prescribe. Matches contracts.ActionType exactly: a
#: passage prescribing anything else raises a KeyError out of the engine, which
#: is a 500 where a refusal belongs.
PRESCRIBABLE = (
    "second_operator_verify",
    "short_rest_then_proceed",
    "duty_rotation",
    "task_deferral",
    "no_action_required",
)

TASK_TYPES = (
    "orbital_burn",
    "docking",
    "eva",
    "robotics_capture",
    "hatch_operation",
    "science_ops",
    "maintenance",
    "medical_contingency",
)

EXTRACT_PROMPT = """TASK: EXTRACT PRECONDITIONS

Read the operating-procedure passage below and propose the machine-checkable
conditions under which it governs a crew-fatigue decision during task execution.

You are drafting for human review. Propose only what the passage states. Where
the passage does not say something, leave it out rather than inferring it -- an
invented precondition is worse than a missing one, because it will be enforced.

Answer in the checker's vocabulary and nothing else:

  task_types              list from: {task_types}
  criticality_in          list from: ["low", "medium", "high"]
  alertness_below         number 0-1, only if the passage gates on crew alertness
  workload_above          number 0-100, only if it gates on sustained duty load
  requires_circadian_flag true, only if it gates on the circadian trough
  phase                   "planning" or "execution", only if the passage says so
  domain                  the subject it governs, if that subject is NOT crew
                          alertness -- for example "vehicle_state", "suit_systems",
                          "staffing". This is how a passage declares it does not
                          apply to fatigue at all.

Also propose:

  prescribes        one of {prescribable}, or null if the passage prescribes no
                    action a fatigue decision could take
  fallback_action   one of {prescribable}, or null -- what the passage itself
                    says to do when the primary action is unavailable
  governs_fatigue   true or false -- whether this passage bears on crew fatigue
                    during execution at all

PASSAGE ({doc} section {section}):
{text}

Respond with JSON only:
{{"applies_when": {{...}}, "prescribes": <string or null>,
  "fallback_action": <string or null>, "governs_fatigue": <bool>,
  "reasoning": "<one sentence on what in the passage supports this>"}}
"""


@dataclass
class Proposal:
    """One model-drafted encoding of a passage, awaiting human review."""

    passage_id: str
    doc: str
    section: str
    title: str
    text: str
    applies_when: dict[str, Any] = field(default_factory=dict)
    prescribes: str | None = None
    fallback_action: str | None = None
    governs_fatigue: bool = True
    reasoning: str = ""
    #: Populated by :func:`validate`. A proposal with warnings is not rejected --
    #: it is shown to the reviewer with the problem stated.
    warnings: list[str] = field(default_factory=list)
    source: str = ""
    provenance: str = "extracted"
    extracted_by: str = ""
    #: Set only by the review tool. Nothing unreviewed may be emitted.
    reviewed_by: str = ""
    reviewed_at: str = ""
    approved: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def validate(proposal: Proposal) -> list[str]:
    """Everything wrong with a proposal, stated plainly for the reviewer.

    Warnings rather than rejections, with one exception enforced at emit time
    (see :mod:`compiler.review`). A reviewer looking at a flagged proposal can
    fix it; a proposal silently dropped teaches nobody anything.
    """
    problems: list[str] = []

    unknown = sorted(set(proposal.applies_when) - set(CLAUSE_VOCABULARY))
    if unknown:
        problems.append(
            f"clauses the checker cannot evaluate: {unknown}. It treats an unevaluable "
            f"precondition as unsatisfied, so this passage would never govern anything."
        )

    for action, label in ((proposal.prescribes, "prescribes"), (proposal.fallback_action, "fallback_action")):
        if action is not None and action not in PRESCRIBABLE:
            problems.append(
                f"{label}={action!r} is not an action the engine can take; "
                f"it would raise rather than refuse. Expected one of {list(PRESCRIBABLE)}."
            )

    types = proposal.applies_when.get("task_types")
    if isinstance(types, list):
        strange = sorted(set(types) - set(TASK_TYPES))
        if strange:
            problems.append(f"task types the engine never produces: {strange}")

    # This is O1's Phase 4 acceptance criterion, and the reason it exists.
    if proposal.governs_fatigue and not proposal.applies_when:
        problems.append(
            "no preconditions at all. The checker treats an empty clause set as applying "
            "always, so this passage would be admissible for every Situation -- fail-open, "
            "in a system whose thesis is fail-closed. Either state its conditions or mark "
            "it as not governing fatigue."
        )

    if proposal.governs_fatigue and proposal.prescribes is None:
        problems.append(
            "governs fatigue but prescribes no action, so it can never ground a "
            "recommendation. Verify that is what the passage says."
        )

    if "domain" in proposal.applies_when and proposal.governs_fatigue:
        problems.append(
            f"declares domain={proposal.applies_when['domain']!r} while also claiming to govern "
            f"fatigue. A domain clause is how a passage says it governs something else."
        )

    return problems


def propose(chunk: Document, llm: ReasoningLLM, *, passage_id: str) -> Proposal:
    """Draft an encoding for one chunk. Never called at request time."""
    meta = chunk.metadata
    doc = str(meta.get("doc_id", ""))
    section = str(meta.get("section", ""))

    prompt = EXTRACT_PROMPT.format(
        task_types=json.dumps(list(TASK_TYPES)),
        prescribable=json.dumps(list(PRESCRIBABLE)),
        doc=doc,
        section=section,
        text=chunk.page_content,
    )

    proposal = Proposal(
        passage_id=passage_id,
        doc=doc,
        section=section,
        title=str(meta.get("section_title", "")),
        text=chunk.page_content,
        source=_source_line(meta),
        provenance=str(meta.get("provenance", "extracted")),
        extracted_by=f"{llm.provider} / {llm.model_id}",
    )

    try:
        payload = extract_json(llm.complete("EXTRACT", prompt, {"chunk": chunk.page_content}))
    except (ParseFailure, Exception) as exc:  # noqa: B014 - ParseFailure is a RuntimeError
        # A draft that could not be read is still shown to the reviewer, empty
        # and flagged. Dropping it would remove the rule from the corpus without
        # anyone deciding to.
        proposal.warnings = [f"the model's response could not be read ({exc}); encode this passage by hand"]
        proposal.governs_fatigue = False
        return proposal

    proposal.applies_when = payload.get("applies_when") or {}
    proposal.prescribes = payload.get("prescribes")
    proposal.fallback_action = payload.get("fallback_action")
    proposal.governs_fatigue = bool(payload.get("governs_fatigue", True))
    proposal.reasoning = str(payload.get("reasoning", ""))
    if not isinstance(proposal.applies_when, dict):
        proposal.warnings.append("applies_when was not an object; it has been cleared")
        proposal.applies_when = {}

    proposal.warnings.extend(validate(proposal))
    return proposal


def _source_line(meta: dict) -> str:
    """The provenance string carried on every emitted passage."""
    bits = [str(meta.get("title", "")).strip()]
    if meta.get("revision"):
        bits.append(f"rev {meta['revision']}")
    if meta.get("page"):
        bits.append(f"p. {meta['page']}")
    if meta.get("retrieved"):
        bits.append(f"retrieved {meta['retrieved']}")
    return ", ".join(b for b in bits if b)


def propose_all(chunks: list[Document], llm: ReasoningLLM, *, prefix: str = "P") -> list[Proposal]:
    """Draft encodings for every chunk, in document order."""
    proposals: list[Proposal] = []
    for index, chunk in enumerate(chunks, start=1):
        section = str(chunk.metadata.get("section", index)).replace(" ", "-")
        proposals.append(propose(chunk, llm, passage_id=f"{prefix}-{section}"))
    return proposals
