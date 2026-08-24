<div align="center">

# HAVEN

### Human Adaptation & Vitality Enhancement Network

**A fatigue-aware safety co-pilot for high-stakes crew decisions.**

*IBM AI Builders Challenge — Space Exploration*

[![IBM watsonx.ai](https://img.shields.io/badge/IBM-watsonx.ai-052FAD?logo=ibm&logoColor=white)](https://www.ibm.com/products/watsonx-ai)
[![Granite 4 H Small](https://img.shields.io/badge/Granite-4--H--Small-0F62FE?logo=ibm&logoColor=white)](https://www.ibm.com/granite)
[![LangChain](https://img.shields.io/badge/LangChain-1.x-1C3C3C?logo=langchain&logoColor=white)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-compiled%20state%20machine-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![RAG](https://img.shields.io/badge/RAG-BM25%20%2B%20dense%20%C2%B7%20RRF-6E4AFF)](#retrieval-and-the-rag-pipeline)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-vector%20store-FF6F61)](https://www.trychroma.com/)

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![REST API](https://img.shields.io/badge/REST-OpenAPI%203.1-85EA2D?logo=openapiinitiative&logoColor=black)](openapi.json)
[![Next.js](https://img.shields.io/badge/Next.js-14.2-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)

[![CI](https://github.com/ishaans04/HAVEN/actions/workflows/ci.yml/badge.svg)](https://github.com/ishaans04/HAVEN/actions/workflows/ci.yml)
[![pytest](https://img.shields.io/badge/pytest-8.x-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![tests](https://img.shields.io/badge/tests-737%20passing-brightgreen)](#testing-and-ci)
[![License](https://img.shields.io/badge/License-Apache%202.0-D22128?logo=apache&logoColor=white)](LICENSE)

</div>

---

## The problem

A fatigued crew member on a long-duration mission is not an edge case. NASA's own
Human Research Program lists *sleep loss, circadian desynchronization and work
overload* as a standing risk to crew performance, and NASA-STD-3001 Volume 1
requires that crew schedule planning include circadian entrainment, work/rest
assessment and fatigue management.

Knowing an operator is impaired is the easy half. The hard half is **what the
procedures say to do about it, right now, for this task** — and that is where a
language model is both the obvious tool and a genuinely dangerous one:

- It will produce an answer even when no procedure governs the situation.
- It will cite the most *similar* rule rather than the one that *applies*.
- It will state a number it computed rather than one that was measured.

Each of those is confidently wrong in exactly the register a tired operator is
least able to challenge. HAVEN is built so that none of them can reach the crew.

> ### The architectural invariant
> The maths owns the numbers. **The compiler owns the rules; the AI proposes; a deterministic checker disposes.** The human owns the decision.
>
> No code path lets the reasoning tier emit a safety-critical figure, cite a rule the checker rejected, or take an irreversible action.

---

## Measured against live IBM watsonx.ai

`ibm/granite-4-h-small`, 20 labelled cases from the golden set
(`uv run --no-sync python -m evaluation.run_eval --provider watsonx`):

<div align="center">

| | Granite alone | **HAVEN** |
|---|:---:|:---:|
| **Accuracy** | 65.0% | **95.0%** |

</div>

| Metric | Result |
|---|---|
| Refusal recall | 100.0% |
| Refusal precision | 90.9% |
| Near-miss rejection | 80.0% |
| **Checker saves** — model wrong, system right | **6** |
| **Unsafe citations** | **0** |
| Provider errors | 0 |
| Median latency | 1,780 ms |

**That thirty-point gap is the architecture, stated as a number.** Granite
proposed the wrong governing rule six times out of twenty. The deterministic
checker caught every one, and not a single incorrect citation reached an
operator. A system that trusted the model's proposal would have shipped six.

Read it in the other direction too: 65% is not a poor model. It is what reading
eleven deliberately-confusable passages actually looks like. The architecture
exists because that number is never going to be 100%.

---

## Quickstart

Dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pip install uv`).
**No API key, model download, database or network connection is required** — the
offline path is a first-class path, and CI asserts it on every push.

```bash
# Setup, once. Name every extra: a bare `uv sync` prunes to the base set.
uv sync --extra providers --extra rag --extra compiler
cd web && npm ci && npm run build && cd ..

# Run
uv run --no-sync python -m scripts.run_haven
```

Open **<http://localhost:8000>**. One process serves the console at `/` and the
API under `/api` from the same origin. Interactive API docs at `/docs`.

> `--no-sync` matters: `uv run` re-syncs before every invocation, and a bare sync
> strips the extras installed above.

**Verify a running instance** — every check in it can fail while the system looks
fine, which is why it exists:

```bash
uv run --no-sync python -m scripts.smoke
```

<details>
<summary><strong>Connecting IBM watsonx.ai</strong></summary>

Copy `.env.example` to `.env` and fill in four values:

| What you have | Variable |
|---|---|
| watsonx API key | `WATSONX_API_KEY` |
| Project ID | `WATSONX_PROJECT_ID` |
| Region URL | `WATSONX_URL` |
| Granite model id | `HAVEN_LLM_MODEL` |
| **Which providers to try** | **`HAVEN_LLM_CHAIN=watsonx,mock`** |

That last row is the one to get right. Without it the chain is `("mock",)`,
watsonx is never attempted, and **no error is raised** — falling through to the
offline stand-in is correct behaviour, which is exactly why a missing chain looks
identical to working credentials.

```bash
uv run --no-sync python -m scripts.check_providers
```

Confirms the credentials are live for a few dozen tokens rather than a full
evaluation sweep, and maps watsonx's several identical-looking authentication
errors onto the one that actually applies.

</details>

<details>
<summary><strong>Docker</strong></summary>

```bash
docker build -t haven .
docker run -p 7860:7860 -v haven-ledger:/data haven
```

The volume keeps the audit ledger across restarts. Port 7860 is what Hugging
Face Spaces expects. *(The Dockerfile is written and its parts are verified
individually; Docker was not installed in the build environment, so the image
itself is unbuilt — see [Honest limits](#honest-limits).)*

</details>

<details>
<summary><strong>Windows and OneDrive</strong></summary>

If the repository lives in a OneDrive-synced folder, `uv sync` can fail partway
with `Access is denied` — OneDrive holds handles open on files uv is replacing,
and a failed sync leaves the environment half-pruned. Installing in place avoids
the prune:

```bash
uv pip install --python .venv/Scripts/python.exe langchain-ibm langchain-ollama
```

An environment constraint, not a repository one: CI runs `uv sync --frozen` on
Linux and is unaffected.

</details>

---

## System architecture

Five tiers with hard boundaries. The arrows that matter are the ones that
**don't** exist: nothing flows from the reasoning tier into the deterministic
one.

```mermaid
flowchart TB
    UI["🖥️ <b>Operator console</b><br/>Next.js 14 · React 18 · six zones"]
    API["⚡ <b>FastAPI</b> · Python 3.12+<br/>REST · OpenAPI contract, types generated both sides"]
    GRAPH["🔀 <b>LangGraph</b><br/>compiled static state machine<br/>no LLM routes · no cycles · topology snapshotted"]
    RAG["📚 <b>Retrieval</b> — decides nothing<br/>BM25 + optional Chroma dense · RRF"]
    LLM["🤖 <b>IBM Granite</b><br/>watsonx.ai · Ollama · offline stand-in<br/>sees passage prose only"]
    DET["🔢 <b>Deterministic tier</b> — owns every safety number<br/>Three-Process Model · NASA-TLX · triggers · screens<br/><b>precondition checker</b>"]
    LEDGER["🔐 <b>Audit ledger</b><br/>HMAC-SHA256 · globally chained · SQLite · INSERT-only"]

    UI <==>|"JSON"| API
    API ==> GRAPH
    GRAPH ==>|"candidates<br/>near-misses included"| RAG
    RAG ==>|"<b>prose only</b><br/>preconditions redacted"| LLM
    LLM ==>|"proposal"| DET
    DET ==>|"admissible, or refused"| GRAPH
    GRAPH -.->|"every step"| LEDGER

    style DET fill:#0F62FE,color:#fff
    style LLM fill:#1C3C3C,color:#fff
    style LEDGER fill:#f4f4f4
```

Follow the thick path: retrieval hands the model **prose only**, the model
returns a **proposal**, and the deterministic tier — not the model — decides
whether it stands. That loop is the whole design.

### Tier boundaries

| Tier | Owns | Never does |
|---|---|---|
| **Deterministic** | Alertness, workload, sleep debt, circadian phase, every threshold, both screens, **and rule admissibility**. | Any language generation. **Select** a rule — it can only veto one. |
| **Retrieval** | Chunking, embedding, top-k candidates — including confusable near-misses, on purpose. | Decide which candidate governs. |
| **Orchestration + audit** | Sequencing, as a compiled graph; a signed, globally-chained, persistent ledger. | Produce safety numbers or make the final decision. |
| **Reasoning LLM** | **Read passage prose**, propose a governing rule, fuse facts, generate cited text, or refuse. | Invent a number. **See compiled preconditions.** **Promote a passage the checker rejected.** |
| **Presentation** | Rendering and capturing human approval. | Any logic decision. |

---

## The workflow, as a compiled state machine

LangGraph is used as a **finite state machine, not an agent**. The safety
property *is* the fixed, auditable step sequence — a model-chosen, variable-length
tool trajectory would be strictly worse to audit. Every edge is either static or
conditional on a deterministic predicate, and the topology is asserted against a
committed snapshot in CI.

```mermaid
flowchart LR
    INGEST([INGEST]) --> SCORE([SCORE])
    SCORE --> TRIGGER{TRIGGER}
    TRIGGER -- "no Situation" --> ARCHIVE([archive])
    TRIGGER -- "Situation raised" --> SITUATIONS([SITUATIONS])
    SITUATIONS --> PRESENT([PRESENT])

    style TRIGGER fill:#0F62FE,color:#fff
```

Per raised Situation, a subgraph runs — and this is where propose/dispose lives:

```mermaid
flowchart LR
    CONF{CONFIDENCE} -- "data too thin" --> WITHHOLD([WITHHOLD])
    CONF -- "sufficient" --> RETRIEVE([RETRIEVE])
    RETRIEVE --> ADM([ADMISSIBILITY])
    ADM --> SELECT([SELECT])
    SELECT --> VERIFY{VERIFY}
    VERIFY -- "checker agrees" --> FUSE([FUSE])
    VERIFY -- "disagreement" --> REFUSE([REFUSE])
    FUSE --> GENERATE([GENERATE])
    GENERATE --> SCREEN{SCREEN}
    SCREEN -- "staffed" --> REC([recommendation])
    SCREEN -- "no cover" --> FALLBACK([prescribed fallback])

    style VERIFY fill:#0F62FE,color:#fff
    style CONF fill:#0F62FE,color:#fff
    style SCREEN fill:#0F62FE,color:#fff
    style SELECT fill:#1C3C3C,color:#fff
    style FUSE fill:#1C3C3C,color:#fff
    style GENERATE fill:#1C3C3C,color:#fff
```

**The model is consulted at exactly three nodes** — SELECT, FUSE, GENERATE (dark
green) — and routes nothing. Every branch (blue) is a deterministic predicate.

Two properties are worth pausing on:

- **ADMISSIBILITY runs before SELECT, and does not filter.** The checker
  evaluates every retrieved candidate *before the model speaks*, and records its
  verdict — but it does not remove the near-misses. Filtering would delete the
  discrimination problem entirely, since a near-miss is inadmissible by
  construction and the whole point is that the model must reject it from prose.
- **CONFIDENCE runs before the model is consulted at all.** When the input data
  is too thin to support a recommendation, nothing is asked of the model. The
  data gap *is* the finding.

### Propose / dispose

```mermaid
sequenceDiagram
    participant R as Retrieval
    participant C as Deterministic checker
    participant M as Granite
    participant V as VERIFY
    participant H as Human

    R->>C: all candidates (near-misses included)
    C->>C: evaluate compiled preconditions
    Note over C: verdict recorded before the model speaks
    R->>M: passage prose only<br/>(preconditions redacted — S4)
    M->>V: "P-FAT-4.4 governs"
    C->>V: "P-FAT-4.4 admissible"
    alt model and checker agree
        V->>H: cited recommendation + clause-by-clause verdict
    else disagree, either direction
        V->>H: refusal naming the unmet clause
    end
    Note over H: the human decides. HAVEN never acts.
```

Both disagreement directions fail closed, and a passage the model did *not*
select is never promoted. A `governing_passage_id` outside the candidate set is
rejected structurally rather than trusted, because a real model can hallucinate
an identifier.

---

## Retrieval and the RAG pipeline

```mermaid
flowchart LR
    Q["Situation<br/>task · criticality · alertness"] --> BM25["BM25<br/>rank_bm25"]
    Q --> DENSE["Chroma + fastembed<br/>ONNX, opt-in"]
    BM25 --> RRF["Reciprocal Rank Fusion<br/>k = 60"]
    DENSE --> RRF
    RRF --> TOPK["top-k candidates<br/>near-misses included on purpose"]
    TOPK --> ADM["ADMISSIBILITY"]

    style RRF fill:#6E4AFF,color:#fff
```

**BM25 alone is the offline terminal** — no download, no service, no network.
Dense retrieval adds Chroma with fastembed ONNX embeddings (~50 MB, deliberately
not sentence-transformers/PyTorch at ~2 GB) and is opt-in via
`HAVEN_RETRIEVAL_MODE=hybrid`, because it fetches its model on first use and
therefore cannot be part of the offline guarantee.

RRF is implemented directly rather than via LangChain's `EnsembleRetriever`,
which returns fused documents without exposing the fused score — and the console
renders that number.

### The procedure corpus, and where it comes from

```mermaid
flowchart LR
    PDF["6 NASA documents<br/>version-verified · SHA-256 pinned"] --> EXTRACT["extract<br/>pypdf / pdfplumber"]
    EXTRACT --> CHUNK["requirement-aware chunking<br/>rule ≠ its rationale block"]
    CHUNK --> PROPOSE["propose<br/>model drafts preconditions"]
    PROPOSE --> GATE{"human review gate"}
    GATE -- "approved" --> EMIT["compiled corpus<br/>+ manifest digest"]
    GATE -- "unapproved" --> REFUSE["build fails"]

    style GATE fill:#0F62FE,color:#fff
    style REFUSE fill:#c62828,color:#fff
```

Six documents are acquired and compiled to **131 passages**: NASA-STD-3001
Volumes 1 and 2, the Human Integration Design Handbook, and three NTRS papers —
each version-verified against its publisher *before* download, pinned by SHA-256,
and labelled `authoritative`, `guidance` or `research`.

**Only an authoritative requirement may ground an action.** NASA-STD-3001 says
*shall*; the HIDH explains why; a paper reports what was measured. Retrieval
cannot tell them apart, and a BM25 probe over the real documents showed why that
matters: ask about the circadian trough and **all five top hits are research
papers**. Without the authority gate, the query HAVEN's own circadian clause
exists to serve would ground its recommendation in a research paper every time,
with a citation an operator could look up and find.

See [`corpus/README.md`](corpus/README.md) for the full provenance record and
[`corpus/EXTRACTION.md`](corpus/EXTRACTION.md) for what each document yielded.

---

## The eight scenarios

The console renders one Situation across six zones. Eight scenarios drive the
same engine over different inputs — nothing is bypassed or replayed.

| Scenario | What it demonstrates |
|---|---|
| **burn_fatigue** | The core case. Chronic sleep restriction before a reboost burn → cited second-operator verification, staffed. |
| **eva_near_miss** | **Discrimination.** A near-miss retrieves at 0.708 against the governing rule's 0.715 — near-tied on similarity — and is rejected on its preconditions. |
| **no_procedure** | **Refusal.** Nothing governs fatigue during a medical contingency. The system escalates rather than reaching for the nearest plausible rule. |
| **roster_block** | A deterministic screen vetoing a well-formed AI recommendation, then regenerating the text for the fallback the same passage prescribes. |
| **circadian_trap** | An 03:20 capture that passes a sleep-totals check and fails on circadian phase and sleep inertia. |
| **thin_data** | The confidence gate withholding *before* the reasoning tier is invoked. The data gap is the finding. |
| **nominal_ops** | Correct silence. A rested crew raises nothing; the audit bar distinguishes quiet from broken. |
| **provider_outage** | Degraded mode. The provider is unreachable, so the system says so and escalates instead of guessing from the deterministic tier alone. |

[`DEMO.md`](DEMO.md) walks six of them in the order that makes the argument.

---

## The safety model, as tests

Ten hard rules, each with a named enforcement point and a test that **fails when
the protection is removed** — every one verified by deliberately breaking it.

| # | Requirement | Enforced at |
|:--:|---|---|
| **S1** | Numbers are computed, never generated | `assert_no_novel_numbers`, on every completion |
| **S2** | Exactly one of recommendation or refusal — no third, self-actioning state | Graph topology |
| **S3** | No citation, no recommendation — every citation resolves | VERIFY + contract |
| **S4** | The reasoning tier never receives compiled preconditions | `_payload_redacted`, asserted on the rendered prompt |
| **S5** | No citation without independent checker confirmation | VERIFY |
| **S6** | Disagreement fails closed, in both directions | VERIFY |
| **S7** | No entry forgeable without the key; none deletable undetectably | HMAC-SHA256, globally chained ledger |
| **S8** | Every outcome records the corpus manifest it was made under | Ledger + `TierStatus` |
| **S9** | The graph is static — no LLM routes, no tool nodes, no unbounded cycles | Committed topology snapshot |
| **S10** | Only a requirements document may ground an action | `preconditions.check` + compiler review gate |

The **offline guarantee** is executable too: `tests/test_offline_guard.py` imports
the API tier in a subprocess with tracing forced *on* and every socket connection
trapped, and asserts nothing reaches the network.

```bash
uv run pytest tests/test_safety_invariants.py tests/test_offline_guard.py
# 148 passed
```

---

## Technology stack

```mermaid
flowchart TB
    subgraph FE["Frontend"]
        N["Next.js 14.2 · static export"]
        RE["React 18 · TypeScript 5"]
        TW["Tailwind CSS · Recharts"]
    end
    subgraph BE["Backend"]
        F["FastAPI · Pydantic v2"]
        U["uvicorn"]
        P["Python 3.12+ · uv · Ruff"]
    end
    subgraph AI["AI / orchestration"]
        LG["LangGraph 1.x"]
        LC["langchain-core 1.x"]
        IBM["langchain-ibm → watsonx.ai"]
        OL["langchain-ollama → local Granite"]
    end
    subgraph DATA["Retrieval + storage"]
        BM["rank_bm25"]
        CH["ChromaDB + fastembed"]
        SQ["SQLite · HMAC-chained ledger"]
    end

    FE -->|"REST / OpenAPI"| BE
    BE --> AI
    BE --> DATA
```

| Layer | Choice | Why |
|---|---|---|
| **Reasoning** | IBM Granite via **watsonx.ai** (`langchain-ibm`) | IBM's own LangChain package — the integration stays explicit rather than hidden behind a generic gateway |
| **Orchestration** | **LangGraph**, compiled static graph | Topology becomes declarative, inspectable and testable as data |
| **RAG** | LangChain `Document` interchange, BM25 + Chroma, RRF | BM25 keeps the offline path real; dense is additive |
| **API** | **FastAPI** + Pydantic v2 | The contract is the schema; console types are generated from it |
| **Console** | **Next.js 14** static export, **React 18** | Fully client-side, so one FastAPI process serves it from the same origin |
| **Ledger** | SQLite, HMAC-SHA256, globally chained | Tamper-*evident* across trails, not merely per-trail |
| **Tooling** | uv · Ruff · pytest · GitHub Actions | One lockfile, one lint config, three CI jobs |

---

## Repository layout

One repository, no `backend/` and `frontend/` split. The Python package carries
the tier boundaries in its own directory names, so the architecture is legible
from the file tree.

```text
pyproject.toml            dependencies, Ruff, pytest — one file
openapi.json              the exported contract; console types are generated from it
LICENSE                   Apache 2.0
haven/
  offline.py              the offline guarantee, enforced at import time
  config.py               every safety threshold, in one reviewable place
  contracts.py            the locked JSON contract (Pydantic)
  engine.py               binds the adapters and invokes the graph
  api/main.py             FastAPI routes + static console mount
  graph/                  the cycle as a compiled state machine
    evaluation_graph.py   INGEST → SCORE → TRIGGER → SITUATIONS → PRESENT
    situation_graph.py    CONFIDENCE → RETRIEVE → ADMISSIBILITY → SELECT → VERIFY → …
    nodes/                one module per node
  deterministic/          owns every safety number, and admissibility
    three_process_model.py  Åkerstedt & Folkard, published parameters
    nasa_tlx.py             Hart & Staveland weighted formula
    triggers.py             raise a Situation, or archive
    screens.py              confidence gate + schedule impact
    preconditions.py        the checker that disposes of the model's proposal
    projection.py           what the recommended action is predicted to buy
  rag/                    retrieves candidates; decides nothing
    corpus.py               passages, near-misses, one deliberate gap, manifest
    backends.py             BM25 · Chroma + fastembed
    fusion.py               reciprocal rank fusion
    retriever.py            LangChain-shaped retriever interface
  reasoning/              reads, proposes, explains, or refuses
    llm.py                  mock | Ollama | watsonx adapters + numeric guard
    chain.py                provider chain + circuit breaker
    orchestrator.py         what each reasoning step does
    parsing.py              the structured-output ladder
    audit.py                the signed, globally-chained, persistent ledger
  data/                   representative roster, synthetic timelines, scenarios
compiler/                 source PDFs → reviewed passages. Never on the request path
corpus/                   source registry, provenance, extraction report
evaluation/               golden set + measurement harness
web/src/                  the six-zone operator console
tests/                    including the safety invariants
scripts/                  run_haven · smoke · check_providers · fetch_corpus · calibrate
```

---

## Configuration

Every value has a working default; the prototype runs with none of them set.
Copy `.env.example` to `.env` — it is read at startup before any setting
resolves, and an exported shell variable still wins over the file.

| Variable | Default | Purpose |
|---|---|---|
| `HAVEN_LLM_CHAIN` | *(unset)* | Provider chain, e.g. `watsonx,mock`. **This is what switches the tier on.** |
| `HAVEN_LLM_MODEL` | `ibm/granite-3-8b-instruct` | Model id — paste the one your project lists |
| `WATSONX_URL` / `WATSONX_API_KEY` / `WATSONX_PROJECT_ID` | — | watsonx.ai credentials |
| `HAVEN_RETRIEVAL_MODE` | `lexical` | `lexical` (BM25, offline) or `hybrid` (adds Chroma) |
| `HAVEN_CORPUS` | *(unset)* | Path to a compiled corpus artefact |
| `HAVEN_LEDGER_DB` / `HAVEN_AUDIT_KEY` | auto | Ledger location and signing key |

---

## Testing and CI

```bash
uv run pytest                      # 737 tests
uv run pytest -m integration       # requires a local Ollama
uv run pytest -m live              # requires watsonx credentials
```

Provider- and service-backed tests are excluded by default, so a clean checkout
runs green with no Ollama and no watsonx credentials.

Three CI jobs, each proving something the others cannot:

| Job | Proves |
|---|---|
| **Engine** | Base install, no extras — the offline path is real. Lint, format, full suite, offline guard, corpus provenance, scenario calibration, evaluation gate |
| **Full** | Every extra installed — nothing was lost to the offline constraint |
| **Contract** | Generated TypeScript has not drifted from `openapi.json`; the console builds |

The evaluation harness runs in CI and **fails the build on a single unsafe
citation**.

---

## Honest limits

Named explicitly, because the system's whole thesis is that flagging uncertainty
beats asserting false confidence.

**Real, executing live on every evaluation:** the Three-Process Model and
NASA-TLX with their published parameters; retrieval; model-proposed and
checker-verified rule selection; the refusal path; both deterministic screens;
forward projection; and a persistent HMAC-signed, globally-chained ledger. The
watsonx integration is measured, not asserted — see the results above.

**Simulated, and labelled in the UI:**

- **The crew roster is representative, not real individuals.** Attaching modelled
  fatigue states to identifiable astronauts would be the wrong default even in a
  demo. Substituting a public roster is a data change in `haven/data/crew.py`.
- **Sleep, duty and task timelines are synthetic.** No public live crew-timeline
  feed exists. The structure follows NASA scheduling literature; values are
  generated from explicit per-night parameters, so every scenario is reproducible.
- **The corpus reasoned over at runtime is still the hand-authored one.** The 131
  compiled NASA passages await human review, and the emit gate refuses without a
  named reviewer — which is it working. The hand-authored passages follow NASA
  flight-rule numbering and precondition style; the prose is not verbatim NASA
  procedure, and every passage carries its provenance *and* its authority.

**Design standards are not execution rules — and now there is evidence.** This
was recorded as a risk before any document was read. NASA-STD-3001 Volume 2
carries 1,579 requirements; fifty-one mention sleep, fatigue or workload; **not
one** says what to do when an operator is below threshold thirty minutes before a
burn. The standards require that a *system* provide sleep accommodation, that a
*programme* establish work-hour limits, that a *schedule* include fatigue
management. The execution-time gating layer remains synthesised and is labelled
as such everywhere it surfaces.

**The audit ledger is tamper-evident, not tamper-proof.** Entries are signed with
HMAC-SHA256 and chained globally across every trail, so an entry cannot be
rewritten and a whole trail cannot be deleted without the key — either leaves a
break the ledger reports, with the sequence number where it happened. What that
does *not* stop is an attacker holding the signing key **and** write access.
Closing that needs storage the attacker cannot reach — WORM media, or an external
notary — which this build does not have. A test asserts this limit explicitly
rather than leaving it implied.

**Not verified here:** the Docker image is unbuilt (Docker was not installed in
the build environment) and the Ollama adapter has no live run (no local Granite
on this machine) — it is covered by unit tests and the provider chain only.

**Deferred:** the closed verification loop — confirming after the fact that
alertness and coverage actually improved — needs a time-simulation layer beyond
this build. Named rather than half-built.

---

## Documentation

| Document | Contents |
|---|---|
| [`DEMO.md`](DEMO.md) | Six-scenario walkthrough, ~8 minutes, ordered so each answers the doubt the last raises |
| [`corpus/README.md`](corpus/README.md) | The NASA source documents, version verification, and the authority model |
| [`corpus/EXTRACTION.md`](corpus/EXTRACTION.md) | What the compiler read from each document, and what retrieval finds in it |
| [`CHANGELOG.md`](CHANGELOG.md) | Every phase, what it decided, and what was deliberately *not* done |

---

## License

Licensed under the **Apache License, Version 2.0** — see [`LICENSE`](LICENSE).

NASA source documents referenced by the corpus are US Government works cleared
for public release; they are not redistributed in this repository. See
[`corpus/README.md`](corpus/README.md).

---

<div align="center">

*The deterministic tier owns all safety numbers. The AI reasoning tier reads, proposes, explains, or refuses.*
*A deterministic checker disposes. **The human owns every decision.***

</div>
