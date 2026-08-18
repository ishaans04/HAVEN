"""Reading source documents, and splitting them into whole rules.

The chunking test that matters is the exception one. A rule and the exception
that qualifies it must land in the same chunk, because a passage whose limits
were split off somewhere else reads as unconditional — and the corpus would look
perfectly healthy while containing a rule that had been quietly widened.

The PDFs here are generated rather than committed, so the readers are exercised
for real without a binary fixture nobody can inspect and without the network.
"""

from __future__ import annotations

import pytest

from compiler.chunk import (
    MIN_CHUNK_CHARS,
    chunk_document,
    chunk_page,
    find_boundaries,
    summarise,
)
from compiler.extract import ExtractionError, SourceDocument, blank_pages, extract_pages
from tests.pdf_fixture import SECOND_PAGE, STANDARD_PAGE, build_pdf


@pytest.fixture
def standard(tmp_path):
    path = tmp_path / "nasa-std-3001-v2.pdf"
    path.write_bytes(build_pdf([STANDARD_PAGE, SECOND_PAGE]))
    return SourceDocument(
        doc_id="NASA-STD-3001-V2",
        title="NASA Space Flight Human-System Standard, Volume 2",
        path=path,
        revision="D",
        url="https://standards.nasa.gov/standard/NASA/NASA-STD-3001-VOL-2",
        retrieved="2026-08-15",
    )


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------
def test_every_page_carries_its_provenance(standard) -> None:
    """A citation an operator cannot look up is not a citation."""
    pages = extract_pages(standard)
    assert len(pages) == 2

    meta = pages[0].metadata
    assert meta["doc_id"] == "NASA-STD-3001-V2"
    assert meta["revision"] == "D"
    assert meta["page"] == 1
    assert meta["url"].startswith("https://")
    assert meta["retrieved"] == "2026-08-15"
    assert len(meta["source_sha256"]) == 64


def test_the_text_of_the_document_actually_comes_through(standard) -> None:
    text = extract_pages(standard)[0].page_content
    assert "[V2 7003]" in text
    assert "sleep opportunity of at least 8 hours" in text


def test_the_checksum_identifies_the_file(standard, tmp_path) -> None:
    """A recompile from a different revision must not look like the same corpus."""
    other = tmp_path / "other.pdf"
    other.write_bytes(build_pdf([SECOND_PAGE]))
    changed = SourceDocument(doc_id="X", title="X", path=other)
    assert changed.sha256() != standard.sha256()


def test_a_missing_document_is_an_error_not_an_empty_result(tmp_path) -> None:
    absent = SourceDocument(doc_id="X", title="X", path=tmp_path / "nope.pdf")
    with pytest.raises(ExtractionError):
        extract_pages(absent)


def test_a_blank_page_is_reported_rather_than_dropped(tmp_path) -> None:
    """A scanned page holds rules the compiler cannot see. Say so."""
    path = tmp_path / "mixed.pdf"
    path.write_bytes(build_pdf([STANDARD_PAGE, [], SECOND_PAGE]))
    pages = extract_pages(SourceDocument(doc_id="X", title="X", path=path))

    assert len(pages) == 3, "a blank page must survive extraction"
    assert blank_pages(pages) == [2]


def test_both_readers_reach_the_same_text(standard) -> None:
    """pdfplumber preserves layout; pypdf is the fallback. Neither may lose rules."""
    layout = extract_pages(standard, prefer_layout=True)
    plain = extract_pages(standard, prefer_layout=False)

    for a, b in zip(layout, plain, strict=True):
        assert "[V2 7003]" in a.page_content or "[V2 7101]" in a.page_content
        assert a.page_content.split() and b.page_content.split()


# --------------------------------------------------------------------------
# Boundaries
# --------------------------------------------------------------------------
def test_bracketed_requirement_identifiers_are_boundaries() -> None:
    text = "[V2 7003] Sleep Opportunity\nThe system shall...\n[V2 7004] Circadian\nThe system shall..."
    sections = [b.section for b in find_boundaries(text)]
    assert sections == ["V2 7003", "V2 7004"]


def test_numbered_headings_are_boundaries() -> None:
    text = "6.2 Crew Sleep\nSome prose here.\n6.3.1 Workload Limits\nMore prose."
    sections = [b.section for b in find_boundaries(text)]
    assert sections == ["6.2", "6.3.1"]


def test_a_heading_immediately_before_a_requirement_is_not_a_separate_rule() -> None:
    """Otherwise the rule is split from its own title."""
    text = "6.2 Sleep\n[V2 7003] Sleep Opportunity\nThe system shall provide..."
    assert len(find_boundaries(text)) <= 2


def test_the_requirement_title_is_captured() -> None:
    boundary = find_boundaries("[V2 7003] Sleep Opportunity\nThe system shall provide...")[0]
    assert boundary.title == "Sleep Opportunity"
    assert boundary.kind == "requirement"


# --------------------------------------------------------------------------
# Chunking: the property this whole module exists for
# --------------------------------------------------------------------------
def test_a_rule_keeps_the_exception_that_qualifies_it(standard) -> None:
    """The failure a fixed-size splitter causes, and it is silent.

    Split the exception away and the rule reads as unconditional: retrieval
    surfaces it, the checker compiles preconditions from a passage whose limits
    are elsewhere, and nothing looks wrong.
    """
    chunks = chunk_document(extract_pages(standard))
    sleep = next(c for c in chunks if c.metadata["section"] == "V2 7003")

    assert "at least 8 hours" in sleep.page_content
    assert "does not apply during launch" in sleep.page_content, "the exception must stay with the rule it qualifies"


def test_one_chunk_per_rule(standard) -> None:
    chunks = chunk_document(extract_pages(standard))
    sections = [c.metadata["section"] for c in chunks]
    assert sections == ["V2 7003", "V2 7004", "V2 7005", "V2 7101"]


def test_a_chunk_does_not_run_into_the_next_rule(standard) -> None:
    chunks = chunk_document(extract_pages(standard))
    sleep = next(c for c in chunks if c.metadata["section"] == "V2 7003")
    assert "[V2 7004]" not in sleep.page_content


def test_chunks_carry_the_page_they_came_from(standard) -> None:
    chunks = chunk_document(extract_pages(standard))
    by_section = {c.metadata["section"]: c.metadata["page"] for c in chunks}
    assert by_section["V2 7003"] == 1
    assert by_section["V2 7101"] == 2, "provenance must survive chunking"


def test_boilerplate_below_the_floor_is_dropped() -> None:
    """Page headers and footers are not rules."""
    page = chunk_page(
        __import__("langchain_core.documents", fromlist=["Document"]).Document(
            page_content="[V2 9001] Tiny\nshort.",
            metadata={"page": 1},
        )
    )
    assert page == [], f"a {MIN_CHUNK_CHARS}-character floor should have dropped this"


def test_a_page_with_no_structure_yields_nothing() -> None:
    from langchain_core.documents import Document

    prose = Document(page_content="This is a foreword with no numbered rules at all.", metadata={"page": 1})
    assert chunk_page(prose) == []


def test_an_overlong_rule_is_split_and_says_so() -> None:
    """A split rule is exactly where a precondition may have been separated."""
    from langchain_core.documents import Document

    body = "The system shall do the thing. " * 200
    page = Document(page_content=f"[V2 8000] Long Rule\n{body}", metadata={"page": 1})
    parts = chunk_page(page)

    assert len(parts) > 1
    assert all(p.metadata["split"] for p in parts)
    assert all(p.metadata["section"] == "V2 8000" for p in parts)


def test_the_summary_reports_what_was_found(standard) -> None:
    summary = summarise(chunk_document(extract_pages(standard)))
    assert summary["chunks"] == 4
    assert summary["requirements"] == 4
    assert summary["split"] == 0
