"""NASA Task Load Index (NASA-TLX).

Six subscales, each rated 0-100, combined using pairwise-comparison weights that
sum to 15. The weighted score is sum(rating * weight) / 15, which is the
published formulation (Hart & Staveland, 1988).

Part of the deterministic tier: workload numbers originate here and nowhere
else.
"""

from __future__ import annotations

from dataclasses import dataclass

SUBSCALES = (
    "mental_demand",
    "physical_demand",
    "temporal_demand",
    "performance",
    "effort",
    "frustration",
)

WEIGHT_TOTAL = 15  # number of pairwise comparisons among six subscales


@dataclass(frozen=True)
class TLXRatings:
    """Raw subscale ratings, 0-100.

    ``performance`` is entered already reversed (0 = perfect, 100 = failure), as
    NASA-TLX scoring requires, so that higher is worse on every subscale.
    """

    mental_demand: float
    physical_demand: float
    temporal_demand: float
    performance: float
    effort: float
    frustration: float

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in SUBSCALES}


@dataclass(frozen=True)
class TLXWeights:
    """Pairwise-comparison tallies. Must sum to 15."""

    mental_demand: int
    physical_demand: int
    temporal_demand: int
    performance: int
    effort: int
    frustration: int

    def __post_init__(self) -> None:
        total = sum(getattr(self, name) for name in SUBSCALES)
        if total != WEIGHT_TOTAL:
            raise ValueError(f"NASA-TLX weights must sum to {WEIGHT_TOTAL}, got {total}")

    def as_dict(self) -> dict[str, int]:
        return {name: int(getattr(self, name)) for name in SUBSCALES}


# Weight profiles observed for these task families in aerospace operations.
# Held here rather than asked of the crew mid-operation.
TASK_WEIGHT_PROFILES: dict[str, TLXWeights] = {
    "orbital_burn": TLXWeights(4, 1, 4, 3, 2, 1),
    "docking": TLXWeights(5, 1, 4, 3, 1, 1),
    "eva": TLXWeights(3, 4, 2, 3, 2, 1),
    "hatch_operation": TLXWeights(3, 3, 2, 4, 2, 1),
    "robotics_capture": TLXWeights(5, 2, 3, 3, 1, 1),
    "science_ops": TLXWeights(3, 2, 2, 3, 3, 2),
    "maintenance": TLXWeights(2, 4, 2, 3, 3, 1),
    "medical_contingency": TLXWeights(4, 2, 4, 3, 1, 1),
    "default": TLXWeights(3, 2, 3, 3, 3, 1),
}


@dataclass(frozen=True)
class WorkloadResult:
    score: float  # 0-100, weighted
    raw_mean: float  # 0-100, unweighted, for comparison
    subscales: dict[str, float]
    weights: dict[str, int]
    band: str  # low | moderate | high | very_high
    profile: str

    def as_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "raw_mean": round(self.raw_mean, 1),
            "subscales": {k: round(v, 1) for k, v in self.subscales.items()},
            "weights": self.weights,
            "band": self.band,
            "profile": self.profile,
        }


def band_for(score: float) -> str:
    if score < 40:
        return "low"
    if score < 60:
        return "moderate"
    if score < 80:
        return "high"
    return "very_high"


def score(ratings: TLXRatings, task_type: str = "default") -> WorkloadResult:
    """Weighted NASA-TLX for one crew member against one task family."""
    profile = task_type if task_type in TASK_WEIGHT_PROFILES else "default"
    weights = TASK_WEIGHT_PROFILES[profile]

    r = ratings.as_dict()
    w = weights.as_dict()
    weighted = sum(r[name] * w[name] for name in SUBSCALES) / WEIGHT_TOTAL
    raw_mean = sum(r.values()) / len(SUBSCALES)

    return WorkloadResult(
        score=float(weighted),
        raw_mean=float(raw_mean),
        subscales=r,
        weights=w,
        band=band_for(weighted),
        profile=profile,
    )


def from_duty_load(
    duty_hours_24h: float,
    concurrent_tasks: int,
    task_type: str,
    criticality: str,
) -> TLXRatings:
    """Derive plausible subscale ratings from observable duty data.

    v1 takes batch operational inputs rather than crew self-report, so subscale
    ratings are estimated from duty hours, task concurrency, and task family.
    The mapping is linear and inspectable on purpose -- a reviewer can check it
    by hand, which is the point of keeping it in the deterministic tier.
    """
    duty_pressure = min(100.0, (duty_hours_24h / 12.0) * 100.0)
    concurrency_pressure = min(100.0, concurrent_tasks * 22.0)
    criticality_pressure = {"low": 25.0, "medium": 50.0, "high": 78.0}.get(criticality, 50.0)

    physical = {"eva": 88.0, "maintenance": 62.0, "hatch_operation": 55.0}.get(task_type, 28.0)
    mental = {"docking": 85.0, "orbital_burn": 80.0, "robotics_capture": 84.0}.get(task_type, 58.0)

    return TLXRatings(
        mental_demand=min(100.0, mental * 0.7 + criticality_pressure * 0.3),
        physical_demand=physical,
        temporal_demand=min(100.0, duty_pressure * 0.55 + concurrency_pressure * 0.45),
        performance=min(100.0, criticality_pressure * 0.6 + duty_pressure * 0.4),
        effort=min(100.0, duty_pressure * 0.6 + concurrency_pressure * 0.4),
        frustration=min(100.0, concurrency_pressure * 0.7 + max(0.0, duty_hours_24h - 8) * 6.0),
    )
