from __future__ import annotations

from app.config import settings
from app.engine.conflict import pairwise_similarity
from app.engine.context import contextual_relevance, temporal_consistency
from app.engine.types import PreprocessedObservation, TrustBreakdown


def compute_trust(items: list[PreprocessedObservation]) -> list[TrustBreakdown]:
    """
    Trust is not a static label and not a plain average of factors.

    Observation quality (freshness × communication) gates how much the sample
    may update anyone's beliefs. Prior reliability is then blended with
    current temporal stability and agreement with other sources, then scaled
    by contextual relevance to the thermal decision.
    """
    valid_temps = {
        i.observation.sensor_id: i.observation.temperature for i in items if i.valid
    }
    breakdowns: list[TrustBreakdown] = []
    for item in items:
        obs = item.observation
        if not item.valid:
            breakdowns.append(
                TrustBreakdown(
                    sensor_id=obs.sensor_id,
                    temperature=obs.temperature,
                    historical_reliability=obs.historical_reliability,
                    temporal_consistency=0.0,
                    source_agreement=0.0,
                    freshness=item.freshness,
                    communication_quality=item.communication_quality,
                    contextual_relevance=0.0,
                    evidence_quality=0.0,
                    trust_score=0.0,
                    status="INVALID",
                    notes=item.notes + ["discarded during validation"],
                )
            )
            continue

        temporal = temporal_consistency(obs)
        agreement = _source_agreement(obs.sensor_id, obs.temperature, valid_temps)
        context = contextual_relevance(item)
        evidence_quality = (item.freshness**1.15) * (item.communication_quality**1.05)
        evidence_quality = max(0.02, min(1.0, evidence_quality))

        # λ leans on history when the current sample is thin; live evidence
        # dominates when the sample is fresh and well-communicated.
        lambda_prior = 0.55 * (1.0 - evidence_quality) + 0.22
        live = 0.55 * temporal + 0.45 * agreement
        posterior = lambda_prior * obs.historical_reliability + (1.0 - lambda_prior) * live
        trust = evidence_quality * posterior * (0.35 + 0.65 * context)
        trust = max(0.01, min(0.99, trust))

        status = "TRUSTED" if trust >= 0.7 else "UNCERTAIN" if trust >= 0.45 else "LOW TRUST"
        notes = list(item.notes)
        if temporal < 0.4:
            notes.append("abrupt temporal jump")
        if agreement < 0.35:
            notes.append("disagrees with peer sources")

        breakdowns.append(
            TrustBreakdown(
                sensor_id=obs.sensor_id,
                temperature=obs.temperature,
                historical_reliability=round(obs.historical_reliability, 4),
                temporal_consistency=round(temporal, 4),
                source_agreement=round(agreement, 4),
                freshness=round(item.freshness, 4),
                communication_quality=round(item.communication_quality, 4),
                contextual_relevance=round(context, 4),
                evidence_quality=round(evidence_quality, 4),
                trust_score=round(trust, 4),
                status=status,
                notes=notes,
            )
        )
    return breakdowns


def update_historical_reliability(
    current: dict[str, float],
    trusts: list[TrustBreakdown],
    dominant_ids: list[str],
    confidence: float,
) -> dict[str, float]:
    """Reliability moves only after a reasonably confident decision."""
    updated = dict(current)
    if confidence < 0.55 or not dominant_ids:
        return updated
    lr = settings.reliability_lr
    for t in trusts:
        prev = updated.get(t.sensor_id, t.historical_reliability)
        agreed = t.sensor_id in dominant_ids
        target = 0.97 if agreed and t.trust_score >= 0.5 else 0.25
        nxt = prev + lr * (target - prev)
        updated[t.sensor_id] = min(
            settings.reliability_ceiling,
            max(settings.reliability_floor, nxt),
        )
    return updated


def _source_agreement(sensor_id: str, value: float, temps: dict[str, float]) -> float:
    others = [(sid, temp) for sid, temp in temps.items() if sid != sensor_id]
    if not others:
        return 0.5
    scores = [pairwise_similarity(value, temp) for _, temp in others]
    return sum(scores) / len(scores)
