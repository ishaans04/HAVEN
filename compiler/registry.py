"""The source registry: which documents, which version, and how that was checked.

A compiled corpus is only as auditable as its inputs. "We used NASA-STD-3001" is
not a provenance record — the standard has seven public revisions, they differ in
what they require, and a recommendation citing a section number without naming
the revision cannot be re-derived a year later.

So the registry is a tracked file carrying, per document: the official document
number, its revision, its approval date, the canonical publisher page, the exact
PDF URL, a pinned SHA-256, and a note recording how the revision was verified to
be the current one. The PDFs themselves are not tracked — they are
redistributable only from their publishers — but everything needed to re-fetch
and re-verify them is.

Two fields exist because of decisions taken explicitly rather than by default:

``authority``
    Whether the document states mandatory requirements, offers guidance, or
    reports research. NASA-STD-3001 says *shall*; the HIDH explains why; an NTRS
    paper reports what was measured. Flattening those into "a NASA document"
    would let a handbook's recommendation be enforced as a requirement NASA
    never wrote. :mod:`haven.deterministic.preconditions` is where that
    distinction is enforced rather than merely recorded.

``rationale``
    Why this document is in the corpus at all. Required for research sources,
    where the temptation to ingest broadly is strongest and the cost is highest:
    a retrieval surface full of topically adjacent papers that govern nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from compiler.extract import SourceDocument

REGISTRY_VERSION = 1

#: What a source document may claim about the force of what it says.
AUTHORITY_CLASSES = ("authoritative", "guidance", "research")

#: Fields every entry must carry. Absence is an error rather than a default: a
#: registry that silently accepts a document with no verified revision is a
#: registry that will eventually contain one.
REQUIRED = (
    "doc_id",
    "title",
    "document_number",
    "revision",
    "published",
    "authority",
    "url",
    "pdf_url",
    "path",
    "retrieved",
    "verified_on",
    "verification",
    "passage_prefix",
)


class RegistryError(ValueError):
    """The registry is malformed. Never repaired silently."""


@dataclass(frozen=True)
class SourceRecord:
    """One document, and everything needed to cite, re-fetch, and re-verify it."""

    doc_id: str
    title: str
    document_number: str
    revision: str
    published: str
    authority: str
    url: str
    pdf_url: str
    path: Path
    retrieved: str
    verified_on: str
    #: How the revision was confirmed current — which publisher page was read
    #: and what it said. Prose, because "verified: true" records only that
    #: somebody clicked something.
    verification: str
    #: Revisions this one replaces. Stated so the registry says what was *not*
    #: ingested, and so an older file found on disk reads as wrong rather than
    #: merely old.
    supersedes: tuple[str, ...] = ()
    #: Why this document is in the corpus. Required for research sources.
    rationale: str = ""
    #: Which parts of the document to compile: ``[{"pages": [134, 135],
    #: "label": "7.9 Behavioural Health and Sleep"}]``. Empty means all of it.
    #: The label is not decoration — it is what makes a page range reviewable,
    #: since "pages 134-135" says nothing about whether the right thing was
    #: ingested.
    scope: tuple[dict, ...] = ()
    #: Short code opening passage ids compiled from this document.
    passage_prefix: str = ""
    #: Pinned at acquisition. Empty means never fetched; a mismatch is refused.
    sha256: str = ""
    bytes: int = 0
    provenance: str = "extracted"

    def to_source_document(self) -> SourceDocument:
        """The shape the extraction pipeline consumes."""
        return SourceDocument(
            doc_id=self.doc_id,
            title=self.title,
            path=self.path,
            revision=self.revision,
            url=self.url,
            retrieved=self.retrieved,
            provenance=self.provenance,
            authority=self.authority,
            pages=tuple((int(s["pages"][0]), int(s["pages"][1])) for s in self.scope if s.get("pages")),
            passage_prefix=self.passage_prefix or self.doc_id,
        )

    def citation(self) -> str:
        """How this document is named where a passage records its source."""
        parts = [self.document_number]
        if self.revision:
            parts.append(f"rev {self.revision}")
        if self.published:
            parts.append(self.published)
        return ", ".join(parts)


def _validate(entry: dict, index: int) -> None:
    missing = [field for field in REQUIRED if not str(entry.get(field, "")).strip()]
    if missing:
        raise RegistryError(f"document {index} ({entry.get('doc_id', '?')}) is missing: {missing}")

    if entry["authority"] not in AUTHORITY_CLASSES:
        raise RegistryError(
            f"{entry['doc_id']}: authority={entry['authority']!r} is not one of "
            f"{list(AUTHORITY_CLASSES)}. A document whose force is unstated gets "
            f"treated as whatever the reader assumes."
        )

    for entry_scope in entry.get("scope", ()):
        pages = entry_scope.get("pages")
        if not (isinstance(pages, list) and len(pages) == 2 and all(isinstance(n, int) for n in pages)):
            raise RegistryError(f"{entry['doc_id']}: every scope entry needs pages as [start, end]")
        if pages[0] > pages[1] or pages[0] < 1:
            raise RegistryError(f"{entry['doc_id']}: scope range {pages} is not a valid 1-based page span")
        if not str(entry_scope.get("label", "")).strip():
            raise RegistryError(
                f"{entry['doc_id']}: scope range {pages} has no label. A page range nobody "
                f"named cannot be reviewed for whether it selects the right material."
            )

    # The rationale is required only where over-collection is the real risk. A
    # standard is in the corpus because it is the standard; a paper is in the
    # corpus because somebody chose it, and that choice should be written down.
    if entry["authority"] == "research" and not str(entry.get("rationale", "")).strip():
        raise RegistryError(
            f"{entry['doc_id']}: a research source must state why it is in the corpus. "
            f"Without that the set grows by accretion and nobody can say what it is for."
        )


def read(path: Path) -> list[SourceRecord]:
    """Read and validate the registry. Raises rather than skipping bad entries."""
    if not path.exists():
        raise RegistryError(
            f"no source registry at {path}. It lists the documents to compile, their "
            f"verified revisions, and where they came from."
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("documents", []) if isinstance(payload, dict) else payload
    version = payload.get("registry_version", REGISTRY_VERSION) if isinstance(payload, dict) else REGISTRY_VERSION

    if version != REGISTRY_VERSION:
        raise RegistryError(f"{path.name} is registry version {version}; this build reads {REGISTRY_VERSION}")
    if not entries:
        raise RegistryError(f"{path.name} lists no documents")

    root = path.parent
    records: list[SourceRecord] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        _validate(entry, index)
        if entry["doc_id"] in seen:
            raise RegistryError(f"duplicate doc_id {entry['doc_id']!r}")
        seen.add(entry["doc_id"])

        declared = Path(entry["path"])
        records.append(
            SourceRecord(
                doc_id=entry["doc_id"],
                title=entry["title"],
                document_number=entry["document_number"],
                revision=entry["revision"],
                published=entry["published"],
                authority=entry["authority"],
                url=entry["url"],
                pdf_url=entry["pdf_url"],
                path=declared if declared.is_absolute() else root / declared,
                retrieved=entry["retrieved"],
                verified_on=entry["verified_on"],
                verification=entry["verification"],
                supersedes=tuple(entry.get("supersedes", ())),
                rationale=entry.get("rationale", ""),
                scope=tuple(entry.get("scope", ())),
                passage_prefix=entry.get("passage_prefix", ""),
                sha256=entry.get("sha256", ""),
                bytes=int(entry.get("bytes", 0)),
                provenance=entry.get("provenance", "extracted"),
            )
        )
    return records


def write(path: Path, records: list[SourceRecord]) -> None:
    """Write the registry back, preserving field order for a readable diff.

    Used by the fetch script to pin checksums. The registry is reviewed in pull
    requests, so a stable key order is not cosmetic — it is what makes "the
    checksum of the standard changed" a one-line diff somebody notices.
    """
    root = path.parent
    payload = {
        "registry_version": REGISTRY_VERSION,
        "documents": [
            {
                "doc_id": r.doc_id,
                "title": r.title,
                "document_number": r.document_number,
                "revision": r.revision,
                "published": r.published,
                "authority": r.authority,
                "provenance": r.provenance,
                "url": r.url,
                "pdf_url": r.pdf_url,
                "path": _relative(r.path, root),
                "retrieved": r.retrieved,
                "verified_on": r.verified_on,
                "verification": r.verification,
                "supersedes": list(r.supersedes),
                "rationale": r.rationale,
                "passage_prefix": r.passage_prefix,
                "scope": list(r.scope),
                "sha256": r.sha256,
                "bytes": r.bytes,
            }
            for r in records
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def _relative(path: Path, root: Path) -> str:
    """Registry paths stay relative and POSIX-shaped, so the file is portable."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def summarise(records: list[SourceRecord]) -> dict:
    return {
        "documents": len(records),
        "authoritative": sum(1 for r in records if r.authority == "authoritative"),
        "guidance": sum(1 for r in records if r.authority == "guidance"),
        "research": sum(1 for r in records if r.authority == "research"),
        "pinned": sum(1 for r in records if r.sha256),
        "present": sum(1 for r in records if r.path.exists()),
    }
