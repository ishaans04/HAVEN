"""The procedure corpus HAVEN reasons over.

HONESTY NOTE (PRD section 10): the passages below are a *representative* corpus.
Their structure, numbering convention, and precondition style follow NASA flight
rule and NTRS human-factors documentation, but the text is synthesised for this
prototype. Nothing here should be read as verbatim NASA procedure. Each passage
carries its provenance in ``source``.

The corpus is built to exercise the reasoning tier, not just to be retrievable:

  * Several passages are deliberate NEAR-MISSES -- topically adjacent, high
    lexical overlap, wrong preconditions. Retrieval will surface them; the
    reasoning tier must reject them.
  * There is a deliberate GAP. No passage governs a fatigue-gated medical
    contingency, so that scenario must reach REFUSE rather than be papered over.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Passage:
    passage_id: str
    doc: str
    section: str
    title: str
    text: str
    task_types: list[str]
    # Machine-checkable preconditions. The reasoning tier must confirm the
    # Situation satisfies these before a passage may be cited -- this is what
    # separates "topically similar" from "actually governing".
    applies_when: dict = field(default_factory=dict)
    prescribes: str | None = None
    # What the passage itself prescribes when the primary action is unavailable.
    # Used by the schedule-impact screen so a downgrade stays grounded in the
    # same cited text rather than being invented by the engine.
    fallback_action: str | None = None
    source: str = "Representative corpus (synthesised; structure per NASA flight rule convention)"
    near_miss_note: str = ""
    # Where this passage came from, and who signed off on its preconditions.
    #
    # "extracted" means compiled from a real source document under review;
    # "synthesised" means written for this prototype because the public record
    # contains no execution-time gating rule for the case. The distinction is a
    # field rather than a convention because it is exactly the kind of thing
    # that quietly disappears otherwise -- and a corpus that cannot say which of
    # its rules are real is not one anybody should reason over.
    provenance: str = "synthesised"
    # The force of what the source document says, and the only thing standing
    # between a handbook's recommendation and a crew being told it is a rule.
    #
    # "authoritative" is a standard stating shall-requirements; "guidance" a
    # handbook; "research" a paper. "prototype" is a rule written for this
    # prototype, which is the default because that is what the hand-authored
    # corpus is. Only authoritative and prototype passages may prescribe -- see
    # haven.deterministic.preconditions.PRESCRIPTIVE_AUTHORITIES, which is where
    # that is enforced rather than merely documented.
    authority: str = "prototype"
    reviewed_by: str = ""


CORPUS: list[Passage] = [
    # ---- OPS-FATIGUE-04 : the fatigue rulebook --------------------------
    Passage(
        passage_id="P-FAT-4.2",
        doc="OPS-FATIGUE-04",
        section="4.2",
        title="Reduced alertness prior to propulsive or proximity operations",
        text=(
            "Where the predicted alertness of the assigned operator falls below the "
            "nominal execution threshold within thirty minutes of a scheduled propulsive "
            "manoeuvre, docking, or proximity operation, the manoeuvre shall not be "
            "executed single-operator. A second qualified operator shall be assigned to "
            "independently verify manoeuvre parameters, burn duration, and abort criteria "
            "prior to execution. Where a second qualified operator is not available, the "
            "manoeuvre shall be deferred to the next available window."
        ),
        task_types=["orbital_burn", "docking"],
        applies_when={
            "task_types": ["orbital_burn", "docking"],
            "alertness_below": 0.70,
            "criticality_in": ["high", "medium"],
        },
        prescribes="second_operator_verify",
        fallback_action="task_deferral",
    ),
    Passage(
        passage_id="P-FAT-4.4",
        doc="OPS-FATIGUE-04",
        section="4.4",
        title="Extravehicular activity with degraded crew alertness",
        text=(
            "Extravehicular activity shall not commence where the predicted alertness of "
            "a suited crew member is below the extravehicular execution threshold. Where "
            "the shortfall is attributable to acute sleep loss rather than accumulated "
            "debt, a protected rest period of no less than ninety minutes may be taken "
            "and alertness re-evaluated prior to egress. Where the shortfall reflects "
            "accumulated sleep debt across three or more consecutive duty days, the "
            "activity shall be deferred and the crew member removed from the "
            "extravehicular roster pending flight surgeon review."
        ),
        task_types=["eva"],
        applies_when={
            "task_types": ["eva"],
            "alertness_below": 0.70,
            "criticality_in": ["high", "medium"],
        },
        prescribes="short_rest_then_proceed",
    ),
    Passage(
        passage_id="P-FAT-5.1",
        doc="OPS-FATIGUE-04",
        section="5.1",
        title="Circadian trough scheduling of safety-critical tasks",
        text=(
            "Safety-critical tasks shall not be scheduled within the assigned operator's "
            "circadian trough where an alternative execution window exists within the "
            "same planning period. Where no alternative window exists, the task shall be "
            "executed under second-operator verification and the deviation recorded in "
            "the daily execution package. This section applies irrespective of measured "
            "sleep sufficiency, as circadian phase alone is sufficient to produce "
            "operationally significant performance decrement."
        ),
        task_types=["orbital_burn", "docking", "eva", "robotics_capture", "hatch_operation"],
        applies_when={
            "task_types": ["orbital_burn", "docking", "eva", "robotics_capture", "hatch_operation"],
            "requires_circadian_flag": True,
            "criticality_in": ["high"],
        },
        prescribes="task_deferral",
    ),
    Passage(
        passage_id="P-FAT-6.3",
        doc="OPS-FATIGUE-04",
        section="6.3",
        title="Sustained duty load and rotation",
        text=(
            "Where an operator has exceeded the sustained duty ceiling across the "
            "trailing twenty-four hour period and is assigned a further task of medium "
            "or high criticality, duty rotation shall be applied. A qualified operator "
            "within duty limits shall assume the assignment. Rotation shall not be "
            "applied where it would leave any safety-critical role unstaffed."
        ),
        task_types=["robotics_capture", "maintenance", "science_ops", "hatch_operation"],
        applies_when={
            "workload_above": 65.0,
            "criticality_in": ["high", "medium"],
        },
        prescribes="duty_rotation",
        fallback_action="task_deferral",
    ),
    # ---- NEAR MISSES : topically adjacent, wrong preconditions ----------
    Passage(
        passage_id="P-SLP-2.1",
        doc="OPS-SLEEP-02",
        section="2.1",
        title="Pre-extravehicular sleep shifting protocol",
        text=(
            "Crew members assigned to extravehicular activity shall begin sleep shifting "
            "no later than three planning days prior to egress, advancing the sleep "
            "period incrementally so that the extravehicular window falls within the "
            "crew member's alert phase. Sleep shifting is a planning activity and shall "
            "be completed before the execution period; it is not a corrective action for "
            "alertness shortfall detected during execution."
        ),
        task_types=["eva"],
        # Planning-phase rule. Deliberately does NOT apply during execution.
        applies_when={"task_types": ["eva"], "phase": "planning"},
        prescribes=None,
        near_miss_note=(
            "High lexical overlap with the EVA fatigue rule (P-FAT-4.4) but scoped to "
            "the planning phase. Must be rejected during execution."
        ),
    ),
    Passage(
        passage_id="P-DCK-3.2",
        doc="OPS-DOCK-07",
        section="3.2",
        title="Docking approach corridor and abort criteria",
        text=(
            "The approach corridor shall be maintained within the defined cone from "
            "range gate entry to capture. The operator shall verify closure rate, "
            "misalignment, and contact conditions against abort criteria at each range "
            "gate. Manual takeover shall be exercised where automated approach exceeds "
            "corridor limits. This section governs vehicle state and approach geometry "
            "only."
        ),
        task_types=["docking"],
        # Vehicle-state rule with no crew-state precondition at all.
        applies_when={"task_types": ["docking"], "domain": "vehicle_state"},
        prescribes=None,
        near_miss_note=(
            "Same task type as P-FAT-4.2 and strong keyword overlap on 'docking', but "
            "governs vehicle geometry, not crew alertness."
        ),
    ),
    Passage(
        passage_id="P-EVA-11.3",
        doc="OPS-EVA-11",
        section="3.4",
        title="Suit pressure integrity and pre-breathe verification",
        text=(
            "Prior to egress the suited crew member shall complete the pre-breathe "
            "protocol and verify suit pressure integrity, communications, and thermal "
            "control. Where pre-breathe is interrupted, the protocol shall be restarted "
            "in full. Crew rest status is verified separately under the fatigue "
            "management procedure and is not assessed by this section."
        ),
        task_types=["eva"],
        applies_when={"task_types": ["eva"], "domain": "suit_systems"},
        prescribes=None,
        near_miss_note="EVA-scoped and mentions crew rest by reference, but explicitly defers it elsewhere.",
    ),
    Passage(
        passage_id="P-DUTY-3.5",
        doc="OPS-DUTY-03",
        section="3.5",
        title="Nominal duty period limits",
        text=(
            "Nominal crew duty shall not exceed the planned duty period without flight "
            "director concurrence. Extended duty is permitted for contingency response "
            "and shall be followed by a protected recovery period. This section defines "
            "planning limits and does not itself gate task execution."
        ),
        task_types=["science_ops", "maintenance"],
        applies_when={"phase": "planning"},
        prescribes=None,
        near_miss_note="Duty-hours vocabulary overlaps the workload rule (P-FAT-6.3) but sets planning limits only.",
    ),
    # ---- Ordinary corpus depth (retrieval noise) ------------------------
    Passage(
        passage_id="P-ROBO-9.1",
        doc="OPS-ROBO-09",
        section="9.1",
        title="Robotic capture operator staffing",
        text=(
            "Robotic capture operations shall be conducted with an operator at the "
            "control station and a second crew member monitoring free-drift status and "
            "capture envelope. Where the monitoring crew member is unavailable, capture "
            "shall be deferred to the next opportunity."
        ),
        task_types=["robotics_capture"],
        applies_when={"task_types": ["robotics_capture"], "domain": "staffing"},
        prescribes="task_deferral",
    ),
    Passage(
        passage_id="P-HAT-5.2",
        doc="OPS-HATCH-05",
        section="5.2",
        title="Hatch operation two-crew rule",
        text=(
            "Hatch opening and closing between pressurised elements shall be performed "
            "with two crew members present, one operating and one verifying seal and "
            "equalisation state. Single-crew hatch operation is prohibited except under "
            "declared emergency."
        ),
        task_types=["hatch_operation"],
        applies_when={"task_types": ["hatch_operation"], "domain": "staffing"},
        prescribes="second_operator_verify",
    ),
    Passage(
        passage_id="P-SCI-2.4",
        doc="OPS-SCI-14",
        section="2.4",
        title="Science payload operations scheduling",
        text=(
            "Payload operations may be rescheduled within the planning period at crew "
            "discretion provided sample viability constraints are met. Payload "
            "operations are not classified safety-critical unless explicitly annotated "
            "in the execution package."
        ),
        task_types=["science_ops"],
        applies_when={"task_types": ["science_ops"], "criticality_in": ["low"]},
        prescribes="no_action_required",
    ),
    # NOTE: there is deliberately NO passage governing crew fatigue during a
    # medical contingency. That gap is what drives the refusal scenario.
]


BY_ID: dict[str, Passage] = {p.passage_id: p for p in CORPUS}

DOCS: dict[str, str] = {
    "OPS-FATIGUE-04": "Crew Fatigue Management for Safety-Critical Task Execution",
    "OPS-SLEEP-02": "Crew Sleep Scheduling and Shifting",
    "OPS-DOCK-07": "Rendezvous, Proximity Operations and Docking",
    "OPS-EVA-11": "Extravehicular Activity Preparation and Execution",
    "OPS-DUTY-03": "Crew Duty Periods and Work-Rest Planning",
    "OPS-ROBO-09": "Robotic Operations and Capture",
    "OPS-HATCH-05": "Pressurised Element Hatch Operations",
    "OPS-SCI-14": "Science Payload Operations",
}


def compute_manifest(passages: list[Passage]) -> str:
    """A digest identifying exactly this rulebook.

    Every decision records the manifest of the corpus it was made under (S8).
    Without it, two evaluations that disagree cannot be told apart: was the
    reasoning different, or was the rulebook? Once Phase 4 compiles the corpus
    from source PDFs and versions it, that stops being a hypothetical -- the
    corpus becomes something that changes between deployments, and a decision
    that does not name its rulebook is not fully auditable.

    Covers every field that could change an admissibility verdict, a citation,
    or the claim made about where a rule came from. ``provenance`` is in the
    digest for that last reason: two corpora with identical rules, one claiming
    to be extracted from a standard and the other admitting it was written for
    this prototype, are materially different rulebooks to anyone auditing a
    decision made under them.

    ``authority`` is in for the same reason and a sharper one: a corpus that
    relabelled a handbook as a standard would otherwise digest identically to
    one that had not, while permitting recommendations the first would refuse.

    ``near_miss_note`` is excluded -- commentary for the corpus's readers that
    never reaches a decision -- and so is ``reviewed_by``, which records process
    rather than content: a second reviewer re-approving an unchanged encoding
    has not changed the rules.
    """
    digest = hashlib.sha256()
    for passage in sorted(passages, key=lambda p: p.passage_id):
        digest.update(
            json.dumps(
                {
                    "passage_id": passage.passage_id,
                    "doc": passage.doc,
                    "section": passage.section,
                    "title": passage.title,
                    "text": passage.text,
                    "task_types": passage.task_types,
                    "applies_when": passage.applies_when,
                    "prescribes": passage.prescribes,
                    "fallback_action": passage.fallback_action,
                    "source": passage.source,
                    "provenance": passage.provenance,
                    "authority": passage.authority,
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        )
    return digest.hexdigest()


def _load_compiled() -> list[Passage] | None:
    """A compiled corpus, when one is configured.

    ``HAVEN_CORPUS`` points at an artefact produced by ``compiler.cli emit``.
    Unset, the hand-authored corpus above is used -- which keeps a fresh clone
    working with no compilation step, and keeps the demo scenarios reproducible.

    The import is deliberately local and narrow. The compiler must not be
    reachable from the request path, and a test asserts that; this reads the
    artefact directly rather than importing anything under ``compiler/``.
    """
    configured = os.getenv("HAVEN_CORPUS", "").strip()
    if not configured:
        return None

    path = pathlib.Path(configured)
    if not path.exists():
        raise RuntimeError(f"HAVEN_CORPUS points at {path}, which does not exist")

    payload = json.loads(path.read_text(encoding="utf-8"))
    passages = [
        Passage(
            passage_id=item["passage_id"],
            doc=item["doc"],
            section=item["section"],
            title=item.get("title", ""),
            text=item["text"],
            task_types=list(item.get("task_types", [])),
            applies_when=dict(item.get("applies_when", {})),
            prescribes=item.get("prescribes"),
            fallback_action=item.get("fallback_action"),
            source=item.get("source", ""),
            near_miss_note=item.get("near_miss_note", ""),
            provenance=item.get("provenance", "extracted"),
            authority=item.get("authority", "authoritative"),
            reviewed_by=item.get("reviewed_by", ""),
        )
        for item in payload.get("passages", [])
    ]

    # Recomputed, never trusted. An artefact edited after compilation -- a
    # precondition widened by hand -- would otherwise load as though a reviewer
    # had approved it, and every decision made under it would record a manifest
    # naming a corpus that never existed.
    claimed = payload.get("manifest", "")
    recomputed = compute_manifest(passages)
    if claimed and claimed != recomputed:
        raise RuntimeError(
            f"{path.name} has been edited since it was compiled: it claims manifest "
            f"{claimed[:16]} but its passages digest to {recomputed[:16]}. Recompile."
        )
    return passages


_compiled = _load_compiled()
if _compiled is not None:
    CORPUS = _compiled
    BY_ID = {p.passage_id: p for p in CORPUS}

CORPUS_MANIFEST: str = compute_manifest(CORPUS)
