from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReadingRow(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cycle: Mapped[int] = mapped_column(Integer, index=True)
    sensor_id: Mapped[str] = mapped_column(String(16), index=True)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    battery: Mapped[float] = mapped_column(Float)
    network_quality: Mapped[float] = mapped_column(Float)
    freshness: Mapped[float] = mapped_column(Float)
    trust_score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32))


class DecisionRow(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cycle: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(32))
    machine_action: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    conflict_level: Mapped[str] = mapped_column(String(16))
    consensus_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    scenario: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)


class ConfiguredSensorRow(Base):
    __tablename__ = "configured_sensors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sensor_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    measurement: Mapped[str] = mapped_column(String(80), index=True)
    unit: Mapped[str] = mapped_column(String(32))
    location: Mapped[str] = mapped_column(String(120), default="")
    expected_interval_seconds: Mapped[float] = mapped_column(Float, default=60.0)
    baseline_tolerance: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConfiguredReadingRow(Base):
    __tablename__ = "configured_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sensor_id: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[float] = mapped_column(Float, index=True)
    network_quality: Mapped[float] = mapped_column(Float, default=1.0)
