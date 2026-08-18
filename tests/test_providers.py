"""The real provider adapters, which were `# pragma: no cover` until now.

Never executed and never tested is a poor state for the code that stands between
this system and the model it is built around. These tests exercise the adapters
with a fake chat model in place of the network, so every line runs on a clean
checkout with no Ollama and no watsonx credentials.

Two properties matter more than the plumbing.

**Every provider failure becomes `LLMUnavailable`.** The flow handles exactly one
failure condition, and it handles it well: degrade, keep the deterministic
evidence, escalate. An adapter that let a `ConnectionError` or a 429 escape as
itself would turn a handled operational event into a 500.

**Neither provider package is needed to import HAVEN.** They are an optional
extra; the offline path installs neither. Constructing a client is lazy, and a
missing package produces a `LLMUnavailable` naming the extra to install rather
than an ImportError from three frames down.
"""

from __future__ import annotations

import os

import pytest

from haven.reasoning.llm import (
    SYSTEM_PROMPT,
    LLMUnavailable,
    MockGraniteLLM,
    OllamaGraniteLLM,
    WatsonxGraniteLLM,
    build_llm,
)


class FakeResponse:
    def __init__(self, content) -> None:
        self.content = content


class FakeChatModel:
    """Stands in for a LangChain chat model, recording how it was called."""

    def __init__(self, content="{}", raises: Exception | None = None) -> None:
        self._content = content
        self._raises = raises
        self.invocations: list[list] = []
        self.bound: dict = {}

    def bind(self, **kwargs):
        self.bound.update(kwargs)
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        if self._raises is not None:
            raise self._raises
        return FakeResponse(self._content)


def with_client(provider, client):
    provider._client = client
    return provider


# --------------------------------------------------------------------------
# The interface holds
# --------------------------------------------------------------------------
@pytest.mark.parametrize("factory", [OllamaGraniteLLM, WatsonxGraniteLLM])
def test_a_provider_sends_the_system_prompt_and_the_task(factory) -> None:
    client = FakeChatModel('{"governing_passage_id": null, "reason": "", "rejected": []}')
    provider = with_client(factory(), client)

    provider.complete("SELECT", "THE TASK", {})

    system, human = client.invocations[0]
    assert system.content == SYSTEM_PROMPT
    assert human.content == "THE TASK"


@pytest.mark.parametrize("factory", [OllamaGraniteLLM, WatsonxGraniteLLM])
def test_content_parts_are_joined_rather_than_stringified(factory) -> None:
    """Some providers return a list of parts instead of a single string."""
    client = FakeChatModel([{"text": "half "}, {"text": "and half"}])
    assert with_client(factory(), client).complete("FUSE", "x", {}) == "half and half"


def test_ollama_asks_for_json_only_on_select() -> None:
    """SELECT is the one step whose answer is a structure rather than prose."""
    client = FakeChatModel("{}")
    provider = with_client(OllamaGraniteLLM(), client)

    provider.complete("FUSE", "x", {})
    assert client.bound == {}, "prose steps must not be constrained to JSON"

    provider.complete("SELECT", "x", {})
    assert client.bound.get("format") == "json"


def test_watsonx_asks_for_json_only_on_select() -> None:
    client = FakeChatModel("{}")
    provider = with_client(WatsonxGraniteLLM(), client)

    provider.complete("GENERATE", "x", {})
    assert client.bound == {}

    provider.complete("SELECT", "x", {})
    assert client.bound.get("response_format") == {"type": "json_object"}


# --------------------------------------------------------------------------
# Every failure becomes the one condition the flow handles
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("label", "error"),
    [
        ("connection refused", ConnectionError("connection refused")),
        ("timeout", TimeoutError("timed out")),
        ("rate limited", RuntimeError("429 Too Many Requests")),
        ("quota exhausted", RuntimeError("token quota exhausted for the current period")),
        ("unknown", ValueError("something else entirely")),
    ],
)
@pytest.mark.parametrize("factory", [OllamaGraniteLLM, WatsonxGraniteLLM])
def test_any_provider_failure_surfaces_as_unavailable(factory, label: str, error: Exception) -> None:
    provider = with_client(factory(), FakeChatModel(raises=error))
    with pytest.raises(LLMUnavailable):
        provider.complete("SELECT", "x", {})


def test_a_rate_limit_says_so(factory=WatsonxGraniteLLM) -> None:
    """The Lite tier is token-limited; exhausting it is foreseeable, not a bug."""
    provider = with_client(factory(), FakeChatModel(raises=RuntimeError("429 Too Many Requests")))
    with pytest.raises(LLMUnavailable) as excinfo:
        provider.complete("SELECT", "x", {})
    assert "rate-limited or out of quota" in str(excinfo.value)


# --------------------------------------------------------------------------
# The optional extra stays optional
# --------------------------------------------------------------------------
def test_constructing_a_provider_opens_no_client() -> None:
    """Import and construction must not require the provider packages."""
    assert OllamaGraniteLLM()._client is None
    assert WatsonxGraniteLLM()._client is None


def test_watsonx_without_credentials_names_what_is_missing() -> None:
    provider = WatsonxGraniteLLM()
    with pytest.raises(LLMUnavailable) as excinfo:
        provider._build_client()
    assert "WATSONX_API_KEY" in str(excinfo.value)


def test_a_missing_provider_package_names_the_extra(monkeypatch) -> None:
    """Better than an ImportError from three frames down."""
    import builtins

    real_import = builtins.__import__

    def refuse_langchain_ollama(name, *args, **kwargs):
        if name == "langchain_ollama":
            raise ImportError("No module named 'langchain_ollama'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse_langchain_ollama)
    with pytest.raises(LLMUnavailable) as excinfo:
        OllamaGraniteLLM()._build_client()
    assert "--extra providers" in str(excinfo.value)


# --------------------------------------------------------------------------
# Selection by name
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("mock", MockGraniteLLM),
        ("ollama", OllamaGraniteLLM),
        ("watsonx", WatsonxGraniteLLM),
        ("MOCK", MockGraniteLLM),
        ("  ollama  ", OllamaGraniteLLM),
    ],
)
def test_build_llm_resolves_a_provider_by_name(name: str, expected) -> None:
    assert isinstance(build_llm(name), expected)


def test_an_unknown_provider_falls_back_to_the_offline_stand_in() -> None:
    """Refusing to start over a typo in an env var would be the worse failure."""
    assert isinstance(build_llm("granite-via-carrier-pigeon"), MockGraniteLLM)


# --------------------------------------------------------------------------
# Infra-gated: these need something real running
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_ollama_answers_for_real() -> None:
    """Requires a local Ollama with the configured model pulled."""
    provider = OllamaGraniteLLM()
    completion = provider.complete("SELECT", 'Reply with {"governing_passage_id": null}', {})
    assert completion.strip()


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("WATSONX_API_KEY"), reason="watsonx credentials not configured")
def test_watsonx_answers_for_real() -> None:
    """Consumes Lite-tier tokens. Run deliberately, not in a loop."""
    provider = WatsonxGraniteLLM()
    completion = provider.complete("SELECT", 'Reply with {"governing_passage_id": null}', {})
    assert completion.strip()
