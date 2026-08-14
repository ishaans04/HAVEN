# HAVEN

**Human Adaptation & Vitality Enhancement Network** — a fatigue-aware safety co-pilot for high-stakes crew decisions.

A runnable prototype of the system specified in *HAVEN Product Requirements Document v1.0* (IBM AI Builders Challenge, Space Exploration category). It couples a deterministic fatigue-and-workload engine with a retrieval-augmented reasoning tier that interprets mission operating procedures, produces cited recommendations, and **refuses when no procedure governs the situation**.

> **The architectural invariant**
> The maths owns the numbers. The AI owns the rulebook reasoning. The human owns the decision.
> No code path lets the reasoning tier emit a safety-critical figure or take an irreversible action.

---

## Running it

Two processes. Neither needs an API key, a model download, a database, or a
network connection — the offline path is a first-class path, not a degraded one,
and CI asserts it on every push.

Dependencies are managed with [uv](https://docs.astral.sh/uv/). Install it once
with `pip install uv`, or see the upstream instructions.

**Backend** (from `backend/`):

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend** (from `frontend/`):

```bash
npm install && npm run dev
```

Open <http://localhost:3000>. Interactive API docs are at <http://localhost:8000/docs>.

**Tests** (from `backend/`):

```bash
uv run pytest
```

Provider- and service-backed tests are excluded by default, so a clean checkout
runs green with no Ollama and no watsonx credentials. Opt in with
`uv run pytest -m integration` or `-m live`.

**See every scenario's outcome in one pass:**

```bash
uv run python -m tools.calibrate
```

**Regenerate the contract** after changing `app/contracts.py` — CI fails if these
are stale:

```bash
uv run python -m tools.export_openapi   # from backend/
npm run gen:types                       # from frontend/
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

```
 PRESENTATION   Next.js 14 · React 18 · TypeScript · Tailwind · Recharts
                six-zone operator console
                      |
                      |  REST / JSON — the locked contract
                      v
 API            FastAPI (async, Python 3.11+)
                      |
      +---------------+----------------+
      v               v                v
 DETERMINISTIC   ORCHESTRATION    RETRIEVAL (RAG)
 Three-Process   + AUDIT          top-k over the
 Model, NASA-    retrieve→select  procedure corpus,
 TLX, triggers,  →gate→fuse→      near-misses
 screens         generate|refuse  included
      ^               |
      |               v
      |          REASONING LLM
      +--------- Granite (mock | Ollama | watsonx.ai)
```

### Tier boundaries

| Tier | Owns | Never does |
|---|---|---|
| **Deterministic** | Alertness, workload, sleep debt, circadian phase, every threshold, both screens. | Any language generation or rule interpretation. |
| **Retrieval** | Chunking, embedding, top-k candidates — including confusable near-misses, on purpose. | Decide which candidate governs. |
| **Orchestration + audit** | Sequencing the flow; a hash-chained record of every step, input, and output. | Produce safety numbers or make the final decision. |
| **Reasoning LLM** | Select the governing rule, fuse facts, generate cited text, or refuse. | Invent or override any number. |
| **Presentation** | Rendering and capturing human approval. | Any logic decision. |

### Layout

```text
backend/
  pyproject.toml                dependencies, Ruff, pytest — one file
  openapi.json                  the exported contract; the console's types are generated from it
backend/app/
  offline.py                    the offline guarantee, enforced at import time
  config.py                     every safety threshold, in one reviewable place
  contracts.py                  the locked JSON contract (Pydantic)
  engine.py                     the seven-stage evaluation cycle
  main.py                       FastAPI routes
  deterministic/
    three_process_model.py      Åkerstedt & Folkard, published parameters
    nasa_tlx.py                 Hart & Staveland weighted formula
    triggers.py                 stage 3 — raise a Situation, or archive
    screens.py                  stage 6 — confidence gate + schedule impact
  retrieval/
    corpus.py                   procedures, near-misses, and one deliberate gap
    vector_store.py             in-process TF-IDF | real ChromaDB
    retriever.py                LangChain-shaped retriever interface
  reasoning/
    llm.py                      mock | Ollama | watsonx adapters + numeric guard
    orchestrator.py             the reasoning flow
    audit.py                    hash-chained append-only trail
  data/
    crew.py                     representative roster, synthetic sleep/duty
    scenarios.py                the eight demo scenarios
frontend/src/
  lib/api-types.ts              generated from openapi.json — do not edit
  lib/types.ts                  friendly names over the generated shapes
  components/                   one file per zone
```

---

## The safety model, as tests

The three hard rules are executable, not aspirational. `backend/tests/test_safety_invariants.py`:

1. **Numbers are computed, never generated.** Every numeral in operator-facing text is asserted to trace back to a value the deterministic tier logged. `assert_no_novel_numbers` raises on violation at runtime, and a test proves the guard actually fires.
2. **The system flags risk; it never acts.** Every Situation resolves to exactly one of a recommendation or a refusal. There is no third, self-actioning state.
3. **No citation, no recommendation.** Every citation is asserted to resolve to a real passage whose document and section match.

Plus: refusals must record what was searched and why the best candidate failed; the audit chain must verify for every Situation; and tampering with a logged step must break it.

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

The prompts in `reasoning/llm.py` are the real prompts — the mock receives them and returns what Granite is asked to return. See `backend/.env.example`.

---

## Honest limits

Named explicitly, because the system's whole thesis is that flagging uncertainty beats asserting false confidence.

**Real:** the Three-Process Model and NASA-TLX with their published parameters; the retrieval, precondition-checked rule selection, refusal path, deterministic screens, and hash-chained audit trail, all executing live on every evaluation; the watsonx and Ollama adapters.

**Simulated, and labelled in the UI:**

- **The crew roster is representative, not real individuals.** Attaching modelled fatigue states to identifiable astronauts would be the wrong default even in a demo. Substituting a public roster is a data change in `data/crew.py`.
- **Sleep, duty, and task timelines are synthetic.** No public live crew-timeline feed exists. The structure follows NASA scheduling literature; the values are generated from explicit per-night parameters so every scenario is reproducible.
- **The procedure corpus text is written for this prototype.** Document numbering, precondition style, and structure follow NASA flight-rule convention; the prose is not verbatim NASA procedure. Provenance is carried on every passage.
- **The reasoning model is a scripted stand-in by default**, so the console runs offline and a demo cannot fail on a network call.

**Deferred:** the closed verification loop — confirming after the fact that alertness and coverage actually improved — needs a time-simulation layer beyond this build. Named rather than half-built.

---

*Deterministic tier owns all safety numbers; the AI reasoning tier reads, selects, explains, or refuses; the human owns every decision.*
