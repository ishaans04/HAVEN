"""Three-Process Model of Alertness (Akerstedt & Folkard).

Alertness A(t) = S(t) + C(t) + W(t) on the model's native 1-16 scale, where

    S  homeostatic sleep pressure: exponential decay awake, exponential
       recovery asleep
    C  circadian process: 24 h fundamental plus a 12 h harmonic that produces
       the post-prandial dip
    W  sleep inertia: a negative transient decaying over the first hours after
       waking

Reference parameters are those published for the model (Akerstedt & Folkard,
1997, "The three-process model of alertness and its extension to performance,
sleep latency, and sleep length", Chronobiology International 14(2)).

This module is part of the deterministic tier. It emits numbers. It contains no
language generation and is never given LLM output as an input.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

# --- Published model constants ------------------------------------------
LOWER_ASYMPTOTE = 2.4  # S floor during extended wakefulness
UPPER_ASYMPTOTE = 14.3  # S ceiling during recovery sleep
WAKE_DECAY_RATE = 0.0353  # per hour, S decay while awake
SLEEP_RECOVERY_RATE = 0.381  # per hour, S recovery while asleep

CIRCADIAN_AMPLITUDE = 2.5  # 24 h fundamental
CIRCADIAN_HARMONIC = 0.7  # 12 h harmonic (afternoon dip)
CIRCADIAN_ACROPHASE_H = 16.8  # local biological hour of peak alertness

INERTIA_MAGNITUDE = 5.72  # W at the moment of waking
INERTIA_DECAY_H = 1.0  # time constant, hours

SCALE_MIN = 1.0
SCALE_MAX = 16.0


@dataclass(frozen=True)
class SleepEpisode:
    """One consolidated sleep period."""

    sleep: datetime
    wake: datetime

    @property
    def duration_h(self) -> float:
        return (self.wake - self.sleep).total_seconds() / 3600.0


@dataclass(frozen=True)
class AlertnessSample:
    """Alertness decomposed into its three processes at one instant."""

    at: datetime
    homeostatic: float
    circadian: float
    inertia: float
    raw: float  # S + C + W, on the 1-16 scale
    score: float  # normalised 0-1, the figure the rest of HAVEN consumes
    kss: float  # Karolinska Sleepiness Scale equivalent, 1-9
    hours_awake: float
    in_circadian_low: bool

    def as_dict(self) -> dict:
        return {
            "at": self.at.isoformat().replace("+00:00", "Z"),
            "homeostatic": round(self.homeostatic, 3),
            "circadian": round(self.circadian, 3),
            "inertia": round(self.inertia, 3),
            "raw": round(self.raw, 3),
            "score": round(self.score, 3),
            "kss": round(self.kss, 2),
            "hours_awake": round(self.hours_awake, 2),
            "in_circadian_low": self.in_circadian_low,
        }


def _hours(a: datetime, b: datetime) -> float:
    return (a - b).total_seconds() / 3600.0


def circadian(at: datetime, acrophase_offset_h: float = 0.0) -> float:
    """Process C at ``at``.

    ``acrophase_offset_h`` shifts the individual's biological day, which is how
    a crew member on a slam-shifted timeline is represented.
    """
    clock_h = at.hour + at.minute / 60.0 + at.second / 3600.0
    phase = clock_h - CIRCADIAN_ACROPHASE_H - acrophase_offset_h
    fundamental = CIRCADIAN_AMPLITUDE * np.cos(2 * np.pi * phase / 24.0)
    harmonic = CIRCADIAN_HARMONIC * np.cos(4 * np.pi * phase / 24.0)
    return float(fundamental + harmonic)


def inertia(hours_awake: float) -> float:
    """Process W. Negative, largest at wake, effectively gone by ~4 h."""
    if hours_awake < 0:
        return 0.0
    return float(-INERTIA_MAGNITUDE * np.exp(-hours_awake / INERTIA_DECAY_H))


def _decay_awake(s0: float, hours: float) -> float:
    return float(LOWER_ASYMPTOTE + (s0 - LOWER_ASYMPTOTE) * np.exp(-WAKE_DECAY_RATE * hours))


def _recover_asleep(s0: float, hours: float) -> float:
    return float(UPPER_ASYMPTOTE - (UPPER_ASYMPTOTE - s0) * np.exp(-SLEEP_RECOVERY_RATE * hours))


def normalise(raw: float) -> float:
    """Map the model's 1-16 alertness onto the 0-1 score used by the contract."""
    return float(np.clip((raw - SCALE_MIN) / (SCALE_MAX - SCALE_MIN), 0.0, 1.0))


def to_kss(raw: float) -> float:
    """Approximate Karolinska Sleepiness Scale (1 alert - 9 very sleepy)."""
    return float(np.clip(9.0 - 8.0 * (raw - SCALE_MIN) / (SCALE_MAX - SCALE_MIN), 1.0, 9.0))


class ThreeProcessModel:
    """Integrates S forward through a crew member's sleep/wake history.

    The trace is built once per evaluation from the sleep log, then queried at
    arbitrary instants -- including instants in the future, where the model
    projects forward under the planned sleep schedule.
    """

    def __init__(
        self,
        sleep_log: list[SleepEpisode],
        acrophase_offset_h: float = 0.0,
        initial_s: float = 12.5,
    ) -> None:
        self.sleep_log = sorted(sleep_log, key=lambda e: e.sleep)
        self.acrophase_offset_h = acrophase_offset_h
        self.initial_s = initial_s
        if not self.sleep_log:
            raise ValueError("Three-Process Model requires at least one sleep episode")
        # S is integrated from the first wake in the record.
        self._origin = self.sleep_log[0].wake
        self._s_at_origin = initial_s

    @property
    def origin(self) -> datetime:
        return self._origin

    def last_wake_before(self, at: datetime) -> datetime | None:
        candidates = [e.wake for e in self.sleep_log if e.wake <= at]
        return max(candidates) if candidates else None

    def is_asleep(self, at: datetime) -> bool:
        return any(e.sleep <= at < e.wake for e in self.sleep_log)

    def homeostatic(self, at: datetime) -> float:
        """Process S, integrated piecewise across every sleep/wake transition."""
        if at <= self._origin:
            return self._s_at_origin

        s = self._s_at_origin
        cursor = self._origin

        for episode in self.sleep_log:
            if episode.wake <= self._origin:
                continue  # already consumed by the origin
            if episode.sleep >= at:
                break
            # Awake from cursor until this episode's sleep onset (or until `at`).
            wake_until = min(episode.sleep, at)
            if wake_until > cursor:
                s = _decay_awake(s, _hours(wake_until, cursor))
                cursor = wake_until
            if at <= episode.sleep:
                return s
            # Asleep from onset until wake (or until `at`).
            sleep_until = min(episode.wake, at)
            if sleep_until > cursor:
                s = _recover_asleep(s, _hours(sleep_until, cursor))
                cursor = sleep_until
            if at <= episode.wake:
                return s

        if at > cursor:
            s = _decay_awake(s, _hours(at, cursor))
        return s

    def sample(self, at: datetime) -> AlertnessSample:
        s = self.homeostatic(at)
        c = circadian(at, self.acrophase_offset_h)
        last_wake = self.last_wake_before(at)
        asleep = self.is_asleep(at)
        hours_awake = _hours(at, last_wake) if last_wake and not asleep else 0.0
        w = inertia(hours_awake) if not asleep else -INERTIA_MAGNITUDE
        raw = float(np.clip(s + c + w, SCALE_MIN, SCALE_MAX))

        biological_h = (at.hour + at.minute / 60.0 - self.acrophase_offset_h) % 24.0
        from app.config import THRESHOLDS

        in_low = THRESHOLDS.circadian_low_start_hour <= biological_h <= THRESHOLDS.circadian_low_end_hour

        return AlertnessSample(
            at=at,
            homeostatic=s,
            circadian=c,
            inertia=w,
            raw=raw,
            score=normalise(raw),
            kss=to_kss(raw),
            hours_awake=hours_awake,
            in_circadian_low=in_low,
        )

    def curve(self, start: datetime, end: datetime, step_minutes: int = 15) -> list[AlertnessSample]:
        """Sample the alertness curve across a window, for the timeline chart."""
        steps = int((end - start).total_seconds() // (step_minutes * 60)) + 1
        return [self.sample(start + timedelta(minutes=step_minutes * i)) for i in range(steps)]

    def sleep_debt_h(self, at: datetime, nights: int = 5, target_h: float = 8.0) -> float:
        """Cumulative shortfall against ``target_h`` over the trailing nights."""
        window_start = at - timedelta(days=nights)
        recent = [e for e in self.sleep_log if e.wake > window_start and e.sleep < at]
        slept = sum(e.duration_h for e in recent)
        expected = target_h * nights
        return float(max(0.0, expected - slept))


def utc(value: str) -> datetime:
    """Parse an ISO-8601 instant into an aware UTC datetime."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
