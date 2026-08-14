"""Immutable audit trail (the IBM Bob orchestration layer's record).

Every step of the reasoning flow is appended with a SHA-256 hash chained to the
previous entry. An entry cannot be altered after the fact without breaking the
chain, and ``verify`` reports that. The trail records inputs and outputs, not
just outcomes, so a reviewer can reconstruct why a recommendation was made --
or why it was refused.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


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

    def compute_hash(self) -> str:
        body = _canonical(
            {
                "seq": self.seq,
                "step": self.step,
                "tier": self.tier,
                "detail": self.detail,
                "inputs": self.inputs,
                "outputs": self.outputs,
                "started_at": self.started_at.isoformat(),
                "prev_hash": self.prev_hash,
            }
        )
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

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
        entry = AuditEntry(
            seq=len(self.entries) + 1,
            step=step,
            tier=tier,
            detail=detail,
            inputs=inputs or {},
            outputs=outputs or {},
            started_at=started_at or _now(),
            duration_ms=duration_ms,
            prev_hash=self.entries[-1].entry_hash if self.entries else GENESIS,
        )
        entry.entry_hash = entry.compute_hash()
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        """Recompute the chain. False means an entry was altered after writing."""
        prev = GENESIS
        for entry in self.entries:
            if entry.prev_hash != prev or entry.compute_hash() != entry.entry_hash:
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


AUDIT = AuditStore()
