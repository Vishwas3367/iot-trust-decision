from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import configured_sensors
from app.database import init_db
from app.engine.types import Observation
from app.runtime import runtime
from app.schemas import (
    ConfiguredReadingCreate,
    ConfiguredSensorCreate,
    IngestRequest,
    ScenarioRequest,
)

SCENARIOS = {
    "normal": "Healthy sensors agree in the normal band.",
    "one_faulty": "One spike outlier; trust should ignore it.",
    "split_conflict": "Two factions; trust mass, not vote count, decides.",
    "poor_network": "A dangerous reading arrives stale over a weak link.",
    "stale": "One otherwise-plausible reading is too old.",
    "emergency": "Fresh, high-trust sensors agree on an emergency.",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    runtime.apply_scenario("normal")
    await runtime.start()
    yield
    await runtime.stop()


app = FastAPI(
    title="IoT Context-Aware Trust Decision API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "running": runtime.running, "cycle": runtime.cycle}


@app.get("/api/state")
def state():
    if runtime.latest is None:
        runtime.tick()
    return runtime.latest


@app.get("/api/history")
def history(limit: int = 80):
    return runtime.history[-limit:]


@app.get("/api/scenarios")
def scenarios():
    return [{"id": key, "description": value} for key, value in SCENARIOS.items()]


@app.post("/api/tick")
def tick():
    return runtime.tick()


@app.post("/api/simulator/start")
async def start():
    await runtime.start()
    return {"running": True}


@app.post("/api/simulator/stop")
async def stop():
    await runtime.stop()
    return {"running": False}


@app.post("/api/scenarios/apply")
def apply_scenario(req: ScenarioRequest):
    if req.name not in SCENARIOS:
        raise HTTPException(400, f"Unknown scenario: {req.name}")
    return runtime.apply_scenario(req.name)


@app.post("/api/request-data")
def request_data():
    return runtime.tick(extra=True)


@app.post("/api/ingest")
def ingest(req: IngestRequest):
    observations = [Observation(**row) for row in req.observations]
    return runtime.ingest_raw(observations, scenario=req.scenario)


@app.get("/api/customer/sensors")
def customer_sensors():
    return configured_sensors.list_sensors()


@app.post("/api/customer/sensors", status_code=201)
def add_customer_sensor(req: ConfiguredSensorCreate):
    try:
        return configured_sensors.create_sensor(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/api/customer/sensors/{sensor_id}", status_code=204)
def delete_customer_sensor(sensor_id: str):
    if not configured_sensors.remove_sensor(sensor_id):
        raise HTTPException(status_code=404, detail=f"Sensor not found: {sensor_id}")
    return None


@app.post("/api/customer/readings", status_code=201)
def add_customer_reading(req: ConfiguredReadingCreate):
    try:
        return configured_sensors.add_reading(req.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/customer/state")
def customer_dashboard_state():
    return configured_sensors.customer_state()
