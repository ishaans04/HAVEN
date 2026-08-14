"""Crew roster and sleep/duty history generation.

HONESTY NOTE (PRD section 10): the roster below is a *representative* six-person
expedition crew with the role mix, qualification structure, and increment shape
of a real ISS expedition. Names are not real astronauts -- modelled fatigue
states should not be attached to identifiable people, and swapping in a public
roster is a data change, not a code change.

Sleep and duty histories are synthetic and labelled as such. They are generated
from explicit per-night parameters so every scenario is reproducible: identical
inputs always produce identical numbers, which is one of the PRD's success
metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

WINDOW_START = datetime.fromisoformat("2026-08-20T00:00:00+00:00")
WINDOW_END = WINDOW_START + timedelta(days=1)

SAFETY_CRITICAL_ROLES = ("commander", "flight_engineer")


@dataclass
class CrewProfile:
    id: str
    name: str
    role: str
    qualified_for: list[str]
    circadian_offset_h: float = 0.0
    # (bedtime hour UTC, duration hours) for each night, most recent last.
    nights: list[tuple[float, float]] = field(default_factory=list)
    duty_blocks: list[tuple[float, float]] = field(default_factory=list)  # (start hour, duration h) per day
    baseline_alertness: float = 0.0


ROSTER: dict[str, dict] = {
    "CM-01": {
        "name": "R. Alvarez",
        "role": "commander",
        "qualified_for": ["orbital_burn", "docking", "eva", "robotics_capture", "hatch_operation"],
    },
    "CM-02": {
        "name": "T. Nakamura",
        "role": "flight_engineer",
        "qualified_for": ["docking", "eva", "robotics_capture", "hatch_operation", "medical_contingency"],
    },
    "CM-03": {
        "name": "L. Petrova",
        "role": "flight_engineer",
        "qualified_for": ["orbital_burn", "docking", "robotics_capture", "hatch_operation", "maintenance"],
    },
    "CM-04": {
        "name": "S. Okafor",
        "role": "mission_specialist",
        "qualified_for": ["eva", "robotics_capture", "science_ops", "hatch_operation"],
    },
    "CM-05": {
        "name": "D. Brandt",
        "role": "mission_specialist",
        "qualified_for": ["science_ops", "maintenance", "hatch_operation"],
    },
    "CM-06": {
        "name": "M. Chen",
        "role": "flight_engineer",
        "qualified_for": ["orbital_burn", "docking", "eva", "robotics_capture", "hatch_operation"],
    },
}

# Named sleep patterns, most recent night last. Nights are generated backwards
# from the evaluation window start. Bedtime is expressed in hours from the start
# of that night's calendar day, so an after-midnight bedtime is written as 24.5
# rather than 0.5 -- that keeps every night attached to the right day.
PATTERNS: dict[str, list[tuple[float, float]]] = {
    # Consolidated 8 h nights: the reference "rested" state.
    "rested": [(22.0, 8.0)] * 6,
    # Chronic restriction across the increment: the long-duration profile.
    "restricted": [(23.5, 6.2), (23.5, 5.6), (24.5, 5.1), (24.5, 4.6), (25.0, 4.4), (25.0, 4.3)],
    # Acute single-night loss on top of an otherwise normal record.
    "acute_loss": [(22.0, 8.0), (22.0, 7.8), (22.0, 7.6), (22.0, 7.9), (22.0, 7.7), (25.5, 3.6)],
    # Woken early for an off-nominal task: sleep looks adequate on paper.
    "early_call": [(22.0, 7.8), (22.0, 7.6), (22.0, 7.5), (22.0, 7.4), (22.0, 7.2), (22.0, 4.5)],
    # Sparse record: the two most recent nights are missing from the downlink.
    "sparse_record": [(22.0, 7.5), (22.0, 7.2)],
    # Moderately short but not alarming.
    "mild": [(23.0, 7.0), (23.0, 6.8), (23.0, 6.6), (23.5, 6.5), (23.5, 6.4), (23.5, 6.3)],
}

DUTY_PATTERNS: dict[str, list[tuple[float, float]]] = {
    "standard": [(8.0, 9.5)] * 6,
    "heavy": [(7.0, 12.0), (7.0, 12.5), (6.5, 13.0), (6.5, 12.5), (6.0, 13.5), (6.0, 13.0)],
    "light": [(9.0, 7.0)] * 6,
    # Duty records absent entirely -- the downlink gap covers both streams.
    "sparse": [],
}


def build_sleep_log(nights: list[tuple[float, float]], window_start: datetime = WINDOW_START) -> list[dict]:
    """Expand a night pattern into concrete sleep episodes.

    ``nights[-1]`` is the night immediately preceding the window. One further
    planned night is appended so the model can project alertness across the
    whole evaluation window rather than falling off the end of the record.
    """
    episodes: list[dict] = []
    count = len(nights)
    for index, (bedtime_h, duration_h) in enumerate(nights):
        days_back = count - index
        base = window_start - timedelta(days=days_back)
        sleep = base.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=bedtime_h)
        episodes.append({"sleep": sleep, "wake": sleep + timedelta(hours=duration_h)})
    # Planned sleep for the night inside the window.
    last_bed, last_dur = nights[-1]
    planned = window_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=last_bed)
    episodes.append({"sleep": planned, "wake": planned + timedelta(hours=last_dur)})
    return episodes


def build_duty_log(
    blocks: list[tuple[float, float]],
    task_type: str = "science_ops",
    window_start: datetime = WINDOW_START,
) -> list[dict]:
    entries: list[dict] = []
    count = len(blocks)
    for index, (start_h, duration_h) in enumerate(blocks):
        days_back = count - index
        base = (window_start - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
        start = base + timedelta(hours=start_h)
        entries.append({"start": start, "end": start + timedelta(hours=duration_h), "task_type": task_type})
    return entries


def duty_hours_24h(duty_log: list[dict], at: datetime) -> float:
    """Duty hours in the trailing 24 h, used as a NASA-TLX input."""
    cutoff = at - timedelta(hours=24)
    total = 0.0
    for entry in duty_log:
        start, end = max(entry["start"], cutoff), min(entry["end"], at)
        if end > start:
            total += (end - start).total_seconds() / 3600.0
    return total


def make_crew(
    crew_id: str,
    sleep_pattern: str,
    duty_pattern: str = "standard",
    circadian_offset_h: float = 0.0,
    window_start: datetime = WINDOW_START,
) -> dict:
    """Assemble one crew member payload in the locked contract's shape."""
    profile = ROSTER[crew_id]
    return {
        "id": crew_id,
        "name": profile["name"],
        "role": profile["role"],
        "qualified_for": profile["qualified_for"],
        "circadian_offset_h": circadian_offset_h,
        "sleep_log": build_sleep_log(PATTERNS[sleep_pattern], window_start),
        "duty_log": build_duty_log(DUTY_PATTERNS[duty_pattern], window_start=window_start),
    }


def task(
    task_id: str,
    task_type: str,
    criticality: str,
    hour: float,
    assigned_to: str,
    label: str,
    duration_min: int = 60,
    window_start: datetime = WINDOW_START,
) -> dict:
    # Round to the minute so a fractional hour like 3.3333 lands on 03:20
    # rather than 03:19:59 and displays as 03:19.
    scheduled = window_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=round(hour * 60))
    return {
        "id": task_id,
        "type": task_type,
        "criticality": criticality,
        "scheduled": scheduled,
        "assigned_to": assigned_to,
        "duration_min": duration_min,
        "label": label,
    }
