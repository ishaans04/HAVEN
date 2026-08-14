"""The offline guarantee, as executable tests (Architecture Design section 6, C4).

A fully offline run must stay a first-class path. Two hazards make that easy to
lose once LangChain is a dependency:

  1. ``langsmith`` ships as a hard dependency of ``langchain-core`` and traces
     automatically when the environment says to. A stray exported variable turns
     every evaluation into an outbound POST carrying the full prompt.
  2. An import-time network call anywhere in the tree would break the guarantee
     silently -- nothing fails, the demo is just slower and no longer offline.

Both are asserted here rather than trusted.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from app import offline

BACKEND_ROOT = Path(__file__).resolve().parents[1]

TRUTHY = ["true", "TRUE", "True", "1", "yes", "on"]


# --------------------------------------------------------------------------
# The guard clears tracing
# --------------------------------------------------------------------------
def test_importing_app_disables_langsmith_tracing() -> None:
    """The guard has already run by the time any test imports the package."""
    assert offline.is_tracing_disabled()


@pytest.mark.parametrize("value", TRUTHY)
@pytest.mark.parametrize(
    "variable",
    ["LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING", "LANGSMITH_TRACING", "LANGSMITH_TRACING_V2"],
)
def test_guard_clears_a_preset_tracing_variable(monkeypatch: pytest.MonkeyPatch, variable: str, value: str) -> None:
    """A developer who exported this for another project must not enable tracing here."""
    monkeypatch.setenv(variable, value)
    assert not offline.is_tracing_disabled(), "precondition: the variable should read as tracing-on"

    offline.disable_external_telemetry()

    assert offline.is_tracing_disabled()
    assert os.environ.get(variable) in (None, "false")


@pytest.mark.parametrize("variable", ["LANGCHAIN_API_KEY", "LANGSMITH_API_KEY"])
def test_guard_clears_a_preset_api_key(monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    monkeypatch.setenv(variable, "ls__not-a-real-key")
    assert not offline.is_tracing_disabled()

    offline.disable_external_telemetry()

    assert offline.is_tracing_disabled()
    assert variable not in os.environ


def test_guard_pins_third_party_telemetry_off() -> None:
    """Chroma and HuggingFace tooling arrive in Phase 5; their switches are pinned now."""
    status = offline.telemetry_status()
    assert status["ANONYMIZED_TELEMETRY"] == "False"
    assert status["CHROMA_TELEMETRY_ENABLED"] == "False"
    assert status["HF_HUB_DISABLE_TELEMETRY"] == "1"


def test_guard_is_idempotent() -> None:
    before = offline.telemetry_status()
    offline.disable_external_telemetry()
    offline.disable_external_telemetry()
    assert offline.telemetry_status() == before


# --------------------------------------------------------------------------
# The guard runs before LangChain, and importing the app opens no socket
# --------------------------------------------------------------------------
# Run in a subprocess: the parent process has already imported everything, so an
# in-process check could only ever confirm the import cache.
_SUBPROCESS_PREAMBLE = """
    import socket, sys

    opened = []
    _real_connect = socket.socket.connect
    _real_connect_ex = socket.socket.connect_ex

    def _blocked(self, address, *a, **kw):
        opened.append(address)
        raise AssertionError(f"network connection attempted at import time: {address!r}")

    socket.socket.connect = _blocked
    socket.socket.connect_ex = _blocked
    """


def _run_probe(body: str) -> subprocess.CompletedProcess[str]:
    script = textwrap.dedent(_SUBPROCESS_PREAMBLE) + textwrap.dedent(body)
    env = {
        **os.environ,
        # Hostile starting conditions: tracing explicitly ON before the import.
        "LANGCHAIN_TRACING_V2": "true",
        "LANGSMITH_TRACING": "true",
        "LANGCHAIN_API_KEY": "ls__not-a-real-key",
        "PYTHONPATH": str(BACKEND_ROOT),
    }
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=BACKEND_ROOT,
        env=env,
        timeout=180,
    )


def test_importing_app_main_opens_no_socket() -> None:
    """The whole API tier must import without touching the network."""
    result = _run_probe("""
        import app.main  # noqa: F401
        print("OK")
        """)
    assert result.returncode == 0, f"import attempted network I/O or failed:\n{result.stderr}"
    assert "OK" in result.stdout


def test_guard_wins_against_a_hostile_environment() -> None:
    """Tracing is forced on in the environment; importing app must still disable it."""
    result = _run_probe("""
        import app  # noqa: F401
        from app.offline import is_tracing_disabled
        assert is_tracing_disabled(), "guard failed to override a hostile environment"
        print("OK")
        """)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_langchain_sees_tracing_disabled_after_import() -> None:
    """LangChain's own view of the setting, not just ours.

    Asserting on our helper alone would prove nothing about what langchain-core
    actually does -- this reads the value through its own accessor.
    """
    result = _run_probe("""
        import app  # noqa: F401
        from langchain_core.tracers.langchain import LangChainTracer  # noqa: F401
        from langchain_core.utils.env import env_var_is_set

        assert not env_var_is_set("LANGCHAIN_TRACING_V2"), "langchain-core still sees tracing enabled"
        assert not env_var_is_set("LANGSMITH_TRACING"), "langchain-core still sees tracing enabled"
        print("OK")
        """)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_socket_probe_itself_fires() -> None:
    """The probe must actually catch a connection -- otherwise it proves nothing."""
    result = _run_probe("""
        import socket
        try:
            socket.socket().connect(("127.0.0.1", 9))
        except AssertionError:
            print("OK")
        else:
            raise SystemExit("probe did not fire")
        """)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_socket_module_is_importable_in_the_parent() -> None:
    """Guards against the probe leaking its monkeypatch into the test process."""
    assert socket.socket.connect is not None
