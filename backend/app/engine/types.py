from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConflictBand(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DecisionAction(str, Enum):
    EXECUTE = "EXECUTE"
    REQUEST_DATA = "REQUEST_DATA"
    DEFER = "DEFER"


class MachineAction(str, Enum):
    NORMAL = "NORMAL"
    WARN = "WARN"
    SHUTDOWN = "SHUTDOWN"
    HOLD = "HOLD"


class OperatingMode(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    HIGH_LOAD = "high_load"


class Observation(BaseModel):
    sensor_id: str
    temperature: float
    humidity: float
    battery: float
    vibration: float
    current: float
    network_quality: float
    signal_quality: float
    timestamp: float
    historical_reliability: float
    context: dict[str, Any] = Field(default_factory=dict)
    previous_temperatures: list[float] = Field(default_factory=list)


class PreprocessedObservation(BaseModel):
    observation: Observation
    valid: bool
    freshness: float
    age_seconds: float
    communication_quality: float
    notes: list[str] = Field(default_factory=list)


class TrustBreakdown(BaseModel):
    sensor_id: str
    temperature: float
    historical_reliability: float
    temporal_consistency: float
    source_agreement: float
    freshness: float
    communication_quality: float
    contextual_relevance: float
    evidence_quality: float
    trust_score: float
    status: str
    notes: list[str] = Field(default_factory=list)


class Cluster(BaseModel):
    sensor_ids: list[str]
    centroid: float
    trust_mass: float
    size: int


class ConflictReport(BaseModel):
    level: ConflictBand
    score: float
    pairs: list[dict[str, Any]]
    clusters: list[Cluster]
    dominant_cluster_ids: list[str]


class DecisionOutcome(BaseModel):
    action: DecisionAction
    machine_action: MachineAction
    confidence: float
    consensus_temperature: float | None
    conflict: ConflictReport
    trusts: list[TrustBreakdown]
    reason: str
    recommended: str
    factors: dict[str, float]
    scenario: str | None = None
