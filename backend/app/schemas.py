import math
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ScenarioRequest(BaseModel):
    name: str


class IngestRequest(BaseModel):
    observations: list[dict[str, Any]]
    scenario: str | None = None


class ConfiguredSensorCreate(BaseModel):
    sensor_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    measurement: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=32)
    location: str = Field(default="", max_length=120)
    expected_interval_seconds: float = Field(default=60, gt=0, le=86400)
    baseline_tolerance: float | None = Field(default=None, ge=0)

    @field_validator("sensor_id")
    @classmethod
    def validate_sensor_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError("Use only letters, numbers, dots, underscores, and hyphens for sensor_id.")
        return value

    @field_validator("measurement", "unit")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field cannot be blank.")
        return cleaned


class ConfiguredReadingCreate(BaseModel):
    sensor_id: str = Field(min_length=1, max_length=64)
    value: float
    timestamp: float | None = None
    network_quality: float = Field(default=1.0, ge=0, le=1)

    @field_validator("value", "timestamp")
    @classmethod
    def validate_finite_number(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("Numeric values must be finite.")
        return value
