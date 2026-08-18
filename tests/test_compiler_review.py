"""The gate that will not open without a human.

A model drafts these preconditions and the deterministic checker then treats them
as ground truth. The checker is the component that disposes of what the reasoning
tier proposes, so its authority rests entirely on the preconditions being right —
which makes "a person approved this" the load-bearing step in the whole compiler.

So the gate refuses rather than filters. A silently dropped passage removes a
rule from the corpus with nobody deciding to; a raised error stops the build.

The third refusal is **O1**, recorded in the CHANGELOG two phases before this
file existed: an extracted passage declaring no preconditions would be
admissible for every Situation, because the checker reads an empty clause set as
"always applies". That semantic is correct for a hand-authored corpus, where
emptiness is a deliberate statement. It is wrong for an extracted one, where it
means the extraction produced nothing and somebody clicked approve. The guard
belongs at the compiler, which is where the risk actually is.
"""

from __future__ import annotations

import json

import pytest

from compiler.propose import PRESCRIBABLE, Proposal, validate
from compiler.review import (
    ReviewIncomplete,
    approve,
    gate,
    read_reviewed,
    summarise,
    write_for_review,
)


def proposal(**overrides) -> Proposal:
    base = dict(
        passage_id="P-V2-7003",
        doc="NASA-STD-3001-V2",
        section="V2 7003",
        title="Sleep Opportunity",
        text="The system shall provide a sleep opportunity of at least 8 hours...",
        applies_when={"task_types": ["eva"], "alertness_below": 0.7},
        prescribes="short_rest_then_proceed",
        governs_fatigue=True,
        provenance="extracted",
    )
    return Proposal(**{**base, **overrides})


def approved(**overrides) -> Proposal:
    return approve(proposal(**overrides), "R. Alvarez")


# --------------------------------------------------------------------------
# The gate refuses
# --------------------------------------------------------------------------
def test_an_unreviewed_passage_is_refused() -> None:
    with pytest.raises(ReviewIncomplete) as excinfo:
        gate([proposal()])
    assert "not reviewed" in str(excinfo.value)


def test_a_reviewed_passage_is_emitted() -> None:
    assert [p.passage_id for p in gate([approved()])] == ["P-V2-7003"]


def test_approval_without_a_reviewer_is_not_approval() -> None:
    """A flag set by a script is not a person having looked."""
    unsigned = proposal()
    unsigned.approved = True
    with pytest.raises(ReviewIncomplete):
        gate([unsigned])


def test_an_extracted_passage_with_no_preconditions_is_refused() -> None:
    """O1. It would be admissible for every Situation -- fail-open."""
    with pytest.raises(ReviewIncomplete) as excinfo:
        gate([approved(applies_when={})])
    message = str(excinfo.value)
    assert "no preconditions" in message or "unresolved warnings" in message


def test_a_hand_authored_passage_may_still_declare_none() -> None:
    """The checker's semantic is correct for authored input; only extraction is at risk."""
    authored = proposal(applies_when={}, provenance="synthesised")
    authored.warnings = []
    authored.approved, authored.reviewed_by = True, "R. Alvarez"
    assert gate([authored])


def test_approving_a_warned_passage_does_not_get_it_through() -> None:
    """Likelier a slip than a decision, and cheap to make the reviewer confirm."""
    warned = approved()
    warned.warnings = ["something the reviewer did not resolve"]
    with pytest.raises(ReviewIncomplete) as excinfo:
        gate([warned])
    assert "unresolved warnings" in str(excinfo.value)


def test_a_passage_marked_as_not_governing_is_excluded_without_error() -> None:
    """A reviewed decision to exclude, not an absence."""
    excluded = approve(proposal(governs_fatigue=False), "R. Alvarez")
    assert [p.passage_id for p in gate([excluded, approved()])] == ["P-V2-7003"]


def test_the_error_names_every_offender_not_just_the_first() -> None:
    """A build that fails one passage at a time wastes a reviewer's afternoon."""
    with pytest.raises(ReviewIncomplete) as excinfo:
        gate([proposal(passage_id="P-A"), proposal(passage_id="P-B")])
    message = str(excinfo.value)
    assert "P-A" in message and "P-B" in message


# --------------------------------------------------------------------------
# Re-validation on approval
# --------------------------------------------------------------------------
def test_approving_revalidates_rather_than_trusting_the_reviewer() -> None:
    """A reviewer's edit is exactly as capable of being wrong as the draft was."""
    edited = proposal(prescribes="teleport_the_crew")
    edited.warnings = []
    approve(edited, "R. Alvarez")
    assert edited.warnings, "an unusable action must be caught even when a human wrote it"


def test_an_action_outside_the_contract_is_flagged() -> None:
    """It would raise out of the engine -- a 500 where a refusal belongs."""
    problems = validate(proposal(prescribes="have_a_nap"))
    assert any("not an action the engine can take" in p for p in problems)
    assert all(action in str(PRESCRIBABLE) for action in ["second_operator_verify", "task_deferral"])


def test_a_clause_the_checker_cannot_evaluate_is_flagged() -> None:
    problems = validate(proposal(applies_when={"phase_of_the_moon": "waxing"}))
    assert any("cannot evaluate" in p for p in problems)


def test_a_domain_clause_contradicting_governs_fatigue_is_flagged() -> None:
    """A domain clause is how a passage says it governs something else."""
    problems = validate(proposal(applies_when={"domain": "vehicle_state"}, governs_fatigue=True))
    assert any("governs something else" in p for p in problems)


def test_governing_without_prescribing_is_flagged() -> None:
    problems = validate(proposal(prescribes=None))
    assert any("can never ground a recommendation" in p for p in problems)


# --------------------------------------------------------------------------
# The review file
# --------------------------------------------------------------------------
def test_the_review_file_leads_with_what_needs_attention(tmp_path) -> None:
    """A reviewer working top-down should meet the hard cases first."""
    clean = proposal(passage_id="P-CLEAN")
    broken = proposal(passage_id="P-BROKEN")
    broken.warnings = ["needs a decision"]

    path = write_for_review([clean, broken], tmp_path / "review.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["proposals"][0]["passage_id"] == "P-BROKEN"
    assert payload["needs_attention"] == 1
    assert payload["total"] == 2


def test_a_reviewed_file_round_trips(tmp_path) -> None:
    path = write_for_review([approved()], tmp_path / "review.json")
    recovered = read_reviewed(path)

    assert len(recovered) == 1
    assert recovered[0].approved
    assert recovered[0].reviewed_by == "R. Alvarez"
    assert recovered[0].applies_when == {"task_types": ["eva"], "alertness_below": 0.7}


def test_reading_a_missing_review_file_says_what_to_do(tmp_path) -> None:
    with pytest.raises(ReviewIncomplete) as excinfo:
        read_reviewed(tmp_path / "absent.json")
    assert "propose step" in str(excinfo.value)


def test_unknown_fields_in_an_edited_file_are_ignored(tmp_path) -> None:
    """Reviewers annotate. A stray note must not break the read."""
    path = tmp_path / "review.json"
    path.write_text(
        json.dumps({"proposals": [{**approved().as_dict(), "reviewer_note": "checked against rev D", "unknown": 1}]}),
        encoding="utf-8",
    )
    assert read_reviewed(path)[0].approved


def test_the_summary_counts_what_remains(tmp_path) -> None:
    counts = summarise(
        [approved(), proposal(passage_id="P-2"), approve(proposal(passage_id="P-3", governs_fatigue=False), "R")]
    )
    assert counts["total"] == 3
    assert counts["awaiting_review"] == 1
    assert counts["excluded"] == 1
