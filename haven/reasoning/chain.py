"""Trying providers in order, and being honest about which one answered.

A chain because the alternative is worse. With one provider, a watsonx outage
during a demo means no reasoning tier at all; with a chain, it means local
Granite picks up, and if that is absent too, the offline stand-in does. The
system keeps working.

The danger in that is obvious the moment it is written down: a chain that
silently degrades is a system quietly telling you less than it knows. HAVEN's
`provider_outage` scenario exists precisely to reject that behaviour. So the
chain is loud. `served_by` names the link that actually answered, and any answer
from below the head of the chain marks the evaluation degraded, exactly as a
total outage does.

The circuit breaker is not an optimisation. Without it a chain whose first link
is down pays that link's timeout on every single call, and an evaluation with
six Situations spends six timeouts discovering the same thing. After a few
consecutive failures the link is skipped outright for a cooling period, then
allowed one probe.

The terminal link is always the mock, which is what makes "the reasoning tier is
unavailable" a state the system can be in rather than a crash.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from haven.config import LLM
from haven.reasoning.llm import LLMUnavailable, MockGraniteLLM, ReasoningLLM, build_llm

#: Consecutive failures before a link is skipped.
FAILURE_THRESHOLD = 3
#: Seconds a link stays skipped before one probe is allowed through.
COOLDOWN_SECONDS = 30.0


@dataclass
class _Breaker:
    """One link's health. Closed means in use; open means skipped for now."""

    failures: int = 0
    opened_at: float | None = None

    def is_open(self, now: float) -> bool:
        if self.opened_at is None:
            return False
        if now - self.opened_at >= COOLDOWN_SECONDS:
            # Half-open: let exactly one call through to find out.
            self.opened_at = None
            self.failures = FAILURE_THRESHOLD - 1
            return False
        return True

    def record_failure(self, now: float) -> None:
        self.failures += 1
        if self.failures >= FAILURE_THRESHOLD and self.opened_at is None:
            self.opened_at = now

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None


@dataclass
class ProviderChain(ReasoningLLM):
    """Providers in preference order, with the offline stand-in last.

    Presents itself as a single ``ReasoningLLM``, so nothing upstream knows there
    is a chain at all -- the graph asks one object for a completion, as before.
    """

    names: tuple[str, ...] = ()
    _links: list[ReasoningLLM] = field(default_factory=list, repr=False)
    _breakers: dict[str, _Breaker] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    #: The link that answered the most recent call, and how it went.
    served_by: str = ""
    attempted: list[str] = field(default_factory=list)
    degraded: bool = False
    degraded_reason: str | None = None

    def __post_init__(self) -> None:
        names = self.names or configured_chain()
        # The mock is appended rather than assumed: a chain that could run out
        # of links would make an outage a crash instead of a state.
        if "mock" not in names:
            names = (*names, "mock")
        self.names = names
        self._links = [build_llm(name) for name in names]
        self._breakers = {name: _Breaker() for name in names}

    # -- ReasoningLLM ----------------------------------------------------
    @property
    def provider(self) -> str:
        """The link that answered, so the audit trail names the real source."""
        return self.served_by or self._links[0].provider

    @property
    def model_id(self) -> str:
        return self._model_id or self._links[0].model_id

    _model_id: str = ""

    def complete(self, task: str, prompt: str, context: dict[str, Any]) -> str:
        attempted: list[str] = []
        failures: list[str] = []
        now = time.monotonic()

        for name, link in zip(self.names, self._links, strict=True):
            with self._lock:
                breaker = self._breakers[name]
                if breaker.is_open(now):
                    failures.append(f"{name}: skipped, circuit open")
                    continue
            attempted.append(name)

            try:
                completion = link.complete(task, prompt, context)
            except LLMUnavailable as exc:
                with self._lock:
                    self._breakers[name].record_failure(now)
                failures.append(f"{name}: {exc}")
                continue

            with self._lock:
                self._breakers[name].record_success()
            self._record(name, link, attempted, failures)
            return completion

        # Unreachable while the mock is terminal and cannot raise, but a chain
        # that assumed that would be relying on an invariant it does not enforce.
        raise LLMUnavailable("; ".join(failures) or "no provider in the chain answered")

    # -- reporting -------------------------------------------------------
    def _record(self, name: str, link: ReasoningLLM, attempted: list[str], failures: list[str]) -> None:
        self.served_by = link.provider
        self._model_id = link.model_id
        self.attempted = attempted
        # Degraded whenever the answer came from below the head of the chain.
        # Falling back is not a neutral event: the operator asked for procedure
        # interpretation from a particular model and got it from another.
        self.degraded = name != self.names[0]
        self.degraded_reason = "; ".join(failures) if failures else None

    def status(self) -> dict[str, Any]:
        return {
            "chain": list(self.names),
            "attempted": list(self.attempted),
            "served_by": self.served_by,
            "degraded": self.degraded,
            "degraded_reason": self.degraded_reason,
        }


def configured_chain() -> tuple[str, ...]:
    """The chain from configuration.

    ``HAVEN_LLM_CHAIN`` wins when set (``watsonx,ollama,mock``). Otherwise the
    single configured provider heads a chain terminating in the mock, so the
    existing single-provider configuration keeps working unchanged.
    """
    raw = LLM.chain.strip()
    if raw:
        return tuple(name.strip().lower() for name in raw.split(",") if name.strip())
    return (LLM.provider or "mock",)


def build_chain(names: tuple[str, ...] | None = None) -> ProviderChain:
    return ProviderChain(names=names or ())


__all__ = [
    "COOLDOWN_SECONDS",
    "FAILURE_THRESHOLD",
    "MockGraniteLLM",
    "ProviderChain",
    "build_chain",
    "configured_chain",
]
