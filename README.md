# HAVEN

**Human Adaptation & Vitality Enhancement Network** — a fatigue-aware safety co-pilot for high-stakes crew decisions.

A runnable prototype of the system specified in *HAVEN Product Requirements Document v1.0* (IBM AI Builders Challenge, Space Exploration category). It couples a deterministic fatigue-and-workload engine with a retrieval-augmented reasoning tier that interprets mission operating procedures, produces cited recommendations, and **refuses when no procedure governs the situation**.

> **The architectural invariant**
> The maths owns the numbers. **The compiler owns the rules; the AI proposes; a deterministic checker disposes.** The human owns the decision.
> No code path lets the reasoning tier emit a safety-critical figure, cite a rule the checker rejected, or take an irreversible action.

---

## Running it

Two processes. Neither needs an API key, a model download, a database, or a
network connection — the offline path is a first-class path, not a degraded one,
and CI asserts it on every push.

Dependencies are managed with [uv](https://docs.astral.sh/uv/). Install it once
with `pip install uv`, or see the upstream instructions.

**Everything, one process** (from the repository root):

```bash
uv sync
cd web && npm ci && npm run build && cd ..
uv run uvicorn haven.api.main:app --port 8000
```

Open <http://localhost:8000>. FastAPI serves the console as a static export from
the same origin as the API, so there is one port and nothing to configure.
Interactive API docs are at `/docs`.

**Or in a container:**

```bash
docker build -t haven .
docker run -p 7860:7860 -v haven-ledger:/data haven
```

The volume keeps the audit ledger across restarts. Without it the container is
still correct, just amnesiac — the right default for a demo and the wrong one
for anything real.

**For development**, run the console separately so it hot-reloads:

```bash
cd web && NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

**Tests** (from the repository root):

```bash
uv run pytest
```

Provider- and service-backed tests are excluded by default, so a clean checkout
runs green with no Ollama and no watsonx credentials. Opt in with
`uv run pytest -m integration` or `-m live`.

**See every scenario's outcome in one pass:**

```bash
uv run python -m scripts.calibrate
```

**Measure the reasoning tier** against the labelled golden set:

```bash
uv run python -m evaluation.run_eval --provider mock --verbose
```

Two accuracies are reported and the distance between them is the point: what the
provider *proposed*, and what HAVEN *did* after the deterministic checker
disposed of that proposal. Unsafe citations — a recommendation citing a passage
that does not govern — must be zero for every provider, and CI gates on it.

**Run against a real model.** Both need the optional extra:

```bash
uv sync --extra providers

ollama pull granite3.3:8b
HAVEN_LLM_PROVIDER=ollama HAVEN_LLM_MODEL=granite3.3:8b uv run python -m evaluation.run_eval --provider ollama
```

Providers can be chained, which is what a demo should do — `HAVEN_LLM_CHAIN=watsonx,ollama,mock`
tries each in turn and always terminates in the offline stand-in, so a run
cannot fail open. Any answer from below the head of the chain marks the
evaluation degraded and names the link that served it.

**Regenerate the contract** after changing `haven/contracts.py` — CI fails if
these are stale:

```bash
uv run python -m scripts.export_openapi   # from the repository root
npm run gen:types                         # from web/
```

---

## What you are looking at

The console renders one Situation across six zones. Eight scenarios along the top drive the same engine over different inputs — nothing is bypassed or replayed.

| Scenario | What it demonstrates |
|---|---|
| **burn_fatigue** | The core case. Chronic sleep restriction before a reboost burn → cited second-operator verification, staffed. |
| **eva_near_miss** | Discrimination. A near-miss passage retrieves at 0.708 against the governing rule's 0.715 — near-tied on similarity — and is rejected on its preconditions. |
| **no_procedure** | **Refusal.** Nothing in the corpus governs fatigue during a medical contingency. The system escalates rather than reaching for the nearest plausible rule. |
| **roster_block** | A deterministic screen vetoing a well-formed AI recommendation, then regenerating the text for the fallback the same passage prescribes. |
| **circadian_trap** | An 03:20 capture that passes a sleep-totals check and fails on circadian phase and sleep inertia. |
| **thin_data** | The confidence gate withholding *before* the reasoning tier is invoked. The data gap is the finding. |
| **nominal_ops** | Correct silence. A rested crew raises nothing; the audit bar distinguishes quiet from broken. |
| **provider_outage** | Degraded mode. The reasoning provider is unreachable, so the system says so and escalates instead of guessing from the deterministic tier alone. |

---

## Architecture

```text
 PRESENTATION   Next.js 14 · React 18 · TypeScript · Tailwind · Recharts
                six-zone operator console
                      |
                      |  REST / JSON — the locked contract, generated both sides
                      v
 API            FastAPI (Python 3.12+)
                      v
 ORCHESTRATION  LangGraph — a compiled, static state machine
                INGEST → SCORE → TRIGGER → SITUATIONS → PRESENT
                                              |
                        per raised Situation: |
                CONFIDENCE → RETRIEVE → ADMISSIBILITY → SELECT → VERIFY
                     |                        ^            |        |
                     ↘ WITHHOLD               |            |        ↘ FUSE → GENERATE
                                              |            |          ↘ REFUSE
                                              |            |                 |
      +---------------------------------------+            |                 v
      |                                                     |            SCREEN
 DETERMINISTIC                                        REASONING LLM
 Three-Process Model, NASA-TLX, triggers,             Granite
 both screens, and the precondition checker           (mock | Ollama | watsonx.ai)
 that disposes of what the model proposes             sees passage prose only

 LEDGER         HMAC-SHA256, globally chained across trails, SQLite, INSERT-only
```

The model is consulted at exactly three nodes — SELECT, FUSE, GENERATE — and
routes nothing. Every branch in the graph is decided by a deterministic
predicate, and the topology is asserted against a committed snapshot.

### Tier boundaries

| Tier | Owns | Never does |
|---|---|---|
| **Deterministic** | Alertness, workload, sleep debt, circadian phase, every threshold, both screens, **and rule admissibility**. | Any language generation. **Select** a rule — it can only veto one. |
| **Retrieval** | Chunking, embedding, top-k candidates — including confusable near-misses, on purpose. | Decide which candidate governs. |
| **Orchestration + audit** | Sequencing, as a compiled graph; a signed, globally-chained, persistent ledger. | Produce safety numbers or make the final decision. |
| **Reasoning LLM** | **Read passage prose**, propose a governing rule, fuse facts, generate cited text, or refuse. | Invent a number. **See compiled preconditions.** **Promote a passage the checker rejected.** |
| **Presentation** | Rendering and capturing human approval. | Any logic decision. |

### Layout

One repository, no `backend/` and `frontend/` split. The Python package carries
the tier boundaries in its own directory names, so the architecture is legible
from the file tree.

```text
pyproject.toml                  dependencies, Ruff, pytest — one file
openapi.json                    the exported contract; the console's types are generated from it
haven/
  offline.py                    the offline guarantee, enforced at import time
  config.py                     every safety threshold, in one reviewable place
  contracts.py                  the locked JSON contract (Pydantic)
  engine.py                     binds the adapters and invokes the graph
  api/
    main.py                     FastAPI routes
  graph/                        the cycle as a compiled state machine
    evaluation_graph.py         INGEST → SCORE → TRIGGER → SITUATIONS → PRESENT
    situation_graph.py          CONFIDENCE → RETRIEVE → ADMISSIBILITY → SELECT → VERIFY → …
    nodes/                      one module per node
  deterministic/                owns every safety number, and admissibility
    three_process_model.py      Åkerstedt & Folkard, published parameters
    nasa_tlx.py                 Hart & Staveland weighted formula
    triggers.py                 raise a Situation, or archive
    screens.py                  confidence gate + schedule impact
    preconditions.py            the checker that disposes of the model's proposal
  rag/                          retrieves candidates; decides nothing
    corpus.py                   procedures, near-misses, one deliberate gap, manifest
    vector_store.py             in-process TF-IDF | real ChromaDB
    retriever.py                LangChain-shaped retriever interface
  reasoning/                    reads, proposes, explains, or refuses
    llm.py                      mock | Ollama | watsonx adapters + numeric guard
    orchestrator.py             what each reasoning step does
    audit.py                    the signed, globally-chained, persistent ledger
    signing.py                  the ledger's key
  data/
    crew.py                     representative roster, synthetic sleep/duty
    scenarios.py                the eight demo scenarios
web/src/                        the six-zone operator console
  lib/api-types.ts              generated from openapi.json — do not edit
  lib/types.ts                  friendly names over the generated shapes
  components/                   one file per zone
tests/                          including the safety invariants
scripts/                        calibrate, export_openapi
```

---

## The safety model, as tests

The three hard rules are executable, not aspirational. `tests/test_safety_invariants.py`:

1. **Numbers are computed, never generated.** Every numeral in operator-facing text is asserted to trace back to a value the deterministic tier logged. `assert_no_novel_numbers` raises on violation at runtime, and a test proves the guard actually fires.
2. **The system flags risk; it never acts.** Every Situation resolves to exactly one of a recommendation or a refusal. There is no third, self-actioning state.
3. **No citation, no recommendation.** Every citation is asserted to resolve to a real passage whose document and section match.

Since v2 they are joined by six more, each with a named enforcement point:

4. **The reasoning tier never receives compiled preconditions.** The model selects from passage prose alone; `applies_when` and `prescribes` are redacted from every provider-bound payload. Asserted on the rendered prompt, not on behaviour.
5. **No citation without independent confirmation.** A passage the deterministic checker rejects cannot be cited, whatever the model proposed.
6. **Disagreement fails closed, in both directions.** A model refusal is never overridden upward, even when the checker believes something is admissible.
7. **No entry is forgeable without the key, and none is deletable undetectably.**
8. **Every recommendation and refusal records the corpus manifest** it was made under.
9. **The graph is static** — no LLM routes, no tool nodes, no unbounded cycles; topology asserted against a committed snapshot.

Plus: refusals must record what was searched and why the best candidate failed; the ledger must verify for every Situation; corrupting a logged step must break it, and so must forging one.

Alongside them, the offline guarantee is executable too: `tests/test_offline_guard.py`
imports the API tier in a subprocess with tracing forced *on* and every socket
connection trapped, and asserts that nothing reaches the network and that
`langchain-core`'s own accessor reports tracing disabled.

```text
123 passed
```

---

## Swapping the mocked tiers for real ones

Both mocked tiers sit behind interfaces their real counterparts already satisfy. Promoting them is configuration, not a rewrite.

| Mocked now | Real path | Switch |
|---|---|---|
| Scripted Granite stand-in | IBM watsonx.ai Granite | `HAVEN_LLM_PROVIDER=watsonx` + credentials |
| Scripted Granite stand-in | Local Granite via Ollama | `HAVEN_LLM_PROVIDER=ollama` |
| In-process TF-IDF store | ChromaDB + sentence-transformers | `HAVEN_VECTOR_STORE=chroma`, after `uv sync --extra rag` |

The prompts in `reasoning/llm.py` are the real prompts — the mock receives them and returns what Granite is asked to return. See `.env.example`.

---

## Honest limits

Named explicitly, because the system's whole thesis is that flagging uncertainty beats asserting false confidence.

**Real:** the Three-Process Model and NASA-TLX with their published parameters; retrieval, model-proposed and checker-verified rule selection, the refusal path, both deterministic screens, and a persistent HMAC-signed globally-chained ledger, all executing live on every evaluation; the watsonx and Ollama adapters.

**Simulated, and labelled in the UI:**

- **The crew roster is representative, not real individuals.** Attaching modelled fatigue states to identifiable astronauts would be the wrong default even in a demo. Substituting a public roster is a data change in `data/crew.py`.
- **Sleep, duty, and task timelines are synthetic.** No public live crew-timeline feed exists. The structure follows NASA scheduling literature; the values are generated from explicit per-night parameters so every scenario is reproducible.
- **The procedure corpus text is written for this prototype.** Document numbering, precondition style, and structure follow NASA flight-rule convention; the prose is not verbatim NASA procedure. Provenance is carried on every passage.
- **The reasoning model is a scripted stand-in by default**, so the console runs offline and a demo cannot fail on a network call.

**The audit ledger is tamper-evident, not tamper-proof.** Entries are signed with HMAC-SHA256 and chained globally across every trail, so an entry cannot be rewritten, and a whole trail cannot be deleted, without the key — either leaves a break the ledger reports, with the sequence number where it happened. What that does *not* stop is an attacker who holds the signing key **and** write access: they can rewrite an entry, re-sign it, re-chain everything after it, and re-write the checkpoints too. Closing that needs storage the attacker cannot reach — WORM media, or an external notary — which this build does not have. The periodic checkpoints narrow the window; they do not close it. A test asserts this limit explicitly rather than leaving it implied.

**Deferred:** the closed verification loop — confirming after the fact that alertness and coverage actually improved — needs a time-simulation layer beyond this build. Named rather than half-built.

---

## Where this stands

Phases 0–8 of the v2 plan are complete. Every gap the architecture design named
is closed and enforced by a test that fails when the protection is removed:

| Gap | Closed by |
|---|---|
| The reasoning tier is bypassed — it was handed the answer key | Phase 1B — it reads prose; a deterministic checker disposes |
| `applies_when` is authored metadata, not extracted knowledge | Phase 4 — a compiler, under human review |
| No persistence; `audit_ref` collides across evaluations | Phase 2 — a SQLite ledger, distinct identities |
| Real-provider adapters never executed | Phase 3 — LangChain chat models, tested |
| The chain detects corruption but not tampering | Phase 2 — HMAC, globally chained |

**651 tests.** Nine safety requirements, each with a named enforcement point.

What has *not* been done, plainly: no live-provider figures exist, because
watsonx credentials were not available here — the evaluation harness reports the
offline stand-in's numbers and exists precisely to produce the comparison the
moment there is something to measure. The container is written and its parts are
verified individually, but Docker was not installed in the build environment, so
the image itself is unbuilt. The corpus is still the hand-authored one; the
compiler that replaces it is tested end to end against generated PDFs rather
than against NASA's.

See `CHANGELOG.md` for what each phase decided and why, and `DEMO.md` for the
six-scenario walkthrough.

---

*Deterministic tier owns all safety numbers; the AI reasoning tier reads, proposes, explains, or refuses; a deterministic checker disposes; the human owns every decision.*
