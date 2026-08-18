"""The retrieval backends, and which of them the offline path depends on.

Three, in increasing order of what they require:

``BM25Backend``    ``rank_bm25`` over the corpus. Okapi BM25 -- the standard
                   lexical ranker, and a genuine improvement on v1's hand-rolled
                   TF-IDF, which weighted every term occurrence linearly and so
                   over-rewarded a passage merely for repeating a word.
                   **This is the offline terminal.** No download, no service.

``DenseBackend``   ``fastembed`` embeddings in a persistent Chroma collection,
                   via ``langchain-chroma``. ONNX rather than PyTorch: ~50MB
                   against ~2GB, which is the difference between an optional
                   extra and a decision. Downloads its model on first use, so it
                   is opt-in and never on the offline path.

``HybridRetrieval`` fuses whichever are available by reciprocal rank.

The corpus is built so lexical retrieval alone is not enough. Near-misses share
the governing rule's vocabulary almost word for word -- that is what makes them
near-misses -- so BM25 ranks them adjacent by construction. Dense retrieval
separates "shall not commence where alertness is below threshold" from "shall be
completed before the execution period" on meaning rather than on wording.

But retrieval is not where that distinction is *decided*. Both are surfaced to
the reasoning tier on purpose, and the deterministic checker disposes. Better
retrieval makes the candidate set better; it never makes the answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from haven.config import RETRIEVAL
from haven.rag.corpus import CORPUS, Passage
from haven.rag.fusion import Ranked, reciprocal_rank_fusion

_TOKEN = re.compile(r"[a-z][a-z0-9\-]+")
_STOP = frozenset(
    """the shall and for with that this not are was where which from any all under been have has
    its than then into per may each prior within""".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 2]


def indexable(passage: Passage) -> str:
    """What a retriever sees. Title and text -- never the preconditions.

    S4 is about the *reasoning* tier, but indexing `applies_when` would leak the
    answer key by a different route: a query mentioning the circadian trough
    would match the passage whose precondition names it, regardless of whether
    its prose says anything on the subject.
    """
    return f"{passage.title}\n{passage.text}"


@dataclass
class Retrieved:
    """One backend's ranking, plus its own scores for display."""

    name: str
    passage_ids: list[str]
    scores: dict[str, float]

    def as_ranked(self) -> Ranked:
        return Ranked(name=self.name, passage_ids=self.passage_ids, scores=self.scores)


class BM25Backend:
    """Okapi BM25 over the corpus. The offline terminal."""

    name = "bm25"
    backend_name = "BM25 (rank_bm25)"

    def __init__(self, passages: list[Passage] | None = None) -> None:
        from rank_bm25 import BM25Okapi

        self.passages = passages if passages is not None else CORPUS
        self._ids = [p.passage_id for p in self.passages]
        self._index = BM25Okapi([tokenize(indexable(p)) for p in self.passages])

    def rank(self, query_text: str, top_k: int) -> Retrieved:
        scores = self._index.get_scores(tokenize(query_text))
        order = sorted(range(len(self._ids)), key=lambda i: (-scores[i], self._ids[i]))[:top_k]
        return Retrieved(
            name=self.name,
            passage_ids=[self._ids[i] for i in order],
            scores={self._ids[i]: float(scores[i]) for i in order},
        )


class DenseBackend:
    """fastembed embeddings in a persistent Chroma collection.

    Opt-in. The model downloads on first use, so this can never be part of the
    offline guarantee -- which is why the retrieval tier degrades to BM25 alone
    rather than failing when it is unavailable.
    """

    name = "dense"
    backend_name = "Chroma + fastembed (ONNX)"

    def __init__(self, passages: list[Passage] | None = None) -> None:
        from langchain_chroma import Chroma
        from langchain_core.documents import Document

        try:
            from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        except ImportError:
            from fastembed import TextEmbedding

            class FastEmbedEmbeddings:  # noqa: N801 - a shim, not a class worth naming twice
                """Minimal embeddings adapter over fastembed.

                Written rather than imported because the LangChain wrapper for
                fastembed lives in ``langchain-community``, which is sunset. The
                interface Chroma needs is two methods.
                """

                def __init__(self, model_name: str) -> None:
                    self._model = TextEmbedding(model_name=model_name)

                def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    return [list(map(float, v)) for v in self._model.embed(texts)]

                def embed_query(self, text: str) -> list[float]:
                    return self.embed_documents([text])[0]

        self.passages = passages if passages is not None else CORPUS
        embeddings = FastEmbedEmbeddings(model_name=RETRIEVAL.dense_model)
        self._store = Chroma(
            collection_name=RETRIEVAL.collection,
            embedding_function=embeddings,
            persist_directory=RETRIEVAL.persist_directory or None,
        )
        self._store.add_documents(
            [Document(page_content=indexable(p), metadata={"passage_id": p.passage_id}) for p in self.passages],
            ids=[p.passage_id for p in self.passages],
        )

    def rank(self, query_text: str, top_k: int) -> Retrieved:
        hits = self._store.similarity_search_with_score(query_text, k=top_k)
        ids = [doc.metadata["passage_id"] for doc, _ in hits]
        # Chroma returns a distance; smaller is nearer. Inverted for display
        # only -- fusion ranks, and never touches these numbers.
        return Retrieved(
            name=self.name,
            passage_ids=ids,
            scores={doc.metadata["passage_id"]: 1.0 / (1.0 + float(d)) for doc, d in hits},
        )


class HybridRetrieval:
    """Every available backend, fused by reciprocal rank.

    Degrades rather than fails. If dense retrieval cannot be constructed -- extra
    not installed, model not downloaded, no network on first run -- the reason is
    recorded and BM25 carries the tier alone. A retrieval layer that refused to
    start without an optional dependency would make the offline path a fiction.
    """

    def __init__(self, passages: list[Passage] | None = None, *, mode: str | None = None) -> None:
        self.passages = passages if passages is not None else CORPUS
        self._by_id = {p.passage_id: p for p in self.passages}
        self.mode = (mode or RETRIEVAL.mode).strip().lower()
        self.degraded_reason = ""

        self.lexical = BM25Backend(self.passages)
        self.dense: DenseBackend | None = None

        if self.mode == "hybrid":
            try:
                self.dense = DenseBackend(self.passages)
            except Exception as exc:
                self.degraded_reason = f"dense retrieval unavailable ({type(exc).__name__}: {exc})"

    @property
    def backend_name(self) -> str:
        if self.dense is not None:
            return f"{self.lexical.backend_name} + {self.dense.backend_name}, RRF-fused"
        if self.degraded_reason:
            return f"{self.lexical.backend_name} (dense requested but unavailable)"
        return self.lexical.backend_name

    def rank(self, query_text: str, top_k: int):
        """Fused ordering, plus each backend's own view for the audit trail.

        Each backend is asked for more than ``top_k`` before fusing: a passage
        ranked fifth by one retriever and first by the other belongs in the
        final four, and truncating before fusion would discard it unseen.
        """
        widen = max(top_k * 3, top_k + 4)
        retrieved = [self.lexical.rank(query_text, widen)]
        if self.dense is not None:
            retrieved.append(self.dense.rank(query_text, widen))

        fused = reciprocal_rank_fusion([r.as_ranked() for r in retrieved])
        return fused[:top_k], {r.name: r for r in retrieved}

    def passage(self, passage_id: str) -> Passage:
        return self._by_id[passage_id]
