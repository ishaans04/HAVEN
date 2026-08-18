"""The compiler, end to end.

    python -m compiler.cli extract  --sources corpus/sources.json
    python -m compiler.cli propose  --sources corpus/sources.json --out corpus/review.json
    python -m compiler.cli emit     --review corpus/review.json --version 2026.08 --out corpus/compiled

Three commands rather than one, because the middle step is a person reading. A
single `compile` that ran extraction, proposal and emission in sequence would
either skip review or pretend a prompt counts as it.

`--approve-all` exists for tests and for compiling the *synthesised* corpus,
where the encodings were hand-written in the first place. It refuses to touch
extracted passages, and says so, because approving a model's reading of a real
standard in bulk is precisely the thing this pipeline is built to prevent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from compiler import emit, registry, review
from compiler.chunk import chunk_document
from compiler.chunk import summarise as summarise_chunks
from compiler.extract import SourceDocument, blank_pages, extract_pages
from compiler.propose import propose_all
from haven.reasoning.llm import build_llm


def load_sources(path: Path) -> list[SourceDocument]:
    """Read the source registry: which documents, which revision, from where."""
    try:
        records = registry.read(path)
    except registry.RegistryError as exc:
        raise SystemExit(f"registry: {exc}") from exc

    missing = [r.doc_id for r in records if not r.path.exists()]
    if missing:
        # The PDFs are not in the repository, so this is the expected first-run
        # state rather than a fault. Naming the command that fixes it beats a
        # FileNotFoundError raised three frames deeper.
        raise SystemExit(
            f"not acquired: {missing}. Run `uv run python -m scripts.fetch_corpus` to "
            f"download the documents the registry names and verify them against their "
            f"pinned checksums."
        )
    return [r.to_source_document() for r in records]


def _chunk_all(sources: list[SourceDocument]) -> list:
    chunks = []
    for source in sources:
        pages = extract_pages(source)
        blanks = blank_pages(pages)
        # Research sources carry no rule structure to follow and no rule to
        # widen -- see compiler.chunk._prose for why that makes a character
        # window acceptable there and nowhere else.
        found = chunk_document(pages, prose_fallback=source.authority == "research")
        print(f"  {source.doc_id:<24} {source.authority:<14} {len(pages):>3} pages, {len(found):>3} passages")
        if blanks:
            # Named rather than counted: these pages hold rules the compiler
            # cannot see, and that is a gap in the corpus, not a statistic.
            print(f"    !! {len(blanks)} page(s) yielded no text (likely scanned): {blanks}")
        chunks.extend(found)
    return chunks


def cmd_extract(args: argparse.Namespace) -> int:
    sources = load_sources(Path(args.sources))
    print(f"Extracting from {len(sources)} document(s):")
    chunks = _chunk_all(sources)
    summary = summarise_chunks(chunks)
    print(f"\n{summary['chunks']} rules ({summary['requirements']} numbered, {summary['headings']} sectioned)")
    if summary["split"]:
        print(f"  {summary['split']} were too long to keep whole and were split -- review those first")
    return 0


def cmd_propose(args: argparse.Namespace) -> int:
    sources = load_sources(Path(args.sources))
    print(f"Extracting from {len(sources)} document(s):")
    chunks = _chunk_all(sources)
    if not chunks:
        raise SystemExit("no rules found; check the source documents and the chunking patterns")

    llm = build_llm(args.provider)
    print(f"\nDrafting preconditions with {llm.provider} / {llm.model_id} ...")
    proposals = propose_all(chunks, llm)

    if args.approve_all:
        extracted = [p.passage_id for p in proposals if p.provenance == "extracted"]
        if extracted:
            raise SystemExit(
                "--approve-all refuses to approve extracted passages: "
                f"{len(extracted)} of them came from a real document. Approving a model's "
                "reading of a standard in bulk is what this pipeline exists to prevent. "
                "Review corpus/review.json by hand."
            )
        for proposal in proposals:
            review.approve(proposal, "compiler --approve-all (synthesised corpus)")

    out = review.write_for_review(proposals, Path(args.out))
    counts = review.summarise(proposals)
    print(f"\nWrote {counts['total']} proposals to {out}")
    print(f"  {counts['warned']} need attention before they can be approved")
    print(f"  {counts['awaiting_review']} await review")
    print("\nEdit that file: set approved=true and reviewed_by for each passage you accept.")
    return 0


def cmd_emit(args: argparse.Namespace) -> int:
    proposals = review.read_reviewed(Path(args.review))
    # The emitted artefact records the registry's provenance verbatim, not a
    # summary of it. A corpus that says which documents it came from but not
    # which revision, nor how that revision was verified to be current, is one
    # nobody can re-derive a decision from a year later.
    sources = (
        [
            {
                "doc_id": r.doc_id,
                "title": r.title,
                "document_number": r.document_number,
                "revision": r.revision,
                "published": r.published,
                "authority": r.authority,
                "url": r.url,
                "retrieved": r.retrieved,
                "verified_on": r.verified_on,
                "verification": r.verification,
                "supersedes": list(r.supersedes),
                "rationale": r.rationale,
                "scope": [dict(entry) for entry in r.scope],
                "sha256": r.sha256,
            }
            for r in registry.read(Path(args.sources))
        ]
        if args.sources
        else []
    )

    try:
        corpus = emit.build(proposals, sources, version=args.version)
    except review.ReviewIncomplete as exc:
        # The gate refusing is the pipeline working. Exit non-zero, loudly.
        print(f"\nRefusing to emit: {exc}", file=sys.stderr)
        return 2

    artefact = emit.write(corpus, Path(args.out))
    summary = corpus.summary()
    print(f"Wrote {artefact}")
    print(f"  {summary['passages']} passages ({summary['extracted']} extracted, {summary['synthesised']} synthesised)")
    print(f"  manifest {summary['manifest'][:16]}...")
    print(f"  documents: {', '.join(summary['documents']) or '(none)'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compiler", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="read and chunk the source documents")
    p_extract.add_argument("--sources", default="corpus/sources.json")
    p_extract.set_defaults(func=cmd_extract)

    p_propose = sub.add_parser("propose", help="draft preconditions for human review")
    p_propose.add_argument("--sources", default="corpus/sources.json")
    p_propose.add_argument("--out", default="corpus/review.json")
    p_propose.add_argument("--provider", default="", help="mock | ollama | watsonx")
    p_propose.add_argument(
        "--approve-all",
        action="store_true",
        help="approve without review; refuses on extracted passages",
    )
    p_propose.set_defaults(func=cmd_propose)

    p_emit = sub.add_parser("emit", help="write the compiled corpus")
    p_emit.add_argument("--review", default="corpus/review.json")
    p_emit.add_argument("--sources", default="")
    p_emit.add_argument("--version", required=True)
    p_emit.add_argument("--out", default="corpus/compiled")
    p_emit.set_defaults(func=cmd_emit)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
