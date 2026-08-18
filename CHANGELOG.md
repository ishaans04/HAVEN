# Changelog

Every phase of the HAVEN v2 build, recorded as it lands. This file is the
continuity anchor: read it before starting a phase, and append to it when one
closes. It records not just what changed but **why**, and what was deliberately
*not* done, so a later phase cannot quietly contradict an earlier decision.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

---

## Governing documents

Three documents govern this build. Where they disagree, the order below wins.

1. **The approved v2 implementation plan** — the authority. Phases 0–8,
   M1 = 0–3, M2 = 4–8. Adds LangGraph (the fixed seven-stage cycle as a
   *static compiled state machine*) and LangChain (the NASA-document RAG
   pipeline) throughout, per explicit instruction.
2. **HAVEN v2 — Architecture Design** — the spec the plan implements. Names the
   five gaps, the propose/dispose invariant, and safety requirements S1–S8.
3. **The task-level plan under `docs/superpowers/`** — a much longer, task-by-task
   elaboration. Useful for detail, but **it predates the LangChain/LangGraph
   instruction and contains no graph layer.** Where it conflicts with (1), (1)
   wins. It is gitignored as local tooling output.

### Reconciliation between (1) and (3)

| Phase | Approved plan (1) | Task-level plan (3) |
|---|---|---|
| 1A | LangGraph StateGraph migration | *absent* — added by (1) |
| 1B | Propose / dispose | its Phase 1 |
| 2 | Ledger | its Phase 2 |
| 3 | Real providers + eval harness | its Phase 3 |
| 4 | Compiler, on **LangChain loaders** | its Phase 4, without LangChain |
| 5 | Hybrid retrieval, on **LangChain retrievers** | its Phase 5, hand-rolled |
| 6 | Perf + forward projection | its Phase 6 (SSE + projection) |
| 7 | Console | its Phase 7 |
| 8 | Ship | its Phase 8 |

### The invariant, in its v2 form

> The maths owns the numbers. **The compiler owns the rules; the AI proposes; a
> deterministic checker disposes.** The human owns the decision.

### Safety requirements

S1–S3 are inherited from v1 and already executable. S4–S9 arrive with the phases
that enforce them.

| # | Requirement | Status |
|---|---|---|
| S1 | Numbers are computed, never generated | v1, green |
| S2 | Exactly one of recommendation / refusal | v1, green |
| S3 | No citation, no recommendation | v1, green |
| S4 | The reasoning tier never receives compiled preconditions | Phase 1B, green |
| S5 | No citation without independent checker confirmation | Phase 1B, green |
| S6 | Model/checker disagreement fails closed, both directions | Phase 1B, green |
| S7 | No entry forgeable without the key; no silent deletion | Phase 2, green |
| S8 | Every outcome records its corpus manifest | Phase 2, green |
| S9 | The graph is static: no LLM routes, no tool nodes, no cycles | Phase 1A, green |

---

## Open decisions carried forward

Recorded here so a later phase cannot resolve them by accident.

### O1 — ~~An empty `applies_when` is vacuously admissible~~ *(resolved, Phase 4.2)*

`preconditions.check` treats a passage declaring no preconditions as applying
always. For the hand-authored corpus that is defensible and deliberate: an empty
clause set is the author's explicit "this always applies", and all 11 current
passages declare clauses, so nothing is affected today.

It becomes dangerous the moment **Phase 4's compiler** authors preconditions from
real PDFs, because then an empty `applies_when` means "the extraction produced
nothing and a human approved it without noticing" — and the passage would be
admissible for *every* Situation. Fail-open, in a system whose thesis is
fail-closed.

**Decision:** do not change the checker. Its semantic is clean, tested, and
correct for authored input. Put the guard where the risk actually is —
**the Phase 4 review tool must refuse to emit an `extracted` passage with an
empty `applies_when`.** This is a Phase 4 acceptance criterion, not a
suggestion.

**Resolved as specified.** `compiler.review.gate` refuses, the checker is
untouched, and a hand-authored passage may still declare none.

### O4 — `P-FAT-4.4` is an execution gate that declares no phase *(decide in Phase 4)*

Surfaced by the evaluation harness, which is exactly what it is for.

`P-FAT-4.4` reads as an execution-time gate — *"Extravehicular activity shall
not commence where the predicted alertness…"* — and `P-SLP-2.1` contrasts itself
against *"alertness shortfall detected during execution"*, which only makes
sense if 4.4 is the execution rule. But 4.4's `applies_when` declares no `phase`
clause, so the checker finds it admissible during planning too. The same is true
of 4.2 and 6.3.

Unreachable today: the engine hardcodes `phase="execution"`, so nothing ever
evaluates at planning. It stops being unreachable the moment anything evaluates
a plan.

**Not fixed here.** Adding `phase: execution` to those three passages is a
change to safety-relevant data on my reading of the prose, and the corpus is
about to be replaced wholesale by Phase 4's compiler — which has to decide how
phase scope is extracted from real documents anyway. The golden set records the
gap explicitly rather than assuming it away, so it cannot be forgotten.

### O2 — Silent task drop on unknown `assigned_to` *(needs a decision)*

Raised in Phase 1A. A task whose `assigned_to` matches no crew member is dropped
before scoring and appears nowhere in the response. A mistyped crew id silently
hides a high-criticality task. Still unfixed, because fixing it changes
behaviour and needs a chosen shape: most likely a Situation with a new refusal
reason, since "the roster does not contain this operator" is exactly the kind of
gap this system exists to surface.

### O3 — ~~`best_candidate.relevance < relevance_gate` holds incidentally~~ *(resolved, Phase 5)*

Recorded in Phase 1B as holding only by coincidence of the retrieval scores,
with the instruction that a failure should be read as a display question rather
than a safety one. Phase 5 changed the display scale and it duly failed. The
assertion now checks what actually matters about a best candidate — that it
names a real passage a reviewer can go and read, and that the document appears
in the searched set. Its score decides nothing.

---

## [Unreleased]

### Phases 4–8 — M2

**Landed.** 651 tests passing, up from 559 at the end of M1. Closes gap 2, the
one the architecture design calls "the deepest architectural question in the
project".

#### Phase 4 — The compiler

- `compiler/` turns source PDFs into passages carrying machine-checkable
  preconditions, under human review, and never runs at request time. Two tests
  enforce that separation: an AST scan, and a subprocess that loads a compiled
  corpus with `compiler` imports poisoned.
- **Chunking follows the document's structure, not a character count.** A rule
  ending "This requirement does not apply during launch, entry, or declared
  contingency operations" split at 400 characters loses its exception to a
  different chunk — and the corpus then looks healthy while containing a rule
  that has been quietly widened. That failure has a test.
- `pypdf`/`pdfplumber` are called directly rather than through LangChain's
  loaders: **`langchain-community` is being sunset**, and depending on an
  unmaintained package for a thin wrapper buys nothing. Dropped from the `rag`
  extra. The maintained packages — `langchain-core`, `langchain-text-splitters`,
  `langchain-chroma` — carry the rest.
- The review gate refuses rather than filters, and names every offender at once.
  **O1 is enforced here.**
- `Passage` gained `provenance` and `reviewed_by`. Provenance is *in* the
  manifest digest: two corpora with identical rules, one claiming to be
  extracted from a standard and one admitting it was written for this prototype,
  are materially different rulebooks to anyone auditing a decision.
- Loading recomputes the manifest rather than trusting it, so an artefact edited
  after review is caught.

**A real fail-open, found by the end-to-end tests:** a proposal the model failed
to draft arrives with `governs_fatigue=False`, and the gate was skipping those as
"deliberately excluded" *before* checking whether anyone had reviewed them. Every
rule the extraction could not read would have been dropped silently. Approval is
now checked first, and the ordering says why.

#### Phase 5 — Hybrid retrieval

- BM25 (`rank_bm25`) fused with optional dense retrieval (Chroma + fastembed
  ONNX) by reciprocal rank. **BM25 alone is the offline terminal**; dense
  downloads its model, so the tier degrades and records why rather than refusing
  to start.
- RRF is written rather than imported: `EnsembleRetriever` returns fused
  documents without fused scores, and Zone 3 renders that number.
- **Retrieval recall over the golden set is total**, and must be — selection
  cannot recover from a miss. The near-miss test asserts the opposite direction:
  P-SLP-2.1 *must* be retrieved, or the model's rejection is a tautology.
- The index sees title and text only. S4 by another route.
- **O3 resolved**, exactly as predicted.

#### Phase 6 — Forward projection

- A recommendation now says what its cost buys. Deterministic tier, necessarily.
- **The projection found two modelling errors of mine.** A 90-minute rest ending
  at task start projected alertness *falling* (0.649 → 0.383) because sleep
  inertia peaks at waking; and a fixed 12-hour deferral of a noon task landed at
  midnight in the circadian trough (0.666 → 0.37). In both the model was right
  and my encoding of the procedure's intent was wrong. Rest now ends three hours
  before the task — a constant taken from the scoring node's existing precedent,
  not chosen, because a constant picked to make a recommendation project well is
  tuning evidence to fit a conclusion. Deferral is a forward sweep for the first
  window that actually works.
- **The performance work was deliberately not done, on measurement.** A full
  evaluation is 87.6 ms of which `curve()` is 1.6 ms; `Send` fan-out gains
  nothing when every scenario raises one Situation. Measuring and declining is
  better than optimising because a plan said so.

#### Phase 7 — The console

- Zone 3 renders propose/dispose: the model's proposal beside the checker's
  clause-by-clause verdict, satisfied clauses included, with disagreement shown
  as a first-class event.
- Zone 4 shows the projection next to the cost. "Predicted", never "achieved",
  with the basis rendered rather than hidden.
- The procedure browser finally calls `GET /api/procedures`, implemented in v1
  and never called. Shows provenance and labels the near-misses.
- A live check caught the API still using a single provider rather than the
  chain, so `provider_chain` arrived empty at the console.

#### Phase 8 — Ship

- Static export served by FastAPI from one origin; one process, one port. The
  mount is declared last (it sits at `/`) and only when the export exists.
- Dockerfile: Node build stage discarded, `--frozen` install, no extras,
  telemetry pinned off, non-root, health-checked, ledger on a volume.
- `DEMO.md` — six scenarios, ordered so each answers the doubt the last raises.
- CI asserts the export is produced.

#### Not claimed

- **No live-provider figures.** watsonx credentials were unavailable and the
  Ollama extra is not installed here, so every reported number is the offline
  stand-in's. The harness exists to produce the comparison the moment there is
  something to measure; running it is a command, not a build.
- **The image is unbuilt.** Docker is not installed in this environment. What is
  verified is everything it depends on: the export is produced, FastAPI serves
  it, and one port answers both `/` and `/api/health` against a running server.
- **The corpus is still hand-authored.** The compiler that replaces it is tested
  end to end against generated PDFs, not against NASA's — those are gitignored
  and must be fetched from their publishers.
- **O2 and O4 remain open**, deliberately. Both change behaviour and need a
  decision rather than a quiet fix.


### Phase 3 — Real providers, offline path intact

**Landed**, in five verified milestones. 559 tests passing, up from 411 at the
end of Phase 2. Closes gap 4. **M1 is complete.**

Gap 4 was that the watsonx and Ollama adapters were `# pragma: no cover` — never
executed, never tested — and `json.loads(completion)` would fail on the first
real model response. The reasoning tier was built around a model it had never
actually spoken to.

#### 3.1 — Measure before switching

- `evaluation/` — 20 labelled Situations and a runner. Refusal cases outnumber
  governing ones deliberately: selection accuracy is the easy metric, and a
  system that always takes the top-ranked candidate scores respectably on it.
- **Two accuracies, and the gap between them is the point.** Model accuracy is
  what the provider proposed; system accuracy is what HAVEN did after VERIFY
  disposed of it. That gap is the checker's value as a number rather than an
  argument. Against the mock: model 85.0%, system 90.0%, refusal recall 100%,
  unsafe citations 0.
- The harness found three things on its first run. Two are real weaknesses in
  the mock's prose reading — it refuses where the sustained-duty and science-ops
  rules govern — and both fail *closed*, which is the safe direction. The third
  was my own labelling error, recorded as **O4**.
- Tests hold the harness to the checker rather than to my opinion: every
  governing label must name a passage the checker admits, every refusal label
  must offer nothing admissible. A corpus change that alters what governs now
  breaks the labels instead of silently moving the score.

#### 3.2 — Survive what a real model returns

- A ladder: extract from fences and prose → validate against a Pydantic model →
  one repair with the specific fault handed back → **refuse**. No rung guesses.
- Extraction scans with a depth counter, not a regex. Greedy runs past the first
  object, non-greedy stops inside a nested one, and neither knows a brace inside
  a string is not structure.
- **Parsing judges shape only.** I first had it reject an out-of-candidate
  identifier; an existing test caught that the flow then recorded the proposal
  as *absent* rather than as *invented*, losing the evidence a reviewer needs.
  Membership belongs to VERIFY.
- The numeric guard gets one repair then a `numeric_integrity_failure` refusal.
  Previously it raised straight out of the flow — a 500 for what a real model
  does routinely. This is the thesis in its most direct form: the evidence is
  intact, the prose about it is not, so the recommendation is withheld.

#### 3.3 — Real providers on IBM's own LangChain packages

- `ChatWatsonx` and `ChatOllama` behind the existing interface. `langchain-ibm`
  specifically, because the challenge scores the watsonx integration and a
  generic gateway would hide it.
- Fixes the old adapter caching the IAM token forever, which would 401 partway
  through a long session.
- **LangChain owns the transport, not the ladder.** `with_structured_output`
  raises on a malformed response, and "raise" is not an outcome this system may
  have. Only SELECT is constrained to JSON; FUSE and GENERATE write prose.
- The packages stay an optional extra and clients build lazily, so the offline
  path installs neither.

#### 3.4 — A chain that falls back without lying

- `provider_chain` and `served_by` on `TierStatus`. Any answer from below the
  head marks the evaluation degraded and names why the earlier links failed.
- The audit trail records the provider that *answered*, not the one at the head.
- Circuit breaker after three consecutive failures, because otherwise a chain
  with a dead head pays its timeout once per Situation.
- The mock is appended if not configured: a chain that could run out of links
  would make an outage a crash rather than a state.

#### 3.5 — Gated and documented

- CI runs the harness and fails on any unsafe citation. Accuracy is reported;
  this is enforced.

#### Deliberately not done

- **No live provider numbers yet.** watsonx credentials are not available, and
  the Ollama extra is not installed in this environment, so the reported figures
  are the mock's. The harness exists precisely so those numbers can be produced
  and compared the moment there is something to measure — running it is a
  command, not a build.
- **The mock's two selection misses are not tuned away.** They are honest
  measurements of a stand-in, and both fail closed.


### Phase 2 — The ledger

**Landed**, in five verified milestones. 411 tests passing, up from 330 at the
end of Phase 1B. Closes gaps 3 and 5; delivers **S7** and **S8**.

Gap 5 was not in v1's honesty statement. It was found by inspection during
design review, and it is the more interesting of the two: v1's chain detected
*corruption* but not *tampering*. An unkeyed SHA-256 is a digest anyone can
recompute, so an attacker with write access could edit an entry, re-digest it,
re-chain everything after it, and leave a record that verified perfectly. The v1
test named itself after tamper-detection while proving only corruption-detection,
because it mutated a field and never recomputed anything.

#### 2.1 — Keyed, globally chained

- HMAC-SHA256 replaces the bare digest, compared with `compare_digest`. Key from
  `HAVEN_AUDIT_KEY`, or generated on first use into a gitignored `.audit_key` —
  generated, because the offline path must need no configuration.
- The signature covers every field that is a *claim about what happened*, plus
  position in trail and ledger, plus the link to the predecessor.
  **`duration_ms` is excluded**: wall-clock noise, not a claim, and signing it
  would make a faithful re-run fail against its own record — turning
  reproducibility into an integrity failure.
- **The chain is global, not per-trail.** Deleting a whole trail now leaves
  broken links and a sequence gap. Under v1 it was invisible: every trail
  restarted from GENESIS, so the survivors still verified.

#### 2.2 — Persistent

- SQLite, INSERT-only, WAL. No UPDATE and no DELETE anywhere in `AuditStore`, so
  the only way to alter a written record is to go around the application.
- The connection opens **lazily**, so importing `haven.api.main` no longer
  creates a database. But laziness alone was wrong and a test caught it: entries
  are built by `append` (which advances the chain) and only handed to `put`
  afterwards, so deferring adoption of the stored head to first database access
  made the first entry after a restart link to GENESIS — the ledger read as two
  unrelated histories. The head is now adopted eagerly when a file exists.
- Verified against a real server: evaluate, record a decision, stop the process,
  start it again, and `GET /api/audit/{ref}` returns all ten steps with
  `chain_valid` true.

#### 2.3 — Distinct identity, named rulebook

- `situation_id` derives from an evaluation id minted in INGEST, with a random
  suffix as well as the clock. Two evaluations of the same window inside one
  second are ordinary — a demo clicking between scenarios does it constantly.
- Deriving ids from a digest of the request was rejected despite being
  reproducible: re-running a scenario would reuse its `audit_ref` and append a
  second set of steps to the trail already on disk.
- **S8**: a corpus manifest digest on every Situation and on `TierStatus`.
  `near_miss_note` is excluded — commentary for the corpus's readers that never
  reaches a decision.

#### 2.4 — Audit completeness as a property

- A committed registry maps every situation-graph node to the steps it may
  write; a node in the graph but not the registry fails a test.
- Per scenario: steps belong to declared nodes, appear in an order consistent
  with a topological walk of the compiled graph, are contiguous from one, and
  always begin with TRIGGER.
- **Deliberately a test rather than the instrumentation wrapper the plan
  sketched.** Each entry is written where its work happens, carrying detail only
  that step can supply. Hoisting the writes into a generic wrapper would buy the
  structural guarantee at the cost of the detail that makes the trail worth
  reading; the guarantee is the part that matters, and it is enforced either way.

#### 2.5 — The limit, stated

- The v1 tamper test is split into three: corruption, forgery, and a test that
  asserts the **residual limit** directly — an entry re-tagged *with* the key
  verifies. Named in the README rather than left implied.

#### Deliberately not done

- **Real tamper-proofing.** An attacker holding the key *and* write access can
  still rewrite an entry, re-sign it, re-chain forward, and rewrite the
  checkpoints. Checkpoints narrow the window; they do not close it. Closing it
  needs storage the attacker cannot reach — WORM media or an external notary —
  which this build does not have.

#### Notes

- `tests/conftest.py` gives the suite its own database and key under pytest's
  temp root, so a test run cannot write into a developer's ledger or leave the
  global chain advanced.
- Locally, pytest's temp root needed redirecting via `PYTEST_DEBUG_TEMPROOT`:
  a stale `pytest-of-inder` directory on this machine has an ACL that denies
  even reading it. A machine fault, not a project one — no workaround was
  committed.


### Phase 1B — Propose / dispose

**Landed.** The core change of the project. 330 tests passing (162 carried
forward + 168 new), **three pre-existing tests edited, all three of them
committed topology snapshots**. All eight scenarios reach the same branch as
v1. Delivers **S4**, **S5** and **S6**.

Before this phase the "AI reasoning tier" was a rules engine wearing a model's
clothes: the SELECT prompt carried each candidate's compiled `applies_when` and
`prescribes`, and `MockGraniteLLM._unmet_conditions` evaluated them with Python
conditionals. The model was handed the answer key, and even a real Granite would
have been doing symbolic matching rather than reading procedure. The gate that
produced HAVEN's headline refusal was a TF-IDF similarity float compared against
`THRESHOLDS.relevance_gate`, with a hardcoded `+0.12` in the mock — a similarity
score wearing a decision's clothes.

#### Added

- `haven/deterministic/preconditions.py` — `check(applies_when, prescribes,
  facts) -> AdmissibilityResult`. The clause logic, moved out of the mock and
  into the deterministic tier where it is a safety component with its own tests.
  It emits a `ClauseDetail` for **every** clause, satisfied or not, because the
  console renders the whole verdict and one reason invites the assumption that
  fixing it would change the answer.
- `haven/graph/nodes/{admissibility,select,verify,fuse,generate,refuse}.py` and
  the second branch in the system, at VERIFY.
- `tests/test_preconditions.py` (29) and `tests/test_propose_dispose.py` (81),
  plus S4/S5/S6 in `tests/test_safety_invariants.py`.

#### Changed

- **The situation graph.** `RETRIEVE → REASON` becomes
  `RETRIEVE → ADMISSIBILITY → SELECT → VERIFY → FUSE → GENERATE`, with
  `VERIFY ↘ REFUSE`; both terminal paths converge on SCREEN. `ReasoningFlow.run`
  — the single indivisible call Phase 1A had to preserve — is gone, and each of
  its steps is a node. This is the seam Phase 1A documented in the `RETRIEVE`
  and `REASON` docstrings, now opened.
- **ADMISSIBILITY does not filter the candidate set,** deliberately. A near-miss
  is inadmissible by construction; dropping the inadmissible candidates before
  SELECT would delete the `eva_near_miss` discrimination case and make the
  model's "rejection" of P-SLP-2.1 a tautology. Pre-cleaning the candidate set
  is the same mistake as showing the model `applies_when`, reached from the
  other direction.
- **The mock reads prose.** `_unmet_conditions` is deleted. `_select` now
  applies four readings in order — disclaimer, crew-state relevance, operation
  scope, and stated categorical conditions — against the passage text and the
  deterministic fact set. It recognises an operation by the words procedure uses
  for it ("propulsive manoeuvre", not `orbital_burn`).
- **The float gate is gone from the decision path.** No GATE step, no `+0.12`,
  and SELECT no longer returns a relevance score at all.
  `THRESHOLDS.relevance_gate` and `Refusal.gate` survive as display-only, and a
  test AST-scans every module in `haven/` to prove no branch reads them.
- Contract: `ClauseDetail`; `Recommendation.verified_clauses`;
  `Refusal.failed_clauses` / `.model_selected` / `.checker_disagreed`; two new
  refusal reasons, `precondition_unmet` and `checker_model_disagreement`.
  `openapi.json` and `web/src/lib/api-types.ts` regenerated.
- Console: Zone 3 renders ADMISSIBILITY and VERIFY and distinguishes "proposed —
  verified" from "proposed — rejected"; the refusal panel leads with the
  unsatisfied clauses and demotes retrieval similarity to "closest candidate".

#### Shapes forced by the required topology

- **A settled outcome is final; later reasoning nodes are inert.** The required
  diagram gives VERIFY the only new branch, so a provider outage at FUSE or
  GENERATE cannot route to REFUSE. Instead the node that loses the provider
  degrades in place and every node after it reads `state["outcome"]` and returns
  without acting. One rule, applied uniformly, rather than four edges.
- **`GENERATE_PROMPT` reworded**, "the action the procedure prescribes" → "the
  action the procedure requires". S4 is asserted as a substring ban and the
  prompt's own English collided with the field name. The wording is the same
  instruction; the alternative was a carve-out in the safety test.

#### Deliberately not done

- **`prescribes`'s *value* still reaches the provider at GENERATE**, as
  `action`. It must: GENERATE's whole job is to state the prescribed action, and
  by then the checker has already verified the citation. S4 is about the
  *selection* stage seeing the answer key, and the tests assert on field names
  for exactly that reason. Worth revisiting only if FUSE/GENERATE ever move
  upstream of VERIFY, which they must not.
- **The mock cannot evaluate `alertness_below`, `workload_above` or
  `criticality_in` from prose**, and does not try. "Below the nominal execution
  threshold" names no number. This is the *correct* limit of a prose reader, and
  it is what makes the mock genuinely fallible — `test_the_mock_is_fallible_and_
  the_checker_is_what_makes_that_safe` pins it.
- **`best_candidate.relevance` on a refusal is now retrieval similarity**, no
  longer the mock's `relevance * 0.55`. `test_refusals_record_what_was_searched`
  still asserts it sits below the gate and still passes — but on the shipped
  corpus that is now incidental rather than structural. Left untouched as a v1
  invariant; flagged here so a future failure is read as a display question, not
  a safety one.

### Phase 1A — The seven-stage cycle as a compiled LangGraph state machine

**Landed.** Pure refactor. 155 tests passing (123 pre-existing + 32 new
topology tests), **zero edits to any pre-existing test**, `calibrate.py` output
byte-identical to the v1 baseline. Delivers **S9**.

#### Added

- `haven/graph/` — two compiled `StateGraph`s:
  - `evaluation_graph`: `INGEST → SCORE → TRIGGER → SITUATIONS → PRESENT`,
    entirely unconditional.
  - `situation_graph`: `CONFIDENCE → RETRIEVE → REASON → SCREEN`, with the one
    branch in the whole system at the confidence gate (`→ WITHHOLD`).
  Both compiled once at import. **No checkpointer** — HAVEN's ledger is the
  system of record and graph state is deliberately not persisted.
- `tests/test_graph_topology.py` — 32 tests enforcing S9 against the *compiled*
  graphs: node and edge sets as committed snapshots, acyclicity, no prebuilt
  agent or `ToolNode`, and a three-layer check that no conditional-edge router
  can reach a provider (source scan, `ast` import scan, live namespace scan).
  Two `*_probe_itself_fires` tests prove the scanners are live.

#### Changed

- `haven/engine.py` is now a 31-line invoker. Its signature and return type are
  unchanged, so `haven/api/main.py`, `scripts/calibrate.py`, and every test call
  it untouched.
- Provider and retriever are bound in `engine.evaluate`, **not** inside a node.
  Deliberate: the graph package then constructs no provider of its own, which is
  what makes the S9 namespace assertion meaningful. Cost: the graph is not
  self-sufficient, and adapters must be injected.

#### Deliberately not done

- **No `instrumentation.py`.** Routing audit writes through graph hooks is
  Phase 2. Every `trail.append(...)` stays exactly where it was — audit content
  and ordering are asserted by existing tests.
- **No `Send` fan-out.** Concurrency is Phase 6; `SITUATIONS` iterates
  sequentially to preserve ordering exactly.
- **`situation_id` / `audit_ref` generation unchanged**, collision included.
  Phase 2 fixes it. Note the suite currently *depends* on `AUDIT.put`
  overwriting by `audit_ref` when scenarios are re-run.

#### Shapes forced by exact-behaviour preservation

- `RETRIEVE` does not retrieve. `ReasoningFlow.run` is one indivisible call
  covering retrieval, SELECT, GATE, FUSE and GENERATE. The honest split was:
  `RETRIEVE` builds the deterministic fact set and binds the flow, `REASON` runs
  it. **This is the Phase 1B seam**, documented in both node docstrings.
- `degraded` is aggregated by hand rather than by a channel reducer. The
  original is "sticky `True`, last reason wins"; a default last-write-wins
  channel would give "last situation wins", which differs when a degraded
  situation is followed by a healthy one.

#### Latent bugs found, NOT fixed (would change behaviour)

Recorded so they are not lost. Each needs a decision, not a silent fix.

1. **Tasks with an unknown `assigned_to` vanish silently.** `by_id.get(...) is
   None → continue` drops the task before scoring: no timeline entry, no
   archive entry, no Situation, no record anywhere in the response. A mistyped
   crew id makes a high-criticality task invisible. **This is the most serious
   one** — a silent failure in a system whose entire thesis is that gaps are
   findings.
2. `ACTION_LABELS[action]` / `RESOURCE_COST[action]` are unguarded dict lookups
   on corpus data. `Passage.prescribes` is `str | None`, not the `ActionType`
   literal, so a corpus entry prescribing anything outside the five keys raises
   `KeyError` out of `evaluate` — a 500 instead of a refusal. Phase 4 makes this
   reachable, since the compiler will author `prescribes` values.
3. `roster_conflict` refusals build `searched` unsorted and un-deduplicated,
   unlike `ReasoningFlow._refuse` which uses `sorted({...})`.
4. `degraded_reason` is last-writer-wins across situations; two different outage
   reasons report only the last.

### Phase 0 — Foundation, contract synchronisation, framework floor

**Landed.** 123 tests passing (68 original + 34 offline-guard + 21 contract).
`scripts/calibrate.py` output byte-identical to the pre-Phase-0 baseline.

#### Added

- `pyproject.toml` + `uv.lock`, replacing `requirements.txt` and `pytest.ini`.
  Optional extras (`providers`, `rag`, `compiler`) are declared but not
  installed, so the base install *is* the offline path. CI syncs without extras
  specifically to prove it.
- Ruff, configured and applied. Line length 120 to match existing style.
- `haven/offline.py` — the offline guarantee enforced at import time, invoked
  from `haven/__init__.py` (the only point guaranteed to precede a LangChain
  import).
- `tests/test_offline_guard.py` — 34 tests. Imports the API tier in a subprocess
  with tracing forced *on* and every socket trapped; asserts nothing reaches the
  network and that `langchain-core`'s own `env_var_is_set` reports tracing
  disabled. Includes a meta-test proving the socket probe itself fires.
- `tests/test_contract_constraints.py` — 21 tests, each asserting the
  *rejection*, since a constraint that never fires is decoration.
- `scripts/export_openapi.py` and a committed `openapi.json`.
- `.github/workflows/ci.yml` — two jobs: engine (lint/format/tests/calibrate)
  and contract (regenerate, fail on drift, typecheck, build).
- `.gitattributes` normalising line endings; Windows dev, Ubuntu CI.

#### Changed

- **The contract is generated, not hand-mirrored.** `web/src/lib/api-types.ts`
  is generated from `openapi.json`; `types.ts` is now friendly aliases over it.
  All seven console components compile unchanged.
- Range constraints on fields that documented a range and enforced nothing.
- Naive datetimes coerced to UTC at the contract boundary. Previously they
  reached `ThreeProcessModel.homeostatic` and raised `TypeError` on the first
  comparison — a 500 for what is really a malformed request.
- `AuditStep.inputs`/`outputs` parameterised as `dict[str, Any]`. As bare
  `dict` they generated `Record<string, never>`, which would have been a compile
  error in Zone 3, where the console reads `retrieveStep.outputs.candidates`.
- `GET /api/scenarios` gained a real response model, so its console type is
  generated rather than hand-maintained.

#### Removed

- `triggers.py` computed `workload_excess` and never used it — the risk formula
  uses raw `workload_score / 100.0`. Dead variable removed and the reason for
  using absolute workload documented. **Behaviour deliberately unchanged:**
  wiring the term in would alter every `risk_level`. If that was a missed term
  rather than an abandoned one, it is a live question, not a settled one.
- An unused `weights` local in the NASA-TLX test. The test hardcodes the weights
  on purpose — an expectation derived from the code under test proves nothing.

#### Notes

- `langsmith` is a **hard dependency of `langchain-core`**, not an optional
  extra, and tracing auto-enables from the environment. Concern C4 was therefore
  real rather than theoretical.
- Python 3.14.5 locally; `cp314` wheels verified for the whole tree including
  `onnxruntime`. `requires-python` capped `<3.15` — without a cap uv resolves
  against unreleased versions. CI runs the **3.12 floor** so newer syntax cannot
  slip in.

### Repository restructure — unified monorepo

**Landed.** Not a phase; requested between Phase 0 and Phase 1.

`backend/app/` → `haven/`, `backend/app/retrieval/` → `haven/rag/`,
`backend/app/main.py` → `haven/api/main.py`, `backend/tests/` → `tests/`,
`backend/tools/` → `scripts/`, `frontend/` → `web/`, and the project files to
the root. No `backend/` or `frontend/` wrappers; the Python package carries the
tier boundaries in its own directory names.

Two judgement calls:

- **`contracts.py` stays at `haven/contracts.py`**, not under `api/`. It is the
  shared boundary spec — `engine.py`, the tests, and the type generator all read
  it — so filing it under the API tier would have `engine.py` importing upward
  from `haven.api`, inverting the dependency direction.
- **`retrieval/` renamed `rag/`**, matching the vocabulary of the document
  pipeline it grows into in Phase 4.

Verified: 123 tests unchanged, calibrate byte-identical, `openapi.json` and
`api-types.ts` regenerating to identical bytes (the real proof the contract
survived), lint/format clean, console typechecks and builds, and a live
`uvicorn haven.api.main:app` returning the expected `burn_fatigue`
recommendation.
