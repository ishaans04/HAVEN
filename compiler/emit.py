"""Writing the compiled corpus the runtime loads.

The output is a versioned artefact with a manifest digest. Phase 2 already
threads that digest onto every Situation and every ledger row, so a decision
records the exact rulebook it was made under — this is where the rulebook stops
being a Python literal and becomes something that can differ between deployments.

Two things are kept that a smaller system would drop.

**Provenance, per passage.** Document, revision, page, retrieval date, the
reviewer's name, and whether the text was extracted from a real source or
written for this prototype. A citation nobody can look up is not a citation, and
the distinction between extracted and synthesised is exactly the kind of thing
that quietly disappears unless it is a field.

**The reviewer's name.** Not for blame — so that a corpus can be asked who
approved a given encoding, which is the only way to re-examine a rule that later
turns out to have been read wrongly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from compiler.propose import Proposal
from compiler.review import gate
from haven.rag.corpus import Passage, compute_manifest

CORPUS_FORMAT_VERSION = 1


@dataclass(frozen=True)
class CompiledCorpus:
    version: str
    manifest: str
    passages: list[Passage]
    sources: list[dict]
    generated_at: str

    def summary(self) -> dict:
        return {
            "version": self.version,
            "manifest": self.manifest,
            "passages": len(self.passages),
            "extracted": sum(1 for p in self.passages if p.provenance == "extracted"),
            "synthesised": sum(1 for p in self.passages if p.provenance == "synthesised"),
            "documents": sorted({p.doc for p in self.passages}),
        }


def to_passage(proposal: Proposal) -> Passage:
    """One approved proposal as the Passage the runtime already understands.

    The runtime's shape is unchanged, which is the point: swapping a
    hand-authored corpus for a compiled one must not ripple into the checker,
    the retriever, or the graph.
    """
    return Passage(
        passage_id=proposal.passage_id,
        doc=proposal.doc,
        section=proposal.section,
        title=proposal.title,
        text=proposal.text,
        task_types=list(proposal.applies_when.get("task_types", [])),
        applies_when=dict(proposal.applies_when),
        prescribes=proposal.prescribes,
        fallback_action=proposal.fallback_action,
        source=proposal.source,
        provenance=proposal.provenance,
        reviewed_by=proposal.reviewed_by,
    )


def build(proposals: list[Proposal], sources: list[dict], *, version: str) -> CompiledCorpus:
    """Gate, convert, and digest. Raises if anything is unapproved."""
    passages = [to_passage(p) for p in gate(proposals)]
    return CompiledCorpus(
        version=version,
        manifest=compute_manifest(passages),
        passages=passages,
        sources=sources,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def write(corpus: CompiledCorpus, directory: Path) -> Path:
    """Write the artefact and its manifest.

    Two files rather than one. The manifest is small and stable enough to read
    at a glance or diff in review, which is what makes "the rulebook changed"
    something a person notices rather than something buried in a large JSON blob.
    """
    directory.mkdir(parents=True, exist_ok=True)
    artefact = directory / f"corpus-{corpus.version}.json"

    payload = {
        "format_version": CORPUS_FORMAT_VERSION,
        "version": corpus.version,
        "manifest": corpus.manifest,
        "generated_at": corpus.generated_at,
        "sources": corpus.sources,
        "passages": [
            {
                "passage_id": p.passage_id,
                "doc": p.doc,
                "section": p.section,
                "title": p.title,
                "text": p.text,
                "task_types": p.task_types,
                "applies_when": p.applies_when,
                "prescribes": p.prescribes,
                "fallback_action": p.fallback_action,
                "source": p.source,
                "provenance": p.provenance,
                "reviewed_by": p.reviewed_by,
                "near_miss_note": p.near_miss_note,
            }
            for p in corpus.passages
        ],
    }
    artefact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")

    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "version": corpus.version,
                "manifest": corpus.manifest,
                "generated_at": corpus.generated_at,
                "artefact": artefact.name,
                **corpus.summary(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return artefact


def load(path: Path) -> list[Passage]:
    """Read a compiled corpus, verifying it is what it claims to be.

    The manifest is recomputed rather than trusted. An artefact edited after
    compilation -- a precondition widened by hand, a passage appended -- would
    otherwise be loaded as though a reviewer had approved it, and every decision
    made under it would record a manifest naming a corpus that never existed.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))

    version = payload.get("format_version")
    if version != CORPUS_FORMAT_VERSION:
        raise ValueError(f"{path.name} is format version {version}; this build reads {CORPUS_FORMAT_VERSION}")

    passages = [
        Passage(
            passage_id=item["passage_id"],
            doc=item["doc"],
            section=item["section"],
            title=item.get("title", ""),
            text=item["text"],
            task_types=list(item.get("task_types", [])),
            applies_when=dict(item.get("applies_when", {})),
            prescribes=item.get("prescribes"),
            fallback_action=item.get("fallback_action"),
            source=item.get("source", ""),
            near_miss_note=item.get("near_miss_note", ""),
            provenance=item.get("provenance", "extracted"),
            reviewed_by=item.get("reviewed_by", ""),
        )
        for item in payload.get("passages", [])
    ]

    recomputed = compute_manifest(passages)
    claimed = payload.get("manifest", "")
    if claimed and recomputed != claimed:
        raise ValueError(
            f"{path.name} has been edited since it was compiled: it claims manifest "
            f"{claimed[:16]}… but its passages digest to {recomputed[:16]}…. "
            f"Recompile rather than editing the artefact by hand."
        )

    return passages
