# The procedure corpus

The rulebook HAVEN reasons over. Either the hand-authored corpus in
`haven/rag/corpus.py`, or an artefact compiled from the real NASA documents
named in `sources.json`.

## The documents

Six, all cleared by NASA for public release, all version-verified against their
publisher before anything was downloaded. `sources.json` carries the full record
— document number, revision, approval date, canonical URL, pinned SHA-256, and a
note saying how the revision was confirmed current. `EXTRACTION.md` records what
each one yielded.

| Document | Revision | Authority |
|---|---|---|
| NASA-STD-3001 Volume 2 — Human Factors, Habitability, Environmental Health | F, 2026-07-14 | authoritative |
| NASA-STD-3001 Volume 1 — Crew Health | C, 2023-09-15 | authoritative |
| NASA/SP-2010-3407 — Human Integration Design Handbook | Rev 1, 2014-06-05 | guidance |
| Evidence Report: sleep loss, circadian desynchronization, work overload | 2016 | research |
| NASA-TM-108839 — planned cockpit rest (Crew Factors IX) | 1994 | research |
| NASA/TM-2001-211385 — alertness management (Crew Factors X) | 2001 | research |

**Volume 1 was added beyond the Volume 2 originally specified**, and the reason
is worth stating because it is a finding rather than a preference. Volume 2 has
1,579 requirements. Fifty-one mention sleep, fatigue or workload, and not one
states a work-rest limit: section 7.9, *Behavioral Health and Sleep*, contains
three requirements, all of them about the sleep environment. The standard's
fatigue requirements are in Volume 1, whose section 6.1 is titled *Circadian
Shifting Operations and Fatigue Management*. Compiling a fatigue corpus from the
volume with no fatigue requirements in it would have been a thorough job of the
wrong thing.

The **HIDH** is the sharper version-verification case. NASA's OCHMO page
publishes Revision 1; the PDF's own history log records a Revision 2 dated
2022-10-20 whose only change is Section 4, *Anthropometry, Biomechanics, and
Strength*, which NASA distributes separately as OCHMO-HB-004 Rev A. So Section 4
of Revision 1 is superseded, and the compiled scope does not reach it — it stops
at 7.10 *Sleep*. That is what "do not ingest a superseded version" means when the
supersession is partial.

The **research set is three papers and is meant to stay small.** Each states its
selection rationale in `sources.json`, and each maps to a specific mechanism:
the Evidence Report is NASA's own account of the risk HAVEN scores; TM-108839 is
the measurement behind the short-rest action; TM-2001-211385 is the countermeasure
taxonomy HAVEN's action types map onto. Every research passage is retrievable and
none can ground an action, so each one added is another near-miss the reasoning
tier has to reject. A handful makes the corpus adversarial. Fifty makes it noise,
and a test fails above five.

## Authority: what a document is allowed to do

Three kinds of text sit in the same index and read almost identically.
NASA-STD-3001 says *shall*. The HIDH explains why. A paper reports what was
measured. Retrieval cannot tell them apart, and left alone that produces the
worst failure this system is capable of — a recommendation grounded in the HIDH,
carrying a real citation to a real NASA document an operator can look up, where
the sentence cited says *should*. An uncited guess would be safer, because it
does not check out.

So `authority` is a field on every passage, carried from the registry, never
proposed by a model, and enforced at two independent points:

- **`compiler.review.gate`** refuses to emit a guidance or research passage that
  declares a prescribed action. It never enters the corpus.
- **`haven.deterministic.preconditions.check`** evaluates authority *first*,
  before any precondition, and fails closed on an unstated one. If such a passage
  ever does get in, it cannot be cited.

`prototype` — the hand-authored layer — is admitted alongside `authoritative`,
because it exists precisely to stand in for the execution-time flight rules the
public record does not contain, and it says so everywhere it surfaces.

`EXTRACTION.md` ends with the probe that settled this: BM25 over the real
passages, five ordinary fatigue queries. Ask about the circadian trough and all
five top hits are research papers. Ask about a protected rest period and four of
five are the cockpit-rest study, with the one actual requirement fifth. The gate
is not protecting against a hypothetical.

## A requirement is not its rationale

The same mistake, at passage scale, and the compiler would have made it. Here is
[V1 6001] in full:

> Crew schedule planning and operations **shall** be provided to include
> circadian entrainment, work/rest schedule assessment, task loading assessment,
> countermeasures, and special activities.
>
> [Rationale: … c. Recommended 8.5 hr. sleep period … e. Avoid scheduling
> critical tasks during the circadian nadir (typically between 1-7 AM relative
> to one's regular sleep schedule) …]

The rationale is where the operationally useful sentences are. It is not the
requirement — in NASA-STD-3001 a rationale block is explanatory and non-binding —
and a reader given the concatenation encodes "avoid the circadian nadir" as a
machine-checkable precondition and produces a rule NASA did not write. So the
chunker separates them, and the extraction prompt receives both, labelled.

## Compiling

```bash
uv sync --extra compiler

uv run python -m scripts.fetch_corpus                 # download and verify
uv run python -m compiler.cli extract --report corpus/EXTRACTION.md
uv run python -m compiler.cli propose --out corpus/review.json --provider ollama
#   ... then a person reads corpus/review.json ...
uv run python -m compiler.cli emit --review corpus/review.json \
    --sources corpus/sources.json --version 2026.08 --out corpus/compiled

HAVEN_CORPUS=corpus/compiled/corpus-2026.08.json uv run uvicorn haven.api.main:app
```

The PDFs are gitignored — they are redistributable only from their publishers —
and so is the review file. Everything needed to reproduce the acquisition byte
for byte is tracked instead. **A checksum mismatch is refused, not warned about:**
a standards body replacing a PDF in place is how a corpus silently becomes a
corpus of a different revision, with every decision under it citing section
numbers that have moved. The remedy is deliberate — verify the new revision,
update the registry, re-review the passages it changes — and that is the right
amount of friction.

The middle step is a person reading. There is no command that does all three,
because a model drafted those preconditions and the deterministic checker will
treat them as ground truth — approval is the step that makes that safe, and the
emit path refuses without it.

## What the compiler will and will not do

It reads a rule and proposes how to encode its preconditions. It cannot decide
whether that reading is right, and it does not pretend to: every proposal is
shown to a reviewer with whatever the validator flagged, and the build fails
until each is either approved or explicitly marked as not governing fatigue.

Four refusals are hard:

- **Nothing unapproved is emitted.** A flag set by a script is not a person
  having looked; `reviewed_by` must name someone.
- **Nothing approved-but-warned is emitted.** Approving a known-broken encoding
  is likelier a slip than a decision.
- **No extracted passage may declare zero preconditions.** The checker reads an
  empty clause set as "always applies", which is correct for a hand-authored
  rule stating exactly that, and wrong for an extracted one where it means the
  extraction produced nothing. Such a passage would be admissible for every
  Situation — fail-open, in a system whose thesis is fail-closed.
- **No guidance or research passage may prescribe an action.** See above.

`--approve-all` exists for the synthesised corpus, whose encodings were written
by hand in the first place. It refuses on extracted passages.

## What has not been done

**Nothing has been reviewed, so no compiled corpus exists.** The 131 extracted
passages sit in `corpus/review.json` awaiting a person; `emit` refuses, which is
the pipeline working rather than failing. Two things are missing and neither is
a matter of running one more command:

- **No extraction model was available.** Ollama is not installed here and there
  are no watsonx credentials, so `propose --provider mock` returns nothing
  readable for EXTRACT and all 131 proposals arrive undrafted. They carry the
  passage text, its provenance and its authority, and are ready to be encoded —
  by a real model with `--provider ollama`, or by hand.
- **No reviewer.** `reviewed_by` must name a person, and the whole point of the
  gate is that it cannot be satisfied by the thing that drafted the proposals.

**Design standards are not execution rules, and now there is evidence.** This
was recorded as a risk before any document was read; four documents later it is
confirmed and sharper than expected. The standards require that a *system*
provide a sleep opportunity, that a *programme* establish work-hour limits, that
a *schedule* include fatigue management. None of them says what to do when an
operator's predicted alertness is below threshold thirty minutes before a burn.
The compiled corpus will therefore be mostly authoritative rules that a reviewer
marks as not governing execution-time fatigue — which is not a failure of the
compile. Those rules are the best adversarial material the corpus has ever had:
genuine NASA requirements about sleep that a fatigue query retrieves and that the
system must decline to cite. The hand-authored execution-gating layer stays,
labelled `prototype` and `synthesised` wherever it appears.
