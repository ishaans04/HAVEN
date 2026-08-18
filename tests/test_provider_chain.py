"""Falling back without lying about it.

A chain keeps the system working when a provider is down. The risk it introduces
is that the system quietly tells you less than it knows -- which is exactly the
behaviour the `provider_outage` scenario exists to reject. So every one of these
tests is really about the same property: *the record says which model answered*.

The circuit breaker is here for a practical reason rather than an elegant one.
Without it, a chain whose first link is unreachable pays that link's timeout on
every call, and an evaluation with six Situations spends six timeouts learning
the same fact.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from haven.reasoning import chain as chain_module
from haven.reasoning.chain import COOLDOWN_SECONDS, FAILURE_THRESHOLD, ProviderChain, configured_chain
from haven.reasoning.llm import LLMUnavailable, MockGraniteLLM, ReasoningLLM


class Link(ReasoningLLM):
    """A provider that answers, or fails, on command."""

    def __init__(self, name: str, *, fails: bool = False, answer: str = "answered") -> None:
        self._name = name
        self.fails = fails
        self.answer = answer
        self.calls = 0

    @property
    def provider(self) -> str:
        return self._name

    @property
    def model_id(self) -> str:
        return f"{self._name}-model"

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:
        self.calls += 1
        if self.fails:
            raise LLMUnavailable(f"{self._name} is down")
        return self.answer


def chain_of(*links: Link) -> ProviderChain:
    """A chain over given links, bypassing name resolution."""
    built = ProviderChain(names=tuple(link.provider for link in links))
    built._links = list(links)
    built._breakers = {link.provider: chain_module._Breaker() for link in links}
    built.names = tuple(link.provider for link in links)
    return built


def call(built: ProviderChain) -> str:
    return built.complete("SELECT", "prompt", {})


# --------------------------------------------------------------------------
# Order and fallback
# --------------------------------------------------------------------------
def test_the_first_healthy_link_answers() -> None:
    head, tail = Link("head"), Link("tail")
    assert call(chain_of(head, tail)) == "answered"
    assert (head.calls, tail.calls) == (1, 0), "a healthy head must not be bypassed"


def test_a_failed_link_falls_through_to_the_next() -> None:
    head, tail = Link("head", fails=True), Link("tail")
    assert call(chain_of(head, tail)) == "answered"
    assert (head.calls, tail.calls) == (1, 1)


def test_the_chain_reports_which_link_answered() -> None:
    built = chain_of(Link("head", fails=True), Link("tail"))
    call(built)

    status = built.status()
    assert status["served_by"] == "tail"
    assert status["attempted"] == ["head", "tail"]
    assert status["chain"] == ["head", "tail"]


def test_answering_from_below_the_head_is_degraded() -> None:
    """The operator asked for one model and was handed another. Say so."""
    built = chain_of(Link("head", fails=True), Link("tail"))
    call(built)

    assert built.degraded is True
    assert "head is down" in built.degraded_reason


def test_answering_at_the_head_is_not_degraded() -> None:
    built = chain_of(Link("head"), Link("tail"))
    call(built)
    assert built.degraded is False
    assert built.degraded_reason is None


def test_the_provider_named_in_the_audit_trail_is_the_one_that_answered() -> None:
    """Recording the head would attribute the reasoning to a model that never ran."""
    built = chain_of(Link("head", fails=True), Link("tail"))
    call(built)
    assert built.provider == "tail"
    assert built.model_id == "tail-model"


# --------------------------------------------------------------------------
# The circuit breaker
# --------------------------------------------------------------------------
def test_a_repeatedly_failing_link_is_skipped() -> None:
    head, tail = Link("head", fails=True), Link("tail")
    built = chain_of(head, tail)

    for _ in range(FAILURE_THRESHOLD):
        call(built)
    calls_at_threshold = head.calls

    call(built)
    assert head.calls == calls_at_threshold, "the open circuit should skip the link entirely"
    assert "circuit open" in built.degraded_reason


def test_the_breaker_reopens_the_circuit_after_the_cooldown() -> None:
    head, tail = Link("head", fails=True), Link("tail")
    built = chain_of(head, tail)

    for _ in range(FAILURE_THRESHOLD):
        call(built)
    skipped = head.calls

    # Backdate the breaker rather than patching the clock: monkeypatching
    # time.monotonic patches it for pytest too, which is a lot of blast radius
    # for a question about one dataclass.
    built._breakers["head"].opened_at -= COOLDOWN_SECONDS + 1

    call(built)
    assert head.calls == skipped + 1, "a recovered link must get a probe"


def test_a_recovered_link_takes_the_lead_again(monkeypatch) -> None:
    head, tail = Link("head", fails=True), Link("tail")
    built = chain_of(head, tail)
    call(built)

    head.fails = False
    call(built)

    assert built.served_by == "head"
    assert built.degraded is False, "recovery must clear the degraded flag, not latch it"


def test_success_resets_the_failure_count() -> None:
    head, tail = Link("head", fails=True), Link("tail")
    built = chain_of(head, tail)

    call(built)
    head.fails = False
    call(built)
    head.fails = True

    # One earlier failure must not count towards the threshold after a success.
    for _ in range(FAILURE_THRESHOLD - 1):
        call(built)
    assert built.served_by == "tail"
    assert "circuit open" not in (built.degraded_reason or "")


# --------------------------------------------------------------------------
# The chain cannot run out
# --------------------------------------------------------------------------
def test_the_mock_is_appended_when_it_is_not_configured() -> None:
    """A chain that could run out of links makes an outage a crash."""
    assert ProviderChain(names=("watsonx",)).names[-1] == "mock"


def test_the_mock_is_not_duplicated_when_already_present() -> None:
    assert ProviderChain(names=("ollama", "mock")).names == ("ollama", "mock")


def test_a_chain_of_only_failures_raises_rather_than_returning_nothing() -> None:
    """Unreachable while the mock is terminal, but not left to an assumption."""
    built = chain_of(Link("a", fails=True), Link("b", fails=True))
    with pytest.raises(LLMUnavailable):
        call(built)


def test_the_default_chain_ends_in_the_offline_stand_in() -> None:
    built = ProviderChain()
    assert built.names[-1] == "mock"
    assert isinstance(built._links[-1], MockGraniteLLM)


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
def test_an_explicit_chain_is_read_in_order(monkeypatch) -> None:
    # LLM is a frozen dataclass -- deliberately, since a safety threshold that
    # can be reassigned at runtime is not a threshold. Replace the whole object.
    monkeypatch.setattr(chain_module, "LLM", SimpleNamespace(chain="watsonx, ollama ,mock", provider="mock"))
    assert configured_chain() == ("watsonx", "ollama", "mock")


def test_a_single_configured_provider_still_works(monkeypatch) -> None:
    """Existing single-provider configuration must keep working unchanged."""
    monkeypatch.setattr(chain_module, "LLM", SimpleNamespace(chain="", provider="ollama"))
    assert configured_chain() == ("ollama",)


def test_an_empty_configuration_still_yields_a_usable_chain(monkeypatch) -> None:
    monkeypatch.setattr(chain_module, "LLM", SimpleNamespace(chain="", provider=""))
    assert configured_chain() == ("mock",)
