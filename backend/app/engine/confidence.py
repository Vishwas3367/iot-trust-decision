from __future__ import annotations

from app.config import settings
from app.engine.types import ConflictReport, TrustBreakdown


def attach_trust_mass(conflict: ConflictReport, trusts: list[TrustBreakdown]) -> ConflictReport:
    by_id = {t.sensor_id: t.trust_score for t in trusts}
    clusters = []
    for cluster in conflict.clusters:
        mass = sum(by_id.get(sid, 0.0) for sid in cluster.sensor_ids)
        clusters.append(cluster.model_copy(update={"trust_mass": round(mass, 4)}))
    if clusters:
        dominant = max(clusters, key=lambda c: (c.trust_mass, c.size))
        dominant_ids = dominant.sensor_ids
    else:
        dominant_ids = []
    return conflict.model_copy(update={"clusters": clusters, "dominant_cluster_ids": dominant_ids})


def decision_confidence(
    trusts: list[TrustBreakdown],
    conflict: ConflictReport,
) -> tuple[float, float | None, dict[str, float]]:
    """
    Confidence is about whether we should act on the trusted faction,
    not whether every sensor agrees.

    A high-conflict reading can still yield high confidence if one cluster
    holds most of the trust mass. Two strong factions suppress confidence.
    """
    if not trusts:
        return 0.0, None, {"trust_mass": 0.0}

    total_trust = sum(t.trust_score for t in trusts) or 1e-6
    dominant_ids = set(conflict.dominant_cluster_ids)
    dominant = [t for t in trusts if t.sensor_id in dominant_ids] or trusts
    rival = [t for t in trusts if t.sensor_id not in dominant_ids]

    trust_mass = sum(t.trust_score for t in dominant) / total_trust
    weights = [max(t.trust_score, 1e-6) for t in dominant]
    consensus = sum(t.temperature * w for t, w in zip(dominant, weights)) / sum(weights)

    if len(dominant) == 1:
        intra = dominant[0].temporal_consistency
    else:
        mean = consensus
        var = sum((t.temperature - mean) ** 2 for t in dominant) / len(dominant)
        intra = max(0.0, 1.0 - (var**0.5) / (settings.agreement_scale_celsius * 2))

    quality = sum(t.evidence_quality for t in dominant) / len(dominant)

    rival_mass = sum(t.trust_score for t in rival) / total_trust
    split_penalty = 0.0
    if rival and rival_mass >= 0.28 and trust_mass < 0.72:
        split_penalty = min(0.55, rival_mass)

    # Margin: acting is easier when consensus is clearly on one side of the line.
    distance = min(
        abs(consensus - settings.warning_celsius),
        abs(consensus - settings.emergency_celsius),
        abs(consensus - 35.0),
    )
    clarity = min(1.0, 0.55 + distance / 25.0)

    confidence = (
        0.34 * trust_mass
        + 0.22 * intra
        + 0.22 * quality
        + 0.22 * clarity
    ) * (1.0 - split_penalty)
    confidence = max(0.02, min(0.99, confidence))

    factors = {
        "trust_mass": round(trust_mass, 4),
        "intra_agreement": round(intra, 4),
        "evidence_quality": round(quality, 4),
        "clarity": round(clarity, 4),
        "rival_mass": round(rival_mass, 4),
        "split_penalty": round(split_penalty, 4),
    }
    return round(confidence, 4), round(consensus, 3), factors
