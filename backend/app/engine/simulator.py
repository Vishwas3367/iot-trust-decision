from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.engine.types import Observation, OperatingMode


@dataclass
class SensorProfile:
    sensor_id: str
    location: str
    role: str
    base_reliability: float
    reliability: float
    history: list[float] = field(default_factory=list)
    last_emitted_at: float | None = None
    bias: float = 0.0
    noise: float = 0.35


@dataclass
class InjectedFault:
    sensor_id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    remaining_ticks: int = 8


class IoTSimulator:
    """Virtual industrial sensors. Faults are injected, not hardware-driven."""

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.mode = OperatingMode.RUNNING
        self.true_temperature = 31.0
        self.true_humidity = 48.0
        self.true_vibration = 0.18
        self.true_current = 12.4
        self.tick = 0
        self.active_scenario: str | None = None
        self.faults: list[InjectedFault] = []
        self.sensors = [
            SensorProfile("S01", "inlet", "temperature", 0.94, 0.94, noise=0.25),
            SensorProfile("S02", "core", "temperature", 0.92, 0.92, noise=0.30),
            SensorProfile("S03", "outlet", "temperature", 0.88, 0.88, noise=0.35),
            SensorProfile("S04", "core-redundant", "temperature", 0.90, 0.90, noise=0.28),
        ]
        self._profiles = {s.sensor_id: s for s in self.sensors}

    def set_mode(self, mode: OperatingMode) -> None:
        self.mode = mode
        if mode == OperatingMode.IDLE:
            self.true_temperature = 28.0
        elif mode == OperatingMode.RUNNING:
            self.true_temperature = 31.5
        else:
            self.true_temperature = 74.0

    def clear_faults(self) -> None:
        self.faults.clear()
        self.active_scenario = None
        for sensor in self.sensors:
            sensor.bias = 0.0

    def apply_scenario(self, name: str) -> None:
        self.clear_faults()
        self.active_scenario = name
        now_bias = {
            "normal": (31.0, OperatingMode.RUNNING, []),
            "one_faulty": (
                31.0,
                OperatingMode.RUNNING,
                [InjectedFault("S04", "spike", {"value": 75.0}, remaining_ticks=12)],
            ),
            "split_conflict": (
                74.0,
                OperatingMode.HIGH_LOAD,
                [
                    InjectedFault("S03", "stuck_low", {"value": 30.0}, remaining_ticks=16),
                    InjectedFault("S04", "stuck_low", {"value": 32.0}, remaining_ticks=16),
                ],
            ),
            "poor_network": (
                31.0,
                OperatingMode.RUNNING,
                [
                    InjectedFault(
                        "S01",
                        "poor_network",
                        {
                            "network": 0.22,
                            "signal": 0.28,
                            "stale_seconds": 55,
                            "value": 75.0,
                        },
                        remaining_ticks=14,
                    )
                ],
            ),
            "stale": (
                72.0,
                OperatingMode.HIGH_LOAD,
                [
                    InjectedFault(
                        "S02",
                        "stale",
                        {"stale_seconds": 150},
                        remaining_ticks=10,
                    )
                ],
            ),
            "emergency": (81.0, OperatingMode.HIGH_LOAD, []),
        }
        if name not in now_bias:
            raise ValueError(f"Unknown scenario: {name}")
        temp, mode, faults = now_bias[name]
        self.true_temperature = temp
        self.mode = mode
        self.faults = faults
        if name == "split_conflict":
            # Two plausible factions: hot core vs cold/faulty pair
            self._profiles["S01"].bias = 1.2
            self._profiles["S02"].bias = -0.4
        for sensor in self.sensors:
            sensor.history = [
                round(self.true_temperature - 0.8, 2),
                round(self.true_temperature - 0.4, 2),
                round(self.true_temperature - 0.1, 2),
            ]

    def update_reliability(self, sensor_id: str, value: float) -> None:
        profile = self._profiles[sensor_id]
        profile.reliability = min(
            settings.reliability_ceiling,
            max(settings.reliability_floor, value),
        )

    def step(self) -> list[Observation]:
        self.tick += 1
        now = time.time()
        self._drift_truth()
        observations: list[Observation] = []
        for sensor in self.sensors:
            observations.append(self._emit(sensor, now))
        self._age_faults()
        return observations

    def extra_reading(self, sensor_id: str | None = None) -> Observation:
        """Used when the controller requests additional data."""
        sensor = self._profiles[sensor_id] if sensor_id else self.rng.choice(self.sensors)
        return self._emit(sensor, time.time(), extra=True)

    def snapshot(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "mode": self.mode.value,
            "true_temperature": round(self.true_temperature, 2),
            "scenario": self.active_scenario,
            "faults": [
                {"sensor_id": f.sensor_id, "kind": f.kind, "remaining_ticks": f.remaining_ticks}
                for f in self.faults
            ],
            "sensors": [
                {
                    "sensor_id": s.sensor_id,
                    "location": s.location,
                    "role": s.role,
                    "historical_reliability": round(s.reliability, 3),
                }
                for s in self.sensors
            ],
        }

    def _drift_truth(self) -> None:
        walk = self.rng.uniform(-0.15, 0.15)
        if self.mode == OperatingMode.HIGH_LOAD:
            walk += 0.05
        self.true_temperature = max(20.0, min(95.0, self.true_temperature + walk))
        self.true_humidity = max(20.0, min(80.0, self.true_humidity + self.rng.uniform(-0.4, 0.4)))
        self.true_vibration = max(0.05, min(1.2, self.true_vibration + self.rng.uniform(-0.02, 0.02)))
        self.true_current = max(4.0, min(28.0, self.true_current + self.rng.uniform(-0.2, 0.2)))

    def _emit(self, sensor: SensorProfile, now: float, extra: bool = False) -> Observation:
        fault = next((f for f in self.faults if f.sensor_id == sensor.sensor_id), None)
        temperature = self.true_temperature + sensor.bias + self.rng.gauss(0, sensor.noise)
        network = min(1.0, max(0.2, 0.93 + self.rng.uniform(-0.05, 0.05)))
        signal = min(1.0, max(0.2, 0.91 + self.rng.uniform(-0.06, 0.05)))
        timestamp = now
        battery = 88.0 - (hash(sensor.sensor_id) % 7) + self.rng.uniform(-0.4, 0.4)

        if fault:
            kind = fault.kind
            payload = fault.payload
            if kind == "spike":
                temperature = float(payload.get("value", 75.0))
            elif kind == "stuck_low":
                temperature = float(payload.get("value", 30.0))
            elif kind == "poor_network":
                network = float(payload.get("network", 0.2))
                signal = float(payload.get("signal", 0.25))
                timestamp = now - float(payload.get("stale_seconds", 40))
                if "value" in payload:
                    temperature = float(payload["value"])
            elif kind == "stale":
                timestamp = now - float(payload.get("stale_seconds", 120))

        if extra and fault is None:
            temperature = self.true_temperature + self.rng.gauss(0, sensor.noise * 0.6)

        sensor.history.append(temperature)
        sensor.history = sensor.history[-20:]
        sensor.last_emitted_at = timestamp

        return Observation(
            sensor_id=sensor.sensor_id,
            temperature=round(temperature, 2),
            humidity=round(self.true_humidity + self.rng.gauss(0, 0.8), 2),
            battery=round(battery, 1),
            vibration=round(self.true_vibration + self.rng.gauss(0, 0.02), 3),
            current=round(self.true_current + self.rng.gauss(0, 0.15), 2),
            network_quality=round(network, 3),
            signal_quality=round(signal, 3),
            timestamp=timestamp,
            historical_reliability=round(sensor.reliability, 3),
            previous_temperatures=[round(v, 2) for v in sensor.history[:-1][-6:]],
            context={
                "location": sensor.location,
                "role": sensor.role,
                "operating_mode": self.mode.value,
                "machine_id": "PRESS-04",
                "tick": self.tick,
                "extra": extra,
            },
        )

    def _age_faults(self) -> None:
        alive: list[InjectedFault] = []
        for fault in self.faults:
            fault.remaining_ticks -= 1
            if fault.remaining_ticks > 0:
                alive.append(fault)
        self.faults = alive
        if not self.faults and self.active_scenario not in (None, "normal", "emergency"):
            # Keep scenario label until operator changes it.
            pass
