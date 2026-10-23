from __future__ import annotations

import math
import statistics
import time
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ConfiguredReadingRow, ConfiguredSensorRow

BASELINE_SAMPLES = 5
HISTORY_WINDOW = 30
ANOMALY_Z_SCORE = 3.5


def list_sensors() -> list[dict]:
    with SessionLocal() as db:
        sensors = db.scalars(
            select(ConfiguredSensorRow).order_by(ConfiguredSensorRow.created_at)
        ).all()
        return [_sensor_json(sensor) for sensor in sensors]


def create_sensor(payload: dict) -> dict:
    with SessionLocal() as db:
        if db.scalar(
            select(ConfiguredSensorRow.id).where(
                ConfiguredSensorRow.sensor_id == payload["sensor_id"]
            )
        ):
            raise ValueError(f"Sensor ID already exists: {payload['sensor_id']}")
        sensor = ConfiguredSensorRow(**payload)
        db.add(sensor)
        db.commit()
        db.refresh(sensor)
        return _sensor_json(sensor)


def remove_sensor(sensor_id: str) -> bool:
    with SessionLocal() as db:
        sensor = db.scalar(
            select(ConfiguredSensorRow).where(ConfiguredSensorRow.sensor_id == sensor_id)
        )
        if sensor is None:
            return False
        db.execute(
            ConfiguredReadingRow.__table__.delete().where(
                ConfiguredReadingRow.sensor_id == sensor_id
            )
        )
        db.delete(sensor)
        db.commit()
        return True


def add_reading(payload: dict) -> dict:
    timestamp = payload.get("timestamp")
    reading_timestamp = timestamp if timestamp is not None else time.time()
    if reading_timestamp > time.time() + 300:
        raise ValueError("Reading timestamp cannot be more than 5 minutes in the future.")

    with SessionLocal() as db:
        sensor = db.scalar(
            select(ConfiguredSensorRow).where(
                ConfiguredSensorRow.sensor_id == payload["sensor_id"]
            )
        )
        if sensor is None:
            raise LookupError(f"Sensor is not configured: {payload['sensor_id']}")
        reading = ConfiguredReadingRow(
            sensor_id=sensor.sensor_id,
            value=payload["value"],
            timestamp=reading_timestamp,
            network_quality=payload.get("network_quality", 1.0),
        )
        db.add(reading)
        db.commit()
        db.refresh(reading)
        return {"id": reading.id, "sensor_id": reading.sensor_id, "timestamp": reading.timestamp}


def customer_state() -> dict:
    with SessionLocal() as db:
        sensors = db.scalars(
            select(ConfiguredSensorRow).order_by(ConfiguredSensorRow.created_at)
        ).all()
        evaluated = [_evaluate_sensor(db, sensor) for sensor in sensors]

    unusual = [row for row in evaluated if row["status"] == "UNUSUAL"]
    calibrating = [row for row in evaluated if row["status"] == "CALIBRATING"]
    low_quality = [row for row in evaluated if row["status"] == "LOW_QUALITY"]
    stale = [row for row in evaluated if row["status"] == "STALE"]
    no_data = [row for row in evaluated if row["status"] == "NO_DATA"]

    if not evaluated:
        summary = {
            "status": "NO_SENSORS",
            "message": "Add a sensor to get started.",
            "unusual_count": 0,
            "calibrating_count": 0,
        }
    elif unusual:
        summary = {
            "status": "CHECK",
            "message": f"{len(unusual)} sensor reading(s) differ from their usual range.",
            "unusual_count": len(unusual),
            "calibrating_count": len(calibrating),
        }
    elif low_quality:
        summary = {
            "status": "LOW_QUALITY",
            "message": f"Check the connection for {len(low_quality)} sensor(s).",
            "unusual_count": 0,
            "calibrating_count": 0,
        }
    elif calibrating:
        summary = {
            "status": "LEARNING",
            "message": f"Collecting readings to learn the usual range for {len(calibrating)} sensor(s).",
            "unusual_count": 0,
            "calibrating_count": len(calibrating),
        }
    elif stale:
        summary = {
            "status": "STALE",
            "message": f"{len(stale)} sensor(s) have not reported recently.",
            "unusual_count": 0,
            "calibrating_count": 0,
        }
    elif no_data:
        summary = {
            "status": "NO_DATA",
            "message": f"Waiting for the first reading from {len(no_data)} sensor(s).",
            "unusual_count": 0,
            "calibrating_count": 0,
        }
    else:
        summary = {
            "status": "NORMAL",
            "message": "Latest readings are within each sensor's usual range.",
            "unusual_count": 0,
            "calibrating_count": 0,
        }
    return {"summary": summary, "sensors": evaluated}


def _evaluate_sensor(db: Session, sensor: ConfiguredSensorRow) -> dict:
    count = db.scalar(
        select(func.count(ConfiguredReadingRow.id)).where(
            ConfiguredReadingRow.sensor_id == sensor.sensor_id
        )
    ) or 0
    recent = db.scalars(
        select(ConfiguredReadingRow)
        .where(ConfiguredReadingRow.sensor_id == sensor.sensor_id)
        .order_by(ConfiguredReadingRow.id.desc())
        .limit(HISTORY_WINDOW + 1)
    ).all()
    readings = list(reversed(recent))
    latest = readings[-1] if readings else None
    result: dict = {
        **_sensor_json(sensor),
        "sample_count": count,
        "baseline_samples_required": BASELINE_SAMPLES,
        "latest_value": latest.value if latest else None,
        "latest_timestamp": latest.timestamp if latest else None,
        "network_quality": latest.network_quality if latest else None,
        "baseline_median": None,
        "baseline_spread": None,
        "deviation_score": None,
        "status": "NO_DATA" if latest is None else "CALIBRATING",
        "message": "Waiting for the first reading." if latest is None else "Learning the usual range.",
    }
    if latest is not None:
        age_seconds = max(0.0, time.time() - latest.timestamp)
        freshness = math.exp(-age_seconds / (3 * sensor.expected_interval_seconds))
        result["age_seconds"] = round(age_seconds, 1)
        result["freshness"] = round(freshness, 3)
        if age_seconds > 3 * sensor.expected_interval_seconds:
            result["status"] = "STALE"
            result["message"] = "No recent reading; check the sensor connection."
            return result
        if latest.network_quality < 0.3:
            result["status"] = "LOW_QUALITY"
            result["message"] = "Connection is weak; check this reading."
            return result

    if latest is None or count <= BASELINE_SAMPLES:
        return result

    baseline = [row.value for row in readings[:-1]][-HISTORY_WINDOW:]
    if len(baseline) < BASELINE_SAMPLES:
        return result

    median = statistics.median(baseline)
    mad = statistics.median(abs(value - median) for value in baseline)
    spread = 1.4826 * mad
    if spread <= 1e-12:
        spread = (
            sensor.baseline_tolerance
            if sensor.baseline_tolerance is not None
            else max(abs(median) * 0.01, 0.01)
        )
    deviation = abs(latest.value - median) / spread

    result["baseline_median"] = round(median, 6)
    result["baseline_spread"] = round(spread, 6)
    result["deviation_score"] = round(deviation, 3)

    result["reliability"] = round(
        math.exp(-max(0.0, deviation - 2.0) / 5.0)
        * latest.network_quality
        * freshness,
        3,
    )
    if deviation >= ANOMALY_Z_SCORE:
        result["status"] = "UNUSUAL"
        result["message"] = "This reading is far from this sensor's usual range."
    else:
        result["status"] = "NORMAL"
        result["message"] = "This reading is within this sensor's usual range."
    return result


def _sensor_json(sensor: ConfiguredSensorRow) -> dict:
    return {
        "sensor_id": sensor.sensor_id,
        "name": sensor.name,
        "measurement": sensor.measurement,
        "unit": sensor.unit,
        "location": sensor.location,
        "expected_interval_seconds": sensor.expected_interval_seconds,
        "baseline_tolerance": sensor.baseline_tolerance,
        "created_at": sensor.created_at.isoformat() if isinstance(sensor.created_at, datetime) else None,
    }
