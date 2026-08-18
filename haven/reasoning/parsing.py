"""Getting a structured answer out of a model that was not asked politely enough.

`json.loads(completion)` works against a scripted mock and fails against the
first real model that wraps its JSON in a fenced block, prefixes it with "Sure,
here is the analysis:", or appends a paragraph of commentary. That is not
misbehaviour -- it is what instruction-tuned models do -- so the parsing has to
expect it.

The ladder, in order, and it fails closed at the bottom:

1. **Native structured output.** Ask the provider for JSON matching a schema.
   Ollama takes `format`, watsonx takes `response_format`. Nothing to parse
   loosely when it works.
2. **Extraction.** Strip fences and prose, find the first balanced object.
3. **Validation.** Against a Pydantic model, not a bare dict, so a response of
   the wrong *shape* is caught here rather than three frames later as a
   confusing AttributeError.
4. **One repair retry**, with the specific error handed back to the model.
5. **Refuse.** A model that cannot say which passage governs, twice, has not
   said anything -- and the correct response to not knowing is to escalate.

Shape is all this module judges. Whether the named passage was in the candidate
set, and whether it governs, belong to VERIFY.

There is no rung that guesses. A partially-parsed selection is not a weak
answer; it is an unknown one wearing an answer's clothes.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

# ```json ... ``` or ``` ... ```, which is how most instruction-tuned models
# return structured output whether or not they were asked to.
_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


class ParseFailure(RuntimeError):
    """The completion could not be read as a selection. Carries the reason.

    The message is handed back to the model on the repair attempt, so it is
    written to be useful to one: specific about what was wrong, not merely that
    something was.
    """


class RejectedCandidate(BaseModel):
    passage_id: str
    why: str = ""


class SelectResponse(BaseModel):
    """The only shape SELECT may return.

    ``governing_passage_id`` is optional because *no passage governs* is a
    first-class answer here, not an error. What is not permitted is omitting the
    field entirely, which would leave "the model did not answer" and "the model
    answered none" indistinguishable.
    """

    governing_passage_id: str | None = Field(default=None)
    reason: str = ""
    rejected: list[RejectedCandidate] = Field(default_factory=list)

    def as_selection(self) -> dict[str, Any]:
        return {
            "governing_passage_id": self.governing_passage_id,
            "reason": self.reason,
            "rejected": [r.model_dump() for r in self.rejected],
        }


def _balanced_object(text: str) -> str | None:
    """The first complete `{...}`, respecting nesting and strings.

    A regex cannot do this correctly: `\\{.*\\}` is greedy past the end of the
    first object, and a non-greedy version stops at the first `}` inside a nested
    one. Scanning with a depth counter is the only honest way, and it has to know
    about string literals, since a brace inside `"why"` text is not structure.
    """
    start = text.find("{")
    if start < 0:
        return None

    depth, in_string, escaped = 0, False, False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def extract_json(completion: str) -> dict[str, Any]:
    """Pull an object out of whatever the model actually returned.

    Raises :class:`ParseFailure` with a message aimed at the model, because that
    message becomes the repair prompt.
    """
    if not completion or not completion.strip():
        raise ParseFailure("the response was empty; return a single JSON object and nothing else")

    for candidate in (completion.strip(), *(m.strip() for m in _FENCE.findall(completion))):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        raise ParseFailure(
            f"the response was a JSON {type(parsed).__name__}, not an object; "
            "return a single JSON object with a governing_passage_id field"
        )

    block = _balanced_object(completion)
    if block is not None:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError as exc:
            raise ParseFailure(
                f"the JSON object in the response could not be parsed ({exc.msg} at position {exc.pos}); "
                "return valid JSON and no commentary"
            ) from exc
        if isinstance(parsed, dict):
            return parsed

    raise ParseFailure("no JSON object was found in the response; return a single JSON object and no prose around it")


def parse_selection(completion: str) -> dict[str, Any]:
    """Read a SELECT completion, or raise :class:`ParseFailure`.

    Validates **shape only**. Whether the chosen passage was in the candidate
    set, and whether it governs, are questions for VERIFY -- the tier that
    disposes. Rejecting an invented identifier here would be the wrong layer and
    would cost real evidence: the flow would fail closed with the proposal
    recorded as *absent* rather than as *invented*, and the trail would no
    longer say which identifier the model produced. Failing closed is not enough
    on its own; the record has to show what happened.
    """
    payload = extract_json(completion)

    try:
        response = SelectResponse.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(p) for p in first["loc"]) or "(root)"
        raise ParseFailure(
            f"the JSON did not match the required shape: {location} {first['msg']}. "
            'Return {"governing_passage_id": <id or null>, "reason": <string>, '
            '"rejected": [{"passage_id": <id>, "why": <string>}]}'
        ) from exc

    return response.as_selection()


def repair_prompt(original: str, failure: str) -> str:
    """The second and final attempt.

    Restating the original matters: some providers are stateless per call, and a
    correction alone would leave the model repairing a task it can no longer see.
    """
    return (
        f"{original}\n\n"
        f"Your previous response could not be used: {failure}\n"
        f"Respond with the JSON object only. No explanation, no code fences, no preamble."
    )
