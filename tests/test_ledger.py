"""The audit ledger's integrity guarantees (S7, part one).

v1 chained entries with an unkeyed SHA-256, per trail. That catches *corruption*
-- a field edited with its digest left stale -- and the v1 test proves exactly
that much, by mutating a field without recomputing anything.

It does not catch *tampering*. An unkeyed digest is one anyone can recompute, so
an attacker with write access could edit an entry, re-digest it, re-chain
everything after it, and leave a ledger that verifies perfectly. Nor could v1
notice a whole trail being deleted: every trail started from GENESIS, so the
survivors still verified and nothing recorded that the missing one had existed.

These tests are about that second class. Each one removes a protection and
checks the ledger notices.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from haven.reasoning import signing
from haven.reasoning.audit import CHAIN, GENESIS, AuditStore, AuditTrail


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """A private key, a private database and a fresh chain, per test.

    The session-wide fixture in ``conftest.py`` keeps the suite out of the real
    ledger; this one goes further and isolates each test from the others, since
    these tests assert on absolute sequence numbers and a shared chain would make
    them order-dependent.
    """
    monkeypatch.delenv("HAVEN_AUDIT_KEY", raising=False)
    monkeypatch.setenv("HAVEN_AUDIT_KEY_FILE", str(tmp_path / ".audit_key"))
    signing.reset_key_cache()
    CHAIN.reset()
    yield
    signing.reset_key_cache()
    CHAIN.reset()


@pytest.fixture
def store(tmp_path) -> AuditStore:
    """A ledger of this test's own, on disk, discarded with the temp directory."""
    opened = AuditStore(tmp_path / "haven_ledger.db")
    yield opened
    opened.close()


def trail_with(store: AuditStore, ref: str, steps: int = 2) -> AuditTrail:
    trail = AuditTrail(audit_ref=ref, situation_id=ref.removeprefix("LOG-"))
    for i in range(steps):
        trail.append(step=f"STEP_{i}", tier="deterministic", detail=f"step {i}", outputs={"i": i})
    store.put(trail)
    return trail


# --------------------------------------------------------------------------
# Key management
# --------------------------------------------------------------------------
def test_key_is_generated_on_first_use_and_then_reused() -> None:
    """The offline path must need no configuration (architecture design 6)."""
    path = signing.key_path()
    assert not path.exists()

    first = signing.audit_key()
    assert path.exists()
    assert len(first) == 32

    signing.reset_key_cache()
    assert signing.audit_key() == first, "a second run must not invent a new key"


def test_environment_key_wins_over_the_file(monkeypatch) -> None:
    from_file = signing.audit_key()
    monkeypatch.setenv("HAVEN_AUDIT_KEY", "ab" * 32)
    signing.reset_key_cache()
    assert signing.audit_key() == bytes.fromhex("ab" * 32) != from_file


def test_a_non_hex_environment_key_is_used_verbatim(monkeypatch) -> None:
    """A key pasted from a password manager must not silently become another key."""
    monkeypatch.setenv("HAVEN_AUDIT_KEY", "not-hex-at-all")
    signing.reset_key_cache()
    assert signing.audit_key() == b"not-hex-at-all"


def test_an_empty_environment_key_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("HAVEN_AUDIT_KEY", "   ")
    signing.reset_key_cache()
    with pytest.raises(ValueError):
        signing.audit_key()


def test_the_key_never_reaches_the_serialised_trail(store) -> None:
    trail = trail_with(store, "LOG-S-1")
    assert signing.audit_key().hex() not in repr(trail.as_dict())


# --------------------------------------------------------------------------
# The chain is global
# --------------------------------------------------------------------------
def test_the_chain_links_across_trail_boundaries(store) -> None:
    first = trail_with(store, "LOG-S-1")
    second = trail_with(store, "LOG-S-2")

    assert second.entries[0].prev_hash == first.entries[-1].entry_hash, (
        "a new trail must chain onto the ledger, not restart from genesis"
    )
    assert first.entries[0].prev_hash == GENESIS
    assert [e.global_seq for e in store.entries_in_order()] == [1, 2, 3, 4]


def test_a_clean_ledger_verifies(store) -> None:
    trail_with(store, "LOG-S-1")
    trail_with(store, "LOG-S-2")

    verdict = store.verify_ledger()
    assert verdict, verdict.reason
    assert verdict.entries_checked == 4
    assert verdict.first_divergent_seq is None


# --------------------------------------------------------------------------
# Tampering
# --------------------------------------------------------------------------
def _canonical_body(row) -> str:
    """The exact bytes an entry's tag is computed over, rebuilt from a database row."""
    return json.dumps(
        {
            "seq": row["seq"],
            "global_seq": row["global_seq"],
            "step": row["step"],
            "tier": row["tier"],
            "detail": row["detail"],
            "inputs": json.loads(row["inputs"]),
            "outputs": json.loads(row["outputs"]),
            "started_at": row["started_at"],
            "prev_hash": row["prev_hash"],
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def test_an_entry_forged_without_the_key_fails_verification(store) -> None:
    """The case v1 could not catch: edited *and* re-digested, in the store itself.

    The attack is on the database, because that is where the record actually
    lives -- mutating a Python object proves nothing about durable state. And the
    **last** entry is forged deliberately: forging any earlier one also breaks
    the link to its successor, so the chain would catch it even with an unkeyed
    digest, and the test would pass while proving nothing about the key. With no
    successor to contradict it, only the key can tell this entry from an honest
    one.
    """
    trail_with(store, "LOG-S-1")
    assert store.verify_ledger()

    conn = store._conn
    row = conn.execute("SELECT * FROM ledger_entries ORDER BY global_seq DESC LIMIT 1").fetchone()

    forged = dict(row)
    forged["outputs"] = json.dumps({"i": 999}, sort_keys=True, separators=(",", ":"))
    # Re-digest exactly as v1 did: an unkeyed SHA-256 anyone can recompute.
    tag = hashlib.sha256(_canonical_body(forged).encode()).hexdigest()
    conn.execute(
        "UPDATE ledger_entries SET outputs = ?, entry_hash = ? WHERE global_seq = ?",
        (forged["outputs"], tag, row["global_seq"]),
    )
    conn.commit()

    verdict = store.verify_ledger()
    assert not verdict, "a forgery without the key must not verify"
    assert "authenticate" in verdict.reason
    assert verdict.first_divergent_seq == row["global_seq"]


def test_deleting_a_whole_trail_is_detected(store) -> None:
    """v1's blind spot: per-trail chains made a deleted trail invisible."""
    trail_with(store, "LOG-S-1")
    trail_with(store, "LOG-S-2")
    trail_with(store, "LOG-S-3")
    assert store.verify_ledger()

    conn = store._conn
    conn.execute("DELETE FROM ledger_entries WHERE audit_ref = ?", ("LOG-S-2",))
    conn.execute("DELETE FROM trails WHERE audit_ref = ?", ("LOG-S-2",))
    conn.commit()
    store._trails.clear()

    verdict = store.verify_ledger()
    assert not verdict
    assert verdict.first_divergent_seq == 5, "should report the first entry after the hole"
    assert "missing" in verdict.reason

    # Each surviving trail still verifies on its own -- which is precisely why a
    # per-trail check was never enough to notice this.
    assert store.get("LOG-S-1").verify()
    assert store.get("LOG-S-3").verify()


def test_a_broken_link_is_reported_with_its_sequence_number(store) -> None:
    trail_with(store, "LOG-S-1")
    trail_with(store, "LOG-S-2")

    conn = store._conn
    conn.execute("UPDATE ledger_entries SET prev_hash = ? WHERE global_seq = ?", (GENESIS, 3))
    conn.commit()
    store._trails.clear()

    verdict = store.verify_ledger()
    assert not verdict
    assert verdict.first_divergent_seq == 3
    # Rewriting the link also invalidates the tag, since prev_hash is signed --
    # either message is a correct description of what went wrong.
    assert "predecessor" in verdict.reason or "authenticate" in verdict.reason


def test_corruption_is_still_caught(store) -> None:
    """The v1 guarantee must survive: a stale tag after an in-place edit."""
    trail = trail_with(store, "LOG-S-1")
    trail.entries[0].outputs["i"] = 999
    assert not trail.verify()


def test_a_ledger_signed_with_another_key_does_not_verify(store, monkeypatch) -> None:
    """Re-keying is not a way to launder a rewritten history."""
    trail_with(store, "LOG-S-1")
    assert store.verify_ledger()

    monkeypatch.setenv("HAVEN_AUDIT_KEY", "cd" * 32)
    signing.reset_key_cache()

    assert not store.verify_ledger()


# --------------------------------------------------------------------------
# Durability
# --------------------------------------------------------------------------
def test_a_trail_survives_the_process_that_wrote_it(tmp_path) -> None:
    """The whole point of Phase 2: v1 lost every trail on restart."""
    db = tmp_path / "haven_ledger.db"

    writer = AuditStore(db)
    trail_with(writer, "LOG-S-1", steps=3)
    written = [e.entry_hash for e in writer.get("LOG-S-1").entries]
    writer.close()

    # A different store object, opening the same file -- as a restarted process
    # would. Nothing is carried over in memory.
    reader = AuditStore(db)
    recovered = reader.get("LOG-S-1")
    assert recovered is not None, "a trail written before a restart must still resolve"
    assert [e.entry_hash for e in recovered.entries] == written
    assert recovered.verify(), "the recovered trail must still authenticate"
    assert reader.verify_ledger()
    reader.close()


def test_a_restart_continues_the_chain_rather_than_starting_a_second_one(tmp_path) -> None:
    """Otherwise the ledger reads as two unrelated histories side by side."""
    db = tmp_path / "haven_ledger.db"

    first = AuditStore(db)
    trail_with(first, "LOG-S-1")
    head_before = first.get("LOG-S-1").entries[-1].entry_hash
    first.close()

    CHAIN.reset()  # as a fresh process would start

    second = AuditStore(db)
    later = trail_with(second, "LOG-S-2")
    assert later.entries[0].prev_hash == head_before
    assert [e.global_seq for e in second.entries_in_order()] == [1, 2, 3, 4]
    assert second.verify_ledger()
    second.close()


def test_decisions_survive_a_restart(tmp_path) -> None:
    db = tmp_path / "haven_ledger.db"

    writer = AuditStore(db)
    writer.record_decision({"decision_id": "DEC-1", "operator": "flight_surgeon", "decision": "approved"})
    writer.close()

    reader = AuditStore(db)
    assert [d["decision_id"] for d in reader.decisions()] == ["DEC-1"]
    reader.close()


def test_a_later_append_is_flushed_by_putting_the_trail_again(store) -> None:
    """The human decision is appended after the trail was first stored."""
    trail = trail_with(store, "LOG-S-1", steps=2)
    trail.append(step="HUMAN_DECISION", tier="human", detail="operator approved")
    store.put(trail)

    store._trails.clear()
    assert [e.step for e in store.get("LOG-S-1").entries][-1] == "HUMAN_DECISION"
    assert store.verify_ledger()


def test_checkpoints_record_where_the_chain_had_reached(store) -> None:
    """A partial anchor. It narrows the window; it does not close it."""
    for i in range(AuditStore.CHECKPOINT_INTERVAL):
        trail_with(store, f"LOG-S-{i}", steps=1)

    marks = store.checkpoints()
    assert marks, "a checkpoint should have been written at the interval"
    at_seq, head = marks[-1]
    assert at_seq == AuditStore.CHECKPOINT_INTERVAL
    assert head == store.entries_in_order()[at_seq - 1].entry_hash


def test_importing_the_package_creates_no_database(tmp_path) -> None:
    """Connecting lazily keeps import free of filesystem side effects."""
    quiet = AuditStore(tmp_path / "unused.db")
    assert not (tmp_path / "unused.db").exists()
    quiet.get("LOG-nothing")
    assert (tmp_path / "unused.db").exists(), "first use should open it"
    quiet.close()
