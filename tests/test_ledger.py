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

import pytest

from haven.reasoning import signing
from haven.reasoning.audit import CHAIN, GENESIS, AuditStore, AuditTrail


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """A private key and a fresh chain per test, leaving nothing in the repo."""
    monkeypatch.delenv("HAVEN_AUDIT_KEY", raising=False)
    monkeypatch.setenv("HAVEN_AUDIT_KEY_FILE", str(tmp_path / ".audit_key"))
    signing.reset_key_cache()
    CHAIN.reset()
    yield
    signing.reset_key_cache()
    CHAIN.reset()


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


def test_the_key_never_reaches_the_serialised_trail() -> None:
    store = AuditStore()
    trail = trail_with(store, "LOG-S-1")
    assert signing.audit_key().hex() not in repr(trail.as_dict())


# --------------------------------------------------------------------------
# The chain is global
# --------------------------------------------------------------------------
def test_the_chain_links_across_trail_boundaries() -> None:
    store = AuditStore()
    first = trail_with(store, "LOG-S-1")
    second = trail_with(store, "LOG-S-2")

    assert second.entries[0].prev_hash == first.entries[-1].entry_hash, (
        "a new trail must chain onto the ledger, not restart from genesis"
    )
    assert first.entries[0].prev_hash == GENESIS
    assert [e.global_seq for e in store.entries_in_order()] == [1, 2, 3, 4]


def test_a_clean_ledger_verifies() -> None:
    store = AuditStore()
    trail_with(store, "LOG-S-1")
    trail_with(store, "LOG-S-2")

    verdict = store.verify_ledger()
    assert verdict, verdict.reason
    assert verdict.entries_checked == 4
    assert verdict.first_divergent_seq is None


# --------------------------------------------------------------------------
# Tampering
# --------------------------------------------------------------------------
def test_an_entry_forged_without_the_key_fails_verification() -> None:
    """The case v1 could not catch: edited *and* re-digested.

    The **last** entry is forged deliberately. Forging any earlier one also
    breaks the link to its successor, so the chain would catch it even with an
    unkeyed digest -- and the test would then pass without proving anything
    about the key. With no successor to contradict it, only the key can tell
    this entry from an honest one.
    """
    import hashlib
    import json

    store = AuditStore()
    trail = trail_with(store, "LOG-S-1")
    entry = trail.entries[-1]

    entry.outputs["i"] = 999
    # Re-digest exactly as v1 did -- unkeyed SHA-256 over the canonical body.
    body = json.dumps(
        {
            "seq": entry.seq,
            "global_seq": entry.global_seq,
            "step": entry.step,
            "tier": entry.tier,
            "detail": entry.detail,
            "inputs": entry.inputs,
            "outputs": entry.outputs,
            "started_at": entry.started_at.isoformat(),
            "prev_hash": entry.prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    entry.entry_hash = hashlib.sha256(body.encode()).hexdigest()

    assert not trail.verify(), "a forgery without the key must not verify"
    assert not store.verify_ledger()


def test_deleting_a_whole_trail_is_detected() -> None:
    """v1's blind spot: per-trail chains made a deleted trail invisible."""
    store = AuditStore()
    trail_with(store, "LOG-S-1")
    trail_with(store, "LOG-S-2")
    trail_with(store, "LOG-S-3")

    assert store.verify_ledger()

    store._trails.pop("LOG-S-2")

    verdict = store.verify_ledger()
    assert not verdict
    assert verdict.first_divergent_seq == 5, "should report the first entry after the hole"
    assert "missing" in verdict.reason

    # The surviving trails each still verify on their own -- which is precisely
    # why a per-trail check was never enough.
    assert store.get("LOG-S-1").verify()
    assert store.get("LOG-S-3").verify()


def test_a_broken_link_is_reported_with_its_sequence_number() -> None:
    store = AuditStore()
    trail_with(store, "LOG-S-1")
    second = trail_with(store, "LOG-S-2")

    second.entries[0].prev_hash = GENESIS
    second.entries[0].entry_hash = second.entries[0].compute_mac()

    verdict = store.verify_ledger()
    assert not verdict
    assert verdict.first_divergent_seq == 3
    assert "predecessor" in verdict.reason


def test_corruption_is_still_caught() -> None:
    """The v1 guarantee must survive: a stale tag after an in-place edit."""
    store = AuditStore()
    trail = trail_with(store, "LOG-S-1")
    trail.entries[0].outputs["i"] = 999
    assert not trail.verify()


def test_a_ledger_signed_with_another_key_does_not_verify(monkeypatch) -> None:
    """Re-keying is not a way to launder a rewritten history."""
    store = AuditStore()
    trail_with(store, "LOG-S-1")
    assert store.verify_ledger()

    monkeypatch.setenv("HAVEN_AUDIT_KEY", "cd" * 32)
    signing.reset_key_cache()

    assert not store.verify_ledger()
