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
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from haven.reasoning.signing import audit_key

_DEFAULT_DB = Path(__file__).resolve().parents[2] / "haven_ledger.db"


def default_db_path() -> Path:
    """Where the ledger lives unless ``HAVEN_LEDGER_DB`` says otherwise."""
    override = os.getenv("HAVEN_LEDGER_DB")
    return Path(override) if override else _DEFAULT_DB


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

    def restore(self, head: str, seq: int) -> None:
        """Adopt a head recovered from durable storage.

        Called when a store opens an existing ledger, so a restart continues the
        chain instead of starting a second one beside it. Without this the first
        entry after a restart would link to GENESIS and the ledger would read as
        two unrelated histories -- exactly the per-trail blindness the global
        chain exists to remove.
        """
        with self._lock:
            self._head, self._seq = head, seq


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


SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_entries (
    global_seq  INTEGER PRIMARY KEY,
    audit_ref   TEXT    NOT NULL,
    seq         INTEGER NOT NULL,
    step        TEXT    NOT NULL,
    tier        TEXT    NOT NULL,
    detail      TEXT    NOT NULL,
    inputs      TEXT    NOT NULL,
    outputs     TEXT    NOT NULL,
    started_at  TEXT    NOT NULL,
    duration_ms REAL    NOT NULL,
    prev_hash   TEXT    NOT NULL,
    entry_hash  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ledger_entries_by_ref ON ledger_entries (audit_ref, seq);

CREATE TABLE IF NOT EXISTS trails (
    audit_ref    TEXT PRIMARY KEY,
    situation_id TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    provider     TEXT NOT NULL,
    model_id     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
    at_global_seq INTEGER PRIMARY KEY,
    head_hash     TEXT NOT NULL,
    recorded_at   TEXT NOT NULL
);
"""


class AuditStore:
    """A durable, append-only ledger backed by SQLite.

    v1 kept trails in a dict, so a restart lost every trail and every human
    decision. "Append-only audit trail" described an intent rather than a
    property of the system.

    Durability here means INSERT and nothing else. There is no UPDATE and no
    DELETE anywhere in this class, so the only way to alter a written record is
    to go around the application to the file -- which is exactly what the keyed
    global chain exists to make evident.

    The in-memory map is a cache, not the record. ``get`` falls back to the
    database, so a trail written before a restart still resolves.
    """

    # Every this many entries, record where the chain had reached.
    CHECKPOINT_INTERVAL = 25

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._configured_path = Path(db_path) if db_path is not None else None
        self._path: Path | None = None
        self._trails: dict[str, AuditTrail] = {}
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None
        self._adopt_if_present()

    def _adopt_if_present(self) -> None:
        """Pick up an existing ledger's chain head before anything is appended.

        Timing matters here. Entries are built by ``AuditTrail.append``, which
        advances the global chain, and only handed to ``put`` afterwards -- so
        waiting for the first database access to adopt the head would let the
        first entry after a restart link to GENESIS. The ledger would then read
        as two unrelated histories laid end to end, which is the exact
        per-trail blindness the global chain exists to remove.

        Opening only when the file already exists keeps the lazy behaviour that
        matters: a fresh checkout still creates no database merely by importing.
        """
        if self.path.exists():
            self._conn  # noqa: B018 - opening is the point; it adopts the head

    @property
    def path(self) -> Path:
        """Where this store writes. Resolved on first use, not at construction."""
        if self._path is None:
            self._path = self._configured_path or default_db_path()
        return self._path

    @property
    def _conn(self) -> sqlite3.Connection:
        """The database handle, opened on first use.

        Deliberately lazy. Connecting in ``__init__`` would mean that merely
        importing ``haven.api.main`` created a database file -- an import with a
        side effect on the filesystem, which is both surprising and awkward to
        test around, since the module-level singleton is built at import time
        and any redirection of the path necessarily happens after that.
        """
        with self._lock:
            if self._connection is None:
                path = self.path
                path.parent.mkdir(parents=True, exist_ok=True)
                # check_same_thread=False because Phase 6 fans Situations out
                # across a threadpool; every write is serialised by self._lock.
                self._connection = sqlite3.connect(str(path), check_same_thread=False)
                self._connection.row_factory = sqlite3.Row
                self._init_schema()
                self._adopt_chain_head()
            return self._connection

    def reopen(self, db_path: str | Path | None = None) -> None:
        """Drop the cache and point at a (possibly different) database.

        Used by tests to redirect the singleton, and by the round-trip test to
        prove a trail survives the process that wrote it.
        """
        with self._lock:
            if self._connection is not None:
                self._connection.close()
            self._connection = None
            self._trails.clear()
            self._configured_path = Path(db_path) if db_path is not None else None
            self._path = None
        self._adopt_if_present()

    # -- schema ----------------------------------------------------------
    def _init_schema(self) -> None:
        conn = self._connection
        assert conn is not None  # only ever called while opening
        # WAL so a reader verifying the ledger never blocks a writer appending.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.executescript(SCHEMA)
        conn.commit()

    def _adopt_chain_head(self) -> None:
        conn = self._connection
        assert conn is not None  # only ever called while opening
        row = conn.execute(
            "SELECT global_seq, entry_hash FROM ledger_entries ORDER BY global_seq DESC LIMIT 1"
        ).fetchone()
        if row is not None:
            CHAIN.restore(row["entry_hash"], row["global_seq"])

    # -- writing ---------------------------------------------------------
    def put(self, trail: AuditTrail) -> None:
        """Persist a trail and any of its entries not yet written.

        Safe to call more than once for the same trail: entries already on disk
        are skipped by primary key, so a later append -- the human decision, for
        instance -- is flushed by calling this again rather than by rewriting
        anything.
        """
        with self._lock:
            self._trails[trail.audit_ref] = trail
            self._conn.execute(
                "INSERT OR IGNORE INTO trails (audit_ref, situation_id, created_at, provider, model_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    trail.audit_ref,
                    trail.situation_id,
                    trail.created_at.isoformat(),
                    trail.provider,
                    trail.model_id,
                ),
            )
            for entry in trail.entries:
                self._conn.execute(
                    "INSERT OR IGNORE INTO ledger_entries "
                    "(global_seq, audit_ref, seq, step, tier, detail, inputs, outputs, "
                    " started_at, duration_ms, prev_hash, entry_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        entry.global_seq,
                        trail.audit_ref,
                        entry.seq,
                        entry.step,
                        entry.tier,
                        entry.detail,
                        _canonical(entry.inputs),
                        _canonical(entry.outputs),
                        entry.started_at.isoformat(),
                        entry.duration_ms,
                        entry.prev_hash,
                        entry.entry_hash,
                    ),
                )
            self._conn.commit()
            self._maybe_checkpoint()

    def _maybe_checkpoint(self) -> None:
        """Record where the chain had reached, at intervals.

        A partial anchor, and no more than that. It narrows the window in which
        a rewrite passes unnoticed -- a forger must reproduce every checkpoint
        too -- but an attacker holding the key and write access can rewrite the
        checkpoints as easily as the entries. Real tamper-evidence needs storage
        the attacker cannot reach: WORM media, or an external notary. Named here
        rather than implied, because a ledger that overstates its guarantees is
        worse than one that admits their edge.
        """
        head, length = CHAIN.head, CHAIN.length
        if length == 0 or length % self.CHECKPOINT_INTERVAL:
            return
        self._conn.execute(
            "INSERT OR IGNORE INTO checkpoints (at_global_seq, head_hash, recorded_at) VALUES (?, ?, ?)",
            (length, head, _now().isoformat()),
        )
        self._conn.commit()

    def record_decision(self, decision: dict) -> None:
        """Human-decision learning loop (PRD 8.2): every accept/override is kept."""
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO decisions (decision_id, payload, recorded_at) VALUES (?, ?, ?)",
                (
                    str(decision.get("decision_id", "")),
                    _canonical(decision),
                    str(decision.get("recorded_at", _now().isoformat())),
                ),
            )
            self._conn.commit()

    # -- reading ---------------------------------------------------------
    def get(self, audit_ref: str) -> AuditTrail | None:
        """The trail, from cache if it is there and from disk if it is not."""
        with self._lock:
            cached = self._trails.get(audit_ref)
            if cached is not None:
                return cached
            trail = self._load(audit_ref)
            if trail is not None:
                self._trails[audit_ref] = trail
            return trail

    def _load(self, audit_ref: str) -> AuditTrail | None:
        head = self._conn.execute("SELECT * FROM trails WHERE audit_ref = ?", (audit_ref,)).fetchone()
        if head is None:
            return None
        trail = AuditTrail(
            audit_ref=head["audit_ref"],
            situation_id=head["situation_id"],
            provider=head["provider"],
            model_id=head["model_id"],
            created_at=datetime.fromisoformat(head["created_at"]),
        )
        rows = self._conn.execute(
            "SELECT * FROM ledger_entries WHERE audit_ref = ? ORDER BY seq", (audit_ref,)
        ).fetchall()
        trail.entries = [self._row_to_entry(r) for r in rows]
        return trail

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> AuditEntry:
        return AuditEntry(
            seq=row["seq"],
            step=row["step"],
            tier=row["tier"],
            detail=row["detail"],
            inputs=json.loads(row["inputs"]),
            outputs=json.loads(row["outputs"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            duration_ms=row["duration_ms"],
            prev_hash=row["prev_hash"],
            entry_hash=row["entry_hash"],
            global_seq=row["global_seq"],
        )

    def recent(self, limit: int = 25) -> list[AuditTrail]:
        rows = self._conn.execute("SELECT audit_ref FROM trails ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [t for t in (self.get(r["audit_ref"]) for r in rows) if t is not None]

    def decisions(self) -> list[dict]:
        rows = self._conn.execute("SELECT payload FROM decisions ORDER BY rowid").fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def entries_in_order(self) -> list[AuditEntry]:
        """Every entry in the ledger, in global order, read from disk."""
        rows = self._conn.execute("SELECT * FROM ledger_entries ORDER BY global_seq").fetchall()
        return [self._row_to_entry(r) for r in rows]

    def checkpoints(self) -> list[tuple[int, str]]:
        rows = self._conn.execute("SELECT at_global_seq, head_hash FROM checkpoints ORDER BY at_global_seq").fetchall()
        return [(r["at_global_seq"], r["head_hash"]) for r in rows]

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def verify_ledger(self) -> LedgerVerdict:
        """Walk the whole chain, across trails, and report the first divergence.

        Catches three failures a per-trail check cannot:

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
                missing = entry.global_seq - expected
                return LedgerVerdict(
                    False,
                    expected - 1,
                    entry.global_seq,
                    f"ledger jumps from {expected - 1} to {entry.global_seq}; {missing} entries are missing"
                    if missing != 1
                    else f"ledger jumps from {expected - 1} to {entry.global_seq}; 1 entry is missing",
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
