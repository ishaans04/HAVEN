"""Splitting a standards document into whole rules.

A fixed-size window is the wrong tool here, and not marginally. Consider:

    [V2 7003] Sleep Opportunity. The system shall provide each crewmember a
    sleep opportunity of at least 8 hours per 24-hour period. This requirement
    does not apply during launch, entry, or declared contingency operations.

Split that at 400 characters and the exception lands in a different chunk from
the rule it qualifies. Retrieval then surfaces a requirement that reads as
unconditional, and the checker compiles preconditions from a passage whose
limits are somewhere else entirely. The failure is silent and it is the worst
kind: the corpus looks fine, the citation resolves, and the rule it cites has
had its exception amputated.

So the primary splitter follows the document's own structure — requirement
identifiers and numbered headings — and a chunk ends only where the next rule
begins. `RecursiveCharacterTextSplitter` from `langchain-text-splitters` is
kept for the prose between rules, where there is no structure to follow, and
for the rare rule long enough that not splitting it would be worse.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

#: `[V2 7003]`, `[V1 4001]` -- NASA-STD-3001 requirement identifiers.
BRACKETED_REQUIREMENT = re.compile(r"\[\s*(?P<volume>V\d+)\s+(?P<number>\d{3,5})\s*\]")

#: `4.2`, `6.3.1`, `10.11.2` at the start of a line, followed by a title.
NUMBERED_HEADING = re.compile(
    r"^(?P<section>\d+(?:\.\d+){1,3})\s+(?P<title>[A-Z][^\n]{2,90})$",
    re.MULTILINE,
)

#: A rule beyond this length is split further; below it, kept whole.
MAX_CHUNK_CHARS = 2400
#: Below this a chunk is boilerplate -- a page header, a footer, a stray line.
MIN_CHUNK_CHARS = 120


@dataclass(frozen=True)
class Boundary:
    """Where a rule starts, and what identifies it."""

    offset: int
    section: str
    title: str
    kind: str  # "requirement" | "heading"


def find_boundaries(text: str) -> list[Boundary]:
    """Every point where a new rule begins, in document order."""
    found: list[Boundary] = []

    for match in BRACKETED_REQUIREMENT.finditer(text):
        # The title usually trails the identifier on the same line.
        line_end = text.find("\n", match.end())
        trailer = text[match.end() : line_end if line_end > 0 else len(text)].strip()
        title = trailer.rstrip(".").strip() if len(trailer) <= 90 else ""
        found.append(
            Boundary(
                offset=match.start(),
                section=f"{match.group('volume')} {match.group('number')}",
                title=title,
                kind="requirement",
            )
        )

    for match in NUMBERED_HEADING.finditer(text):
        found.append(
            Boundary(
                offset=match.start(),
                section=match.group("section"),
                title=match.group("title").strip(),
                kind="heading",
            )
        )

    found.sort(key=lambda b: b.offset)

    # A heading immediately followed by a bracketed requirement is that
    # requirement's title, not a rule of its own. Keeping both would split the
    # rule from its own heading.
    deduped: list[Boundary] = []
    for boundary in found:
        if deduped and boundary.offset - deduped[-1].offset < 8:
            continue
        deduped.append(boundary)
    return deduped


def _overlong(document: Document) -> list[Document]:
    """Split a chunk too long to keep whole, on paragraph then sentence."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=MAX_CHUNK_CHARS,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " "],
    )
    parts = splitter.split_text(document.page_content)
    if len(parts) <= 1:
        return [document]
    return [
        Document(
            page_content=part,
            metadata={
                **document.metadata,
                "part": index,
                "parts": len(parts),
                # Recorded because a split rule is exactly the case where a
                # precondition may have been separated from what it qualifies,
                # and the reviewer should be told which passages to read whole.
                "split": True,
            },
        )
        for index, part in enumerate(parts, start=1)
    ]


def chunk_page(page: Document) -> list[Document]:
    """One page into whole rules."""
    text = page.page_content
    boundaries = find_boundaries(text)
    if not boundaries:
        return []

    chunks: list[Document] = []
    for index, boundary in enumerate(boundaries):
        end = boundaries[index + 1].offset if index + 1 < len(boundaries) else len(text)
        body = text[boundary.offset : end].strip()
        if len(body) < MIN_CHUNK_CHARS:
            continue

        chunk = Document(
            page_content=body,
            metadata={
                **page.metadata,
                "section": boundary.section,
                "section_title": boundary.title,
                "boundary_kind": boundary.kind,
            },
        )
        chunks.extend(_overlong(chunk))
    return chunks


def chunk_document(pages: list[Document]) -> list[Document]:
    """Every page of a document into whole rules, in document order.

    Pages are processed independently. A rule spanning a page break is therefore
    truncated -- a real limitation, recorded here rather than hidden: joining
    pages first would fold headers and footers into the middle of rules, and
    stripping those reliably needs per-document templates the compiler does not
    have. The reviewer sees a chunk that ends mid-sentence and can reject it,
    which is a visible failure rather than a silent one.
    """
    chunks: list[Document] = []
    for page in pages:
        if page.metadata.get("empty"):
            continue
        chunks.extend(chunk_page(page))
    return chunks


def summarise(chunks: list[Document]) -> dict:
    """What the compiler found, for the operator running it."""
    return {
        "chunks": len(chunks),
        "requirements": sum(1 for c in chunks if c.metadata.get("boundary_kind") == "requirement"),
        "headings": sum(1 for c in chunks if c.metadata.get("boundary_kind") == "heading"),
        "split": sum(1 for c in chunks if c.metadata.get("split")),
        "sections": sorted({c.metadata.get("section", "") for c in chunks}),
    }
