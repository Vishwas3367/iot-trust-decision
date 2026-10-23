from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = "sqlite:///data/iot_trust.db"

    # Decision thresholds (industrial thermal protection demo)
    warning_celsius: float = 70.0
    emergency_celsius: float = 78.0

    # Observation noise expected among healthy co-located sensors
    agreement_scale_celsius: float = 4.0
    conflict_gap_celsius: float = 8.0

    # Freshness half-life in seconds (simulator ticks ~2s)
    freshness_tau_seconds: float = 25.0
    stale_after_seconds: float = 40.0

    # Confidence bands
    execute_confidence: float = 0.80
    request_confidence: float = 0.50

    # Reliability learning
    reliability_lr: float = 0.08
    reliability_floor: float = 0.15
    reliability_ceiling: float = 0.98

    # Default sensors
    sensor_ids: tuple[str, ...] = ("S01", "S02", "S03", "S04")


settings = Settings()
