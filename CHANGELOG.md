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
| S7 | No entry forgeable without the key; no silent deletion | Phase 2 |
| S8 | Every outcome records its corpus manifest | Phase 2 |
| S9 | The graph is static: no LLM routes, no tool nodes, no cycles | Phase 1A |

---

## [Unreleased]

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
