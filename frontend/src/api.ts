import type { AppState, ConfiguredDashboard, ConfiguredSensor, ScenarioInfo } from './types'

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(await res.text())
  }
  return res.json() as Promise<T>
}

export const api = {
  state: () => fetch('/api/state').then((r) => asJson<AppState>(r)),
  history: () => fetch('/api/history?limit=60').then((r) => asJson<AppState[]>(r)),
  scenarios: () => fetch('/api/scenarios').then((r) => asJson<ScenarioInfo[]>(r)),
  apply: (name: string) =>
    fetch('/api/scenarios/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }).then((r) => asJson<AppState>(r)),
  start: () =>
    fetch('/api/simulator/start', { method: 'POST' }).then((r) =>
      asJson<{ running: boolean }>(r),
    ),
  stop: () =>
    fetch('/api/simulator/stop', { method: 'POST' }).then((r) =>
      asJson<{ running: boolean }>(r),
    ),
  requestData: () =>
    fetch('/api/request-data', { method: 'POST' }).then((r) => asJson<AppState>(r)),
  configuredSensors: () =>
    fetch('/api/customer/sensors').then((r) => asJson<ConfiguredSensor[]>(r)),
  configuredState: () =>
    fetch('/api/customer/state').then((r) => asJson<ConfiguredDashboard>(r)),
  addConfiguredSensor: (sensor: Omit<ConfiguredSensor, 'created_at'>) =>
    fetch('/api/customer/sensors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sensor),
    }).then((r) => asJson<ConfiguredSensor>(r)),
  removeConfiguredSensor: (sensorId: string) =>
    fetch(`/api/customer/sensors/${encodeURIComponent(sensorId)}`, { method: 'DELETE' }).then(
      async (r) => {
        if (!r.ok) throw new Error(await r.text())
      },
    ),
  addConfiguredReading: (reading: {
    sensor_id: string
    value: number
    network_quality: number
  }) =>
    fetch('/api/customer/readings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(reading),
    }).then((r) => asJson<{ id: number; sensor_id: string; timestamp: number }>(r)),
}
