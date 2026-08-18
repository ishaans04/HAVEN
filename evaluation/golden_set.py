"""Labelled Situations, with the answer a correct reasoning tier must give.

Each case is a deterministic fact set plus the candidate passages retrieval
would surface, labelled with which passage governs -- or with `None`, meaning
the honest answer is that none do.

Two design choices worth stating.

**Cases with no governing rule are over-represented on purpose.** Selection
accuracy is the easy metric and the least interesting one: a system that always
picks the top-ranked candidate scores respectably on it. What distinguishes this
architecture is refusing when nothing applies, so refusal precision is the
number that matters, and it needs cases to be measured on.

**Every near-miss is labelled with why it fails**, not merely that it does. A
model that rejects the pre-EVA sleep-shifting rule because it dislikes the word
"shifting" is not doing the same thing as one that rejects it because the
passage says it is a planning activity, and only the second will transfer to a
procedure library it has not seen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from haven.rag.corpus import BY_ID

# The keys the reasoning tier is allowed to see. Anything outside this set is a
# compiled precondition and withholding it is S4.
PROSE_KEYS = ("passage_id", "doc", "section", "title", "text")


@dataclass(frozen=True)
class GoldenCase:
    """One Situation with a known-correct disposition."""

    case_id: str
    facts: dict
    candidate_ids: tuple[str, ...]
    # The passage that governs, or None when the correct answer is "none do".
    governs: str | None
    # passage_id -> the reason it does not govern, in the corpus's own terms.
    why_not: dict[str, str] = field(default_factory=dict)
    note: str = ""

    @property
    def should_refuse(self) -> bool:
        return self.governs is None

    def prose(self) -> list[dict]:
        """The candidate set as the reasoning tier sees it: prose, nothing else."""
        return [{k: getattr(BY_ID[pid], k) for k in PROSE_KEYS} for pid in self.candidate_ids]


def facts(
    task_type: str,
    criticality: str = "high",
    *,
    alertness: float = 0.61,
    workload: float = 58.0,
    circadian: bool = False,
    phase: str = "execution",
    hours_awake: float = 15.0,
    sleep_debt: float = 9.0,
) -> dict:
    """A deterministic fact set, in the shape the engine hands to the flow."""
    return {
        "crew_name": "T. Nakamura",
        "crew_role": "flight_engineer",
        "task_id": "T-000",
        "task_type": task_type,
        "criticality": criticality,
        "phase": phase,
        "alertness_score": alertness,
        "alertness_threshold": 0.70,
        "workload_score": workload,
        "circadian_flag": circadian,
        "hours_awake": hours_awake,
        "sleep_debt_h": sleep_debt,
        "kss": 6.0,
    }


PLANNING_SCOPE = "governs the planning phase, not execution"
VEHICLE_SCOPE = "governs vehicle state, not crew alertness"
SUIT_SCOPE = "defers crew rest status to the fatigue procedure"
DUTY_PLANNING = "sets planning limits and does not gate execution"
WRONG_TASK = "scoped to a different task family"
NO_ACTION = "states no prescribed action for this condition"


CASES: list[GoldenCase] = [
    # ---- the governing cases, one per rule in OPS-FATIGUE-04 -------------
    GoldenCase(
        "burn-governed",
        facts("orbital_burn"),
        ("P-FAT-4.2", "P-DCK-3.2"),
        "P-FAT-4.2",
        {"P-DCK-3.2": VEHICLE_SCOPE},
        "The core case. The docking approach rule shares the vocabulary and governs geometry.",
    ),
    GoldenCase(
        "eva-governed",
        facts("eva", alertness=0.55),
        ("P-FAT-4.4", "P-SLP-2.1", "P-EVA-11.3"),
        "P-FAT-4.4",
        {"P-SLP-2.1": PLANNING_SCOPE, "P-EVA-11.3": SUIT_SCOPE},
        "The headline discrimination case: two EVA-scoped near-misses beside the rule that governs.",
    ),
    GoldenCase(
        "circadian-governed",
        facts("robotics_capture", alertness=0.51, circadian=True),
        ("P-FAT-5.1", "P-ROBO-9.1"),
        "P-FAT-5.1",
        {"P-ROBO-9.1": "governs staffing, not crew alertness"},
        "Circadian phase is the discriminator; sleep totals alone would clear this.",
    ),
    GoldenCase(
        "workload-governed",
        facts("maintenance", "medium", alertness=0.66, workload=72.0),
        ("P-FAT-6.3", "P-DUTY-3.5"),
        "P-FAT-6.3",
        {"P-DUTY-3.5": DUTY_PLANNING},
        "Sustained duty load. The duty-limits passage shares the vocabulary and plans rather than gates.",
    ),
    GoldenCase(
        "docking-governed",
        facts("docking", alertness=0.64),
        ("P-FAT-4.2", "P-DCK-3.2"),
        "P-FAT-4.2",
        {"P-DCK-3.2": VEHICLE_SCOPE},
    ),
    # ---- no governing rule: the metric that matters ----------------------
    GoldenCase(
        "medical-contingency",
        facts("medical_contingency"),
        ("P-FAT-4.2", "P-DCK-3.2", "P-EVA-11.3"),
        None,
        {"P-FAT-4.2": WRONG_TASK, "P-DCK-3.2": VEHICLE_SCOPE, "P-EVA-11.3": SUIT_SCOPE},
        "The corpus gap. Nothing governs fatigue during a medical contingency.",
    ),
    GoldenCase(
        "eva-planning-phase",
        facts("eva", alertness=0.55, phase="planning"),
        ("P-SLP-2.1", "P-FAT-4.4"),
        # Labelled from the corpus as written, not from what it appears to mean.
        # P-FAT-4.4 reads as an execution gate ("shall not commence"), and
        # P-SLP-2.1 contrasts itself against "alertness shortfall detected during
        # execution" -- but 4.4 declares no `phase` clause, so it is admissible
        # here. See CHANGELOG O4: a latent fail-open, unreachable today because
        # the engine only ever evaluates at execution, and a decision Phase 4
        # has to make deliberately rather than inherit.
        "P-FAT-4.4",
        {"P-SLP-2.1": NO_ACTION},
        "Records the phase-scope gap rather than assuming it away.",
    ),
    GoldenCase(
        "vehicle-state-only",
        facts("docking", alertness=0.88),
        ("P-DCK-3.2",),
        None,
        {"P-DCK-3.2": VEHICLE_SCOPE},
        "A rested operator, and the only candidate governs geometry.",
    ),
    GoldenCase(
        "suit-systems-only",
        facts("eva", alertness=0.90),
        ("P-EVA-11.3", "P-SLP-2.1"),
        None,
        {"P-EVA-11.3": SUIT_SCOPE, "P-SLP-2.1": PLANNING_SCOPE},
        "Both candidates are EVA-scoped and neither addresses crew alertness during execution.",
    ),
    GoldenCase(
        "alertness-above-threshold",
        facts("orbital_burn", alertness=0.86),
        ("P-FAT-4.2", "P-DCK-3.2"),
        None,
        {"P-FAT-4.2": "requires alertness below the execution threshold", "P-DCK-3.2": VEHICLE_SCOPE},
        "The fatigue rule is the right rule for the wrong Situation.",
    ),
    GoldenCase(
        "workload-below-ceiling",
        facts("maintenance", "medium", alertness=0.80, workload=41.0),
        ("P-FAT-6.3", "P-DUTY-3.5"),
        None,
        {"P-FAT-6.3": "requires sustained duty above the ceiling", "P-DUTY-3.5": DUTY_PLANNING},
    ),
    GoldenCase(
        "circadian-clear",
        facts("robotics_capture", alertness=0.82, circadian=False),
        ("P-FAT-5.1", "P-ROBO-9.1"),
        None,
        {"P-FAT-5.1": "requires the task to fall in the circadian trough", "P-ROBO-9.1": "governs staffing"},
        "The circadian rule applies irrespective of sleep -- but only inside the trough.",
    ),
    GoldenCase(
        "empty-candidate-set",
        facts("medical_contingency"),
        (),
        None,
        note="Retrieval found nothing. The only honest answer is that none govern.",
    ),
    GoldenCase(
        "low-criticality-science",
        facts("science_ops", "low", alertness=0.62),
        ("P-SCI-2.4", "P-DUTY-3.5"),
        "P-SCI-2.4",
        {"P-DUTY-3.5": DUTY_PLANNING},
        "The one passage prescribing no_action_required. Proceeding is a decision too.",
    ),
    # ---- near-miss pressure: the governing rule buried in noise ----------
    GoldenCase(
        "burn-crowded",
        facts("orbital_burn"),
        ("P-DCK-3.2", "P-DUTY-3.5", "P-FAT-4.2", "P-SLP-2.1"),
        "P-FAT-4.2",
        {"P-DCK-3.2": VEHICLE_SCOPE, "P-DUTY-3.5": DUTY_PLANNING, "P-SLP-2.1": PLANNING_SCOPE},
        "Three near-misses and one rule, with the rule ranked third.",
    ),
    GoldenCase(
        "eva-crowded",
        facts("eva", alertness=0.52),
        ("P-SLP-2.1", "P-EVA-11.3", "P-HAT-5.2", "P-FAT-4.4"),
        "P-FAT-4.4",
        {"P-SLP-2.1": PLANNING_SCOPE, "P-EVA-11.3": SUIT_SCOPE, "P-HAT-5.2": WRONG_TASK},
    ),
    GoldenCase(
        "hatch-staffing-not-fatigue",
        facts("hatch_operation", "medium", alertness=0.60),
        ("P-HAT-5.2", "P-FAT-4.2"),
        None,
        {"P-HAT-5.2": "governs staffing, not crew alertness", "P-FAT-4.2": WRONG_TASK},
        "A two-crew rule is not a fatigue rule, however much it looks like second-operator verification.",
    ),
    GoldenCase(
        "robotics-staffing-only",
        facts("robotics_capture", alertness=0.63),
        ("P-ROBO-9.1",),
        None,
        {"P-ROBO-9.1": "governs staffing, not crew alertness"},
    ),
    # ---- criticality boundaries -----------------------------------------
    GoldenCase(
        "burn-medium-criticality",
        facts("orbital_burn", "medium", alertness=0.55),
        ("P-FAT-4.2",),
        "P-FAT-4.2",
        note="4.2 applies at medium as well as high.",
    ),
    GoldenCase(
        "circadian-medium-criticality",
        facts("robotics_capture", "medium", alertness=0.50, circadian=True),
        ("P-FAT-5.1",),
        None,
        {"P-FAT-5.1": "applies at high criticality only"},
        "5.1 is scoped to high criticality; medium is outside it even inside the trough.",
    ),
]


BY_CASE_ID: dict[str, GoldenCase] = {c.case_id: c for c in CASES}

GOVERNING_CASES = [c for c in CASES if not c.should_refuse]
REFUSAL_CASES = [c for c in CASES if c.should_refuse]
