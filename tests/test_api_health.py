"""`/api/health` must describe the process that is actually running.

This endpoint answers one question — *is this thing real, or is it the mock?* —
and it answered it wrongly for a correctly configured system. Both tier fields
reported v1 configuration rather than v2 behaviour:

* ``reasoning_provider`` read ``LLM.provider``, the *single*-provider setting.
  Any deployment configured the documented way, with ``HAVEN_LLM_CHAIN``, leaves
  that at ``mock`` — so a server genuinely calling watsonx announced itself as
  running the offline stand-in.
* ``retrieval`` read ``RETRIEVAL.backend``, describing a vector store Phase 5
  replaced. It said ``inprocess`` while BM25 was serving every query.

Both were wrong in the same direction: they understated the system as more
mocked than it was. That is the safer direction to be wrong in and still
unacceptable, because the operator-facing claim this project makes is that a
degraded tier is *always* visible as degraded — which is worth nothing if a
live tier is also displayed as degraded.

These tests pin health to the same sources the evaluation response uses, so the
two cannot disagree again.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from haven.api.main import app
from haven.config import LLM
from haven.rag.retriever import get_retriever
from haven.reasoning.chain import configured_chain


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_health_is_served(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_the_chain_not_the_single_provider(client: TestClient) -> None:
    """The bug, reproduced rather than described.

    The two settings have to be made to *differ*, because that is the only
    condition under which the fault is visible — and it is the ordinary
    production condition. `.env.example` configures `HAVEN_LLM_CHAIN=watsonx,mock`
    and leaves `HAVEN_LLM_PROVIDER=mock`, so the deployment calling watsonx is
    exactly the one whose `LLM.provider` still says `mock`.

    An earlier version of this test asserted only that health equals
    `configured_chain()`, which the suite's own pin makes true of `LLM.provider`
    as well — it passed with the bug reinstated. Hence the explicit divergence.
    """
    original = LLM.chain
    object.__setattr__(LLM, "chain", "watsonx,mock")
    try:
        tiers = client.get("/api/health").json()["tiers"]
        assert tiers["reasoning_provider"] == "watsonx -> mock"
        assert tiers["reasoning_provider"] != LLM.provider, (
            "health is reporting the single-provider setting; a server calling "
            "watsonx would announce itself as the offline stand-in"
        )
    finally:
        object.__setattr__(LLM, "chain", original)


def test_health_renders_whatever_the_chain_resolves_to(client: TestClient) -> None:
    """And with no divergence forced, it still tracks the real source."""
    tiers = client.get("/api/health").json()["tiers"]
    assert tiers["reasoning_provider"] == " -> ".join(configured_chain())


def test_health_reports_the_retrieval_backend_that_runs(client: TestClient) -> None:
    tiers = client.get("/api/health").json()["tiers"]
    assert tiers["retrieval"] == get_retriever().backend_name
    assert tiers["retrieval"] != "inprocess", "the v1 vector-store field is not what serves queries"


def test_health_agrees_with_the_evaluation_response(client: TestClient) -> None:
    """The invariant worth having: one process, one account of itself.

    Health is read before anything is evaluated and TierStatus after, so they
    are produced by different code at different times. If they can disagree,
    the one a reader happens to look at decides what they believe.
    """
    tiers = client.get("/api/health").json()["tiers"]
    status = client.get("/api/scenarios/nominal_ops/evaluate").json()["tier_status"]

    assert tiers["retrieval"] == status["retrieval"]
    assert tiers["reasoning_provider"] == " -> ".join(status["provider_chain"])

    # Two vocabularies, deliberately: the chain holds configuration names
    # ("watsonx") and served_by holds the adapter's own name
    # ("watsonx-granite"), because the second says which implementation
    # answered. Asserting the prefix keeps them tied without pretending they
    # are the same string.
    assert any(status["served_by"].startswith(name) for name in status["provider_chain"]), (
        f"served_by={status['served_by']!r} names no link in {status['provider_chain']}"
    )


def test_health_names_the_model(client: TestClient) -> None:
    """Which Granite. Model ids differ in capability and the id is the only
    record of which one produced a given decision."""
    assert client.get("/api/health").json()["tiers"]["reasoning_model"] == LLM.model_id
