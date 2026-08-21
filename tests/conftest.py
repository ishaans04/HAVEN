"""Test isolation: the audit ledger, and the reasoning provider.

From Phase 2 the ledger is durable, which means a test run would otherwise write
into the same `haven_ledger.db` a developer's console is using, sign it with the
same key, and leave the global chain advanced by however many entries the suite
happened to append. Three separate ways for a test run to change the answer a
later one gets.

So the whole session is redirected: its own database, its own signing key, both
under pytest's temp root and both discarded afterwards. Nothing here weakens
what is under test -- the ledger is exercised exactly as it is in production,
just somewhere disposable.

Phase 10 adds the same treatment to the provider chain, for the same reason.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def offline_provider_chain() -> None:
    """Pin the suite to the offline stand-in, whatever `.env` says.

    Since Phase 10 a `.env` in the working directory is loaded at import, so a
    developer with real watsonx credentials configured would have the suite
    inherit them. Nothing reaches a provider today -- every test that evaluates
    passes ``llm=`` explicitly -- but that holds by convention rather than by
    construction, and the cost of the convention lapsing is a test run billed
    against a token-limited account and made non-deterministic by a live model.

    Set rather than merely cleared, so an exported HAVEN_LLM_CHAIN cannot win
    either: this is the one place where ambient configuration must lose.

    The credentials go too, and pinning the chain alone was not enough --
    `test_providers.py` constructs `WatsonxGraniteLLM()._build_client()` directly
    to assert it names the missing variable, which stopped raising the moment a
    developer had a real `.env`. The test was not wrong; the suite was reading
    live credentials. A test asserting behaviour *without* credentials has to be
    run without them, or it asserts nothing on the machines that matter most.
    """
    pinned = ("HAVEN_LLM_CHAIN", "HAVEN_LLM_PROVIDER", "WATSONX_API_KEY", "WATSONX_PROJECT_ID")
    previous = {name: os.environ.get(name) for name in pinned}
    os.environ["HAVEN_LLM_CHAIN"] = "mock"
    os.environ["HAVEN_LLM_PROVIDER"] = "mock"
    os.environ.pop("WATSONX_API_KEY", None)
    os.environ.pop("WATSONX_PROJECT_ID", None)

    # The settings object resolved at import, so the environment alone is too
    # late. It is mutated in place rather than replaced because every consumer
    # did `from haven.config import LLM`, binding this exact instance --
    # rebinding the name in haven.config would leave chain.py and llm.py holding
    # the original. LLMSettings is frozen to stop the reasoning tier altering
    # configuration at runtime; a session fixture pinning the offline provider
    # is the one place that restriction is deliberately stepped around, and it
    # is put back below.
    from haven.config import LLM

    original = {
        "chain": LLM.chain,
        "provider": LLM.provider,
        "watsonx_api_key": LLM.watsonx_api_key,
        "watsonx_project_id": LLM.watsonx_project_id,
    }
    object.__setattr__(LLM, "chain", "mock")
    object.__setattr__(LLM, "provider", "mock")
    object.__setattr__(LLM, "watsonx_api_key", "")
    object.__setattr__(LLM, "watsonx_project_id", "")

    yield

    for name, value in original.items():
        object.__setattr__(LLM, name, value)
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture(scope="session", autouse=True)
def isolated_ledger_session(tmp_path_factory) -> None:
    """Point the ledger and its key at throwaway paths for the whole run."""
    import haven.reasoning.audit as audit_module
    from haven.reasoning import signing

    root = tmp_path_factory.mktemp("ledger")

    # Set before the store is rebuilt, so it opens the temporary database.
    import os

    os.environ["HAVEN_LEDGER_DB"] = str(root / "haven_ledger.db")
    os.environ["HAVEN_AUDIT_KEY_FILE"] = str(root / ".audit_key")
    os.environ.pop("HAVEN_AUDIT_KEY", None)

    signing.reset_key_cache()
    audit_module.CHAIN.reset()

    # The singleton was built at import, before those variables were set. It has
    # not opened anything yet -- the connection is lazy precisely so this works
    # -- so pointing it at the temporary database is enough. No rebinding, which
    # matters: `from ... import AUDIT` binds the object, and any module that had
    # already imported it would otherwise keep writing to the wrong store.
    audit_module.AUDIT.reopen()

    yield

    audit_module.AUDIT.close()
