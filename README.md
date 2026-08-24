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

## Why HAVEN?

A fatigued crew member on a long-duration mission is not an edge case. NASA's own
Human Research Program maintains a standing evidence report on *sleep loss,
circadian desynchronization and work overload* as a risk to crew performance, and
NASA-STD-3001 Volume 1 requires that crew schedule planning include circadian
entrainment, work/rest assessment and fatigue management.

Detecting that an operator is impaired is the easy half. Sleep debt, circadian
phase and workload are well-studied and computable. The hard half is the question
that follows immediately:

> **What do the procedures require us to do about it — right now, for this task,
> for this crew member?**

That is what a language model looks perfectly suited to answer, and it is also
where a language model is genuinely dangerous. Three failure modes, all of them
confident:

| Failure | What it looks like |
|---|---|
| **It answers when nothing governs** | No procedure covers fatigue during a medical contingency, so the model reaches for the closest rule and presents it as the governing one. |
| **It cites the most *similar* rule, not the one that *applies*** | A pre-EVA sleep-shifting protocol shares almost every keyword with the EVA fatigue rule — and is scoped to *planning*, not execution. |
| **It states a number it computed** | Given alertness 0.65 and a threshold of 0.70, it writes "a shortfall of 0.05" — a figure no instrument measured and no model produced. |

Each is wrong in exactly the register a tired operator is least able to
challenge: fluent, cited, specific. HAVEN is built so that none of them can reach
the crew — not by asking the model to be more careful, but by making it
structurally unable to be the last word.

> ### The architectural invariant
> The maths owns the numbers. **The compiler owns the rules; the AI proposes; a deterministic checker disposes.** The human owns the decision.
>
> No code path lets the reasoning tier emit a safety-critical figure, cite a rule the checker rejected, or take an irreversible action.

---

## What makes HAVEN different?

Most retrieval-augmented systems are a pipeline: retrieve, prompt, return. The
model is the last component in the chain, so whatever it says *is* the answer.
HAVEN inverts that — the model's output is an **input** to a deterministic
component that can overrule it.

| | Typical RAG assistant | HAVEN |
|---|---|---|
| **Who decides which rule applies** | The model. Retrieval ranks, the model picks, the pick ships. | The model **proposes**; a deterministic checker evaluates the rule's compiled preconditions independently and can veto. |
| **Numbers in the answer** | Whatever the model writes. | Every numeral must trace to a value the deterministic tier computed. A violation is caught, repaired once, then **refused**. |
| **When nothing applies** | Returns the nearest match, confidently. | **Refusal is a first-class output** — it records what was searched, the closest candidate, and escalates. |
| **Near-misses in retrieval** | Filtered out to improve precision. | **Deliberately kept.** Filtering would delete the discrimination problem rather than solve it. |
| **Source authority** | All retrieved text is equally citable. | A standard says *shall*, a handbook says *should*, a paper reports a measurement. **Only a requirement may ground an action.** |
| **Orchestration** | An agent loop; variable-length tool trajectory. | A **compiled static state machine**. No LLM routes, no cycles, topology asserted against a committed snapshot. |
| **Audit** | Logs, if any. | Every step written to an **HMAC-signed, globally chained ledger**; every decision records the corpus digest it was made under. |
| **Provider failure** | An error, or a silent fallback. | Falls through a provider chain and **says so** — `degraded: true`, and the console names the link that answered. |

The measurable consequence is below: on the same twenty cases, Granite alone is
right 65% of the time and HAVEN is right 95% of the time. The difference is not a
better prompt. It is the checker.

---

## The core idea in one example

The `eva_near_miss` scenario, start to finish. Every number below is from the
running system.

**The situation.** A suited crew member is assigned an EVA. The deterministic
tier computes predicted alertness **0.65** against an execution threshold of
**0.70**, task criticality **high**. A Situation is raised.

**Retrieval returns four candidates.** Two matter:

| Passage | Document | Relevance | What it is |
|---|---|:--:|---|
| `P-SLP-2.1` | OPS-SLEEP-02 §2.1 | **0.9839** | Pre-extravehicular **sleep-shifting protocol** |
| `P-FAT-4.4` | OPS-FATIGUE-04 §4.4 | **0.9683** | Extravehicular activity with **degraded crew alertness** |

Note the order. **The wrong passage ranks first.** Both are EVA-scoped, both
discuss sleep and extravehicular activity, and the near-miss scores *higher* than
the rule that actually governs. A pipeline that trusted retrieval ranking would
cite `P-SLP-2.1`.

**The checker reads both, before the model speaks.** Their compiled preconditions
are not similar at all:

```text
P-SLP-2.1   applies_when: { task_types: [eva], phase: "planning" }
            prescribes:   null
            phase is "execution", not "planning"      FAIL
            states no action a fatigue decision can take
            -> INADMISSIBLE

P-FAT-4.4   applies_when: { task_types: [eva],
                            alertness_below: 0.70,
                            criticality_in: [high, medium] }
            prescribes:   short_rest_then_proceed
            eva = eva                                 OK
            0.65 is below 0.70                        OK
            high is in [high, medium]                 OK
            authority: may prescribe                  OK
            -> ADMISSIBLE
```

**The model never sees any of that.** It receives passage prose only —
`passage_id`, `doc`, `section`, `title`, `text`. No preconditions, no prescribed
action, no near-miss annotation. It has to read `P-SLP-2.1` and notice that its
own wording scopes it to planning days before egress. Live Granite proposes
**`P-FAT-4.4`**.

**VERIFY compares the two verdicts.** Model says `P-FAT-4.4`; checker says
`P-FAT-4.4` is admissible. They agree, so the recommendation stands — and it
carries the checker's clause-by-clause verdict with it, so an operator can audit
the citation rather than trust it.

**What live Granite actually wrote:**

> *Alertness is below the extravehicular execution threshold. The task is high
> criticality. Therefore, extravehicular activity shall not commence.*

No arithmetic, no invented figure. An earlier run of this exact scenario produced
*"the shortfall of 0.05"* — Granite had computed `0.70 − 0.65` — and the numeric
guard **refused the entire recommendation** rather than publish it.

**Had the model proposed `P-SLP-2.1` instead**, the checker would have rejected it
on the `phase` clause and HAVEN would have returned a refusal naming that clause.
The wrong answer is unreachable from either direction.

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

Five tiers with hard boundaries. **Blue** is deterministic, **dark green** is the
reasoning tier, **amber** is the offline corpus compiler, **grey** is durable
storage. The two edges that matter most both leave retrieval: the checker
receives the **compiled preconditions**, the model receives the **prose only**.

```mermaid
flowchart TD
    %% ================= lane 1: crew state, deterministic =================
    REQ["Scenario or API request<br/>POST /api/evaluate"]
    ROSTER[("Crew roster<br/>sleep log · duty log · tasks")]
    REQ --> INGEST["INGEST<br/>contract validation · UTC normalise"]
    ROSTER --> INGEST

    INGEST --> TPM["Three-Process Model<br/>homeostatic · circadian · inertia"]
    INGEST --> TLX["NASA-TLX<br/>weighted workload"]
    TPM --> READY["SCORE<br/>readiness + risk band"]
    TLX --> READY
    READY --> TRIGGER["TRIGGER<br/>alertness and workload thresholds"]

    TRIGGER -->|nominal| ARCHIVE["Archived<br/>no Situation raised"]
    TRIGGER -->|Situation raised| CONF["CONFIDENCE<br/>data coverage gate"]
    CONF -->|coverage too thin| WITHHOLD["WITHHOLD<br/>the data gap is the finding"]

    %% ================= lane 2: corpus compiler, offline =================
    PDFS["NASA source documents<br/>STD-3001 V1 + V2 · HIDH · 3 NTRS papers"]
    PDFS --> EXTRACT["Extract<br/>pypdf · pdfplumber"]
    EXTRACT --> CHUNK["Requirement-aware chunking<br/>rule kept apart from its rationale"]
    CHUNK --> PROPOSE["Propose preconditions<br/>Granite · offline · never at request time"]
    PROPOSE --> GATE["Human review gate<br/>refuses anything unapproved"]
    GATE -->|approved| CORPUS[("Procedure corpus<br/>passages + manifest digest")]

    %% ================= lane 3: retrieval =================
    CONF -->|sufficient| RETRIEVE["RETRIEVE"]
    CORPUS --> BM25["BM25 lexical<br/>rank_bm25 · offline terminal"]
    CORPUS --> DENSE["Chroma + fastembed<br/>ONNX · opt-in"]
    RETRIEVE --> BM25
    RETRIEVE --> DENSE
    BM25 --> RRF["Reciprocal Rank Fusion<br/>k = 60"]
    DENSE --> RRF
    RRF --> CAND["Top-k candidates<br/>near-misses included on purpose"]

    %% ================= lane 4: propose / dispose =================
    CAND --> ADM["ADMISSIBILITY<br/>checker reads every candidate"]
    CAND -->|"prose only · preconditions redacted"| SELECT["SELECT<br/>model proposes a governing rule"]

    CHAIN["Provider chain<br/>watsonx → ollama → mock"] --> SELECT
    WX["IBM watsonx.ai<br/>granite-4-h-small"] --> CHAIN
    OLL["Ollama · local Granite"] --> CHAIN
    MOCK["Offline stand-in<br/>terminal link, never fails open"] --> CHAIN

    ADM --> VERIFY["VERIFY<br/>model proposal vs checker verdict"]
    SELECT --> VERIFY

    VERIFY -->|"disagree, either direction"| REFUSE["REFUSE<br/>names the unmet clause"]
    VERIFY -->|agree| FUSE["FUSE<br/>justification"]
    FUSE --> GEN["GENERATE<br/>operator-facing text"]
    GEN --> NUM["Numeric guard<br/>every figure traces to a computed value"]
    NUM -->|invented figure| REFUSE
    NUM -->|clean| SCREEN["SCREEN<br/>roster + schedule impact"]

    SCREEN -->|cover available| REC["Recommendation<br/>cited · clause-by-clause verdict"]
    SCREEN -->|no cover| FALLBACK["Prescribed fallback<br/>from the same cited passage"]
    SCREEN --> PROJ["Forward projection<br/>what the action is predicted to buy"]

    %% ================= lane 5: presentation + audit =================
    REC --> PRESENT["PRESENT"]
    FALLBACK --> PRESENT
    REFUSE --> PRESENT
    WITHHOLD --> PRESENT
    ARCHIVE --> PRESENT
    PROJ --> PRESENT

    PRESENT --> API["FastAPI gateway<br/>REST · OpenAPI contract · static console mount"]
    API --> UI["Operator console<br/>Next.js 14 · React 18 · six zones"]
    UI --> HUMAN["Human decision<br/>approve · override · escalate"]

    LEDGER[("Audit ledger<br/>HMAC-SHA256 · globally chained · SQLite")]
    INGEST -.->|every step| LEDGER
    ADM -.-> LEDGER
    VERIFY -.-> LEDGER
    NUM -.-> LEDGER
    HUMAN -.-> LEDGER

    %% ================= styling =================
    classDef det fill:#0F62FE,stroke:#0043ce,color:#ffffff
    classDef ai fill:#1C3C3C,stroke:#0f2424,color:#ffffff
    classDef store fill:#e0e0e0,stroke:#8d8d8d,color:#161616
    classDef offline fill:#fff8e1,stroke:#f1c21b,color:#161616
    classDef out fill:#d0e8ff,stroke:#0F62FE,color:#161616

    class TPM,TLX,READY,TRIGGER,CONF,ADM,VERIFY,NUM,SCREEN,GATE det
    class SELECT,FUSE,GEN,CHAIN,WX,OLL,MOCK ai
    class CORPUS,LEDGER,ROSTER store
    class PDFS,EXTRACT,CHUNK,PROPOSE offline
    class REC,FALLBACK,REFUSE,WITHHOLD,ARCHIVE,HUMAN out
```

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
property *is* the fixed, auditable step sequence — a model-chosen,
variable-length tool trajectory would be strictly worse to audit. Every edge is
either static or conditional on a deterministic predicate, and the topology is
asserted against a committed snapshot in CI.

**The outer graph** runs once per evaluation:

```text
INGEST → SCORE → TRIGGER → SITUATIONS → PRESENT
```

`TRIGGER` decides whether a Situation is raised at all. A rested crew produces
none, and the console distinguishes that silence from a failure.

**The situation subgraph** runs once per raised Situation:

```text
CONFIDENCE ──┬── withhold ─────────────────────────────────────────────→ END
             │
             └── RETRIEVE → ADMISSIBILITY → SELECT → VERIFY ──┬── FUSE → GENERATE ──┐
                                                              │                      │
                                                              └── REFUSE ────────────┤
                                                                                     │
                                                                     SCREEN ←────────┘
                                                                        ↓
                                                                       END
```

The model is consulted at exactly **three** nodes — `SELECT`, `FUSE`, `GENERATE`
— and routes nothing. Two properties are worth pausing on:

- **ADMISSIBILITY runs before SELECT, and does not filter.** The checker
  evaluates every retrieved candidate *before the model speaks*, and records its
  verdict — but it does not remove the near-misses. Filtering would delete the
  discrimination problem entirely, since a near-miss is inadmissible by
  construction and the whole point is that the model must reject it from prose.
- **CONFIDENCE runs before the model is consulted at all.** When the input data
  is too thin to support a recommendation, nothing is asked of the model. The
  data gap *is* the finding.

### Propose / dispose

`VERIFY` is deterministic and its disposition table is exhaustive:

| Model proposed | Checker says | Result |
|---|---|---|
| passage *P* | *P* is admissible | **Proceed** — recommendation, with the clause verdict attached |
| passage *P* | *P* is inadmissible | **Refuse**, naming the unmet clause |
| none govern | something is admissible | **Refuse**, logging the disagreement |
| none govern | nothing is admissible | **Refuse** — no governing procedure |

Both disagreement directions fail closed, and a passage the model did *not*
select is never promoted. A `governing_passage_id` outside the candidate set is
rejected structurally rather than trusted, because a real model can hallucinate
an identifier.

---

## Retrieval and the RAG pipeline

Two backends, fused by reciprocal rank:

- **BM25** (`rank_bm25`) is lexical and is the **offline terminal** — no
  download, no service, no network. It is a base dependency rather than an extra,
  because the offline guarantee depends on it.
- **Dense** retrieval adds ChromaDB with fastembed ONNX embeddings (~50 MB,
  deliberately not sentence-transformers/PyTorch at ~2 GB). It is opt-in via
  `HAVEN_RETRIEVAL_MODE=hybrid`, because it fetches its model on first use and
  therefore cannot be part of the offline guarantee. When it is unavailable the
  tier degrades to BM25 and records why.
- **Reciprocal Rank Fusion** (k = 60) combines them. It is implemented directly
  rather than via LangChain's `EnsembleRetriever`, which returns fused documents
  without exposing the fused score — and the console renders that number.

The index sees **title and text only**. The compiled preconditions never enter
it, which is safety requirement S4 arrived at from a second direction.

In `eva_near_miss` the near-miss passage retrieves at **0.984 against the
governing rule's 0.968** — retrieval ranks the wrong passage *first*, and the
system cites the right one anyway. That is the case the architecture exists for,
and it is why ADMISSIBILITY does not filter: a pipeline that dropped the
near-miss would have deleted the problem instead of solving it.

### The procedure corpus, and where it comes from

The corpus compiler turns source PDFs into passages carrying machine-checkable
preconditions, under human review. It runs **offline and never at request time** —
a test asserts that nothing under `haven/` imports it.

```text
NASA PDFs → extract → requirement-aware chunk → propose → HUMAN REVIEW → emit
                                                               │
                                                               └─ unapproved → build fails
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
| **eva_near_miss** | **Discrimination.** The near-miss P-SLP-2.1 retrieves at 0.984, *above* the governing rule's 0.968 — retrieval ranks it first and the system still cites P-FAT-4.4. |
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

| Layer | Technology | Used for |
|---|---|---|
| **Frontend** | Next.js 14.2 *(static export)* | The six-zone operator console, exported as static files so one process serves everything |
| | React 18 · TypeScript 5 | Component model and type safety across the console |
| | Tailwind CSS 3.4 | Styling, via the shared `ui.tsx` primitives |
| | Recharts 3 | Alertness curves and the forward-projection overlay |
| | lucide-react · clsx | Icons; conditional class composition |
| | openapi-typescript 7 | Generates `api-types.ts` from `openapi.json` — CI fails on drift |
| **Backend** | Python 3.12+ | Runtime floor; CI runs the floor, not the newest interpreter |
| | FastAPI 0.115+ | REST API, OpenAPI schema, and the static console mount |
| | Pydantic v2 | The locked contract — validation, range constraints, UTC normalisation |
| | uvicorn *(standard)* | ASGI server |
| | python-dotenv | Loads `.env` before any setting resolves |
| **AI / orchestration** | LangGraph 1.x | The seven-stage cycle as a **compiled static state machine** |
| | langchain-core 1.x | `Document` interchange, message types, prompt templates |
| | langchain-ibm | **IBM watsonx.ai** Granite — IBM's own package, so the integration stays explicit |
| | langchain-ollama | Local Granite, for free unmetered iteration |
| | *scripted stand-in* | Offline terminal of the provider chain; the default, so a demo cannot fail on a network call |
| **Retrieval** | rank_bm25 | Lexical retrieval; the **offline terminal**, and a base dependency |
| | ChromaDB 0.5+ | Persistent vector store for dense retrieval |
| | fastembed | ONNX embeddings (~50 MB) rather than PyTorch (~2 GB) |
| | langchain-chroma | Chroma integration |
| | *hand-written RRF* | Reciprocal rank fusion, k = 60 — written rather than imported so the fused score is exposed |
| **Corpus compiler** | pypdf · pdfplumber | Page text and layout from source PDFs; called directly rather than via the sunset `langchain-community` |
| | langchain-text-splitters | Prose splitting between numbered requirements |
| **Data + storage** | SQLite *(WAL, INSERT-only)* | The audit ledger |
| | HMAC-SHA256 | Ledger entry signing, chained **globally** across trails |
| | NumPy 2 | Vectorised alertness-curve sampling |
| | JSON artefacts | Compiled corpus + manifest digest; source registry with pinned SHA-256 |
| **Testing** | pytest 8 | 737 tests, with `integration` and `live` markers excluded by default |
| | Hypothesis | Property tests — the checker must be total over arbitrary input shapes |
| | *evaluation harness* | 20-case golden set; **fails the build on one unsafe citation** |
| **DevOps** | GitHub Actions | Three jobs: engine (base install), full (all extras), contract (type drift) |
| | uv | Dependency resolution and locking — one `uv.lock` |
| | Ruff | Lint and format, one configuration |
| | Docker | Two-stage build; Node builds the console, Python serves it. Port 7860 for HF Spaces |

**Deliberately not adopted:** the `langchain` meta-package; `langchain-community`
(being sunset); LangSmith tracing (it would breach the offline guarantee, and a
test asserts it stays off); LangGraph's checkpointer as system of record (it
provides neither HMAC nor global chaining); LiteLLM (it would hide the watsonx
integration behind a generic gateway).

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
