"""The human in the middle, and the gate that will not open without them.

A model drafted these preconditions. The deterministic checker will treat them
as ground truth — it is the component that disposes of what the reasoning tier
proposes, and its authority rests entirely on the preconditions being right.

So the compiler cannot emit a passage nobody approved. Not "should not": the
emit path refuses, and a test proves it refuses. That refusal is the only thing
standing between "a model suggested this encoding" and "a safety component
enforces this encoding", and it is worth being blunt about.

Review is a file. The compiler writes proposals to JSON, a person edits it —
setting `approved` and their name, fixing whatever the warnings flagged — and
the compiler reads it back. No web UI, because a reviewer needs to see the
passage text beside the encoding and think, and a form encourages clicking.
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path

from compiler.propose import Proposal, validate
from haven.deterministic.preconditions import PRESCRIPTIVE_AUTHORITIES


class ReviewIncomplete(RuntimeError):
    """Something unapproved reached the emit path. Never a warning."""


def write_for_review(proposals: list[Proposal], path: Path) -> Path:
    """Write proposals to a file a person edits.

    Ordered so the ones needing attention are impossible to miss: anything with
    a warning first, then the rest. A reviewer working top-down meets the hard
    cases while they are still paying attention.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(proposals, key=lambda p: (not p.warnings, p.passage_id))
    payload = {
        "instructions": [
            "Set approved=true and reviewed_by to your name for each passage you accept.",
            "Fix or clear anything listed in warnings before approving it.",
            "A passage that does not bear on crew fatigue during execution: set",
            "governs_fatigue=false. It will be recorded as reviewed and excluded",
            "from the corpus, rather than silently dropped.",
            "Nothing unapproved is emitted. The compiler refuses.",
        ],
        "needs_attention": sum(1 for p in ordered if p.warnings),
        "total": len(ordered),
        "proposals": [p.as_dict() for p in ordered],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8", newline="\n")
    return path


def read_reviewed(path: Path) -> list[Proposal]:
    """Read a reviewed file back, keeping only fields the dataclass declares."""
    if not path.exists():
        raise ReviewIncomplete(f"no review file at {path}; run the propose step first")

    payload = json.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Proposal)}
    return [Proposal(**{k: v for k, v in item.items() if k in known}) for item in payload.get("proposals", [])]


def approve(proposal: Proposal, reviewer: str) -> Proposal:
    """Mark a proposal reviewed. Used by tests and by the CLI's --approve-all.

    Re-validates rather than trusting the flag: a reviewer may have edited the
    encoding while approving it, and the edit is exactly as capable of being
    wrong as the model's draft was.
    """
    proposal.warnings = validate(proposal)
    proposal.reviewed_by = reviewer
    proposal.reviewed_at = datetime.now(timezone.utc).isoformat()
    proposal.approved = True
    return proposal


def gate(proposals: list[Proposal]) -> list[Proposal]:
    """The passages that may be emitted. Raises rather than filtering silently.

    Four refusals, and the third is O1's acceptance criterion, recorded in the
    CHANGELOG before this file existed:

    * unapproved — nobody signed off;
    * approved but still warned — the reviewer approved a known-broken encoding,
      which is likelier to be a slip than a decision;
    * **extracted, governing, and declaring no preconditions** — the checker
      treats an empty clause set as applying always, so such a passage would be
      admissible for every Situation. Fail-open, in a system whose entire thesis
      is fail-closed. It is refused at the compiler because that is where the
      risk is: the checker's semantic is correct for authored input.
    * **guidance or research declaring a prescribed action** — the corpus holds
      three kinds of text and retrieval cannot tell them apart. The deterministic
      checker refuses such a citation at request time too, and the duplication is
      deliberate: this refusal keeps the passage out of the corpus, that one
      catches it if it ever gets in.
    """
    emitted: list[Proposal] = []
    unapproved: list[str] = []
    warned: list[str] = []
    unconditional: list[str] = []
    promoted: list[str] = []

    for proposal in proposals:
        # Approval is checked *before* exclusion, and the order is load-bearing.
        # A proposal the model failed to draft arrives with governs_fatigue
        # false, so skipping exclusions first would silently drop every rule the
        # extraction could not read -- the corpus quietly losing rules with
        # nobody deciding to, which is the exact failure this gate exists to
        # prevent. An exclusion only counts once a person has made it.
        if not (proposal.approved and proposal.reviewed_by):
            unapproved.append(proposal.passage_id)
            continue
        if not proposal.governs_fatigue:
            # A reviewed decision to exclude. Not an error, and recorded as a
            # decision rather than an absence.
            continue
        if proposal.warnings:
            warned.append(f"{proposal.passage_id}: {proposal.warnings[0]}")
            continue
        if proposal.provenance == "extracted" and not proposal.applies_when:
            unconditional.append(proposal.passage_id)
            continue
        if proposal.authority not in PRESCRIPTIVE_AUTHORITIES and (
            proposal.prescribes is not None or proposal.fallback_action is not None
        ):
            promoted.append(f"{proposal.passage_id} ({proposal.authority} -> {proposal.prescribes})")
            continue
        emitted.append(proposal)

    problems: list[str] = []
    if unapproved:
        problems.append(f"not reviewed: {sorted(unapproved)}")
    if warned:
        problems.append(f"approved with unresolved warnings: {warned}")
    if unconditional:
        problems.append(
            f"extracted passages declaring no preconditions: {sorted(unconditional)} -- these would be "
            f"admissible for every Situation"
        )
    if promoted:
        problems.append(
            f"guidance or research passages prescribing an action: {sorted(promoted)} -- a handbook's "
            f"recommendation and a paper's finding are not requirements, and a crew told to take an "
            f"action on one would be following a rule nobody wrote"
        )
    if problems:
        raise ReviewIncomplete("; ".join(problems))

    return emitted


def summarise(proposals: list[Proposal]) -> dict:
    return {
        "total": len(proposals),
        "approved": sum(1 for p in proposals if p.approved),
        "warned": sum(1 for p in proposals if p.warnings),
        "excluded": sum(1 for p in proposals if not p.governs_fatigue),
        "awaiting_review": sum(1 for p in proposals if p.governs_fatigue and not p.approved),
    }
