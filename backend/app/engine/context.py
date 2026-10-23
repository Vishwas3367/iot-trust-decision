from __future__ import annotations

from app.engine.types import Observation, OperatingMode, PreprocessedObservation


def contextual_relevance(item: PreprocessedObservation) -> float:
    """How much this observation should count for the current thermal decision."""
    obs = item.observation
    ctx = obs.context or {}
    score = 1.0
    notes_penalty = 0.0

    role = str(ctx.get("role", "temperature"))
    if role != "temperature":
        score *= 0.35

    location = str(ctx.get("location", ""))
    if location in {"core", "core-redundant", "inlet"}:
        score *= 1.0
    elif location == "outlet":
        score *= 0.9
    else:
        score *= 0.75

    mode = str(ctx.get("operating_mode", OperatingMode.RUNNING.value))
    # Under high load, a cold reading is less contextually plausible than a hot one.
    if mode == OperatingMode.HIGH_LOAD.value and obs.temperature < 40:
        notes_penalty += 0.25
    if mode == OperatingMode.IDLE.value and obs.temperature > 65:
        notes_penalty += 0.15

    if obs.battery < 20:
        notes_penalty += 0.2
    elif obs.battery < 40:
        notes_penalty += 0.08

    if item.age_seconds > 90:
        notes_penalty += 0.15

    return max(0.05, min(1.0, score * (1.0 - notes_penalty)))


def temporal_consistency(obs: Observation) -> float:
    history = obs.previous_temperatures
    if not history:
        return 0.55
    last = history[-1]
    jump = abs(obs.temperature - last)
    # Healthy industrial probes rarely jump tens of degrees in one sample.
    if jump < 1.5:
        base = 0.97
    elif jump < 4:
        base = 0.82
    elif jump < 8:
        base = 0.55
    else:
        base = max(0.08, 0.45 * (8 / jump))

    if len(history) >= 3:
        mean = sum(history) / len(history)
        drift = abs(obs.temperature - mean)
        if drift > 20:
            base *= 0.45
        elif drift > 10:
            base *= 0.7
    return max(0.05, min(1.0, base))
