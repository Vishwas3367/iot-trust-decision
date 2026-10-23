# IoT Sensor Trust & Decision Demo

A software prototype for receiving sensor readings, learning what is normal for
each sensor, and highlighting readings that may need attention. It includes a
simulated industrial machine, a configurable sensor workflow, a REST API, and a
web dashboard.

No physical sensors are needed to run the demo.

## What the system does

There are two separate workflows:

### 1. PRESS-04 demo

The virtual sensors repeatedly send temperature readings. The trust engine
checks whether readings are recent, agree with other sensors, match their
history, and have acceptable communication quality. It then recommends normal
operation, a warning, a shutdown, more data, or human review.

Use **Overview**, **Sensor readings**, **Try a scenario**, and **History & trends**
in the dashboard to explore this workflow.

### 2. Your configured sensors

Add sensors with any measurement name and unit, such as `temperature` / `°C`,
`vibration` / `mm/s`, or `humidity` / `%`. Send readings manually through the
dashboard or from a device through the REST API. Each sensor is compared with
its own readings; different sensor types and units are never compared to each
other.

The first five readings teach the system the sensor's usual range. Starting
with the sixth reading, the system compares the latest reading against the
previous five (up to a 30-reading history window). It marks a reading as
unusual when it is far from that sensor's baseline. Old readings and weak
connections are flagged separately.

This baseline feature is a prototype to help review data. It is not a certified
alarm or a safety controller.

## Dashboard pages

| Page | What it is for |
|---|---|
| **Overview** | Current PRESS-04 recommendation and a quick sensor summary |
| **Sensor readings** | Details for the virtual PRESS-04 sensors |
| **Try a scenario** | Test normal, faulty, stale, weak-network, and emergency examples |
| **History & trends** | Charts of virtual sensor readings and decision confidence |
| **Sensor setup** | Add or remove your own sensor definitions |
| **My readings** | Enter readings and see baseline results for configured sensors |

## Run locally

Requirements: Python 3.11 or later, Node.js 20.19+ or 22.12+, and npm.

Run these commands from the project root.

### 1. Install backend packages

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
```

If an existing `.venv` was created in another folder and reports a bad
interpreter, recreate that virtual environment with:

```bash
python3 -m venv --clear .venv
.venv/bin/python -m pip install -r backend/requirements.txt
```

### 2. Start the backend

In terminal 1:

```bash
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

The backend creates or updates the local SQLite database at
`backend/data/iot_trust.db` when it starts.

### 3. Start the dashboard

In terminal 2, from the project root:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The dashboard sends API requests to the backend
through the Vite development proxy.

Check backend status at <http://127.0.0.1:8000/api/health>. Interactive API
documentation is at <http://127.0.0.1:8000/docs>.

## Configure a sensor

1. Open **Sensor setup**.
2. Enter a unique sensor ID, a name, the measured quantity, and its unit.
3. Set the expected reporting interval in seconds.
4. Optionally enter the smallest normal variation for readings that otherwise
   have no variation in the baseline.
5. Select **Add sensor**.
6. Open **My readings** and submit readings for that sensor.
7. Collect at least five normal readings. The sixth and later readings can be
   checked against its learned baseline.

The sensor ID is the identifier devices must use when sending readings.
Removing a configured sensor also removes its saved readings.

## Send readings from a device

Add a sensor first using **Sensor setup** or `POST /api/customer/sensors`.
Then send a reading to `POST /api/customer/readings`:

```json
{
  "sensor_id": "motor-vibration-1",
  "value": 2.4,
  "network_quality": 0.95
}
```

`network_quality` is optional and defaults to `1.0`; valid values are from
`0.0` to `1.0`. `timestamp` is also optional and defaults to the server's
current time. If supplied, it must be a Unix timestamp and cannot be more than
five minutes in the future.

Use the same numeric unit for every reading sent to a given sensor. The API
stores the unit on the sensor definition; it does not convert units.

## API reference

### Configured sensors

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/customer/sensors` | List configured sensors |
| `POST` | `/api/customer/sensors` | Create a sensor |
| `DELETE` | `/api/customer/sensors/{sensor_id}` | Remove sensor and saved readings |
| `GET` | `/api/customer/state` | Get latest readings and baseline results |
| `POST` | `/api/customer/readings` | Submit a device or manual reading |

Example sensor definition:

```json
{
  "sensor_id": "motor-vibration-1",
  "name": "Motor vibration",
  "measurement": "vibration",
  "unit": "mm/s",
  "location": "Motor A",
  "expected_interval_seconds": 60,
  "baseline_tolerance": 0.1
}
```

`sensor_id`, `name`, `measurement`, and `unit` are required.
`expected_interval_seconds` defaults to 60 and must be from 1 to 86400.
`baseline_tolerance` is optional and must be zero or greater.

### PRESS-04 virtual demo

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Check that the backend is running |
| `GET` | `/api/state` | Get latest demo sensor readings and decision |
| `GET` | `/api/history?limit=80` | Get recent demo cycles |
| `GET` | `/api/scenarios` | List available demo situations |
| `POST` | `/api/scenarios/apply` | Start a scenario with `{"name":"emergency"}` |
| `POST` | `/api/request-data` | Generate an additional virtual reading |
| `POST` | `/api/ingest` | Send a batch in the PRESS-04 observation format |
| `POST` | `/api/simulator/start` | Start automatic virtual readings |
| `POST` | `/api/simulator/stop` | Pause automatic virtual readings |

Available demo scenario names: `normal`, `one_faulty`, `split_conflict`,
`poor_network`, `stale`, and `emergency`.

## Run tests and checks

From the project root:

```bash
.venv/bin/python -m pytest -q
cd frontend
npm run build
npm run lint
```

The backend tests cover the PRESS-04 scenarios, decision bands, configurable
sensor baselines, stale readings, unknown sensor IDs, and upgrading an older
SQLite schema.

## Project structure

```text
backend/
  app/
    engine/             PRESS-04 simulation and trust/decision pipeline
    configured_sensors.py
                        User-configured sensor storage and baseline checks
    main.py             FastAPI routes
    database.py         SQLite connection and startup schema update
    models.py           Database tables
  tests/                Backend tests
frontend/
  src/App.tsx            Main dashboard navigation and PRESS-04 pages
  src/CustomerWorkspace.tsx
                         Sensor setup and customer reading pages
  src/api.ts             Frontend API calls
docs/
  INVENTION.md           Decision-mechanism notes
```

## Current limits

- This is a prototype; no physical sensors or MQTT connector are included.
- Configured sensors learn a separate baseline for each sensor. The system does
  not combine different measurements into one machine-level decision.
- Sensor names and units are customer-defined labels; the system does not
  validate conversions or whether a unit is suitable for a measurement.
- The app currently has one shared workspace, with no login or customer-data
  separation. Do not expose it to multiple customers as a hosted service yet.
- Recommendations are advisory and must not be used to control safety-critical
  equipment.

## Design notes

See [docs/INVENTION.md](docs/INVENTION.md) for how the PRESS-04 trust, conflict,
confidence, and decision mechanism works.
