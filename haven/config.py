"""HAVEN configuration.

Every threshold that can change a safety outcome lives here, in one place, so it
can be reviewed as a unit. Nothing in the reasoning tier may read or alter these
at runtime -- they are inputs to the deterministic tier only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Thresholds:
    """Deterministic gates. See PRD section 4 (stages 3 and 6) and section 6."""

    # --- Stage 3: trigger -------------------------------------------------
    # Alertness is normalised 0-1 (1.0 = fully alert). At or below these values
    # a task of the matching criticality raises a Situation.
    alertness_trigger_high: float = 0.70
    alertness_trigger_medium: float = 0.58
    alertness_trigger_low: float = 0.45

    # NASA-TLX weighted workload, 0-100. At or above this a Situation is raised
    # regardless of alertness.
    workload_trigger: float = 65.0

    # Risk banding on the composite (alertness + workload + criticality).
    risk_elevated_at: float = 0.20
    risk_critical_at: float = 0.42

    # --- Stage 4/5: retrieval + reasoning ---------------------------------
    # DISPLAY ONLY since Phase 1B. This was the v1 relevance gate: a TF-IDF
    # similarity float compared against a threshold, with the comparison treated
    # as a decision about whether a rule governs. It is not one -- similarity is
    # a property of wording, admissibility is a property of the rule -- so that
    # branch is gone and ``deterministic/preconditions.py`` settles the question
    # clause by clause instead. The number survives so refusal payloads can show
    # an operator the retrieval floor that was in force beside the closest
    # candidate's score. Nothing may branch on it; a test in
    # ``tests/test_propose_dispose.py`` scans the package and enforces that.
    relevance_gate: float = 0.45
    # Number of candidate passages handed to the reasoning tier. Deliberately
    # generous so confusable near-misses are included (PRD 4, stage 4).
    retrieval_top_k: int = 4

    # --- Stage 6: screens -------------------------------------------------
    # Record completeness over the trailing lookback, scored as the fraction of
    # expected sleep *and* duty records actually present.
    confidence_full_coverage: float = 0.85
    confidence_low_coverage: float = 0.60
    # Below this the input cannot support a recommendation at all.
    confidence_minimum: float = 0.40
    # An alternate operator must be at least this alert to be counted as
    # available cover by the schedule-impact screen.
    alternate_min_alertness: float = 0.72

    # --- Circadian --------------------------------------------------------
    # Local biological hours considered the circadian trough.
    circadian_low_start_hour: float = 2.0
    circadian_low_end_hour: float = 6.0


@dataclass(frozen=True)
class LLMSettings:
    """Reasoning-tier provider selection.

    ``mock`` is the default so the prototype runs with no external service. The
    watsonx and ollama adapters implement the same interface; switching is a
    config change, not a code change (PRD section 3).
    """

    provider: str = field(default_factory=lambda: os.getenv("HAVEN_LLM_PROVIDER", "mock"))
    model_id: str = field(default_factory=lambda: os.getenv("HAVEN_LLM_MODEL", "ibm/granite-3-8b-instruct"))
    watsonx_url: str = field(default_factory=lambda: os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"))
    watsonx_api_key: str = field(default_factory=lambda: os.getenv("WATSONX_API_KEY", ""))
    watsonx_project_id: str = field(default_factory=lambda: os.getenv("WATSONX_PROJECT_ID", ""))
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434"))
    request_timeout_s: float = 30.0


@dataclass(frozen=True)
class RetrievalSettings:
    """Vector-store selection for the procedure corpus."""

    # ``inprocess`` is a dependency-free stand-in with the same interface as the
    # ChromaDB-backed store. Set HAVEN_VECTOR_STORE=chroma to use real Chroma.
    backend: str = field(default_factory=lambda: os.getenv("HAVEN_VECTOR_STORE", "inprocess"))
    collection: str = "haven_procedures"
    embedding_model: str = field(
        default_factory=lambda: os.getenv("HAVEN_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    )


THRESHOLDS = Thresholds()
LLM = LLMSettings()
RETRIEVAL = RetrievalSettings()

# Displayed in the audit bar so an operator can tell a mocked tier from a live one.
BUILD_MODE = os.getenv("HAVEN_BUILD_MODE", "prototype")
