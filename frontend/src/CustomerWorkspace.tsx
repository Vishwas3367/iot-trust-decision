import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { api } from './api'
import type { ConfiguredDashboard, ConfiguredSensor } from './types'

type WorkspacePage = 'setup' | 'customer_readings'

export default function CustomerWorkspace({ page }: { page: WorkspacePage }) {
  const [sensors, setSensors] = useState<ConfiguredSensor[]>([])
  const [dashboard, setDashboard] = useState<ConfiguredDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const [sensorId, setSensorId] = useState('')
  const [readingValue, setReadingValue] = useState('')
  const [networkQuality, setNetworkQuality] = useState('1')
  const [submitting, setSubmitting] = useState(false)

  async function loadWorkspace() {
    setLoading(true)
    try {
      const [nextSensors, nextDashboard] = await Promise.all([
        api.configuredSensors(),
        api.configuredState(),
      ])
      setSensors(nextSensors)
      setDashboard(nextDashboard)
      setSensorId((current) => current || nextSensors[0]?.sensor_id || '')
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load sensors.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadWorkspace()
  }, [])

  async function saveSensor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const formElement = event.currentTarget
    const form = new FormData(formElement)
    const toleranceText = String(form.get('baseline_tolerance') ?? '').trim()
    const tolerance = toleranceText ? Number(toleranceText) : null
    try {
      const created = await api.addConfiguredSensor({
        sensor_id: String(form.get('sensor_id')).trim(),
        name: String(form.get('name')).trim(),
        measurement: String(form.get('measurement')).trim(),
        unit: String(form.get('unit')).trim(),
        location: String(form.get('location') ?? '').trim(),
        expected_interval_seconds: Number(form.get('expected_interval_seconds')),
        baseline_tolerance: tolerance,
      })
      formElement.reset()
      setSaved(`Added ${created.name}.`)
      await loadWorkspace()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add sensor.')
    }
  }

  async function deleteSensor(sensor: ConfiguredSensor) {
    if (!window.confirm(`Remove ${sensor.name} and its saved readings?`)) return
    try {
      await api.removeConfiguredSensor(sensor.sensor_id)
      setSaved(`Removed ${sensor.name}.`)
      setSensorId('')
      await loadWorkspace()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove sensor.')
    }
  }

  async function submitReading(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!sensorId) return
    setSubmitting(true)
    try {
      await api.addConfiguredReading({
        sensor_id: sensorId,
        value: Number(readingValue),
        network_quality: Number(networkQuality),
      })
      setSaved('Reading received.')
      setReadingValue('')
      await loadWorkspace()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save reading.')
    } finally {
      setSubmitting(false)
    }
  }

  const resultStyle = dashboard?.summary.status === 'CHECK'
    ? 'border-rose-400/30 bg-rose-400/10 text-rose-100'
    : dashboard?.summary.status === 'NORMAL'
      ? 'border-teal-400/30 bg-teal-400/10 text-teal-100'
      : 'border-amber-400/30 bg-amber-400/10 text-amber-100'

  if (loading && !dashboard) {
    return <p className="py-10 text-center text-slate-400">Loading…</p>
  }

  return (
    <div className="space-y-5">
      {(error || saved) && (
        <div
          role={error ? 'alert' : 'status'}
          className={`rounded-lg border px-4 py-3 text-sm ${error ? 'border-rose-400/30 bg-rose-500/10 text-rose-200' : 'border-teal-400/20 bg-teal-400/5 text-teal-200'}`}
        >
          {error ?? saved}
          {error && (
            <button className="ml-3 underline" onClick={() => void loadWorkspace()}>
              Retry
            </button>
          )}
        </div>
      )}

      {page === 'setup' ? (
        <>
          <div>
            <h2 className="text-xl font-semibold text-slate-100">Set up your sensors</h2>
            <p className="mt-1 text-sm text-slate-500">Add the sensor details once, then send readings to it.</p>
          </div>
          <form onSubmit={saveSensor} className="grid gap-4 rounded-xl border border-white/10 bg-[#0b1820]/90 p-5 sm:grid-cols-2">
            <Field label="Sensor ID">
              <input name="sensor_id" required maxLength={64} placeholder="for example, motor-temp-1" className="input" />
            </Field>
            <Field label="Sensor name">
              <input name="name" required maxLength={120} placeholder="Motor temperature" className="input" />
            </Field>
            <Field label="What does it measure?">
              <input name="measurement" required maxLength={80} placeholder="temperature, vibration, humidity…" className="input" />
            </Field>
            <Field label="Unit">
              <input name="unit" required maxLength={32} placeholder="°C, mm/s, %…" className="input" />
            </Field>
            <Field label="Location (optional)">
              <input name="location" maxLength={120} placeholder="Motor A" className="input" />
            </Field>
            <Field label="Reading interval (seconds)">
              <input name="expected_interval_seconds" type="number" min="1" max="86400" step="1" defaultValue="60" required className="input" />
            </Field>
            <Field label="Smallest normal change (optional)">
              <input name="baseline_tolerance" type="number" min="0" step="any" placeholder="for example, 0.1" className="input" />
            </Field>
            <div className="sm:col-span-2">
              <button className="rounded-lg bg-teal-300 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-teal-200">
                Add sensor
              </button>
            </div>
          </form>

          <section className="overflow-hidden rounded-xl border border-white/10 bg-[#0b1820]/90">
            <div className="border-b border-white/10 px-5 py-4">
              <h3 className="font-semibold text-slate-100">Configured sensors <span className="ml-1 text-slate-500">({sensors.length})</span></h3>
            </div>
            {sensors.length ? (
              <div className="divide-y divide-white/5">
                {sensors.map((sensor) => (
                  <div key={sensor.sensor_id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                    <div>
                      <p className="font-medium text-slate-100">{sensor.name} <span className="text-xs text-slate-500">({sensor.sensor_id})</span></p>
                      <p className="mt-1 text-sm text-slate-400">{sensor.measurement} · {sensor.unit}{sensor.location ? ` · ${sensor.location}` : ''}</p>
                    </div>
                    <button
                      className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-slate-400 hover:border-rose-300/30 hover:text-rose-200"
                      onClick={() => void deleteSensor(sensor)}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="px-5 py-8 text-center text-sm text-slate-500">No sensors added yet.</p>
            )}
          </section>
        </>
      ) : (
        <>
          <div>
            <h2 className="text-xl font-semibold text-slate-100">Your sensor readings</h2>
            <p className="mt-1 text-sm text-slate-500">Add a reading or send it from a device using the API.</p>
          </div>
          {dashboard && (
            <section className={`rounded-xl border p-5 ${resultStyle}`}>
              <p className="text-xs uppercase tracking-wider opacity-75">Current result</p>
              <h3 className="mt-1 text-xl font-semibold">{dashboard.summary.message}</h3>
            </section>
          )}
          <form onSubmit={submitReading} className="grid gap-4 rounded-xl border border-white/10 bg-[#0b1820]/90 p-5 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end">
            <Field label="Sensor">
              <select required value={sensorId} onChange={(event) => setSensorId(event.target.value)} className="input">
                <option value="">Choose sensor</option>
                {sensors.map((sensor) => (
                  <option key={sensor.sensor_id} value={sensor.sensor_id}>
                    {sensor.name} ({sensor.unit})
                  </option>
                ))}
              </select>
            </Field>
            <Field label={`Reading value${sensors.find((sensor) => sensor.sensor_id === sensorId) ? ` (${sensors.find((sensor) => sensor.sensor_id === sensorId)?.unit})` : ''}`}>
              <input required type="number" step="any" value={readingValue} onChange={(event) => setReadingValue(event.target.value)} className="input" />
            </Field>
            <Field label="Connection quality (0–1)">
              <input required type="number" min="0" max="1" step="0.01" value={networkQuality} onChange={(event) => setNetworkQuality(event.target.value)} className="input" />
            </Field>
            <button disabled={!sensors.length || submitting} className="rounded-lg bg-teal-300 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-teal-200 disabled:cursor-not-allowed disabled:opacity-50">
              {submitting ? 'Saving…' : 'Send reading'}
            </button>
          </form>
          {!sensors.length && (
            <p className="rounded-lg border border-amber-400/20 bg-amber-400/5 p-4 text-sm text-amber-100">
              Add a sensor in “Sensor setup” before sending readings.
            </p>
          )}
          <section className="grid gap-3 sm:grid-cols-2">
            {dashboard?.sensors.map((sensor) => (
              <article key={sensor.sensor_id} className="rounded-xl border border-white/10 bg-[#0b1820]/90 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-medium text-slate-100">{sensor.name}</h3>
                    <p className="text-xs text-slate-500">{sensor.measurement} · {sensor.unit}</p>
                  </div>
                  <ResultBadge status={sensor.status ?? 'NO_DATA'} />
                </div>
                {sensor.latest_value == null ? (
                  <p className="mt-4 text-sm text-slate-400">Waiting for first reading</p>
                ) : (
                  <>
                    <p className="mt-4 text-2xl font-semibold text-slate-100">{sensor.latest_value} <span className="text-sm text-slate-400">{sensor.unit}</span></p>
                    <p className="mt-1 text-sm text-slate-400">{sensor.message}</p>
                    <p className="mt-3 text-xs text-slate-500">
                      {sensor.status === 'CALIBRATING'
                        ? `${sensor.sample_count ?? 0} of ${sensor.baseline_samples_required ?? 5} readings collected`
                        : `Usual value: about ${sensor.baseline_median} ${sensor.unit}`}
                    </p>
                  </>
                )}
              </article>
            ))}
          </section>
          <details className="rounded-xl border border-white/10 bg-[#0b1820]/90 p-4">
            <summary className="cursor-pointer text-sm font-medium text-slate-200">Connect a device with REST</summary>
            <p className="mt-3 text-xs text-slate-400">Send a POST request to <code>/api/customer/readings</code>:</p>
            <pre className="mt-2 overflow-x-auto rounded-lg bg-black/30 p-3 text-xs leading-5 text-teal-100">{`{
  "sensor_id": "motor-temp-1",
  "value": 42.7,
  "network_quality": 0.94
}`}</pre>
          </details>
        </>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm text-slate-300">
      <span className="mb-1.5 block">{label}</span>
      {children}
    </label>
  )
}

function ResultBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    NO_DATA: 'bg-slate-400/10 text-slate-300',
    NO_SENSORS: 'bg-slate-400/10 text-slate-300',
    CALIBRATING: 'bg-amber-300/10 text-amber-200',
    NORMAL: 'bg-teal-300/10 text-teal-200',
    UNUSUAL: 'bg-rose-300/10 text-rose-200',
    LOW_QUALITY: 'bg-amber-300/10 text-amber-200',
    STALE: 'bg-amber-300/10 text-amber-200',
  }
  const labels: Record<string, string> = {
    NO_DATA: 'No data',
    NO_SENSORS: 'No sensors',
    CALIBRATING: 'Learning',
    NORMAL: 'Usual',
    UNUSUAL: 'Unusual',
    LOW_QUALITY: 'Weak signal',
    STALE: 'Old data',
  }
  return <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${styles[status] ?? styles.NO_DATA}`}>{labels[status] ?? status}</span>
}
