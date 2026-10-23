from __future__ import annotations

import math
import time

from app.config import settings
from app.engine.types import Observation, PreprocessedObservation


def freshness_from_age(age_seconds: float) -> float:
    age = max(0.0, age_seconds)
    return float(math.exp(-age / settings.freshness_tau_seconds))


def preprocess(observations: list[Observation], now: float | None = None) -> list[PreprocessedObservation]:
    clock = now if now is not None else time.time()
    prepared: list[PreprocessedObservation] = []
    for obs in observations:
        notes: list[str] = []
        valid = True
        if not math.isfinite(obs.temperature):
            valid = False
            notes.append("non-finite temperature")
        if obs.temperature < -20 or obs.temperature > 200:
            valid = False
            notes.append("temperature out of physical range")

        age = max(0.0, clock - obs.timestamp)
        freshness = freshness_from_age(age)
        if age >= settings.stale_after_seconds:
            notes.append("stale observation")
        communication = max(0.0, min(1.0, math.sqrt(obs.network_quality * obs.signal_quality)))
        if communication < 0.4:
            notes.append("poor communication")

        prepared.append(
            PreprocessedObservation(
                observation=obs,
                valid=valid,
                freshness=round(freshness, 4),
                age_seconds=round(age, 3),
                communication_quality=round(communication, 4),
                notes=notes,
            )
        )
    return prepared
