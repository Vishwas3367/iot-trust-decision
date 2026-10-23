from __future__ import annotations

from app.engine.confidence import attach_trust_mass, decision_confidence
from app.engine.conflict import detect_conflict
from app.engine.controller import decide
from app.engine.preprocessing import preprocess
from app.engine.trust import compute_trust, update_historical_reliability
from app.engine.types import DecisionOutcome, Observation


class DecisionPipeline:
    def __init__(self) -> None:
        self.reliability: dict[str, float] = {}

    def ingest(self, observations: list[Observation], scenario: str | None = None) -> DecisionOutcome:
        for obs in observations:
            if obs.sensor_id in self.reliability:
                obs.historical_reliability = self.reliability[obs.sensor_id]
            else:
                self.reliability[obs.sensor_id] = obs.historical_reliability

        prepared = preprocess(observations)
        conflict = detect_conflict(prepared)
        trusts = compute_trust(prepared)
        conflict = attach_trust_mass(conflict, trusts)
        confidence, consensus, factors = decision_confidence(trusts, conflict)
        action, machine, reason, recommended = decide(
            confidence, consensus, conflict.level, trusts
        )

        self.reliability = update_historical_reliability(
            self.reliability, trusts, conflict.dominant_cluster_ids, confidence
        )

        return DecisionOutcome(
            action=action,
            machine_action=machine,
            confidence=confidence,
            consensus_temperature=consensus,
            conflict=conflict,
            trusts=trusts,
            reason=reason,
            recommended=recommended,
            factors=factors,
            scenario=scenario,
        )
