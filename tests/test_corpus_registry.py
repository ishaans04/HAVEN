"""The committed source registry, checked as data.

These run offline and need neither the PDFs nor the compiler extra. That is the
point: the registry is the part of the corpus that is *in* the repository, so it
is the part that can be verified on every commit by anyone, including CI on a
machine that has never downloaded a NASA document.

What they defend is narrow and worth stating. A corpus compiled from published
standards is auditable only if the registry can answer three questions a year
later: which document, which revision, and how anyone knew that revision was the
current one. Each of those degrades silently — a revision letter left stale, a
checksum left unpinned, a verification note reduced to "checked" — and each
degradation looks like nothing at all in a diff.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from compiler.registry import AUTHORITY_CLASSES, REQUIRED, RegistryError, read, summarise

REGISTRY = Path("corpus/sources.json")
REPORT = Path("corpus/EXTRACTION.md")

SHA256 = re.compile(r"^[0-9a-f]{64}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@pytest.fixture(scope="module")
def records():
    return read(REGISTRY)


def test_the_registry_reads(records) -> None:
    assert records, "the registry lists no documents"


def test_every_document_is_pinned(records) -> None:
    """An unpinned document is one a publisher can replace underneath us.

    Standards bodies do re-issue PDFs in place. Without a pin, a corpus
    recompiled six months from now would quietly be a corpus of a different
    revision, citing section numbers that had moved.
    """
    for record in records:
        assert SHA256.match(record.sha256), f"{record.doc_id} has no pinned SHA-256"
        assert record.bytes > 0, f"{record.doc_id} records no size"


def test_every_document_states_a_verified_revision(records) -> None:
    for record in records:
        assert record.revision, f"{record.doc_id} names no revision"
        assert ISO_DATE.match(record.published), f"{record.doc_id}: published={record.published!r}"
        assert ISO_DATE.match(record.verified_on), f"{record.doc_id}: verified_on={record.verified_on!r}"


def test_a_verification_note_says_what_was_checked(records) -> None:
    """ "Verified: true" records that somebody clicked something.

    The note has to name the page that was read and what it said, because the
    whole value of the field is that a later reader can repeat the check.
    """
    for record in records:
        note = record.verification
        assert len(note) > 80, f"{record.doc_id}: verification note is too short to be a record"
        assert record.verified_on in note or "read" in note.lower(), (
            f"{record.doc_id}: verification note does not say what was consulted, or when"
        )


def test_every_document_declares_its_authority(records) -> None:
    for record in records:
        assert record.authority in AUTHORITY_CLASSES


def test_the_corpus_has_an_authoritative_source(records) -> None:
    """Guidance and research cannot ground an action, so a corpus of only those
    could never produce a recommendation at all."""
    assert summarise(records)["authoritative"] >= 1


def test_every_research_source_says_why_it_is_here(records) -> None:
    """The research layer is where over-collection happens, so it is where the
    justification is required rather than encouraged."""
    for record in records:
        if record.authority == "research":
            assert len(record.rationale) > 120, (
                f"{record.doc_id}: a one-line rationale does not distinguish this paper from "
                f"the hundreds of NTRS papers that are also about fatigue"
            )


def test_the_research_set_stays_small(records) -> None:
    """A deliberate ceiling, and a failing test is the place to argue about it.

    Every research passage is retrievable and none of them can ground an action,
    so each one added is a near-miss the reasoning tier has to reject. A handful
    makes the corpus adversarial; fifty makes it noise.
    """
    assert summarise(records)["research"] <= 5


def test_every_scope_range_is_named(records) -> None:
    for record in records:
        for entry in record.scope:
            start, end = entry["pages"]
            assert 1 <= start <= end
            assert entry.get("label", "").strip(), f"{record.doc_id}: pages {start}-{end} are unnamed"


def test_passage_prefixes_are_distinct(records) -> None:
    """Two documents sharing a prefix would collide in the passage id, and a
    collision means one rule silently replaces another."""
    prefixes = [r.passage_prefix for r in records]
    assert len(set(prefixes)) == len(prefixes), f"duplicate passage prefixes: {prefixes}"


def test_a_superseded_revision_is_not_the_one_ingested(records) -> None:
    """The registry records what it replaced; it must not ingest one of them."""
    for record in records:
        for replaced in record.supersedes:
            assert record.revision not in replaced.split(), (
                f"{record.doc_id} claims revision {record.revision} while listing {replaced!r} as superseded"
            )


def test_the_extraction_report_matches_the_registry(records) -> None:
    """The report is the tracked evidence of what a compile read.

    Regenerating it is one command, and forgetting to would leave the repository
    asserting a compile of documents it no longer names.
    """
    report = REPORT.read_text(encoding="utf-8")
    for record in records:
        assert record.doc_id in report, f"{record.doc_id} is missing from {REPORT}"
        assert record.sha256[:16] in report, f"{record.doc_id}: {REPORT} records a different checksum"
        assert record.authority in report


def test_a_malformed_registry_raises_rather_than_degrading(tmp_path) -> None:
    """Every field in REQUIRED is one a decision would later need to name."""
    complete = json.loads(REGISTRY.read_text(encoding="utf-8"))["documents"][0]
    for field in REQUIRED:
        broken = {**complete, field: ""}
        path = tmp_path / "sources.json"
        path.write_text(json.dumps({"registry_version": 1, "documents": [broken]}), encoding="utf-8")
        with pytest.raises(RegistryError):
            read(path)


def test_a_future_registry_version_is_refused(tmp_path) -> None:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    payload["registry_version"] = 99
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RegistryError, match="registry version"):
        read(path)
