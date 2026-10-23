from __future__ import annotations

import asyncio
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.engine.pipeline import DecisionPipeline
from app.engine.simulator import IoTSimulator
from app.engine.types import DecisionOutcome, Observation
from app.models import DecisionRow, ReadingRow


class Runtime:
    def __init__(self) -> None:
        self.simulator = IoTSimulator()
        self.pipeline = DecisionPipeline()
        self.running = False
        self.interval_seconds = 2.0
        self.cycle = 0
        self.latest: dict | None = None
        self.history: list[dict] = []
        self._task: asyncio.Task | None = None

    def tick(self, extra: bool = False) -> dict:
        if extra:
            observations = self.simulator.step()
            extra_obs = self.simulator.extra_reading()
            observations.append(extra_obs)
        else:
            observations = self.simulator.step()
        outcome = self.pipeline.ingest(observations, scenario=self.simulator.active_scenario)
        self.cycle += 1
        snapshot = self._pack(observations, outcome)
        self.latest = snapshot
        self.history.append(snapshot)
        self.history = self.history[-200:]
        self._persist(snapshot, outcome)
        return snapshot

    def ingest_raw(self, observations: list[Observation], scenario: str | None = None) -> dict:
        outcome = self.pipeline.ingest(observations, scenario=scenario)
        self.cycle += 1
        snapshot = self._pack(observations, outcome)
        self.latest = snapshot
        self.history.append(snapshot)
        self.history = self.history[-200:]
        self._persist(snapshot, outcome)
        return snapshot

    def apply_scenario(self, name: str) -> dict:
        self.simulator.apply_scenario(name)
        return self.tick()

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        try:
            while self.running:
                self.tick()
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            return

    def _pack(self, observations: list[Observation], outcome: DecisionOutcome) -> dict:
        trust_map = {t.sensor_id: t for t in outcome.trusts}
        sensors = []
        for obs in observations:
            t = trust_map.get(obs.sensor_id)
            sensors.append(
                {
                    "sensor_id": obs.sensor_id,
                    "temperature": obs.temperature,
                    "humidity": obs.humidity,
                    "battery": obs.battery,
                    "vibration": obs.vibration,
                    "current": obs.current,
                    "network_quality": obs.network_quality,
                    "signal_quality": obs.signal_quality,
                    "timestamp": obs.timestamp,
                    "historical_reliability": obs.historical_reliability,
                    "context": obs.context,
                    "trust": t.model_dump() if t else None,
                }
            )
        return {
            "cycle": self.cycle,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "simulator": self.simulator.snapshot(),
            "sensors": sensors,
            "decision": outcome.model_dump(),
            "naive_average": round(sum(o.temperature for o in observations) / len(observations), 2)
            if observations
            else None,
        }

    def _persist(self, snapshot: dict, outcome: DecisionOutcome) -> None:
        db: Session = SessionLocal()
        try:
            for sensor in snapshot["sensors"]:
                trust = sensor.get("trust") or {}
                db.add(
                    ReadingRow(
                        cycle=self.cycle,
                        sensor_id=sensor["sensor_id"],
                        temperature=sensor["temperature"],
                        humidity=sensor["humidity"],
                        battery=sensor["battery"],
                        network_quality=sensor["network_quality"],
                        freshness=trust.get("freshness", 0.0),
                        trust_score=trust.get("trust_score", 0.0),
                        status=trust.get("status", "UNKNOWN"),
                    )
                )
            db.add(
                DecisionRow(
                    cycle=self.cycle,
                    action=outcome.action.value,
                    machine_action=outcome.machine_action.value,
                    confidence=outcome.confidence,
                    conflict_level=outcome.conflict.level.value,
                    consensus_temperature=outcome.consensus_temperature,
                    scenario=outcome.scenario,
                    reason=outcome.reason,
                    payload_json=json.dumps(snapshot["decision"]),
                )
            )
            db.commit()
        finally:
            db.close()


runtime = Runtime()
