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
import json
import sys
from pathlib import Path

from compiler import emit, review
from compiler.chunk import chunk_document
from compiler.chunk import summarise as summarise_chunks
from compiler.extract import SourceDocument, blank_pages, extract_pages
from compiler.propose import propose_all
from haven.reasoning.llm import build_llm


def load_sources(path: Path) -> list[SourceDocument]:
    """Read the source manifest: which documents, which revision, from where."""
    if not path.exists():
        raise SystemExit(
            f"no source manifest at {path}.\n"
            f"Create one listing the documents to compile, for example:\n"
            f'  [{{"doc_id": "NASA-STD-3001-V2", "title": "...", "path": "corpus/sources/v2.pdf",\n'
            f'     "revision": "D", "url": "https://...", "retrieved": "2026-08-15"}}]'
        )
    entries = json.loads(path.read_text(encoding="utf-8"))
    root = path.parent
    return [
        SourceDocument(
            doc_id=entry["doc_id"],
            title=entry["title"],
            path=(root / entry["path"]) if not Path(entry["path"]).is_absolute() else Path(entry["path"]),
            revision=entry.get("revision", ""),
            url=entry.get("url", ""),
            retrieved=entry.get("retrieved", ""),
            provenance=entry.get("provenance", "extracted"),
        )
        for entry in entries
    ]


def _chunk_all(sources: list[SourceDocument]) -> list:
    chunks = []
    for source in sources:
        pages = extract_pages(source)
        blanks = blank_pages(pages)
        found = chunk_document(pages)
        print(f"  {source.doc_id:<24} {len(pages):>3} pages, {len(found):>3} rules")
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
    sources = (
        [
            {
                "doc_id": s.doc_id,
                "title": s.title,
                "revision": s.revision,
                "url": s.url,
                "retrieved": s.retrieved,
                "sha256": s.sha256(),
            }
            for s in load_sources(Path(args.sources))
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
