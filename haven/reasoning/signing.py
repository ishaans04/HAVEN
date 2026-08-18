"""The audit ledger's signing key.

The v1 chain was an *unkeyed* SHA-256. That detects corruption -- a field edited
in place, hashes left stale -- but not tampering: anyone able to write to the
store could edit an entry, recompute the digest, re-chain everything after it,
and ``verify()`` would happily return ``True``. A digest anyone can recompute
authenticates nobody.

Keying the chain closes that. Without the key an attacker can still *destroy*
the record, which the chain makes obvious, but can no longer *rewrite* it into a
different plausible history.

Two things this deliberately does not do, both recorded honestly rather than
papered over:

* It does not defend against an attacker holding the key **and** write access.
  They can re-chain forward exactly as before. Closing that needs an external
  anchor -- WORM storage, or a notary the attacker cannot reach -- and is
  deferred. The checkpoint file added in milestone 2.2 is a partial mitigation,
  not a solution.
* It is not a secrets-management system. A production deployment injects
  ``HAVEN_AUDIT_KEY`` from a real vault.

The key is generated on first use when absent, because the offline path must
need no configuration (architecture design section 6). A fresh clone with no
environment set must simply work.
"""

from __future__ import annotations

import binascii
import os
import secrets
import threading
from pathlib import Path

# Repository root: haven/reasoning/signing.py -> haven/reasoning -> haven -> root
_DEFAULT_KEY_PATH = Path(__file__).resolve().parents[2] / ".audit_key"

_KEY_BYTES = 32  # 256-bit, matching the SHA-256 block the MAC is built on

_lock = threading.Lock()
_cached: bytes | None = None
_cached_from: Path | None = None


def key_path() -> Path:
    """Where the key lives when it is not supplied by the environment."""
    override = os.getenv("HAVEN_AUDIT_KEY_FILE")
    return Path(override) if override else _DEFAULT_KEY_PATH


def _decode(raw: str) -> bytes:
    """Accept a hex key, or fall back to treating the value as raw bytes.

    Hex is the documented form. Raw is accepted because a key pasted from a
    password manager should not silently produce a *different* key from the one
    the operator thinks they set -- better to use exactly what they gave us.
    """
    stripped = raw.strip()
    if not stripped:
        raise ValueError("HAVEN_AUDIT_KEY is set but empty")
    try:
        decoded = binascii.unhexlify(stripped)
    except (binascii.Error, ValueError):
        return stripped.encode("utf-8")
    return decoded or stripped.encode("utf-8")


def _generate(path: Path) -> bytes:
    key = secrets.token_bytes(_KEY_BYTES)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create, so two processes racing on first run cannot each believe
    # they authored the key and sign with different ones.
    try:
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(key.hex())
    except FileExistsError:
        return _decode(path.read_text(encoding="utf-8"))
    # Owner-only. Windows largely ignores this; it is still correct to ask.
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - platform dependent
        pass
    return key


def audit_key() -> bytes:
    """The key every ledger entry is signed with.

    ``HAVEN_AUDIT_KEY`` wins when set. Otherwise the key is read from, or
    generated into, :func:`key_path`. Cached, because it is consulted once per
    audit entry and re-reading the file each time would be a needless syscall on
    a hot path.
    """
    global _cached, _cached_from

    from_env = os.getenv("HAVEN_AUDIT_KEY")
    if from_env:
        return _decode(from_env)

    path = key_path()
    with _lock:
        if _cached is not None and _cached_from == path:
            return _cached
        key = _decode(path.read_text(encoding="utf-8")) if path.exists() else _generate(path)
        _cached, _cached_from = key, path
        return key


def reset_key_cache() -> None:
    """Forget the cached key. For tests that repoint the key location."""
    global _cached, _cached_from
    with _lock:
        _cached, _cached_from = None, None
