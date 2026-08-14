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
| S4 | The reasoning tier never receives compiled preconditions | Phase 1B |
| S5 | No citation without independent checker confirmation | Phase 1B |
| S6 | Model/checker disagreement fails closed, both directions | Phase 1B |
| S7 | No entry forgeable without the key; no silent deletion | Phase 2 |
| S8 | Every outcome records its corpus manifest | Phase 2 |
| S9 | The graph is static: no LLM routes, no tool nodes, no cycles | Phase 1A |

---

## [Unreleased]

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
