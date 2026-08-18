"""A PDF in, a rulebook the runtime can reason over out.

The pieces are tested separately; this asserts they compose, and that the two
properties which make the whole pipeline trustworthy survive the composition:

**Nothing unapproved is emitted.** The gate is what stands between "a model
suggested this encoding" and "a safety component enforces it".

**A compiled artefact cannot be edited afterwards.** The manifest is recomputed
on load, never trusted, so a precondition widened by hand after review is caught
rather than loaded as though a reviewer had approved it.
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

# The compiler is an optional subsystem: it never runs at request time, and its
# dependencies (pypdf, pdfplumber, langchain-text-splitters) are an extra. These
# tests are skipped when it is absent so a base install is not blocked from
# running the rest of the suite.
#
# Not a weakening. CI installs every extra in a dedicated job and runs this file
# in full; skipping here only spares a developer who has not asked for the
# compiler, and `uv sync --extra compiler` turns it back on.
pytest.importorskip("pypdf", reason="the compiler extra is not installed")
pytest.importorskip("pdfplumber", reason="the compiler extra is not installed")
pytest.importorskip("langchain_text_splitters", reason="the compiler extra is not installed")

from compiler import emit, review
from compiler.chunk import chunk_document
from compiler.cli import main as cli_main
from compiler.extract import SourceDocument, extract_pages
from compiler.propose import Proposal, propose_all
from haven.reasoning.llm import MockGraniteLLM
from tests.pdf_fixture import SECOND_PAGE, STANDARD_PAGE, build_pdf


@pytest.fixture
def source(tmp_path) -> SourceDocument:
    path = tmp_path / "std.pdf"
    path.write_bytes(build_pdf([STANDARD_PAGE, SECOND_PAGE]))
    return SourceDocument(
        doc_id="NASA-STD-3001-V2",
        title="NASA Space Flight Human-System Standard, Volume 2",
        path=path,
        revision="D",
        url="https://standards.nasa.gov/",
        retrieved="2026-08-15",
    )


def drafted(source: SourceDocument) -> list[Proposal]:
    return propose_all(chunk_document(extract_pages(source)), MockGraniteLLM())


def encoded(proposal: Proposal, reviewer: str = "R. Alvarez") -> Proposal:
    """Approve a proposal, giving it a usable encoding first.

    The mock is not an extraction model -- it answers SELECT, not EXTRACT -- so
    its drafts arrive unusable and flagged. Standing in for the reviewer here is
    the honest thing to do: it is a person's judgement either way.
    """
    proposal.applies_when = {"task_types": ["eva"], "alertness_below": 0.7}
    proposal.prescribes = "short_rest_then_proceed"
    proposal.governs_fatigue = True
    return review.approve(proposal, reviewer)


# --------------------------------------------------------------------------
# The pipeline composes
# --------------------------------------------------------------------------
def test_a_pdf_becomes_a_corpus_the_runtime_can_load(source, tmp_path) -> None:
    proposals = [encoded(p) for p in drafted(source)]
    corpus = emit.build(proposals, sources=[], version="test.1")
    artefact = emit.write(corpus, tmp_path / "compiled")

    loaded = emit.load(artefact)
    assert len(loaded) == len(proposals)
    assert {p.doc for p in loaded} == {"NASA-STD-3001-V2"}
    assert all(p.provenance == "extracted" for p in loaded)


def test_provenance_survives_the_whole_pipeline(source, tmp_path) -> None:
    """A citation nobody can look up is not a citation."""
    proposals = [encoded(p) for p in drafted(source)]
    artefact = emit.write(emit.build(proposals, [], version="test.1"), tmp_path / "compiled")

    sleep = next(p for p in emit.load(artefact) if p.section == "V2 7003")
    assert "Volume 2" in sleep.source
    assert "rev D" in sleep.source
    assert "p. 1" in sleep.source
    assert sleep.reviewed_by == "R. Alvarez"


def test_the_rule_still_carries_its_exception(source, tmp_path) -> None:
    """Chunking's guarantee has to survive compilation, not just chunking."""
    proposals = [encoded(p) for p in drafted(source)]
    artefact = emit.write(emit.build(proposals, [], version="test.1"), tmp_path / "compiled")

    sleep = next(p for p in emit.load(artefact) if p.section == "V2 7003")
    assert "does not apply during launch" in sleep.text


def test_a_manifest_accompanies_the_artefact(source, tmp_path) -> None:
    proposals = [encoded(p) for p in drafted(source)]
    corpus = emit.build(proposals, [], version="2026.08")
    emit.write(corpus, tmp_path / "compiled")

    manifest = json.loads((tmp_path / "compiled" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "2026.08"
    assert manifest["manifest"] == corpus.manifest
    assert manifest["extracted"] == len(proposals)


# --------------------------------------------------------------------------
# The gate holds under composition
# --------------------------------------------------------------------------
def test_nothing_unapproved_reaches_the_artefact(source) -> None:
    with pytest.raises(review.ReviewIncomplete):
        emit.build(drafted(source), [], version="test.1")


def test_one_unapproved_passage_stops_the_whole_build(source) -> None:
    """Emitting the rest would ship a corpus quietly missing a rule."""
    proposals = [encoded(p) for p in drafted(source)]
    proposals[1].approved = False

    with pytest.raises(review.ReviewIncomplete) as excinfo:
        emit.build(proposals, [], version="test.1")
    assert proposals[1].passage_id in str(excinfo.value)


# --------------------------------------------------------------------------
# The artefact cannot be edited after review
# --------------------------------------------------------------------------
def test_editing_a_compiled_corpus_is_detected(source, tmp_path) -> None:
    """The attack the manifest exists to catch: widen a rule after approval."""
    proposals = [encoded(p) for p in drafted(source)]
    artefact = emit.write(emit.build(proposals, [], version="test.1"), tmp_path / "compiled")

    payload = json.loads(artefact.read_text(encoding="utf-8"))
    payload["passages"][0]["applies_when"] = {}  # admissible for everything
    artefact.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        emit.load(artefact)
    assert "edited since it was compiled" in str(excinfo.value)


def test_an_unknown_format_version_is_refused(source, tmp_path) -> None:
    proposals = [encoded(p) for p in drafted(source)]
    artefact = emit.write(emit.build(proposals, [], version="test.1"), tmp_path / "compiled")

    payload = json.loads(artefact.read_text(encoding="utf-8"))
    payload["format_version"] = 99
    artefact.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ValueError):
        emit.load(artefact)


# --------------------------------------------------------------------------
# The CLI
# --------------------------------------------------------------------------
def write_registry(tmp_path, source: SourceDocument, **overrides) -> str:
    """A minimally valid source registry pointing at the generated PDF."""
    registry_path = tmp_path / "sources.json"
    entry = {
        "doc_id": source.doc_id,
        "title": source.title,
        "document_number": source.doc_id,
        "revision": source.revision,
        "published": "2026-01-01",
        "authority": "authoritative",
        "url": "https://example.invalid/standard",
        "pdf_url": "https://example.invalid/standard.pdf",
        "path": source.path.name,
        "retrieved": source.retrieved,
        "verified_on": source.retrieved,
        "verification": "generated by the test fixture; no publisher was consulted",
        "passage_prefix": "TEST",
    }
    entry.update(overrides)
    registry_path.write_text(
        json.dumps({"registry_version": 1, "documents": [entry]}),
        encoding="utf-8",
    )
    return str(registry_path)


def test_the_registry_refuses_an_entry_that_cannot_be_cited(source, tmp_path) -> None:
    """Every field in REQUIRED is one a decision would later need to name."""
    for field in ("revision", "published", "url", "verification"):
        path = write_registry(tmp_path, source, **{field: ""})
        with pytest.raises(SystemExit) as excinfo:
            cli_main(["extract", "--sources", path])
        assert field in str(excinfo.value)


def test_the_registry_refuses_an_unstated_authority(source, tmp_path) -> None:
    """A document whose force is unstated gets read as whatever is assumed."""
    path = write_registry(tmp_path, source, authority="official-ish")
    with pytest.raises(SystemExit) as excinfo:
        cli_main(["extract", "--sources", path])
    assert "authority" in str(excinfo.value)


def test_a_research_source_must_say_why_it_is_in_the_corpus(source, tmp_path) -> None:
    """Over-collection is the failure mode specific to the research layer."""
    path = write_registry(tmp_path, source, authority="research")
    with pytest.raises(SystemExit) as excinfo:
        cli_main(["extract", "--sources", path])
    assert "why it is in the corpus" in str(excinfo.value)


def test_the_extract_command_reports_what_it_found(source, tmp_path, capsys) -> None:
    assert cli_main(["extract", "--sources", write_registry(tmp_path, source)]) == 0
    out = capsys.readouterr().out
    assert "4 rules" in out


def test_approve_all_refuses_on_extracted_passages(source, tmp_path) -> None:
    """Approving a model's reading of a standard in bulk is the whole risk."""
    with pytest.raises(SystemExit) as excinfo:
        cli_main(
            [
                "propose",
                "--sources",
                write_registry(tmp_path, source),
                "--out",
                str(tmp_path / "review.json"),
                "--approve-all",
            ]
        )
    assert "refuses to approve extracted passages" in str(excinfo.value)


def test_the_emit_command_exits_non_zero_when_review_is_incomplete(source, tmp_path, capsys) -> None:
    review.write_for_review(drafted(source), tmp_path / "review.json")

    code = cli_main(["emit", "--review", str(tmp_path / "review.json"), "--version", "x", "--out", str(tmp_path / "c")])
    assert code == 2, "an incomplete review must fail the build, not warn"
    assert "Refusing to emit" in capsys.readouterr().err


def test_the_missing_source_registry_explains_itself(tmp_path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_main(["extract", "--sources", str(tmp_path / "absent.json")])
    assert "no source registry" in str(excinfo.value)


def test_an_unacquired_document_names_the_command_that_fixes_it(source, tmp_path) -> None:
    """The PDFs are not in the repository, so this is the ordinary first run."""
    path = write_registry(tmp_path, source, path="never-downloaded.pdf")
    with pytest.raises(SystemExit) as excinfo:
        cli_main(["extract", "--sources", path])
    assert "fetch_corpus" in str(excinfo.value)


# --------------------------------------------------------------------------
# The compiler is never on the request path
# --------------------------------------------------------------------------
def test_nothing_in_the_engine_imports_the_compiler() -> None:
    """A model authoring preconditions live would defeat the architecture.

    The checker's authority comes from preconditions being fixed, reviewed and
    signed off before any Situation is evaluated. If the request path could
    reach the compiler, that ordering would be a convention rather than a fact.
    """
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    offenders: list[str] = []

    for path in (root / "haven").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name.split(".")[0] == "compiler" for name in names):
                offenders.append(str(path.relative_to(root)))

    assert not offenders, f"the request path can reach the compiler: {offenders}"


def test_the_runtime_reads_a_compiled_corpus_without_importing_the_compiler(source, tmp_path) -> None:
    """The artefact is the interface between the two, and it is just a file."""
    proposals = [encoded(p) for p in drafted(source)]
    artefact = emit.write(emit.build(proposals, [], version="test.1"), tmp_path / "compiled")

    import subprocess
    import sys

    probe = (
        "import os, sys;"
        "sys.modules['compiler'] = None;"  # any import of it would now fail loudly
        "import haven.rag.corpus as c;"
        "print(len(c.CORPUS), c.CORPUS_MANIFEST[:8])"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=str(pathlib.Path(__file__).resolve().parents[1]),
        env={
            **os.environ,
            "HAVEN_CORPUS": str(artefact),
            "PYTHONPATH": str(pathlib.Path(__file__).resolve().parents[1]),
        },
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    count, digest = result.stdout.split()
    assert int(count) == len(proposals)
    assert len(digest) == 8
