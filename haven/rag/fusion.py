"""Reciprocal Rank Fusion, and why it is written here rather than imported.

Two retrievers disagree about what matters. BM25 rewards a passage that repeats
the query's words; a dense retriever rewards one that means the same thing in
different words. Both are right about different passages, and the corpus is
built so that neither alone is enough: near-misses share the governing rule's
vocabulary almost exactly, which is precisely the case BM25 cannot separate.

RRF combines rankings rather than scores, which is the property that makes it
usable here. Scores from two retrievers are not comparable -- a BM25 score of
4.2 and a cosine similarity of 0.71 have no common scale, and normalising them
means inventing one. Ranks are already comparable, and a passage ranked first by
one retriever and fourth by the other lands where it should without anyone
choosing a weighting.

LangChain ships `EnsembleRetriever`, which does this. It is not used, for one
concrete reason: it returns fused documents without their fused scores, and
Zone 3 renders exactly that number beside each candidate. Reimplementing fifteen
lines to keep the console honest is a better trade than displaying a score the
retriever did not actually rank on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: The constant from the original RRF paper (Cormack et al., 2009). It damps the
#: influence of top ranks: without it, first place would dominate so heavily that
#: the second retriever could never move anything, which defeats the point of
#: fusing at all.
RRF_K = 60


@dataclass(frozen=True)
class Ranked:
    """One retriever's opinion: an ordered list of passage identifiers."""

    name: str
    passage_ids: Sequence[str]
    #: The retriever's own scores, kept only for display. Never fused directly.
    scores: dict[str, float] | None = None


@dataclass(frozen=True)
class Fused:
    """One passage's fused standing, with the working shown.

    ``contributions`` is per-retriever so the console can say *why* a passage
    ranked where it did -- "BM25 put this first, the dense retriever ninth" is a
    reviewable statement; a single fused float is not.
    """

    passage_id: str
    score: float
    rank: int
    contributions: dict[str, int]

    def as_dict(self) -> dict:
        return {
            "passage_id": self.passage_id,
            "fused_score": round(self.score, 5),
            "rank": self.rank,
            "ranked_by": dict(self.contributions),
        }


def reciprocal_rank_fusion(rankings: Sequence[Ranked], *, k: int = RRF_K) -> list[Fused]:
    """Fuse ranked lists into one ordering.

    A passage absent from a retriever's list contributes nothing rather than a
    penalty. That matters for the offline path: with dense retrieval disabled
    there is one ranking, and fusion must degrade to it exactly rather than
    scoring everything as half-missing.
    """
    totals: dict[str, float] = {}
    contributions: dict[str, dict[str, int]] = {}

    for ranking in rankings:
        for position, passage_id in enumerate(ranking.passage_ids, start=1):
            totals[passage_id] = totals.get(passage_id, 0.0) + 1.0 / (k + position)
            contributions.setdefault(passage_id, {})[ranking.name] = position

    # Ties broken by identifier so the order is reproducible run to run -- a
    # demo that reorders its candidate list between identical evaluations
    # undermines the reproducibility this project treats as a success metric.
    ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    return [
        Fused(passage_id=pid, score=score, rank=rank, contributions=contributions[pid])
        for rank, (pid, score) in enumerate(ordered, start=1)
    ]


def display_relevance(fused: Fused, count: int) -> float:
    """A 0-1 figure for the console, from a fused score that has no natural scale.

    Presentation only. Nothing branches on it: the float gate was removed in
    Phase 1B precisely because a similarity score was deciding what governs, and
    this must not become that again by the back door. It exists so Zone 3 can
    draw a bar of a sensible length.
    """
    if count <= 0:
        return 0.0
    best_possible = 1.0 / (RRF_K + 1)
    return min(1.0, fused.score / best_possible) if best_possible else 0.0
