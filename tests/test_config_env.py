"""`.env` loading, and the two things it must never be allowed to do.

Everything here runs in a subprocess. It has to: `haven.config` resolves every
setting at import time, so a test that imported it in-process would be asserting
against whatever the environment looked like when pytest started.

What is being defended is narrow. Before Phase 10 `.env.example` told people to
copy it to `.env`, and nothing read the result — credentials went in, the console
came up on the offline stand-in, and no error was raised anywhere, because the
provider chain falling through to the mock is correct behaviour rather than a
fault. Making the file work is easy. Making it work without handing it the two
powers it must not have is what these tests cover.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Reports the resolved configuration as JSON. Kept to one statement per line so
#: a failure points at something readable.
PROBE = """
import json
from haven.config import LLM
from haven.offline import is_tracing_disabled
from haven.reasoning.chain import configured_chain
print(json.dumps({
    "api_key": LLM.watsonx_api_key,
    "project_id": LLM.watsonx_project_id,
    "url": LLM.watsonx_url,
    "model_id": LLM.model_id,
    "chain": list(configured_chain()),
    "tracing_disabled": is_tracing_disabled(),
}))
"""


def resolve(workdir: Path, env_file: str | None = None, **overrides: str) -> dict:
    """Import HAVEN in a clean subprocess and report what it resolved to."""
    if env_file is not None:
        (workdir / ".env").write_text(env_file, encoding="utf-8")

    # Only PATH and the interpreter's own plumbing survive, so an ambient
    # WATSONX_API_KEY on the developer's machine cannot make a test pass.
    import os

    env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "PYTHONPATH": str(REPO_ROOT),
        "PYTHONIOENCODING": "utf-8",
        **overrides,
    }

    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"probe failed:\n{result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


# --------------------------------------------------------------------------
# It works at all
# --------------------------------------------------------------------------
def test_a_dot_env_file_reaches_the_configuration(tmp_path) -> None:
    """The claim `.env.example` has always made, now true."""
    resolved = resolve(
        tmp_path,
        env_file=(
            "WATSONX_API_KEY=key-from-the-file\n"
            "WATSONX_PROJECT_ID=project-from-the-file\n"
            "WATSONX_URL=https://eu-de.ml.cloud.ibm.com\n"
            "HAVEN_LLM_MODEL=ibm/granite-from-the-file\n"
        ),
    )
    assert resolved["api_key"] == "key-from-the-file"
    assert resolved["project_id"] == "project-from-the-file"
    assert resolved["url"] == "https://eu-de.ml.cloud.ibm.com"
    assert resolved["model_id"] == "ibm/granite-from-the-file"


def test_the_chain_from_dot_env_switches_the_tier_on(tmp_path) -> None:
    """The variable people forget, and the reason a correct key still runs mock."""
    resolved = resolve(tmp_path, env_file="HAVEN_LLM_CHAIN=watsonx,ollama,mock\n")
    assert resolved["chain"] == ["watsonx", "ollama", "mock"]


def test_no_dot_env_leaves_the_defaults_alone(tmp_path) -> None:
    """The offline default is the shipped behaviour and must not need a file."""
    resolved = resolve(tmp_path)
    assert resolved["api_key"] == ""
    assert resolved["chain"] == ["mock"]


# --------------------------------------------------------------------------
# What the file may not do, 1: override a real environment
# --------------------------------------------------------------------------
def test_an_exported_variable_beats_the_file(tmp_path) -> None:
    """`override=False`, and it is load-bearing rather than a preference.

    CI, the Dockerfile and `tests/conftest.py` all configure HAVEN by setting
    variables directly. If a `.env` that happened to be present could overrule
    them, a developer's local credentials would silently change what CI tested.
    """
    resolved = resolve(
        tmp_path,
        env_file="WATSONX_API_KEY=key-from-the-file\nHAVEN_LLM_CHAIN=watsonx,mock\n",
        WATSONX_API_KEY="key-from-the-environment",
        HAVEN_LLM_CHAIN="mock",
    )
    assert resolved["api_key"] == "key-from-the-environment"
    assert resolved["chain"] == ["mock"]


# --------------------------------------------------------------------------
# What the file may not do, 2: switch telemetry back on
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "line",
    [
        "LANGCHAIN_TRACING_V2=true",
        "LANGSMITH_TRACING=true",
        "LANGCHAIN_API_KEY=ls-would-phone-home",
        "LANGSMITH_API_KEY=ls-would-phone-home",
    ],
)
def test_a_dot_env_cannot_re_enable_tracing(tmp_path, line: str) -> None:
    """The ordering guard, and the reason the two lines in `haven/__init__.py`
    are in the order they are.

    `load_dotenv()` runs first so the file can supply credentials;
    `disable_external_telemetry()` runs second so the file cannot supply
    telemetry. Swapping them breaks the two API-key cases below — and only those,
    which is worth knowing rather than glossing. The two tracing switches survive
    a swap because `haven.offline` pins them to "false" *positively* and
    `override=False` then refuses to replace a value that is already set; the API
    keys are only cleared, so nothing stops a later load from reinstating them.
    Both halves are needed, and this is the half that depends on the order.

    A reinstated LangSmith tracer would send prompt content — passage prose, crew
    state — to a third party, and look like nothing at all while doing it.
    """
    resolved = resolve(tmp_path, env_file=line + "\n")
    assert resolved["tracing_disabled"] is True


def test_the_offline_guard_still_runs_when_a_dot_env_exists(tmp_path) -> None:
    """A malformed or exotic `.env` must not stop the guard executing."""
    resolved = resolve(tmp_path, env_file="NOT_A_PAIR\n\n# comment only\nWATSONX_API_KEY=k\n")
    assert resolved["tracing_disabled"] is True
    assert resolved["api_key"] == "k"


# --------------------------------------------------------------------------
# The suite pins itself to the stand-in
# --------------------------------------------------------------------------
def test_this_suite_never_reaches_a_real_provider() -> None:
    """`tests/conftest.py` pins the chain, and here is the assertion that says so.

    Without it the suite would inherit whatever a developer has configured, and
    a single test that forgot to pass `llm=` would bill a token-limited account
    and make its own result non-deterministic.
    """
    from haven.reasoning.chain import configured_chain

    assert configured_chain() == ("mock",)


def test_the_preflight_never_prints_a_credential(tmp_path) -> None:
    """It is the output people paste into a chat window when asking for help."""
    from scripts.check_providers import mask

    secret = "abcdefghijklmnopqrstuvwxyz012345"
    masked = mask(secret)
    assert secret not in masked
    assert masked.startswith("abc")
    assert "2345" in masked, "enough tail to tell two keys apart"
    assert mask("") == "(not set)"
    # A short value is not partially revealed: three characters of an eight
    # character secret is a meaningful fraction of it.
    assert "short" not in mask("short") and mask("short") == "set, *****"


# --------------------------------------------------------------------------
# The preflight's diagnosis
#
# Its whole value is turning one of watsonx's several indistinguishable-looking
# authentication errors into the thing that is actually wrong. The strings below
# are the real ones, taken from live responses rather than invented, because a
# matcher tested against invented text is a matcher tested against itself.
# --------------------------------------------------------------------------
IAM_KEY_NOT_FOUND = (
    "InvalidCredentialsError: Attempt of authenticating connection to service failed, "
    'please validate your credentials. Error: {"errorCode":"BXNIM0415E",'
    '"errorMessage":"Provided API key could not be found.","context":{"url":"https://iam.cloud.ibm.com"}}'
)


def test_a_missing_key_is_not_blamed_on_the_region() -> None:
    """The mis-diagnosis worth preventing.

    IBM Cloud IAM resolves API keys at one global endpoint, so a key that "could
    not be found" is not a regional problem and `WATSONX_URL` is irrelevant. The
    obvious matcher — treat every authentication error as possibly-regional —
    would send somebody to change a URL that was already correct.
    """
    from scripts.check_providers import explain

    lines = " ".join(explain("watsonx", RuntimeError(IAM_KEY_NOT_FOUND)))
    assert "region is not" in lines
    assert "truncated paste" in lines
    assert "WATSONX_URL" not in lines, "the region must not be offered as a cause here"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("401 Unauthorized", "wrong region"),
        ("403 Forbidden: no_associated_service", "not reachable"),
        ("429 Too Many Requests: quota exhausted", "rate-limited"),
        ("404 model_not_supported: unknown model", "was not found in this project"),
        ("ModuleNotFoundError: No module named 'langchain_ibm'", "uv sync --extra providers"),
    ],
)
def test_each_failure_names_its_own_cause(error: str, expected: str) -> None:
    from scripts.check_providers import explain

    assert expected in " ".join(explain("watsonx", RuntimeError(error)))


def test_an_unrecognised_error_says_so_rather_than_guessing() -> None:
    """A confident wrong diagnosis costs more than an honest shrug."""
    from scripts.check_providers import explain

    assert "no specific cause" in " ".join(explain("watsonx", RuntimeError("connection reset by peer")))


def test_the_suite_runs_without_watsonx_credentials() -> None:
    """Pinning the chain was not enough, and the gap was invisible until a real key existed.

    `test_providers.py` builds a watsonx client directly to assert it names the
    missing variable. With a developer's `.env` loaded that stopped raising —
    the assertion had quietly inverted into "credentials are present", on
    exactly the machines where the test mattered. A test about behaviour
    *without* credentials has to run without them.
    """
    from haven.config import LLM

    assert LLM.watsonx_api_key == ""
    assert LLM.watsonx_project_id == ""
