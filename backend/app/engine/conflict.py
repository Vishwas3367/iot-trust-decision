from __future__ import annotations

from app.config import settings
from app.engine.types import Cluster, ConflictBand, ConflictReport, PreprocessedObservation


def pairwise_similarity(a: float, b: float) -> float:
    gap = abs(a - b)
    return float(pow(2.718281828, -gap / settings.agreement_scale_celsius))


def detect_conflict(items: list[PreprocessedObservation]) -> ConflictReport:
    valid = [i for i in items if i.valid]
    pairs: list[dict] = []
    n = len(valid)
    conflict_hits = 0
    comparable = 0
    for i in range(n):
        for j in range(i + 1, n):
            comparable += 1
            vi = valid[i].observation.temperature
            vj = valid[j].observation.temperature
            gap = abs(vi - vj)
            similar = pairwise_similarity(vi, vj)
            is_conflict = gap >= settings.conflict_gap_celsius
            if is_conflict:
                conflict_hits += 1
            pairs.append(
                {
                    "a": valid[i].observation.sensor_id,
                    "b": valid[j].observation.sensor_id,
                    "gap": round(gap, 2),
                    "agreement": round(similar, 3),
                    "conflict": is_conflict,
                }
            )

    clusters = _cluster(valid)
    if comparable == 0:
        score = 0.0
    else:
        score = conflict_hits / comparable
        if len(clusters) >= 3:
            score = min(1.0, score + 0.15)

    if score < 0.2 and len(clusters) <= 1:
        level = ConflictBand.LOW
    elif score < 0.5:
        level = ConflictBand.MEDIUM
    else:
        level = ConflictBand.HIGH

    # Dominant cluster is chosen later with trust mass; here we seed by size.
    dominant = max(clusters, key=lambda c: c.size).sensor_ids if clusters else []
    return ConflictReport(
        level=level,
        score=round(score, 3),
        pairs=pairs,
        clusters=clusters,
        dominant_cluster_ids=dominant,
    )


def _cluster(items: list[PreprocessedObservation]) -> list[Cluster]:
    if not items:
        return []
    ordered = sorted(items, key=lambda x: x.observation.temperature)
    groups: list[list[PreprocessedObservation]] = [[ordered[0]]]
    for item in ordered[1:]:
        prev = groups[-1][-1].observation.temperature
        if item.observation.temperature - prev >= settings.conflict_gap_celsius:
            groups.append([item])
        else:
            groups[-1].append(item)

    clusters: list[Cluster] = []
    for group in groups:
        temps = [g.observation.temperature for g in group]
        clusters.append(
            Cluster(
                sensor_ids=[g.observation.sensor_id for g in group],
                centroid=round(sum(temps) / len(temps), 3),
                trust_mass=0.0,
                size=len(group),
            )
        )
    return clusters
