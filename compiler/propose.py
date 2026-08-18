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

from haven.deterministic.preconditions import CLAUSE_VOCABULARY, PRESCRIPTIVE_AUTHORITIES
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

{authority_note}PASSAGE ({doc} section {section}):
{text}
{rationale_note}
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
    #: Carried from the source registry, never proposed by the model.
    authority: str = "authoritative"
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

    if proposal.prescribes is not None and proposal.authority not in PRESCRIPTIVE_AUTHORITIES:
        problems.append(
            f"prescribes={proposal.prescribes!r} but the source is {proposal.authority}, not a "
            f"requirements document. A handbook's recommendation and a paper's finding are not "
            f"rules; encoding one as an action the crew is told to take would enforce a "
            f"requirement nobody wrote. Set prescribes to null."
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

    # A NASA standard states its requirement and then explains itself in a
    # bracketed rationale block. The explanation is where the operationally
    # useful sentences live -- "avoid scheduling critical tasks during the
    # circadian nadir" is rationale, not requirement -- and encoding one as a
    # binding precondition produces a rule the standard does not contain. So the
    # two are named for the model rather than handed over concatenated.
    prompt = EXTRACT_PROMPT.format(
        task_types=json.dumps(list(TASK_TYPES)),
        prescribable=json.dumps(list(PRESCRIBABLE)),
        doc=doc,
        section=section,
        authority_note=_authority_note(str(meta.get("authority", "authoritative"))),
        text=meta.get("requirement_text") or chunk.page_content,
        rationale_note=_rationale_note(meta),
    )

    proposal = Proposal(
        passage_id=passage_id,
        doc=doc,
        section=section,
        title=str(meta.get("section_title", "")),
        text=chunk.page_content,
        source=_source_line(meta),
        provenance=str(meta.get("provenance", "extracted")),
        authority=str(meta.get("authority", "authoritative")),
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


#: What the model is told about a source that cannot impose a requirement.
#: Stated in the prompt as well as enforced at the gate, because a proposal
#: drafted and then refused wastes a reviewer's attention on a passage that was
#: never eligible.
_AUTHORITY_NOTES = {
    "guidance": (
        "NOTE: this passage is from a design handbook. It states rationale and recommended\n"
        "practice, never requirements. Set prescribes and fallback_action to null: a\n"
        "recommendation the crew is told to follow may only be grounded in a requirement.\n\n"
    ),
    "research": (
        "NOTE: this passage is from a research paper. It reports what was measured, not what\n"
        "shall be done. Set prescribes and fallback_action to null: a finding is evidence for\n"
        "a rule, never the rule itself.\n\n"
    ),
}


def _authority_note(authority: str) -> str:
    return _AUTHORITY_NOTES.get(authority, "")


def _rationale_note(meta: dict) -> str:
    """The rationale block, labelled as explanation rather than requirement."""
    if not meta.get("has_rationale"):
        return ""
    return (
        "\nEXPLANATORY RATIONALE (not a requirement; it explains the rule above,\n"
        "and may not by itself establish a precondition):\n" + str(meta.get("rationale_text", "")) + "\n"
    )


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


def passage_id(chunk: Document, taken: set[str], *, prefix: str = "P") -> str:
    """A stable, unique, human-readable identifier for one chunk.

    Uniqueness is not a nicety. ``BY_ID`` is a dict, every citation resolves
    through it, and two chunks sharing an id means one rule silently replaces
    another — a corpus that looks complete while a passage an operator can be
    shown a citation to no longer exists.

    Collisions are real rather than theoretical: section numbers repeat across
    documents (both a NASA standard and a technical memorandum have a "5.1"),
    and a requirement spanning a page break is seen twice, since pages are
    chunked independently. So the document's own short code opens the id, and a
    repeat is numbered rather than dropped. ``P-V1-4002-2`` reads as what it is —
    the second chunk carrying that requirement number — and asks the reviewer to
    look at whether the rule was split across pages.
    """
    stem = str(chunk.metadata.get("section", "")).strip().replace(" ", "-") or "unsectioned"
    code = str(chunk.metadata.get("passage_prefix", "")).strip().replace(" ", "-")
    # A requirement identifier already opens with its volume, so "V1" plus
    # "V1-6001" would stutter.
    if code and not stem.upper().startswith(f"{code.upper()}-"):
        stem = f"{code}-{stem}"

    candidate = f"{prefix}-{stem}"
    if candidate not in taken:
        return candidate
    suffix = 2
    while f"{candidate}-{suffix}" in taken:
        suffix += 1
    return f"{candidate}-{suffix}"


def propose_all(chunks: list[Document], llm: ReasoningLLM, *, prefix: str = "P") -> list[Proposal]:
    """Draft encodings for every chunk, in document order."""
    proposals: list[Proposal] = []
    taken: set[str] = set()
    for chunk in chunks:
        identifier = passage_id(chunk, taken, prefix=prefix)
        taken.add(identifier)
        proposals.append(propose(chunk, llm, passage_id=identifier))
    return proposals
