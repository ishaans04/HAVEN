"""Test isolation for the audit ledger.

From Phase 2 the ledger is durable, which means a test run would otherwise write
into the same `haven_ledger.db` a developer's console is using, sign it with the
same key, and leave the global chain advanced by however many entries the suite
happened to append. Three separate ways for a test run to change the answer a
later one gets.

So the whole session is redirected: its own database, its own signing key, both
under pytest's temp root and both discarded afterwards. Nothing here weakens
what is under test -- the ledger is exercised exactly as it is in production,
just somewhere disposable.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_ledger_session(tmp_path_factory) -> None:
    """Point the ledger and its key at throwaway paths for the whole run."""
    import haven.reasoning.audit as audit_module
    from haven.reasoning import signing

    root = tmp_path_factory.mktemp("ledger")

    # Set before the store is rebuilt, so it opens the temporary database.
    import os

    os.environ["HAVEN_LEDGER_DB"] = str(root / "haven_ledger.db")
    os.environ["HAVEN_AUDIT_KEY_FILE"] = str(root / ".audit_key")
    os.environ.pop("HAVEN_AUDIT_KEY", None)

    signing.reset_key_cache()
    audit_module.CHAIN.reset()

    # The singleton was built at import, before those variables were set. It has
    # not opened anything yet -- the connection is lazy precisely so this works
    # -- so pointing it at the temporary database is enough. No rebinding, which
    # matters: `from ... import AUDIT` binds the object, and any module that had
    # already imported it would otherwise keep writing to the wrong store.
    audit_module.AUDIT.reopen()

    yield

    audit_module.AUDIT.close()
