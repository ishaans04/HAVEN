# The demo, in six scenarios

Roughly eight minutes. Each scenario shows one thing the architecture claims,
and they are ordered so each answers the doubt the last one raises.

Start it:

```bash
uv run --no-sync python -m scripts.run_haven
```

Then open <http://localhost:8000>. One process serves the console and the API.
The launcher reports whether the console build is current and which provider
chain will be tried, both of which fail silently otherwise.

`--no-sync` is not optional: `uv run` re-syncs by default, and a bare sync
prunes the optional extras — including the watsonx packages — thirty seconds
before a demo.

For development with hot reload, run the console separately instead:

```bash
cd web && NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

---

## 1 · `burn_fatigue` — it works

The commander has run six nights of restricted sleep and is assigned a reboost
burn at 12:40. Predicted alertness 0.69, below the 0.70 execution threshold for
a high-criticality task.

**Show:** the recommendation cites OPS-FATIGUE-04 §4.2 and asks for a second
qualified operator. Zone 5 names who: L. Petrova, above the alertness floor and
uncommitted. Zone 4 shows what it buys — 0.69 → 0.76, clearing the threshold.

**Say:** every number came from the deterministic tier. The model chose the rule
and wrote the sentence; it never produced a figure, and a test asserts that for
every numeral in that text.

---

## 2 · `eva_near_miss` — it discriminates

Retrieval surfaces three EVA-scoped passages. Two are near-misses that share the
governing rule's vocabulary almost word for word.

**Show:** Zone 3, both columns. The model proposed §4.4 reading prose alone. The
checker independently evaluated all three and found only §4.4 admissible —
P-SLP-2.1 fails on `phase`, because it governs planning, and it says so in its
own text.

**Say:** the model never saw the preconditions. It reads the passage as written,
which is the skill that transfers to a procedure library it has not seen. The
checker's agreement is what makes the citation trustworthy, and disagreement
would have produced a refusal.

Open **the corpus** in the header. The near-misses are labelled as passages that
exist to be rejected. The corpus is adversarial on purpose.

---

## 3 · `no_procedure` — it refuses

Fatigue during a medical contingency. Nothing in the corpus governs it.

**Show:** a refusal, styled deliberately unlike an error. It records what was
searched, the closest candidate, and escalates to the flight director.

**Say:** this is the scenario the whole design exists for. A system that always
produces an answer produces a wrong one eventually, and the wrong answer here
looks exactly as confident as the right ones. Refusing is a first-class output.

**On a real model the refusal often arrives by a different route, and it is the
better story.** The offline stand-in reports that nothing governs, and the
refusal reads `no_governing_procedure`. Live Granite tends to reach for the
closest passage instead — exactly the failure the architecture predicts — and
the deterministic checker rejects it, so the refusal reads `precondition_unmet`
and names the clause that failed. Same outcome, and the second version shows
the checker earning its place rather than the model happening not to need it.

---

## 4 · `roster_block` — the maths overrules the AI

The governing rule prescribes second-operator verification. Every qualified
alternate is below the alertness floor or committed elsewhere.

**Show:** the deterministic screen vetoed a well-formed recommendation, and the
action was downgraded to the deferral **the same cited passage prescribes**. The
audit trail carries a `GENERATE_FALLBACK` step where the text was rewritten.

**Say:** the reasoning tier proposes; deterministic screens dispose. The
downgrade is grounded in the cited text rather than invented by the engine.

---

## 5 · `thin_data` — it withholds

Most of the operator's sleep record is missing from the downlink.

**Show:** a refusal, and the audit trail with exactly three steps —
`TRIGGER → CONFIDENCE → WITHHOLD`. No reasoning-tier entry at all.

**Say:** the confidence gate runs before the model is consulted. There was
nothing to reason about, and asserting anything would have been false certainty.
The data gap *is* the finding.

---

## 6 · `provider_outage` — it fails loudly

The same reboost-burn inputs, with the reasoning provider unreachable.

**Show:** degraded mode declared in Zone 6, the deterministic evidence intact,
the Situation escalated. Then expand the audit bar: the hash chain verified
across every step.

**Say:** it does not guess from the deterministic tier alone. Alertness and
workload are unaffected by the outage; what is missing is the procedure
interpretation, and the system says so rather than quietly producing less.

---

## If asked

**"Is the AI real?"** The reasoning tier reads passage prose and proposes a
governing rule. The compiled preconditions are withheld from it — a test asserts
no such field reaches any provider. By default it runs against a scripted
stand-in so the demo cannot fail on a network call; `HAVEN_LLM_CHAIN=watsonx,ollama,mock`
runs real Granite with the stand-in as the last link, and Zone 6 names which one
answered.

Before demonstrating on watsonx, confirm the credentials are live — a chain that
silently falls through to the stand-in looks exactly like one that never tried:

```bash
uv run python -m scripts.check_providers
```

**"How do you know it works?"**

```bash
uv run python -m evaluation.run_eval --provider mock --verbose
```

Twenty labelled Situations, weighted towards cases where *nothing* governs. Two
accuracies are reported: what the model proposed, and what the system did after
the checker disposed of it. Unsafe citations must be zero, and CI fails on one.

**"Are the NASA documents real?"** The documents are: NASA-STD-3001 Volumes 1
and 2, the HIDH, and three NTRS papers, each version-verified against its
publisher before download and pinned by SHA-256 in `corpus/sources.json`. The
corpus the console *reasons over* is still the hand-authored one, because the
131 compiled passages have not been reviewed and the emit gate refuses without a
named reviewer. Open the corpus browser: every row is labelled with its
authority, and only `authoritative` and `prototype` rows may ground an action —
a handbook's recommendation and a paper's finding cannot, and the deterministic
checker enforces that before it evaluates a single precondition.

**"What is not real?"** The crew roster is representative, not real individuals.
Sleep and duty timelines are synthetic. The runtime corpus is written for this
prototype and labelled `synthesised` and `prototype` in the browser. No
live-provider figures have been produced, because the credentials are not
available here. The ledger is tamper-evident, not tamper-proof. All of this is
in the README under Honest limits, and the console has a "Real vs simulated"
panel in the header.
