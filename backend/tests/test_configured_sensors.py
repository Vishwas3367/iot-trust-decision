import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import configured_sensors
from app.database import Base, init_db
from app.models import ConfiguredReadingRow


@pytest.fixture
def configured_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(configured_sensors, "SessionLocal", test_sessions)
    yield test_sessions
    engine.dispose()


def add_sensor():
    return configured_sensors.create_sensor(
        {
            "sensor_id": "vibration-1",
            "name": "Motor vibration",
            "measurement": "vibration",
            "unit": "mm/s",
            "location": "Motor A",
            "baseline_tolerance": 0.1,
        }
    )


def test_custom_sensor_requires_baseline_before_judgment(configured_db):
    add_sensor()
    for index in range(5):
        configured_sensors.add_reading(
            {
                "sensor_id": "vibration-1",
                "value": 2.0 + (index % 2) * 0.05,
                "timestamp": time.time() + index,
                "network_quality": 0.95,
            }
        )

    result = configured_sensors.customer_state()

    assert result["sensors"][0]["measurement"] == "vibration"
    assert result["sensors"][0]["status"] == "CALIBRATING"
    assert "usual range" in result["sensors"][0]["message"]


def test_configured_sensor_without_readings_is_not_reported_as_normal(configured_db):
    add_sensor()

    result = configured_sensors.customer_state()

    assert result["summary"]["status"] == "NO_DATA"
    assert result["sensors"][0]["status"] == "NO_DATA"


def test_custom_sensor_flags_value_far_from_its_learned_baseline(configured_db):
    add_sensor()
    base_time = time.time()
    for index, value in enumerate([2.0, 2.05, 1.95, 2.0, 2.05, 2.0]):
        configured_sensors.add_reading(
            {
                "sensor_id": "vibration-1",
                "value": value,
                "timestamp": base_time + index,
                "network_quality": 0.95,
            }
        )
    configured_sensors.add_reading(
        {
            "sensor_id": "vibration-1",
            "value": 12.0,
            "timestamp": base_time + 7,
            "network_quality": 0.95,
        }
    )

    result = configured_sensors.customer_state()

    assert result["summary"]["status"] == "CHECK"
    assert result["sensors"][0]["status"] == "UNUSUAL"
    assert result["sensors"][0]["baseline_median"] is not None
    assert result["sensors"][0]["deviation_score"] > 3.5


def test_unknown_sensor_cannot_receive_reading(configured_db):
    with pytest.raises(LookupError, match="not configured"):
        configured_sensors.add_reading(
            {
                "sensor_id": "missing",
                "value": 3.0,
                "network_quality": 1.0,
            }
        )


def test_stale_device_reading_is_not_judged_as_current(configured_db):
    add_sensor()
    base_time = time.time()
    for index, value in enumerate([2.0, 2.05, 1.95, 2.0, 2.05]):
        configured_sensors.add_reading(
            {
                "sensor_id": "vibration-1",
                "value": value,
                "timestamp": base_time + index,
                "network_quality": 0.95,
            }
        )
    configured_sensors.add_reading(
        {
            "sensor_id": "vibration-1",
            "value": 2.0,
            "timestamp": time.time() - 300,
            "network_quality": 0.95,
        }
    )

    result = configured_sensors.customer_state()

    assert result["sensors"][0]["status"] == "STALE"
    assert result["summary"]["status"] == "STALE"


def test_removing_sensor_also_removes_its_readings(configured_db):
    add_sensor()
    configured_sensors.add_reading(
        {
            "sensor_id": "vibration-1",
            "value": 2.0,
            "network_quality": 1.0,
        }
    )

    assert configured_sensors.remove_sensor("vibration-1") is True
    assert configured_sensors.list_sensors() == []
    with configured_db() as db:
        assert db.query(ConfiguredReadingRow).count() == 0


def test_existing_database_adds_reporting_interval_column(monkeypatch):
    legacy_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with legacy_engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE configured_sensors (
                id INTEGER PRIMARY KEY,
                sensor_id VARCHAR(64) NOT NULL UNIQUE,
                name VARCHAR(120) NOT NULL,
                measurement VARCHAR(80) NOT NULL,
                unit VARCHAR(32) NOT NULL,
                location VARCHAR(120) NOT NULL DEFAULT '',
                baseline_tolerance FLOAT,
                created_at DATETIME NOT NULL
            )
            """
        )
    monkeypatch.setattr("app.database.engine", legacy_engine)

    init_db()

    with legacy_engine.connect() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(configured_sensors)")
        }
    legacy_engine.dispose()
    assert "expected_interval_seconds" in columns
