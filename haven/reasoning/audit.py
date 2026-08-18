"""Immutable audit trail (the IBM Bob orchestration layer's record).

Every step of the reasoning flow is appended with an HMAC-SHA256 tag chained to
the previous entry. The trail records inputs and outputs, not just outcomes, so
a reviewer can reconstruct why a recommendation was made -- or why it was
refused.

Two properties, and the difference between them matters:

*Corruption* is an entry edited in place with its tag left stale. An unkeyed
digest catches that, and v1's did.

*Tampering* is an entry rewritten and re-digested so the record still verifies.
An unkeyed digest cannot catch it, because anyone can recompute it. v1 could not
tell a rewritten history from a true one -- a gap found by inspection, absent
from v1's own honesty statement. Keying the chain (see :mod:`haven.reasoning.signing`)
closes it: without the key an attacker can destroy the record, which is obvious,
but cannot forge a different plausible one.

The chain is **global**, not per-trail. Each entry links to whatever entry was
written before it anywhere in the ledger, so removing an entire trail breaks the
links either side of the hole. Under v1's per-trail chains every trail restarted
from GENESIS and a whole trail could be deleted undetectably -- the remaining
trails still verified perfectly, because nothing recorded that the deleted one
had ever existed.
"""

from __future__ import annotations

import hmac
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256

from haven.reasoning.signing import audit_key


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


@dataclass
class AuditEntry:
    seq: int
    step: str
    tier: str
    detail: str
    inputs: dict
    outputs: dict
    started_at: datetime
    duration_ms: float
    prev_hash: str
    entry_hash: str = ""
    # Position in the global ledger, distinct from ``seq`` which counts within
    # one trail. Signed, but deliberately absent from ``as_dict``: it is
    # ledger bookkeeping, and the locked contract does not carry it.
    global_seq: int = 0

    def compute_mac(self) -> str:
        """The entry's authentication tag.

        Covers every field that is a *claim about what happened*, plus the
        entry's position in both its trail and the ledger, plus the link to its
        predecessor -- so neither the content, nor the ordering, nor the
        threading of the chain can be altered without the key.

        ``duration_ms`` is deliberately excluded. It is wall-clock measurement
        noise rather than a claim about what happened, and signing it would make
        a faithful re-run of the same decision fail to verify against its own
        record -- turning reproducibility, which this system treats as a success
        metric, into an integrity failure.
        """
        body = _canonical(
            {
                "seq": self.seq,
                "global_seq": self.global_seq,
                "step": self.step,
                "tier": self.tier,
                "detail": self.detail,
                "inputs": self.inputs,
                "outputs": self.outputs,
                "started_at": self.started_at.isoformat(),
                "prev_hash": self.prev_hash,
            }
        )
        return hmac.new(audit_key(), body.encode("utf-8"), sha256).hexdigest()

    def mac_is_valid(self) -> bool:
        """Constant-time comparison. ``==`` on a tag leaks it a byte at a time."""
        return hmac.compare_digest(self.compute_mac(), self.entry_hash)

    def as_dict(self) -> dict:
        return {
            "seq": self.seq,
            "step": self.step,
            "tier": self.tier,
            "detail": self.detail,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "started_at": self.started_at,
            "duration_ms": round(self.duration_ms, 2),
            "entry_hash": self.entry_hash,
            "prev_hash": self.prev_hash,
        }


GENESIS = "0" * 64


class _GlobalChain:
    """The single append point for the whole ledger.

    A process-wide head, advanced under a lock. Every trail's entries thread
    through it, which is what makes a deleted trail leave a visible hole rather
    than vanishing cleanly.

    Milestone 2.2 gives this durable backing; in this milestone the chain lives
    for the life of the process, which is enough to make the linking property
    real and testable.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._head = GENESIS
        self._seq = 0

    def advance(self, build) -> AuditEntry:
        """Bind ``build`` to the current head and publish the entry it returns.

        The callback receives ``(prev_hash, global_seq)`` and returns a fully
        populated entry. Held under the lock for its whole duration so two
        concurrent situations cannot both chain onto the same predecessor and
        silently fork the ledger -- which Phase 6's fan-out makes reachable.
        """
        with self._lock:
            self._seq += 1
            entry = build(self._head, self._seq)
            entry.entry_hash = entry.compute_mac()
            self._head = entry.entry_hash
            return entry

    @property
    def head(self) -> str:
        return self._head

    @property
    def length(self) -> int:
        return self._seq

    def reset(self) -> None:
        """Return to genesis. For tests that need an isolated ledger."""
        with self._lock:
            self._head, self._seq = GENESIS, 0


CHAIN = _GlobalChain()


@dataclass
class AuditTrail:
    """Append-only, hash-chained log for one Situation."""

    audit_ref: str
    situation_id: str
    provider: str = ""
    model_id: str = ""
    created_at: datetime = field(default_factory=_now)
    entries: list[AuditEntry] = field(default_factory=list)

    def append(
        self,
        step: str,
        tier: str,
        detail: str,
        inputs: dict | None = None,
        outputs: dict | None = None,
        duration_ms: float = 0.0,
        started_at: datetime | None = None,
    ) -> AuditEntry:
        seq = len(self.entries) + 1
        at = started_at or _now()

        def build(prev_hash: str, global_seq: int) -> AuditEntry:
            return AuditEntry(
                seq=seq,
                step=step,
                tier=tier,
                detail=detail,
                inputs=inputs or {},
                outputs=outputs or {},
                started_at=at,
                duration_ms=duration_ms,
                prev_hash=prev_hash,
                global_seq=global_seq,
            )

        entry = CHAIN.advance(build)
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        """Recheck this trail. False means an entry was altered after writing.

        Two things are checked: that every entry's tag still authenticates its
        contents, and that consecutive entries within the trail link to each
        other.

        The first entry's ``prev_hash`` is *not* compared against GENESIS. Under
        the global chain it points at whatever was written before it anywhere in
        the ledger, which is usually another trail. Verifying that link is the
        ledger's job, not a single trail's -- see :func:`verify_ledger`.
        """
        prev: str | None = None
        for entry in self.entries:
            if not entry.mac_is_valid():
                return False
            if prev is not None and entry.prev_hash != prev:
                return False
            prev = entry.entry_hash
        return True

    def as_dict(self) -> dict:
        return {
            "audit_ref": self.audit_ref,
            "situation_id": self.situation_id,
            "created_at": self.created_at,
            "steps": [e.as_dict() for e in self.entries],
            "chain_valid": self.verify(),
            "provider": self.provider,
            "model_id": self.model_id,
        }


@dataclass(frozen=True)
class LedgerVerdict:
    """The result of walking the whole ledger.

    ``ok`` alone would be a worse answer: when a ledger fails, the first thing a
    reviewer needs is *where*, and what kind of failure it was.
    """

    ok: bool
    entries_checked: int
    first_divergent_seq: int | None = None
    reason: str = ""

    def __bool__(self) -> bool:
        return self.ok


class AuditStore:
    """In-memory store. A production deployment writes to append-only storage."""

    def __init__(self) -> None:
        self._trails: dict[str, AuditTrail] = {}
        self._decisions: list[dict] = []
        self._lock = threading.Lock()

    def put(self, trail: AuditTrail) -> None:
        with self._lock:
            self._trails[trail.audit_ref] = trail

    def get(self, audit_ref: str) -> AuditTrail | None:
        return self._trails.get(audit_ref)

    def recent(self, limit: int = 25) -> list[AuditTrail]:
        return sorted(self._trails.values(), key=lambda t: t.created_at, reverse=True)[:limit]

    def record_decision(self, decision: dict) -> None:
        """Human-decision learning loop (PRD 8.2): every accept/override is kept."""
        with self._lock:
            self._decisions.append(decision)

    def decisions(self) -> list[dict]:
        return list(self._decisions)

    def entries_in_order(self) -> list[AuditEntry]:
        """Every entry the store holds, in global ledger order."""
        with self._lock:
            trails = list(self._trails.values())
        return sorted((e for t in trails for e in t.entries), key=lambda e: e.global_seq)

    def verify_ledger(self) -> LedgerVerdict:
        """Walk the whole chain, across trails, and report the first divergence.

        Catches three distinct failures a per-trail check cannot:

        * a forged or corrupted entry, wherever it sits;
        * a broken link between two entries, including across a trail boundary;
        * a **gap** in the global sequence, which is what deleting an entire
          trail leaves behind. Under v1 that deletion was invisible, because
          each surviving trail chained only to itself and verified perfectly.
        """
        entries = self.entries_in_order()
        prev, expected = GENESIS, 1

        for entry in entries:
            if entry.global_seq != expected:
                return LedgerVerdict(
                    False,
                    expected - 1,
                    entry.global_seq,
                    f"ledger jumps from {expected - 1} to {entry.global_seq}; "
                    f"{entry.global_seq - expected} entr"
                    f"{'y is' if entry.global_seq - expected == 1 else 'ies are'} missing",
                )
            if not entry.mac_is_valid():
                return LedgerVerdict(
                    False, expected - 1, entry.global_seq, "entry does not authenticate under the ledger key"
                )
            if entry.prev_hash != prev:
                return LedgerVerdict(False, expected - 1, entry.global_seq, "entry does not link to its predecessor")
            prev = entry.entry_hash
            expected += 1

        return LedgerVerdict(True, len(entries))


AUDIT = AuditStore()
