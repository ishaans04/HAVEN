"""Retrieval owes the reasoning tier a candidate set containing the answer.

Everything downstream can only choose among what retrieval surfaced. A missed
governing rule is unrecoverable: the checker cannot admit a passage nobody
retrieved, the model cannot select one it never saw, and the system refuses —
correctly, and for the wrong reason. So recall over the golden set is the metric
this tier is held to, and it must be total.

The second property is stranger and just as deliberate: near-misses must *also*
be retrieved. They share the governing rule's vocabulary almost word for word,
which is what makes them near-misses, and a retriever tuned to exclude them
would delete the discrimination case entirely — the model's rejection of
P-SLP-2.1 would become a tautology rather than a judgement.

Retrieval makes the candidate set better. It never makes the answer.
"""

from __future__ import annotations

import pytest

from evaluation.golden_set import CASES, GOVERNING_CASES
from haven.rag.backends import BM25Backend, HybridRetrieval, indexable, tokenize
from haven.rag.corpus import BY_ID, CORPUS
from haven.rag.fusion import RRF_K, Fused, Ranked, display_relevance, reciprocal_rank_fusion
from haven.rag.retriever import ProcedureRetriever, SituationQuery


def query_for(case) -> SituationQuery:
    facts = case.facts
    return SituationQuery(
        task_type=facts["task_type"],
        criticality=facts["criticality"],
        alertness_score=facts["alertness_score"],
        workload_score=facts["workload_score"],
        circadian_flag=facts["circadian_flag"],
        phase=facts["phase"],
    )


@pytest.fixture(scope="module")
def retriever() -> ProcedureRetriever:
    return ProcedureRetriever()


# --------------------------------------------------------------------------
# Recall: the property selection cannot recover from
# --------------------------------------------------------------------------
@pytest.mark.parametrize("case", GOVERNING_CASES, ids=lambda c: c.case_id)
def test_the_governing_rule_is_always_retrieved(case, retriever) -> None:
    """100%, or the refusal downstream is right for the wrong reason."""
    found = [c.passage.passage_id for c in retriever.get_relevant_documents(query_for(case), top_k=6)]
    assert case.governs in found, (
        f"{case.case_id}: {case.governs} was not retrieved, so nothing downstream could have chosen it. "
        f"Retrieved: {found}"
    )


def test_recall_over_the_whole_golden_set_is_total(retriever) -> None:
    misses = [
        case.case_id
        for case in GOVERNING_CASES
        if case.governs
        not in [c.passage.passage_id for c in retriever.get_relevant_documents(query_for(case), top_k=6)]
    ]
    assert not misses, f"retrieval missed the governing rule for: {misses}"


# --------------------------------------------------------------------------
# Near-misses must survive too
# --------------------------------------------------------------------------
def test_the_confusable_near_miss_reaches_the_candidate_set(retriever) -> None:
    """Excluding it would make the discrimination case a tautology."""
    eva = next(c for c in CASES if c.case_id == "eva-governed")
    found = [c.passage.passage_id for c in retriever.get_relevant_documents(query_for(eva), top_k=6)]

    assert "P-FAT-4.4" in found
    assert "P-SLP-2.1" in found, (
        "the pre-EVA sleep-shifting rule must be retrieved so the reasoning tier "
        "has something to reject; a retriever that filtered it would be deciding"
    )


def test_candidates_carry_which_retriever_found_them(retriever) -> None:
    """'BM25 first, dense ninth' is reviewable; one fused number is not."""
    burn = next(c for c in CASES if c.case_id == "burn-governed")
    for candidate in retriever.get_relevant_documents(query_for(burn), top_k=4):
        assert candidate.ranked_by, "a candidate must record how it was ranked"
        assert "bm25" in candidate.ranked_by


# --------------------------------------------------------------------------
# What the index may see
# --------------------------------------------------------------------------
def test_the_index_never_sees_compiled_preconditions() -> None:
    """S4 by another route.

    Indexing `applies_when` would let a query mentioning the circadian trough
    match the passage whose *precondition* names it, whatever its prose says --
    the answer key leaking in through retrieval rather than through the prompt.
    """
    circadian = BY_ID["P-FAT-5.1"]
    text = indexable(circadian)

    assert circadian.text in text
    assert "requires_circadian_flag" not in text
    assert "applies_when" not in text
    assert str(circadian.prescribes) not in text or circadian.prescribes in circadian.text


def test_every_passage_is_indexed() -> None:
    backend = BM25Backend()
    assert len(backend.passage_ids if hasattr(backend, "passage_ids") else backend._ids) == len(CORPUS)


def test_tokenisation_drops_procedure_boilerplate() -> None:
    """'shall' appears in every rule and distinguishes none of them."""
    tokens = tokenize("The system shall provide a sleep opportunity")
    assert "shall" not in tokens
    assert "sleep" in tokens and "opportunity" in tokens


# --------------------------------------------------------------------------
# Fusion
# --------------------------------------------------------------------------
def test_fusion_of_one_ranking_reproduces_it_exactly() -> None:
    """The offline path is a single ranking; fusion must be a no-op there."""
    single = Ranked(name="bm25", passage_ids=["A", "B", "C"])
    assert [f.passage_id for f in reciprocal_rank_fusion([single])] == ["A", "B", "C"]


def test_a_passage_ranked_well_by_both_beats_one_ranked_well_by_either() -> None:
    fused = reciprocal_rank_fusion(
        [
            Ranked(name="bm25", passage_ids=["agreed", "lexical-only"]),
            Ranked(name="dense", passage_ids=["agreed", "dense-only"]),
        ]
    )
    assert fused[0].passage_id == "agreed"
    assert fused[0].contributions == {"bm25": 1, "dense": 1}


def test_absence_from_one_ranking_is_not_a_penalty() -> None:
    """Otherwise disabling dense retrieval would score everything as half-missing."""
    both = reciprocal_rank_fusion(
        [Ranked(name="bm25", passage_ids=["A", "B"]), Ranked(name="dense", passage_ids=["A"])]
    )
    assert [f.passage_id for f in both] == ["A", "B"]
    assert both[1].contributions == {"bm25": 2}


def test_ties_break_reproducibly() -> None:
    """A demo that reorders its candidates between identical runs is not credible."""
    first = reciprocal_rank_fusion([Ranked(name="x", passage_ids=["B", "A"])])
    second = reciprocal_rank_fusion([Ranked(name="x", passage_ids=["B", "A"])])
    assert [f.passage_id for f in first] == [f.passage_id for f in second]


def test_the_displayed_relevance_stays_inside_the_unit_interval() -> None:
    fused = reciprocal_rank_fusion([Ranked(name="x", passage_ids=list("ABCDEFGH"))])
    for entry in fused:
        assert 0.0 <= display_relevance(entry, len(fused)) <= 1.0


def test_the_rrf_constant_damps_the_top_rank() -> None:
    """Without it first place would dominate and fusing would be pointless."""
    assert RRF_K == 60
    top = Fused("A", 1.0 / (RRF_K + 1), 1, {})
    second = Fused("B", 1.0 / (RRF_K + 2), 2, {})
    assert top.score / second.score < 1.1, "one rank apart should not be an order of magnitude"


# --------------------------------------------------------------------------
# The offline terminal
# --------------------------------------------------------------------------
def test_lexical_mode_needs_no_dense_backend() -> None:
    """BM25 alone is the offline path: no download, no service."""
    store = HybridRetrieval(mode="lexical")
    assert store.dense is None
    assert store.degraded_reason == ""
    assert "BM25" in store.backend_name


def test_hybrid_degrades_to_lexical_rather_than_failing(monkeypatch) -> None:
    """A retrieval tier that refused to start without an extra would make the
    offline guarantee a fiction."""
    import haven.rag.backends as backends

    def unavailable(*args, **kwargs):
        raise ImportError("fastembed is not installed")

    monkeypatch.setattr(backends, "DenseBackend", unavailable)
    store = backends.HybridRetrieval(mode="hybrid")

    assert store.dense is None
    assert "unavailable" in store.degraded_reason
    assert store.rank("orbital burn", 4)[0], "retrieval must still return candidates"


def test_the_backend_name_says_when_dense_was_wanted_but_missing(monkeypatch) -> None:
    import haven.rag.backends as backends

    monkeypatch.setattr(backends, "DenseBackend", lambda *a, **k: (_ for _ in ()).throw(ImportError("no")))
    store = backends.HybridRetrieval(mode="hybrid")
    assert "unavailable" in store.backend_name


# --------------------------------------------------------------------------
# Dense retrieval, when it is actually installed
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_dense_retrieval_ranks_the_governing_rule(tmp_path, monkeypatch) -> None:
    """Downloads a model on first run. Opt-in, never on the offline path."""
    monkeypatch.setenv("HAVEN_CHROMA_DIR", str(tmp_path / "chroma"))
    store = HybridRetrieval(mode="hybrid")
    assert store.dense is not None, store.degraded_reason

    burn = next(c for c in CASES if c.case_id == "burn-governed")
    fused, views = store.rank(query_for(burn).to_text(), 4)
    assert "dense" in views
    assert "P-FAT-4.2" in [f.passage_id for f in fused]
