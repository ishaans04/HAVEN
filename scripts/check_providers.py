"""Check the reasoning-tier configuration before spending tokens on it.

    uv run python -m scripts.check_providers
    uv run python -m scripts.check_providers --provider watsonx
    uv run python -m scripts.check_providers --no-call        # config only

The watsonx Lite tier allows roughly 300k tokens a month, and the natural way to
discover that a key is wrong is to burn a twenty-scenario evaluation sweep
finding out. This does it for a few dozen tokens.

It exists mainly because the failure it diagnoses is silent. HAVEN's provider
chain terminates in the offline stand-in on purpose -- a demo that dies because
watsonx returned 429 is worse than one that degrades and says so -- which means
an unset variable, a missing extra, an expired key and a correctly configured
system that simply has not been asked to use watsonx all produce the same
outcome: a working console served by the mock. The chain is right to behave that
way. This is the tool that tells the difference.

Checks run in order and stop at the first thing that is actually wrong, because
reporting six failures that are all one missing variable is not a diagnosis.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from haven.config import LLM
from haven.reasoning.chain import configured_chain
from haven.reasoning.llm import LLMUnavailable, build_llm

#: Cheap and unambiguous: a correct answer is a handful of tokens, and a model
#: that cannot manage it is not going to interpret a procedure.
PROBE_PROMPT = "Reply with exactly the word: ready"

#: Vocabulary the provider needs for its client, per provider name.
REQUIRED_MODULE = {"watsonx": "langchain_ibm", "ollama": "langchain_ollama"}


def mask(value: str) -> str:
    """Enough of a secret to recognise it, never enough to use it.

    A preflight tool is exactly the output somebody pastes into a chat window
    when asking why it failed.
    """
    if not value:
        return "(not set)"
    if len(value) <= 8:
        return "set, " + "*" * len(value)
    return f"{value[:3]}...{value[-4:]} ({len(value)} chars)"


def report_environment() -> None:
    env_file = Path(".env")
    if env_file.exists():
        print(f"  .env                  found at {env_file.resolve()}")
    else:
        print("  .env                  not found -- reading the shell environment only")
        print("                        (copy .env.example to .env to configure it there)")

    print(f"  HAVEN_LLM_CHAIN       {os.getenv('HAVEN_LLM_CHAIN') or '(not set)'}")
    print(f"  HAVEN_LLM_PROVIDER    {LLM.provider}")
    print(f"  HAVEN_LLM_MODEL       {LLM.model_id}")
    print(f"  WATSONX_URL           {LLM.watsonx_url}")
    print(f"  WATSONX_API_KEY       {mask(LLM.watsonx_api_key)}")
    print(f"  WATSONX_PROJECT_ID    {mask(LLM.watsonx_project_id)}")
    print(f"  OLLAMA_URL            {LLM.ollama_url}")


def explain(provider: str, error: Exception) -> list[str]:
    """Map a provider failure onto the thing that is actually wrong.

    watsonx reports most misconfiguration as an authentication error, including
    two cases that are not one: a key valid in another region, and a project the
    key cannot see. Both read as "bad API key" and send people to regenerate a
    key that was fine.
    """
    text = str(error).lower()

    if "extra" in text or "no module named" in text:
        return ["install the provider packages:  uv sync --extra providers"]

    if provider == "watsonx":
        # IBM Cloud IAM is a single global endpoint, so an API key is scoped to
        # an *account*, never to a region. That distinction decides the advice:
        # "could not be found" means the key string itself is not recognised and
        # WATSONX_URL is irrelevant, while a plain 401 leaves the region open.
        # Getting this backwards sends people to regenerate a key that was fine.
        if "could not be found" in text or "bxnim0415" in text:
            return [
                "IBM IAM does not recognise this API key at all, so the region is not",
                "  the problem -- key lookup happens at a single global endpoint.",
                "  1. Check for a truncated paste, or a trailing space or newline.",
                "  2. The key may have been deleted, or belong to another account.",
                "  Create a fresh one under Manage > Access (IAM) > API keys.",
            ]
        if "401" in text or "unauthor" in text or "authenticat" in text or "invalidcredentials" in text:
            return [
                "the key was rejected. In order of likelihood:",
                "  1. WATSONX_API_KEY is expired, revoked, or was copied with whitespace.",
                "  2. WATSONX_URL is the wrong region for this project. It is",
                f"     {LLM.watsonx_url!r}.",
                "  3. The key is valid but its account has no access to this project.",
            ]
        if "model" in text and ("404" in text or "not found" in text or "not_supported" in text):
            return [
                f"the model id {LLM.model_id!r} was not found in this project.",
                "  watsonx model ids change between releases -- open your project's",
                "  model list and paste the id it shows into HAVEN_LLM_MODEL.",
            ]
        if "403" in text or "forbidden" in text or "no_associated_service" in text:
            return [
                f"authenticated, but project {mask(LLM.watsonx_project_id)} is not reachable",
                "  with this key. Check WATSONX_PROJECT_ID, that the project has a",
                "  Watson Machine Learning service associated, and that the key's",
                "  account is the one that owns it.",
            ]
        if "429" in text or "quota" in text or "rate limit" in text or "exhausted" in text:
            return [
                "authenticated, but the account is rate-limited or out of quota.",
                "  The Lite tier is ~300k tokens/month. Run evaluation sweeps against",
                "  Ollama and keep watsonx for the demo.",
            ]
        if "404" in text or "not found" in text:
            return [
                f"a 404 from {LLM.watsonx_url!r}. Either the region URL is wrong, or",
                f"  the model id {LLM.model_id!r} is not deployed in this project.",
            ]
    if provider == "ollama" and ("connect" in text or "refused" in text):
        return [f"nothing is listening on {LLM.ollama_url}. Start it with `ollama serve`."]

    return ["no specific cause could be inferred from the error above."]


def check(provider: str, *, call: bool) -> bool:
    print(f"\nProvider: {provider}")

    module = REQUIRED_MODULE.get(provider)
    if module:
        try:
            __import__(module)
            print(f"  package               {module} importable")
        except ImportError:
            print(f"  package               {module} MISSING")
            print("                        fix:  uv sync --extra providers")
            return False

    if provider == "watsonx" and not (LLM.watsonx_api_key and LLM.watsonx_project_id):
        missing = [
            name
            for name, value in (
                ("WATSONX_API_KEY", LLM.watsonx_api_key),
                ("WATSONX_PROJECT_ID", LLM.watsonx_project_id),
            )
            if not value
        ]
        print(f"  credentials           MISSING: {', '.join(missing)}")
        return False

    if not call:
        print("  live call             skipped (--no-call)")
        return True

    try:
        llm = build_llm(provider)
        answer = llm.complete("PREFLIGHT", PROBE_PROMPT, {})
    except LLMUnavailable as exc:
        print(f"  live call             FAILED -- {exc}")
        for line in explain(provider, exc):
            print(f"                        {line}")
        return False
    except Exception as exc:  # noqa: BLE001 - a preflight reports, it does not raise
        print(f"  live call             FAILED -- {type(exc).__name__}: {exc}")
        for line in explain(provider, exc):
            print(f"                        {line}")
        return False

    print(f"  live call             OK -- answered {answer.strip()[:60]!r}")
    print(f"  model                 {llm.model_id}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_providers", description=__doc__)
    parser.add_argument("--provider", action="append", default=[], help="check only this provider; repeatable")
    parser.add_argument("--no-call", action="store_true", help="report configuration without contacting anything")
    args = parser.parse_args(argv)

    print("Configuration")
    report_environment()

    chain = configured_chain()
    print(f"\n  resolved chain        {' -> '.join(chain)}")
    if chain == ("mock",) and not args.provider:
        # The single most common reason a correctly credentialled setup still
        # runs on the stand-in, and nothing else in the system says so out loud.
        print("                        !! nothing but the offline stand-in will be tried.")
        print("                        !! set HAVEN_LLM_CHAIN=watsonx,mock to use watsonx.")

    # The mock always works and proves nothing, so it is not worth a live call.
    targets = args.provider or [name for name in chain if name != "mock"]
    if not targets:
        print("\nNo real provider configured. Nothing to check.")
        return 1

    results = {name: check(name, call=not args.no_call) for name in targets}

    print()
    if all(results.values()):
        print(f"Ready: {', '.join(results)}. Zone 6 will name the link that served each answer.")
        return 0
    failed = [name for name, ok in results.items() if not ok]
    print(f"Not ready: {', '.join(failed)}. HAVEN would fall through to the offline stand-in and say so.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
