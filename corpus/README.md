# The procedure corpus

The rulebook HAVEN reasons over. Either the hand-authored corpus in
`haven/rag/corpus.py`, or an artefact compiled from source documents.

## Compiling from source documents

Put the PDFs in `corpus/sources/` — gitignored, because they are redistributable
only from their original publishers — and list them in `corpus/sources.json`.
Copy `sources.example.json` to start.

```bash
uv sync --extra compiler

python -m compiler.cli extract --sources corpus/sources.json
python -m compiler.cli propose --sources corpus/sources.json --out corpus/review.json --provider ollama
# then edit corpus/review.json by hand
python -m compiler.cli emit --review corpus/review.json --sources corpus/sources.json \
    --version 2026.08 --out corpus/compiled

HAVEN_CORPUS=corpus/compiled/corpus-2026.08.json uv run uvicorn haven.api.main:app
```

The middle step is a person reading. There is no command that does all three,
because a model drafted those preconditions and the deterministic checker will
treat them as ground truth — approval is the step that makes that safe, and the
emit path refuses without it.

## What the compiler will and will not do

It reads a rule and proposes how to encode its preconditions. It cannot decide
whether that reading is right, and it does not pretend to: every proposal is
shown to a reviewer with whatever the validator flagged, and the build fails
until each is either approved or explicitly marked as not governing fatigue.

Three refusals are hard:

- **Nothing unapproved is emitted.** A flag set by a script is not a person
  having looked; `reviewed_by` must name someone.
- **Nothing approved-but-warned is emitted.** Approving a known-broken encoding
  is likelier a slip than a decision.
- **No extracted passage may declare zero preconditions.** The checker reads an
  empty clause set as "always applies", which is correct for a hand-authored
  rule stating exactly that, and wrong for an extracted one where it means the
  extraction produced nothing. Such a passage would be admissible for every
  Situation — fail-open, in a system whose thesis is fail-closed.

`--approve-all` exists for the synthesised corpus, whose encodings were written
by hand in the first place. It refuses on extracted passages.

## A caution about design standards

NASA-STD-3001 and the HIDH are *design* standards. They say the system shall
provide an 8-hour sleep opportunity; they do not say what to do when an operator
is below the alertness threshold thirty minutes before a burn. HAVEN's reasoning
demonstration needs execution-time gating rules with preconditions, and the
public record largely does not contain them.

So a compiled corpus will mix the two, and the distinction is a field rather
than a footnote: `provenance` is `extracted` for anything read from a real
document and `synthesised` for a rule written for this prototype because the
public record has no execution-time equivalent. It is part of the corpus
manifest, so two corpora with identical rules but different provenance claims
digest differently — an auditor reading a decision can tell which rules were
real.
