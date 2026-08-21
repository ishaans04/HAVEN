"""Retrying a burst, and refusing to retry an outage.

Found by running eight scenarios against live watsonx in sequence. Three of them
came back served by the offline stand-in with `degraded: true`, and the reason
was not a bug in HAVEN — it was this, verbatim:

    429 consumption_limit_reached: "the total number of free concurrent requests
    for model ibm/granite-4-h-small has reached its limit 10"

The chain behaved exactly as designed: it fell through, marked the evaluation
degraded, and named the cause. Nothing was hidden. But the *condition* is a
concurrency burst that clears in seconds, and treating it as an outage means a
demo silently spends its first several scenarios on the mock — honestly
labelled, and still not what anyone wanted to show.

watsonx returns 429 for two unrelated things, and the whole of this module is
about telling them apart:

* **concurrent-request limit** — clears as soon as in-flight calls finish.
  Waiting a moment fixes it.
* **plan token allowance** — does not clear this month. Waiting fixes nothing,
  and retrying only delays an outage the operator needs to be told about.

Getting that backwards in either direction is a real cost: retry the second and
a demo hangs three times as long before failing anyway; refuse to retry the
first and it degrades for no reason.
"""

from __future__ import annotations

import pytest

from haven.reasoning.llm import (
    RETRY_ATTEMPTS,
    LLMUnavailable,
    _is_worth_retrying,
)

# Real strings, from live responses during the Phase 11 verification run.
CONCURRENCY_429 = (
    "Failure during chat. (POST https://us-south.ml.cloud.ibm.com/ml/v1/text/chat) Status code: 429, "
    'body: {"errors":[{"code":"consumption_limit_reached","message":"The usage limit for the current '
    "plan has been reached: the total number of free concurrent requests for model "
    'ibm/granite-4-h-small has reached its limit 10. Please try again later"}]}'
)
PLAN_EXHAUSTED_429 = (
    'Status code: 429, body: {"errors":[{"code":"consumption_limit_reached",'
    '"message":"The usage limit for the current plan has been reached: token quota exhausted '
    'for the current period"}]}'
)


# --------------------------------------------------------------------------
# The classification
# --------------------------------------------------------------------------
def test_a_concurrency_limit_is_retried() -> None:
    assert _is_worth_retrying(RuntimeError(CONCURRENCY_429))


def test_an_exhausted_plan_is_not_retried() -> None:
    """The case the obvious matcher gets wrong.

    Both bodies carry `consumption_limit_reached` and the phrase "usage limit
    for the current plan has been reached". Matching on 429, or on either of
    those, retries a monthly allowance that will not refill for weeks.
    """
    assert not _is_worth_retrying(RuntimeError(PLAN_EXHAUSTED_429))


@pytest.mark.parametrize(
    ("error", "retry"),
    [
        ("Read timed out", True),
        ("503 Service Unavailable", True),
        ("Connection reset by peer", True),
        ("401 Provided API key could not be found", False),
        ("404 model_not_supported: unknown model id", False),
        ("403 Forbidden", False),
    ],
)
def test_transient_and_permanent_are_separated(error: str, retry: bool) -> None:
    assert _is_worth_retrying(RuntimeError(error)) is retry


# --------------------------------------------------------------------------
# The retry itself
# --------------------------------------------------------------------------
class _FlakyClient:
    """Fails with the given errors, then succeeds."""

    def __init__(self, failures: list[str]) -> None:
        self.failures = list(failures)
        self.calls = 0

    def invoke(self, messages):  # noqa: ANN001 - a stub for one method
        self.calls += 1
        if self.failures:
            raise RuntimeError(self.failures.pop(0))

        class _Response:
            content = "ready"

        return _Response()


def _provider(client) -> object:
    """A LangChain-backed provider wired to a stub client, no network."""
    from haven.reasoning.llm import _LangChainProvider

    provider = _LangChainProvider()
    provider._client = client
    return provider


def test_a_burst_recovers_without_degrading(monkeypatch) -> None:
    """The point of the change: the second attempt answers, so nothing degrades."""
    monkeypatch.setattr("haven.reasoning.llm.RETRY_BACKOFF_SECONDS", 0.0)
    client = _FlakyClient([CONCURRENCY_429])

    assert _provider(client).complete("FUSE", "prompt", {}) == "ready"
    assert client.calls == 2, "one failure, one success"


def test_retries_are_bounded(monkeypatch) -> None:
    """A link that keeps failing must reach the chain, not be retried forever.

    The chain's whole job is falling through to the next provider and saying so.
    A retry loop that never gives up would prevent that from ever happening.
    """
    monkeypatch.setattr("haven.reasoning.llm.RETRY_BACKOFF_SECONDS", 0.0)
    client = _FlakyClient([CONCURRENCY_429] * 10)

    with pytest.raises(LLMUnavailable):
        _provider(client).complete("FUSE", "prompt", {})
    assert client.calls == RETRY_ATTEMPTS


def test_a_permanent_failure_is_not_retried_at_all(monkeypatch) -> None:
    """A bad key three times over is still a bad key, thirty seconds later."""
    monkeypatch.setattr("haven.reasoning.llm.RETRY_BACKOFF_SECONDS", 0.0)
    client = _FlakyClient(["401 Provided API key could not be found"] * 10)

    with pytest.raises(LLMUnavailable):
        _provider(client).complete("FUSE", "prompt", {})
    assert client.calls == 1, "a permanent failure must fail on the first attempt"


def test_the_failure_still_arrives_as_LLMUnavailable(monkeypatch) -> None:
    """The chain only counts LLMUnavailable, so the retry must not change the type.

    If a raw exception escaped here it would bypass the circuit breaker and the
    fallback entirely, and a watsonx outage would become a 500 rather than a
    degraded evaluation.
    """
    monkeypatch.setattr("haven.reasoning.llm.RETRY_BACKOFF_SECONDS", 0.0)
    client = _FlakyClient([PLAN_EXHAUSTED_429])

    with pytest.raises(LLMUnavailable, match="rate-limited or out of quota"):
        _provider(client).complete("FUSE", "prompt", {})
