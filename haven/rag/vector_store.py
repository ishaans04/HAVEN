"""Vector store for the procedure corpus.

Two backends behind one interface:

  ``InProcessVectorStore``  dependency-free TF-IDF + cosine. This is what the
                            prototype runs on, so the demo needs no services and
                            no model download. Deterministic and reproducible.

  ``ChromaVectorStore``     real ChromaDB + sentence-transformers, selected with
                            HAVEN_VECTOR_STORE=chroma. Same method signatures, so
                            promoting the prototype is a config change.

Retrieval returns candidates *and their scores*. It never decides which
candidate governs -- that is the reasoning tier's job (PRD section 2.3).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from haven.config import RETRIEVAL
from haven.rag.corpus import CORPUS, Passage

_TOKEN = re.compile(r"[a-z][a-z0-9\-]+")
_STOP = {
    "the",
    "shall",
    "and",
    "for",
    "with",
    "that",
    "this",
    "not",
    "are",
    "was",
    "where",
    "which",
    "from",
    "any",
    "all",
    "under",
    "been",
    "have",
    "has",
    "its",
    "than",
    "then",
    "into",
    "per",
    "may",
    "each",
    "prior",
    "within",
}


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 2]


@dataclass
class Candidate:
    """One retrieved passage with its similarity breakdown.

    The breakdown is exposed rather than collapsed to a single number so the
    audit trail can show *why* something was retrieved.
    """

    passage: Passage
    lexical: float  # TF-IDF cosine
    tag_match: float  # task-type agreement
    criticality_match: float
    # A 0-1 figure for display. Nothing branches on it: the float gate was
    # deleted in Phase 1B because a similarity score was deciding what governs.
    relevance: float
    # Which retriever ranked this passage where. "bm25 put it first, dense put
    # it ninth" is a reviewable statement; one fused number is not.
    ranked_by: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "passage_id": self.passage.passage_id,
            "doc": self.passage.doc,
            "section": self.passage.section,
            "title": self.passage.title,
            "relevance": round(self.relevance, 3),
            "lexical": round(self.lexical, 3),
            "tag_match": round(self.tag_match, 3),
            "ranked_by": dict(self.ranked_by),
        }


# Task families that are operationally adjacent. Adjacency raises retrieval
# score, which is exactly how a near-miss gets into the candidate set.
_ADJACENT: dict[str, set[str]] = {
    "orbital_burn": {"docking"},
    "docking": {"orbital_burn", "robotics_capture"},
    "eva": {"hatch_operation"},
    "hatch_operation": {"eva"},
    "robotics_capture": {"docking"},
    "medical_contingency": set(),
    "science_ops": {"maintenance"},
    "maintenance": {"science_ops"},
}


class InProcessVectorStore:
    """TF-IDF vector store over the procedure corpus.

    Stands in for ChromaDB + sentence-transformers. The interface, chunking, and
    score semantics match, so the reasoning tier above cannot tell the
    difference -- which is the point of keeping retrieval behind an interface.
    """

    backend_name = "in-process TF-IDF (ChromaDB stand-in)"

    def __init__(self, passages: list[Passage] | None = None) -> None:
        self.passages = passages if passages is not None else CORPUS
        self._docs = [tokenize(f"{p.title} {p.text} {' '.join(p.task_types)}") for p in self.passages]
        self._idf = self._build_idf()
        self._vectors = [self._vector(d) for d in self._docs]

    def _build_idf(self) -> dict[str, float]:
        n = len(self._docs)
        df = Counter()
        for doc in self._docs:
            df.update(set(doc))
        return {term: math.log((n + 1) / (count + 1)) + 1.0 for term, count in df.items()}

    def _vector(self, tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        tf = Counter(tokens)
        length = len(tokens)
        vec = {t: (c / length) * self._idf.get(t, 1.0) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(v * b.get(t, 0.0) for t, v in a.items())

    def query(
        self,
        query_text: str,
        task_type: str,
        criticality: str,
        top_k: int = 4,
    ) -> list[Candidate]:
        """Return the top-k candidates, near-misses included by design."""
        qvec = self._vector(tokenize(query_text))
        adjacent = _ADJACENT.get(task_type, set())

        candidates: list[Candidate] = []
        for passage, pvec in zip(self.passages, self._vectors, strict=True):
            lexical = self._cosine(qvec, pvec)
            if task_type in passage.task_types:
                tag = 1.0
            elif adjacent & set(passage.task_types):
                tag = 0.40
            else:
                tag = 0.0
            crit_ok = criticality in passage.applies_when.get("criticality_in", [criticality])
            crit = 1.0 if crit_ok else 0.3

            relevance = 0.52 * min(1.0, lexical * 2.2) + 0.33 * tag + 0.15 * crit
            candidates.append(
                Candidate(
                    passage=passage,
                    lexical=lexical,
                    tag_match=tag,
                    criticality_match=crit,
                    relevance=round(relevance, 4),
                )
            )

        candidates.sort(key=lambda c: c.relevance, reverse=True)
        return candidates[:top_k]


class ChromaVectorStore:
    """Real ChromaDB backend. Selected with HAVEN_VECTOR_STORE=chroma.

    Kept deliberately thin: it is the same contract as the in-process store, so
    swapping backends does not touch the reasoning tier.
    """

    backend_name = "ChromaDB + sentence-transformers"

    def __init__(self, passages: list[Passage] | None = None) -> None:
        try:
            import chromadb  # type: ignore
            from chromadb.utils import embedding_functions  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "HAVEN_VECTOR_STORE=chroma requires `pip install chromadb sentence-transformers`"
            ) from exc

        self.passages = passages if passages is not None else CORPUS
        client = chromadb.EphemeralClient()
        embed = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=RETRIEVAL.embedding_model.split("/")[-1]
        )
        self.collection = client.get_or_create_collection(RETRIEVAL.collection, embedding_function=embed)
        self.collection.add(
            ids=[p.passage_id for p in self.passages],
            documents=[f"{p.title}\n{p.text}" for p in self.passages],
            metadatas=[
                {"doc": p.doc, "section": p.section, "task_types": ",".join(p.task_types)} for p in self.passages
            ],
        )
        self._by_id = {p.passage_id: p for p in self.passages}

    def query(
        self, query_text: str, task_type: str, criticality: str, top_k: int = 4
    ) -> list[Candidate]:  # pragma: no cover
        result = self.collection.query(query_texts=[query_text], n_results=top_k)
        out: list[Candidate] = []
        adjacent = _ADJACENT.get(task_type, set())
        for pid, distance in zip(result["ids"][0], result["distances"][0], strict=True):
            passage = self._by_id[pid]
            lexical = max(0.0, 1.0 - distance / 2.0)  # cosine distance -> similarity
            if task_type in passage.task_types:
                tag = 1.0
            elif adjacent & set(passage.task_types):
                tag = 0.40
            else:
                tag = 0.0
            crit_ok = criticality in passage.applies_when.get("criticality_in", [criticality])
            crit = 1.0 if crit_ok else 0.3
            out.append(Candidate(passage, lexical, tag, crit, round(0.52 * lexical + 0.33 * tag + 0.15 * crit, 4)))
        out.sort(key=lambda c: c.relevance, reverse=True)
        return out


def build_store():
    if RETRIEVAL.backend == "chroma":
        return ChromaVectorStore()
    return InProcessVectorStore()
