"""Demo scenarios.

Each scenario is a fully-specified request in the locked contract's shape. They
exist to exercise every branch the PRD names -- in particular the two that
matter most: correct discrimination against a confusable near-miss, and correct
refusal when no procedure governs.

Nothing here is bypassed at runtime. A scenario supplies inputs; the same engine
path runs over them as would run over live data.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from haven.data.crew import WINDOW_END, WINDOW_START, make_crew, task


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    subtitle: str
    note: str
    demonstrates: str
    build: Callable[[], dict]


def _request(crew: list[dict], tasks: list[dict], scenario_id: str) -> dict:
    return {
        "evaluation_window": {"start": WINDOW_START, "end": WINDOW_END},
        "crew": crew,
        "tasks": tasks,
        "scenario_id": scenario_id,
    }


# --------------------------------------------------------------------------
def _nominal_ops() -> dict:
    crew = [
        make_crew("CM-01", "rested"),
        make_crew("CM-02", "rested"),
        make_crew("CM-03", "mild", "light"),
        make_crew("CM-04", "rested", "light"),
        make_crew("CM-05", "mild", "light"),
        make_crew("CM-06", "rested"),
    ]
    tasks = [
        task("T-101", "science_ops", "low", 9.5, "CM-05", "Combustion rack sample exchange"),
        task("T-102", "docking", "high", 14.0, "CM-06", "Cargo vehicle docking", 120),
        task("T-103", "maintenance", "medium", 16.5, "CM-03", "CDRA bed replacement", 90),
        task("T-104", "hatch_operation", "medium", 18.0, "CM-02", "Node 2 hatch closeout", 30),
    ]
    return _request(crew, tasks, "nominal_ops")


def _burn_fatigue() -> dict:
    crew = [
        make_crew("CM-01", "restricted", "heavy"),
        make_crew("CM-02", "mild"),
        make_crew("CM-03", "rested"),
        make_crew("CM-04", "mild", "light"),
        make_crew("CM-05", "rested", "light"),
        make_crew("CM-06", "rested"),
    ]
    tasks = [
        task("T-118", "science_ops", "low", 8.5, "CM-05", "Plant habitat imaging"),
        task("T-119", "orbital_burn", "high", 12.67, "CM-01", "Reboost burn, +2.1 m/s", 45),
        task("T-120", "maintenance", "medium", 15.0, "CM-03", "Water processor filter swap", 90),
        task("T-121", "hatch_operation", "medium", 19.5, "CM-02", "Vestibule hatch closeout", 30),
    ]
    return _request(crew, tasks, "burn_fatigue")


def _eva_near_miss() -> dict:
    crew = [
        make_crew("CM-01", "rested"),
        make_crew("CM-02", "mild"),
        make_crew("CM-03", "rested"),
        make_crew("CM-04", "restricted", "heavy"),
        make_crew("CM-05", "mild", "light"),
        make_crew("CM-06", "rested"),
    ]
    tasks = [
        task("T-140", "eva", "high", 11.5, "CM-04", "EVA 82: radiator beam inspection", 390),
        task("T-141", "robotics_capture", "high", 11.5, "CM-06", "SSRMS support for EVA 82", 390),
        task("T-142", "science_ops", "low", 20.0, "CM-05", "Microgravity science glovebox run"),
    ]
    return _request(crew, tasks, "eva_near_miss")


def _no_procedure() -> dict:
    crew = [
        make_crew("CM-01", "mild"),
        make_crew("CM-02", "restricted", "heavy"),
        make_crew("CM-03", "rested"),
        make_crew("CM-04", "mild", "light"),
        make_crew("CM-05", "rested", "light"),
        make_crew("CM-06", "mild"),
    ]
    tasks = [
        task(
            "T-160",
            "medical_contingency",
            "high",
            11.5,
            "CM-02",
            "Crew medical contingency response, ground comm degraded",
            120,
        ),
        task("T-161", "science_ops", "low", 15.0, "CM-05", "Protein crystal growth checkpoint"),
    ]
    return _request(crew, tasks, "no_procedure")


def _roster_block() -> dict:
    # Every docking-qualified alternate is either fatigued or committed to
    # another safety-critical task in the same window.
    crew = [
        make_crew("CM-01", "restricted", "heavy"),
        make_crew("CM-02", "restricted", "heavy"),
        make_crew("CM-03", "restricted", "heavy"),
        make_crew("CM-04", "mild", "light"),
        make_crew("CM-05", "mild", "light"),
        make_crew("CM-06", "rested"),
    ]
    tasks = [
        task("T-180", "docking", "high", 12.0, "CM-01", "Crew vehicle docking, manual takeover armed", 120),
        task("T-181", "robotics_capture", "high", 12.0, "CM-06", "Free-flyer capture, concurrent op", 120),
        task("T-182", "science_ops", "low", 17.0, "CM-04", "Earth observation pass"),
    ]
    return _request(crew, tasks, "roster_block")


def _thin_data() -> dict:
    crew = [
        make_crew("CM-01", "rested"),
        make_crew("CM-02", "mild"),
        make_crew("CM-03", "rested"),
        make_crew("CM-04", "mild", "light"),
        make_crew("CM-05", "sparse_record", "sparse"),
        make_crew("CM-06", "rested"),
    ]
    tasks = [
        task("T-190", "hatch_operation", "high", 4.5, "CM-05", "Emergency hatch drill, off-nominal timing", 45),
        task("T-191", "science_ops", "low", 14.0, "CM-04", "Fluid physics run"),
    ]
    return _request(crew, tasks, "thin_data")


def _circadian_trap() -> dict:
    crew = [
        make_crew("CM-01", "rested"),
        make_crew("CM-02", "rested"),
        make_crew("CM-03", "early_call", "light"),
        make_crew("CM-04", "mild", "light"),
        make_crew("CM-05", "rested", "light"),
        make_crew("CM-06", "mild"),
    ]
    tasks = [
        task("T-201", "robotics_capture", "high", 3.33, "CM-03", "Unplanned free-flyer capture, 03:20 window", 90),
        task("T-202", "science_ops", "low", 13.0, "CM-05", "Rodent research habitat servicing"),
    ]
    return _request(crew, tasks, "circadian_trap")


def _provider_outage() -> dict:
    return _burn_fatigue() | {"scenario_id": "provider_outage"}


SCENARIOS: list[Scenario] = [
    Scenario(
        id="burn_fatigue",
        title="Reboost burn under chronic sleep restriction",
        subtitle="The core case",
        note=(
            "The commander has run a restricted sleep pattern for six nights and is assigned a "
            "high-criticality reboost burn at 12:40. Sleep debt is the driver, not a single bad night."
        ),
        demonstrates="Rule selection, citation, and a staffed second-operator recommendation.",
        build=_burn_fatigue,
    ),
    Scenario(
        id="eva_near_miss",
        title="EVA with a confusable near-miss in the candidate set",
        subtitle="Discrimination",
        note=(
            "Retrieval surfaces the pre-EVA sleep-shifting protocol and the suit pre-breathe section "
            "alongside the rule that actually governs. Both near-misses are EVA-scoped with heavy keyword "
            "overlap; only one passage's preconditions are satisfied during execution."
        ),
        demonstrates="Reasoning beating similarity: the top lexical match is rejected with a stated reason.",
        build=_eva_near_miss,
    ),
    Scenario(
        id="no_procedure",
        title="Fatigue during a medical contingency",
        subtitle="Refusal",
        note=(
            "No passage in the corpus governs crew fatigue during a medical contingency. The system "
            "searches, finds nothing whose preconditions match, and escalates instead of reaching for "
            "the nearest plausible rule."
        ),
        demonstrates="Refusal as a first-class output, with the full searched set recorded.",
        build=_no_procedure,
    ),
    Scenario(
        id="roster_block",
        title="Recommendation that cannot be staffed",
        subtitle="Schedule-impact veto",
        note=(
            "The governing rule prescribes second-operator verification, but every qualified alternate is "
            "either below the alertness floor or committed to a concurrent safety-critical task. The "
            "deterministic screen blocks the primary action and falls back to the deferral the same "
            "passage prescribes."
        ),
        demonstrates="A deterministic screen overriding a well-formed AI recommendation.",
        build=_roster_block,
    ),
    Scenario(
        id="circadian_trap",
        title="Adequate sleep, wrong hour",
        subtitle="Circadian awareness",
        note=(
            "The operator is woken for an unplanned 03:20 capture. Nightly sleep totals look acceptable, "
            "so a duty-hours check would pass this. Circadian phase and sleep inertia do not."
        ),
        demonstrates="The circadian term catching a case sleep totals alone would clear.",
        build=_circadian_trap,
    ),
    Scenario(
        id="thin_data",
        title="Sparse sleep record",
        subtitle="Confidence gate",
        note=(
            "Most of the operator's sleep record is missing from the downlink. The confidence gate "
            "withholds before the reasoning tier is invoked -- the data gap is the finding."
        ),
        demonstrates="Withholding instead of asserting false certainty on thin input.",
        build=_thin_data,
    ),
    Scenario(
        id="nominal_ops",
        title="Nominal operations",
        subtitle="Quiet system",
        note=(
            "A rested crew on a normal timeline. Every task is archived as low-risk and no Situation is "
            "raised. Shown because a monitoring system that never goes quiet cannot be trusted when it "
            "speaks."
        ),
        demonstrates="Correct silence, and the audit bar distinguishing quiet from broken.",
        build=_nominal_ops,
    ),
    Scenario(
        id="provider_outage",
        title="Reasoning provider unavailable",
        subtitle="Degraded mode",
        note=(
            "The same reboost-burn inputs, with the reasoning provider unreachable. The system does not "
            "guess from the deterministic tier alone: it declares degraded mode, hands the operator the "
            "raw evidence, and escalates."
        ),
        demonstrates="Failing loudly rather than silently downgrading to unreasoned output.",
        build=_provider_outage,
    ),
]

BY_ID = {s.id: s for s in SCENARIOS}
