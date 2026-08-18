"""Source documents to text, with provenance attached to every page.

`pypdf` and `pdfplumber` are called directly rather than through LangChain's
document loaders. Two reasons, and the second is the load-bearing one:

* `langchain-community`, which holds those loaders, is being sunset and is no
  longer actively maintained. Taking a dependency on an unmaintained package for
  a thin wrapper over `pypdf` is a liability with nothing on the other side of
  it.
* Doing it here means controlling the metadata. Every passage in the compiled
  corpus has to be traceable to a document, revision, section and page, because
  a citation an operator cannot look up is not a citation. A generic loader
  gives page numbers and little else.

The output is a `langchain_core.documents.Document`, which stays the interchange
type through chunking and retrieval.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document


@dataclass(frozen=True)
class SourceDocument:
    """A document to compile, and everything needed to cite it afterwards.

    ``revision`` and ``retrieved`` matter more than they look: a flight rule is
    a living document, and a recommendation citing "section 4.2" without saying
    *which revision* of the document is not auditable a year later.
    """

    doc_id: str
    title: str
    path: Path
    revision: str = ""
    url: str = ""
    retrieved: str = ""
    #: Marks passages compiled from this source. Real documents are "extracted";
    #: anything written for the prototype must say so.
    provenance: str = "extracted"
    #: The force of what this document says: "authoritative" for a standard
    #: stating shall-requirements, "guidance" for a handbook, "research" for a
    #: paper. It travels with every page and every chunk, because the one thing
    #: that must not happen to a handbook's recommendation is to arrive at the
    #: checker indistinguishable from a requirement.
    authority: str = "authoritative"
    #: Page ranges to compile, 1-based and inclusive, as ``((start, end), ...)``.
    #: Empty means the whole document.
    #:
    #: Scoping is not an optimisation. NASA-STD-3001 Volume 2 carries 1,579
    #: requirements, three of which concern sleep; compiling all of them would
    #: bury the fatigue rulebook inside a corpus about acoustics, radiation and
    #: hatch clearances, and every one of those would compete for retrieval
    #: against the rules that actually govern. A corpus is a claim about what is
    #: relevant, and an unscoped one makes no claim at all.
    #:
    #: Page numbers are safe to pin because the file itself is: the registry
    #: carries a SHA-256, so a re-issued PDF is refused rather than silently
    #: re-paginated underneath these ranges.
    pages: tuple[tuple[int, int], ...] = ()
    #: Short code opening every passage id compiled from this document, e.g.
    #: ``V1`` giving ``P-V1-6001``. Stated per document rather than derived,
    #: because passage ids appear in citations an operator reads and in audit
    #: rows that outlive the corpus -- they should be short, stable, and chosen.
    passage_prefix: str = ""

    def sha256(self) -> str:
        digest = hashlib.sha256()
        with open(self.path, "rb") as handle:
            for block in iter(lambda: handle.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()

    def citation_prefix(self) -> str:
        parts = [self.title]
        if self.revision:
            parts.append(f"rev {self.revision}")
        return ", ".join(parts)


class ExtractionError(RuntimeError):
    """The document could not be read. Never silently skipped."""


def _require(module: str):
    try:
        return __import__(module)
    except ImportError as exc:  # pragma: no cover - exercised by the extra being absent
        raise ExtractionError(
            f"the compiler needs {module}; install the extra with `uv sync --extra compiler`"
        ) from exc


def _read(pages, source: SourceDocument, wanted: set[int] | None) -> list[tuple[int, str]]:
    """Extract text from the pages in scope, and only those.

    Both readers expose pages as a lazy sequence, so skipping the rest is the
    difference between reading four pages of the HIDH and reading all 1,301 of
    them to throw 1,297 away.
    """
    if wanted is not None:
        beyond = sorted(n for n in wanted if n > len(pages))
        if beyond:
            # A range naming pages the document does not have means the scope was
            # written against a different file — a different revision, most
            # likely. Compiling the overlap would produce a corpus quietly
            # missing whatever those pages held.
            raise ExtractionError(
                f"{source.doc_id}: scope names page(s) {beyond[:5]} but the document has "
                f"{len(pages)}. The scope was written against a different file."
            )

    extracted = [
        (number, page.extract_text() or "")
        for number, page in enumerate(pages, start=1)
        if wanted is None or number in wanted
    ]
    if wanted is not None and not extracted:
        raise ExtractionError(f"{source.doc_id}: the configured scope selects no pages")
    return extracted


def extract_pages(source: SourceDocument, *, prefer_layout: bool = True) -> list[Document]:
    """One `Document` per page, carrying the source's provenance.

    ``pdfplumber`` is tried first because it preserves layout, and layout is
    meaning in a standards document: a requirement identifier sitting in the
    left margin is structurally different from the same string inside a
    paragraph, and a reader that flattens the page loses that. ``pypdf`` is the
    fallback, since pdfplumber is the slower of the two and fails on some
    generators.

    A page that yields no text is kept, not dropped. Silently discarding it
    would let a scanned page — one needing OCR the pipeline does not do — vanish
    without anyone noticing that a rule went missing.
    """
    if not source.path.exists():
        raise ExtractionError(f"{source.doc_id}: no such file {source.path}")

    wanted = {n for start, end in source.pages for n in range(start, end + 1)} or None

    numbered: list[tuple[int, str]] = []
    if prefer_layout:
        try:
            pdfplumber = _require("pdfplumber")
            with pdfplumber.open(str(source.path)) as pdf:
                numbered = _read(pdf.pages, source, wanted)
        except ExtractionError:
            raise
        except Exception:
            numbered = []

    if not numbered:
        pypdf = _require("pypdf")
        try:
            reader = pypdf.PdfReader(str(source.path))
            numbered = _read(reader.pages, source, wanted)
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError(f"{source.doc_id}: could not be read ({exc})") from exc

    if not numbered:
        raise ExtractionError(f"{source.doc_id}: contains no pages")

    checksum = source.sha256()
    return [
        Document(
            page_content=text,
            metadata={
                "doc_id": source.doc_id,
                "title": source.title,
                "revision": source.revision,
                "url": source.url,
                "retrieved": source.retrieved,
                "provenance": source.provenance,
                "authority": source.authority,
                "passage_prefix": source.passage_prefix or source.doc_id,
                "source_sha256": checksum,
                "page": number,
                "empty": not text.strip(),
            },
        )
        for number, text in numbered
    ]


def blank_pages(pages: list[Document]) -> list[int]:
    """Pages that yielded nothing, so the operator can be told rather than not.

    A blank page is usually a scan. The compiler does no OCR, so those pages
    contain rules it cannot see, and reporting the count is the difference
    between "this document had no more rules" and "this document had rules I
    could not read".
    """
    return [p.metadata["page"] for p in pages if p.metadata.get("empty")]
