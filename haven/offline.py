"""The offline guarantee, enforced at import time.

HAVEN v2 Architecture Design section 6 requires that a fully offline run -- no
API key, no model download, no network -- stays a first-class path rather than a
degraded one. Adding LangChain puts that guarantee at risk in a way that is easy
to miss:

``langsmith`` is a hard dependency of ``langchain-core``, not an optional extra.
It ships whether or not anyone asked for it, and ``langchain-core`` enables
tracing automatically whenever ``LANGCHAIN_TRACING_V2`` or ``LANGSMITH_TRACING``
is truthy in the environment. A developer who once exported that variable for an
unrelated project would silently turn every HAVEN evaluation into an outbound
POST carrying the full prompt -- including the deterministic fact set.

So the variables are cleared rather than merely left unset, and the clearing
happens in ``app/__init__.py`` before any submodule is imported, which is the
only point guaranteed to precede a LangChain import.

This module deliberately imports nothing but ``os``. It must stay importable
before the rest of the package exists.
"""

from __future__ import annotations

import os

# Every environment variable that can cause LangChain, LangGraph, or LangSmith to
# emit telemetry or contact a hosted service. Cleared, not read.
_TELEMETRY_ENV_VARS = (
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_TRACING",
    "LANGSMITH_TRACING",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_API_KEY",
    "LANGSMITH_API_KEY",
    "LANGCHAIN_ENDPOINT",
    "LANGSMITH_ENDPOINT",
    "LANGCHAIN_PROJECT",
    "LANGSMITH_PROJECT",
    "LANGCHAIN_CALLBACKS_BACKGROUND",
)

# Set positively rather than merely cleared, so that a library reading the value
# directly sees an explicit "off" instead of an absent key it might default.
_TELEMETRY_OFF = {
    "LANGCHAIN_TRACING_V2": "false",
    "LANGSMITH_TRACING": "false",
    # Chroma (Phase 5) posts anonymised usage stats unless told otherwise.
    "ANONYMIZED_TELEMETRY": "False",
    "CHROMA_TELEMETRY_ENABLED": "False",
    # HuggingFace tooling reachable via fastembed (Phase 5).
    "HF_HUB_DISABLE_TELEMETRY": "1",
}


def disable_external_telemetry() -> None:
    """Clear every tracing/telemetry variable, then pin the switches to off.

    Idempotent, and safe to call before any third-party package is imported.
    """
    for name in _TELEMETRY_ENV_VARS:
        os.environ.pop(name, None)
    os.environ.update(_TELEMETRY_OFF)


def telemetry_status() -> dict[str, str | None]:
    """The current value of every guarded variable, for assertion in tests.

    Returned rather than logged: this is evidence for a test, not diagnostics.
    """
    names = set(_TELEMETRY_ENV_VARS) | set(_TELEMETRY_OFF)
    return {name: os.environ.get(name) for name in sorted(names)}


def is_tracing_disabled() -> bool:
    """True when nothing in the environment can enable LangSmith tracing."""
    for name in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING", "LANGSMITH_TRACING", "LANGSMITH_TRACING_V2"):
        value = os.environ.get(name)
        if value is not None and value.strip().lower() in {"true", "1", "yes", "on"}:
            return False
    return not (os.environ.get("LANGCHAIN_API_KEY") or os.environ.get("LANGSMITH_API_KEY"))
