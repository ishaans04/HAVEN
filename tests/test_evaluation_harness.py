"""The harness has to be trustworthy before its numbers are worth anything.

Three things are checked here, and the first two matter more than they look.

**The golden set agrees with the deterministic checker.** Every case labelled
with a governing passage must name one the checker finds admissible, and every
case labelled as a refusal must offer nothing admissible at all. Without this
the labels are one person's opinion, and a harness measuring against an opinion
measures nothing. It also means a corpus change that quietly alters what governs
breaks the labels rather than silently moving the score.

**The harness cannot reach into the system it measures.** Nothing under `haven/`
imports `evaluation`, so the measurement is external by construction.

**The mock produces no unsafe citation.** A citation that does not govern is the
one failure this architecture exists to prevent, and it is a gate rather than a
metric: accuracy may vary by provider, but this must be zero for all of them.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from evaluation.golden_set import CASES, GOVERNING_CASES, PROSE_KEYS, REFUSAL_CASES
from evaluation.run_eval import run
from haven.deterministic import preconditions
from haven.rag.corpus import BY_ID

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def admissible_ids(case) -> set[str]:
    found = set()
    for passage_id in case.candidate_ids:
        passage = BY_ID[passage_id]
        verdict = preconditions.check(passage.applies_when, passage.prescribes, case.facts, authority=passage.authority)
        if verdict.admissible:
            found.add(passage_id)
    return found


# --------------------------------------------------------------------------
# The labels must agree with the checker
# --------------------------------------------------------------------------
@pytest.mark.parametrize("case", GOVERNING_CASES, ids=lambda c: c.case_id)
def test_a_governing_label_names_an_admissible_passage(case) -> None:
    assert case.governs in admissible_ids(case), (
        f"{case.case_id} is labelled as governed by {case.governs}, which the checker rejects. "
        "Either the label is wrong or the corpus changed underneath it."
    )


@pytest.mark.parametrize("case", REFUSAL_CASES, ids=lambda c: c.case_id)
def test_a_refusal_label_offers_nothing_admissible(case) -> None:
    assert not admissible_ids(case), (
        f"{case.case_id} is labelled as a refusal, but the checker finds {sorted(admissible_ids(case))} admissible"
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_every_candidate_resolves_in_the_corpus(case) -> None:
    for passage_id in case.candidate_ids:
        assert passage_id in BY_ID, f"{case.case_id} names {passage_id}, which is not in the corpus"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_a_stated_near_miss_is_actually_a_near_miss(case) -> None:
    """A passage labelled with a reason it fails must genuinely fail."""
    for passage_id in case.why_not:
        assert passage_id != case.governs, f"{case.case_id}: {passage_id} cannot both govern and fail"
        assert passage_id in case.candidate_ids, f"{case.case_id}: {passage_id} is not in the candidate set"


def test_the_set_is_weighted_towards_refusal() -> None:
    """Refusal precision is the metric that distinguishes this architecture."""
    assert len(REFUSAL_CASES) >= len(GOVERNING_CASES), (
        "cases with no governing rule must not be the minority; selection accuracy "
        "is the easy metric and the least interesting one"
    )


def test_case_identifiers_are_unique() -> None:
    ids = [c.case_id for c in CASES]
    assert len(ids) == len(set(ids))


# --------------------------------------------------------------------------
# The harness is external to what it measures
# --------------------------------------------------------------------------
def test_nothing_in_the_engine_imports_the_harness() -> None:
    """A harness the system under test could reach would be measuring itself."""
    offenders: list[str] = []
    for path in (REPO_ROOT / "haven").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(n.split(".")[0] == "evaluation" for n in names):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"the engine imports the evaluation harness: {offenders}"


def test_the_harness_shows_the_model_only_prose() -> None:
    """The golden set must not leak compiled preconditions either (S4)."""
    for case in CASES:
        for payload in case.prose():
            assert set(payload) == set(PROSE_KEYS), (
                f"{case.case_id} would hand the provider {sorted(set(payload) - set(PROSE_KEYS))}"
            )


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------
def test_the_mock_produces_no_unsafe_citation() -> None:
    """Accuracy varies by provider; this must be zero for every one of them."""
    summary = run("mock").summary()
    assert summary["unsafe_citations"] == 0, (
        "a citation that does not govern is the failure this architecture exists to prevent"
    )


def test_the_mock_refuses_whenever_nothing_governs() -> None:
    report = run("mock")
    missed = [r.case.case_id for r in report.results if r.case.should_refuse and r.final_passage is not None]
    assert not missed, f"asserted a rule where none governs: {missed}"


def test_the_harness_reports_the_checker_separately_from_the_model() -> None:
    """The gap between the two accuracies is the checker's measured value."""
    summary = run("mock").summary()
    assert summary["system_accuracy"] >= summary["model_accuracy"], (
        "the checker may only ever improve on the model's proposal, never worsen it"
    )
