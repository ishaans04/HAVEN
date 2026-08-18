"""Every evaluation is distinguishable, and names the rulebook it used (S8).

Two defects fixed here, both recorded in the CHANGELOG before they were fixed.

The identifier collision: `S-{window_date}-{index}` and `LOG-` in front of it
meant all eight scenarios -- which share the window date 2026-08-20 -- reused the
same audit_ref. In v1 that merely overwrote a dict entry and the demo got away
with it, because the console re-fetched immediately. With a durable ledger it is
worse: trails from different evaluations would accumulate under one reference.

The missing manifest: a decision that does not name the corpus it reasoned over
cannot be fully audited. Two evaluations that disagree are only comparable if
they were reading the same rulebook, and from Phase 4 the corpus is compiled and
versioned rather than fixed.
"""

from __future__ import annotations

import pytest

from haven.data.scenarios import SCENARIOS
from haven.rag.corpus import CORPUS, CORPUS_MANIFEST, Passage, compute_manifest
from haven.reasoning.audit import AUDIT
from tests.test_engine import run

ALL_SCENARIOS = [s.id for s in SCENARIOS]


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
def test_every_scenario_in_one_process_gets_a_distinct_audit_ref() -> None:
    """The regression this milestone exists to prevent."""
    refs: list[str] = []
    for scenario_id in ALL_SCENARIOS:
        refs.extend(s.audit_ref for s in run(scenario_id).situations)

    assert len(refs) == len(set(refs)), f"audit_ref collision across scenarios: {refs}"


def test_every_trail_remains_retrievable_after_all_scenarios_have_run() -> None:
    """Collisions used to silently replace an earlier scenario's trail."""
    expected: dict[str, str] = {}
    for scenario_id in ALL_SCENARIOS:
        for situation in run(scenario_id).situations:
            expected[situation.audit_ref] = situation.situation_id

    for audit_ref, situation_id in expected.items():
        trail = AUDIT.get(audit_ref)
        assert trail is not None, f"{audit_ref} was lost"
        assert trail.situation_id == situation_id
        assert trail.entries, "a retrieved trail must still carry its steps"


def test_re_running_one_scenario_does_not_reuse_its_identifiers() -> None:
    first = run("burn_fatigue")
    second = run("burn_fatigue")

    assert first.evaluation_id != second.evaluation_id
    assert {s.audit_ref for s in first.situations}.isdisjoint(s.audit_ref for s in second.situations)


def test_a_situation_identifier_carries_its_evaluation() -> None:
    """So a Situation can be traced back to the run that produced it."""
    response = run("burn_fatigue")
    token = response.evaluation_id.removeprefix("EVAL-")
    for situation in response.situations:
        assert situation.situation_id.startswith(f"S-{token}-")
        assert situation.audit_ref == f"LOG-{situation.situation_id}"


def test_the_trail_does_not_duplicate_its_steps_across_runs() -> None:
    """Deriving identifiers from the request would have caused exactly this."""
    first = run("burn_fatigue").situations[0]
    steps_first = len(AUDIT.get(first.audit_ref).entries)

    second = run("burn_fatigue").situations[0]
    assert len(AUDIT.get(second.audit_ref).entries) == steps_first
    assert len(AUDIT.get(first.audit_ref).entries) == steps_first, "an earlier trail must not grow"


# --------------------------------------------------------------------------
# S8 -- every outcome names its rulebook
# --------------------------------------------------------------------------
@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
def test_every_outcome_records_the_corpus_manifest(scenario_id: str) -> None:
    response = run(scenario_id)
    assert response.tier_status.corpus_manifest == CORPUS_MANIFEST

    for situation in response.situations:
        assert situation.corpus_manifest, f"{situation.situation_id} does not name its rulebook"
        assert situation.corpus_manifest == CORPUS_MANIFEST


def test_the_manifest_is_stable_for_an_unchanged_corpus() -> None:
    assert compute_manifest(CORPUS) == compute_manifest(list(reversed(CORPUS))) == CORPUS_MANIFEST


def test_the_manifest_changes_when_a_rule_changes() -> None:
    """A manifest that did not move with the corpus would identify nothing."""
    edited = [
        Passage(**{**vars(p), "prescribes": "task_deferral"}) if p.passage_id == "P-FAT-4.2" else p for p in CORPUS
    ]
    assert compute_manifest(edited) != CORPUS_MANIFEST


def test_the_manifest_changes_when_a_passage_is_removed() -> None:
    assert compute_manifest([p for p in CORPUS if p.passage_id != "P-FAT-4.4"]) != CORPUS_MANIFEST


def test_the_manifest_ignores_commentary_that_cannot_reach_a_decision() -> None:
    """near_miss_note is for the corpus's readers, never for the engine."""
    annotated = [
        Passage(**{**vars(p), "near_miss_note": "note added for reviewers"}) if p.passage_id == "P-DCK-3.2" else p
        for p in CORPUS
    ]
    assert compute_manifest(annotated) == CORPUS_MANIFEST


def test_the_situation_and_the_evaluation_agree_on_the_rulebook() -> None:
    response = run("burn_fatigue")
    for situation in response.situations:
        assert situation.corpus_manifest == response.tier_status.corpus_manifest
