"""What a real provider actually returns, and what HAVEN does about it.

The mock returns exactly the JSON it was asked for, every time, so none of this
was exercised before. A real instruction-tuned model fences its JSON, prefixes it
with "Certainly!", appends a paragraph of explanation, or returns a plausible
sentence where an object was requested — none of it misbehaviour, all of it fatal
to `json.loads(completion)`.

The same applies to figures. A model asked to write about an alertness of 0.61
will sooner or later write "roughly 0.6", or restate a threshold from the passage
text. S1 says every numeral traces to a computed value, so that text cannot be
published — but it also should not crash the API, and the model usually corrects
itself when told precisely what was wrong.

Both paths end the same way if the second attempt fails: refuse. Not knowing is
an answer this system is allowed to give.
"""

from __future__ import annotations

import pytest

from haven.reasoning.parsing import (
    ParseFailure,
    extract_json,
    parse_selection,
    repair_prompt,
)

VALID = '{"governing_passage_id": "P-FAT-4.2", "reason": "governs", "rejected": []}'


# --------------------------------------------------------------------------
# Extraction: what models actually send
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("label", "completion"),
    [
        ("bare object", VALID),
        ("fenced json", f"```json\n{VALID}\n```"),
        ("fenced plain", f"```\n{VALID}\n```"),
        ("preamble", f"Certainly! Here is the analysis:\n\n{VALID}"),
        ("postamble", f"{VALID}\n\nLet me know if you need anything else."),
        ("both", f"Sure — here you go:\n```json\n{VALID}\n```\nHope that helps!"),
        ("leading whitespace", f"\n\n   {VALID}   \n"),
    ],
)
def test_a_selection_survives_the_wrapping_models_add(label: str, completion: str) -> None:
    assert parse_selection(completion)["governing_passage_id"] == "P-FAT-4.2"


def test_a_brace_inside_a_string_does_not_end_the_object() -> None:
    """Why the scanner tracks string state instead of matching a regex."""
    completion = (
        'Here: {"governing_passage_id": null, "reason": "the rule uses {braces} in its text", "rejected": []} — done.'
    )
    assert parse_selection(completion)["governing_passage_id"] is None


def test_a_nested_object_does_not_truncate_the_parse() -> None:
    completion = (
        'prefix {"governing_passage_id": "P-FAT-4.4", "reason": "x", '
        '"rejected": [{"passage_id": "P-SLP-2.1", "why": "planning"}]} suffix'
    )
    parsed = parse_selection(completion)
    assert parsed["governing_passage_id"] == "P-FAT-4.4"
    assert parsed["rejected"][0]["passage_id"] == "P-SLP-2.1"


def test_a_null_selection_is_a_real_answer_not_a_failure() -> None:
    """No passage governs is the answer this architecture exists to give."""
    parsed = parse_selection('{"governing_passage_id": null, "reason": "none apply", "rejected": []}')
    assert parsed["governing_passage_id"] is None


# --------------------------------------------------------------------------
# Rejection: what must not be accepted
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("label", "completion"),
    [
        ("empty", ""),
        ("whitespace", "   \n  "),
        ("prose only", "The fatigue rule in section 4.2 clearly governs this situation."),
        ("truncated", '{"governing_passage_id": "P-FAT-4.2", "reason":'),
        ("a list", '["P-FAT-4.2"]'),
        ("a bare string", '"P-FAT-4.2"'),
    ],
)
def test_an_unreadable_response_raises_rather_than_guessing(label: str, completion: str) -> None:
    with pytest.raises(ParseFailure):
        parse_selection(completion)


def test_the_wrong_shape_is_caught_at_the_contract_not_three_frames_later() -> None:
    with pytest.raises(ParseFailure) as excinfo:
        parse_selection('{"governing_passage_id": 42}')
    assert "shape" in str(excinfo.value)


def test_a_failure_message_tells_the_model_what_to_do() -> None:
    """The message becomes the repair prompt, so it is written for a model."""
    with pytest.raises(ParseFailure) as excinfo:
        parse_selection("no json here at all")
    message = str(excinfo.value)
    assert "JSON object" in message


def test_membership_is_not_judged_here() -> None:
    """An invented identifier is VERIFY's business, and the trail must record it.

    Rejecting it at the parse layer would fail closed, but the record would then
    show the proposal as *absent* rather than as *invented* — losing exactly the
    evidence a reviewer needs.
    """
    parsed = parse_selection('{"governing_passage_id": "P-INVENTED", "reason": "x", "rejected": []}')
    assert parsed["governing_passage_id"] == "P-INVENTED"


# --------------------------------------------------------------------------
# The repair prompt
# --------------------------------------------------------------------------
def test_the_repair_restates_the_task() -> None:
    """Providers are stateless per call; a correction alone would strand it."""
    prompt = repair_prompt("ORIGINAL TASK TEXT", "the response was empty")
    assert "ORIGINAL TASK TEXT" in prompt
    assert "the response was empty" in prompt


def test_extract_json_accepts_an_object_with_extra_keys() -> None:
    """Models add fields. Unknown ones are ignored, not fatal."""
    parsed = extract_json('{"governing_passage_id": "P-FAT-4.2", "confidence": 0.9}')
    assert parsed["governing_passage_id"] == "P-FAT-4.2"
