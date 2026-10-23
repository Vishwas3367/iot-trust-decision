from __future__ import annotations

import time

from app.engine.pipeline import DecisionPipeline
from app.engine.types import DecisionAction, MachineAction, Observation


def obs(
    sensor_id: str,
    temperature: float,
    *,
    reliability: float = 0.93,
    network: float = 0.95,
    signal: float = 0.94,
    age: float = 1.0,
    history: list[float] | None = None,
    location: str = "core",
    mode: str = "running",
    battery: float = 86.0,
) -> Observation:
    now = time.time()
    prev = history if history is not None else [temperature - 0.4, temperature - 0.2, temperature]
    return Observation(
        sensor_id=sensor_id,
        temperature=temperature,
        humidity=50.0,
        battery=battery,
        vibration=0.2,
        current=12.0,
        network_quality=network,
        signal_quality=signal,
        timestamp=now - age,
        historical_reliability=reliability,
        previous_temperatures=prev,
        context={
            "location": location,
            "role": "temperature",
            "operating_mode": mode,
            "machine_id": "PRESS-04",
        },
    )


def test_normal_agreement_executes_normal_operation():
    pipeline = DecisionPipeline()
    outcome = pipeline.ingest(
        [
            obs("S01", 30, location="inlet"),
            obs("S02", 31),
            obs("S03", 30, location="outlet"),
            obs("S04", 31, location="core-redundant"),
        ],
        scenario="normal",
    )
    assert outcome.conflict.level.value == "LOW"
    assert outcome.confidence >= 0.80
    assert outcome.action == DecisionAction.EXECUTE
    assert outcome.machine_action == MachineAction.NORMAL


def test_one_faulty_sensor_is_downweighted_not_averaged():
    pipeline = DecisionPipeline()
    outcome = pipeline.ingest(
        [
            obs("S01", 30, location="inlet", history=[29.5, 29.8, 30.0]),
            obs("S02", 31, history=[30.4, 30.7, 30.9]),
            obs("S03", 30, location="outlet", history=[29.6, 29.9, 30.1]),
            obs("S04", 75, reliability=0.9, history=[30.5, 30.8, 31.0]),
        ],
        scenario="one_faulty",
    )
    trust = {t.sensor_id: t for t in outcome.trusts}
    assert trust["S04"].trust_score < 0.45
    assert trust["S04"].status == "LOW TRUST"
    assert outcome.consensus_temperature is not None
    assert outcome.consensus_temperature < 40
    naive = (30 + 31 + 30 + 75) / 4
    assert outcome.consensus_temperature < naive - 8
    assert outcome.machine_action == MachineAction.NORMAL
    assert outcome.action in {DecisionAction.EXECUTE, DecisionAction.REQUEST_DATA}


def test_split_conflict_follows_trust_mass_not_headcount():
    pipeline = DecisionPipeline()
    outcome = pipeline.ingest(
        [
            obs(
                "S01",
                75,
                reliability=0.95,
                history=[72, 73, 74, 75],
                location="inlet",
                mode="high_load",
            ),
            obs(
                "S02",
                73,
                reliability=0.93,
                history=[71, 72, 73, 73],
                mode="high_load",
            ),
            obs(
                "S03",
                30,
                reliability=0.45,
                network=0.35,
                signal=0.32,
                age=35,
                history=[71, 72, 73, 30],
                location="outlet",
                mode="high_load",
            ),
            obs(
                "S04",
                32,
                reliability=0.48,
                network=0.4,
                signal=0.38,
                age=28,
                history=[70, 71, 72, 32],
                location="core-redundant",
                mode="high_load",
            ),
        ],
        scenario="split_conflict",
    )
    assert outcome.conflict.level.value == "HIGH"
    assert set(outcome.conflict.dominant_cluster_ids) == {"S01", "S02"}
    assert outcome.consensus_temperature is not None
    assert outcome.consensus_temperature > 65
    trust = {t.sensor_id: t for t in outcome.trusts}
    assert trust["S01"].trust_score > trust["S03"].trust_score
    assert trust["S03"].status == "LOW TRUST"


def test_poor_network_does_not_trigger_blind_shutdown():
    pipeline = DecisionPipeline()
    outcome = pipeline.ingest(
        [
            obs(
                "S01",
                75,
                reliability=0.9,
                network=0.22,
                signal=0.25,
                age=55,
                history=[31, 31.2, 75],
            ),
            obs("S02", 31, history=[30.6, 30.8, 31.0]),
            obs("S03", 30.5, location="outlet", history=[30.2, 30.4, 30.5]),
            obs("S04", 31.2, location="core-redundant", history=[30.9, 31.0, 31.1]),
        ],
        scenario="poor_network",
    )
    trust = {t.sensor_id: t for t in outcome.trusts}
    assert trust["S01"].trust_score < 0.5
    assert outcome.machine_action != MachineAction.SHUTDOWN
    assert outcome.consensus_temperature is not None
    assert outcome.consensus_temperature < 45


def test_stale_reading_is_penalized():
    pipeline = DecisionPipeline()
    outcome = pipeline.ingest(
        [
            obs("S01", 72, history=[70, 71, 72], mode="high_load", location="inlet"),
            obs("S02", 71.5, age=150, history=[70, 71, 71.5], mode="high_load"),
            obs("S03", 72.4, location="outlet", history=[71, 71.8, 72], mode="high_load"),
            obs("S04", 72.1, location="core-redundant", history=[71, 71.6, 72], mode="high_load"),
        ],
        scenario="stale",
    )
    trust = {t.sensor_id: t for t in outcome.trusts}
    assert trust["S02"].freshness < trust["S01"].freshness
    assert trust["S02"].trust_score < trust["S01"].trust_score


def test_genuine_emergency_executes_shutdown():
    pipeline = DecisionPipeline()
    outcome = pipeline.ingest(
        [
            obs("S01", 80, history=[78, 79, 80], mode="high_load", location="inlet"),
            obs("S02", 82, history=[80, 81, 81.5], mode="high_load"),
            obs("S03", 81, location="outlet", history=[79, 80, 80.5], mode="high_load"),
            obs("S04", 80.5, location="core-redundant", history=[79, 80, 80.2], mode="high_load"),
        ],
        scenario="emergency",
    )
    assert outcome.conflict.level.value == "LOW"
    assert outcome.confidence >= 0.80
    assert outcome.action == DecisionAction.EXECUTE
    assert outcome.machine_action == MachineAction.SHUTDOWN
