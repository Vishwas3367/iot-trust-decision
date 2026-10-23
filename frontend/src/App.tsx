import { useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from './api'
import CustomerWorkspace from './CustomerWorkspace'
import type { AppState, ScenarioInfo } from './types'

type Page = 'overview' | 'sensors' | 'scenarios' | 'trends' | 'setup' | 'customer_readings'

const pages: { id: Page; label: string; icon: string }[] = [
  { id: 'overview', label: 'Overview', icon: '◫' },
  { id: 'sensors', label: 'Sensor readings', icon: '◉' },
  { id: 'scenarios', label: 'Try a scenario', icon: '◇' },
  { id: 'trends', label: 'History & trends', icon: '⌁' },
  { id: 'setup', label: 'Sensor setup', icon: '+' },
  { id: 'customer_readings', label: 'My readings', icon: '▤' },
]

const scenarioLabels: Record<string, string> = {
  normal: 'Normal readings',
  one_faulty: 'One faulty sensor',
  split_conflict: 'Sensors disagree',
  poor_network: 'Weak connection',
  stale: 'Old reading',
  emergency: 'Very high temperature',
}

const scenarioDescriptions: Record<string, string> = {
  normal: 'All sensors report a similar temperature.',
  one_faulty: 'One sensor reports a very different temperature.',
  split_conflict: 'Two sensors report hot; two report cool.',
  poor_network: 'A high reading arrives through a weak connection.',
  stale: 'One sensor reading is out of date.',
  emergency: 'All sensors report a dangerously high temperature.',
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`
}

function recommendation(state: AppState) {
  const { action, machine_action: machineAction, consensus_temperature: temperature } = state.decision
  if (action === 'REQUEST_DATA') return 'Get another reading before deciding'
  if (action === 'DEFER') return 'Pause and ask someone to review'
  if (machineAction === 'SHUTDOWN') return 'Temperature is dangerously high'
  if (machineAction === 'WARN') return 'Temperature is higher than normal'
  return temperature == null ? 'Not enough information to decide' : 'Temperature looks normal'
}

function decisionStyle(action: AppState['decision']['action']) {
  if (action === 'EXECUTE') {
    return {
      card: 'border-teal-400/25 bg-[linear-gradient(120deg,rgba(13,69,64,0.75),rgba(11,24,32,0.9))]',
      badge: 'bg-teal-300/15 text-teal-200',
      dot: 'bg-teal-300',
    }
  }
  if (action === 'REQUEST_DATA') {
    return {
      card: 'border-amber-400/25 bg-[linear-gradient(120deg,rgba(85,58,22,0.7),rgba(11,24,32,0.9))]',
      badge: 'bg-amber-300/15 text-amber-200',
      dot: 'bg-amber-300',
    }
  }
  return {
    card: 'border-rose-400/25 bg-[linear-gradient(120deg,rgba(84,32,40,0.7),rgba(11,24,32,0.9))]',
    badge: 'bg-rose-300/15 text-rose-200',
    dot: 'bg-rose-300',
  }
}

function sensorStatus(status: string) {
  if (status === 'TRUSTED') return 'Good'
  if (status === 'UNCERTAIN') return 'Check'
  if (status === 'INVALID') return 'Invalid'
  return 'Poor'
}

function statusColor(status: string) {
  if (status === 'TRUSTED') return 'text-teal-300'
  if (status === 'UNCERTAIN') return 'text-amber-300'
  return 'text-rose-300'
}

function sensorNote(notes: string[]) {
  if (notes.includes('stale observation')) return 'Reading is old'
  if (notes.includes('poor communication')) return 'Weak connection'
  if (notes.includes('abrupt temporal jump')) return 'Sudden change'
  if (notes.includes('disagrees with peer sources')) return 'Different from other sensors'
  if (notes.length) return 'Needs checking'
  return 'No issue found'
}

export default function App() {
  const [state, setState] = useState<AppState | null>(null)
  const [history, setHistory] = useState<AppState[]>([])
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([])
  const [page, setPage] = useState<Page>('overview')
  const [running, setRunning] = useState(true)
  const [error, setError] = useState<string | null>(null)

  function showError(err: unknown) {
    setError(err instanceof Error ? err.message : 'Could not contact the server.')
  }

  async function refresh() {
    try {
      const [nextState, nextHistory] = await Promise.all([api.state(), api.history()])
      setState(nextState)
      setHistory(nextHistory)
      setError(null)
    } catch (err) {
      showError(err)
    }
  }

  useEffect(() => {
    api.scenarios().then(setScenarios).catch(showError)
    void refresh()
  }, [])

  useEffect(() => {
    if (!running) return
    const interval = window.setInterval(() => void refresh(), 2000)
    return () => window.clearInterval(interval)
  }, [running])

  async function chooseScenario(name: string) {
    try {
      setState(await api.apply(name))
      setPage('overview')
      setError(null)
    } catch (err) {
      showError(err)
    }
  }

  async function requestReading() {
    try {
      setState(await api.requestData())
      await refresh()
    } catch (err) {
      showError(err)
    }
  }

  async function toggleUpdates() {
    try {
      if (running) await api.stop()
      else await api.start()
      setRunning(!running)
    } catch (err) {
      showError(err)
    }
  }

  const chartData = useMemo(
    () =>
      history.map((row) => {
        const point: Record<string, number> = {
          cycle: row.cycle,
          confidence: Math.round(row.decision.confidence * 100),
          consensus: row.decision.consensus_temperature ?? 0,
        }
        for (const sensor of row.sensors) {
          point[`${sensor.sensor_id}`] = sensor.temperature
        }
        return point
      }),
    [history],
  )

  if (!state) {
    return (
      <main className="grid min-h-screen place-items-center px-5 py-10">
        <section className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#0b1820] p-6 shadow-2xl">
          <div className="mb-5 grid h-11 w-11 place-items-center rounded-xl bg-teal-300/10 text-xl text-teal-200">◉</div>
          <h1 className="text-xl font-semibold text-slate-100">
            {error ? 'Backend is not running' : 'Connecting…'}
          </h1>
          {error && (
            <>
              <p className="mt-2 text-sm text-slate-400">Start the backend, then try again.</p>
              <pre className="mt-4 whitespace-pre-wrap rounded-lg bg-black/30 p-3 text-sm text-slate-200">
                cd backend{'\n'}../.venv/bin/python -m uvicorn app.main:app --reload --port 8000
              </pre>
              <button
                className="mt-4 rounded-lg bg-teal-300 px-4 py-2 font-semibold text-slate-950"
                onClick={() => void refresh()}
              >
                Try again
              </button>
            </>
          )}
        </section>
      </main>
    )
  }

  const decision = state.decision
  const style = decisionStyle(decision.action)
  const activeScenario = scenarioLabels[state.simulator.scenario ?? ''] ?? 'Live demo'
  const pageTitle = pages.find((item) => item.id === page)?.label ?? 'Overview'

  return (
    <div className="min-h-screen lg:flex">
      <aside className="border-b border-white/10 bg-[#09141b] lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col lg:border-b-0 lg:border-r">
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-teal-300/10 text-lg text-teal-200">◉</div>
          <div>
            <p className="font-semibold tracking-wide text-slate-100">SENSOR DESK</p>
            <p className="text-xs text-slate-500">IoT decision demo</p>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-1 lg:flex-col lg:overflow-visible lg:py-5" aria-label="Main navigation">
          {pages.map((item) => (
            <button
              key={item.id}
              onClick={() => setPage(item.id)}
              aria-current={page === item.id ? 'page' : undefined}
              className={`flex shrink-0 items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                page === item.id
                  ? 'bg-teal-300/10 font-medium text-teal-100'
                  : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'
              }`}
            >
              <span className="w-5 text-center text-base">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="hidden border-t border-white/10 p-4 text-xs text-slate-500 lg:block">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${running ? 'bg-teal-300' : 'bg-slate-500'}`} />
            {running ? 'Demo is updating' : 'Demo is paused'}
          </div>
          <p className="mt-2">Simulation only · no real equipment</p>
        </div>
      </aside>

      <div className="min-w-0 flex-1 lg:ml-64">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-white/10 bg-[#071018]/90 px-5 py-4 backdrop-blur sm:px-8">
          <div>
            <p className="text-xs text-slate-500">PRESS-04 / DEMO</p>
            <h1 className="mt-0.5 text-lg font-semibold text-slate-100">{pageTitle}</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              className="rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-300 hover:bg-white/5"
              onClick={() => void toggleUpdates()}
            >
              {running ? 'Pause' : 'Resume'}
            </button>
            {page !== 'setup' && page !== 'customer_readings' && (
              <button
                className="rounded-lg bg-teal-300 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-teal-200"
                onClick={() => void requestReading()}
              >
                New demo reading
              </button>
            )}
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-5 py-6 sm:px-8">
          {error && (
            <p role="alert" className="mb-5 rounded-lg border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
              Update failed: {error}
            </p>
          )}
          {page === 'overview' && (
            <Overview
              state={state}
              style={style}
              activeScenario={activeScenario}
              onViewSensors={() => setPage('sensors')}
              onViewScenarios={() => setPage('scenarios')}
              onChooseScenario={chooseScenario}
            />
          )}
          {page === 'sensors' && <Sensors state={state} />}
          {page === 'scenarios' && (
            <Scenarios
              scenarios={scenarios}
              activeScenario={state.simulator.scenario}
              onChoose={chooseScenario}
            />
          )}
          {page === 'trends' && <Trends data={chartData} />}
          {(page === 'setup' || page === 'customer_readings') && (
            <CustomerWorkspace page={page} />
          )}
        </main>
      </div>
    </div>
  )
}

function Overview({
  state,
  style,
  activeScenario,
  onViewSensors,
  onViewScenarios,
  onChooseScenario,
}: {
  state: AppState
  style: ReturnType<typeof decisionStyle>
  activeScenario: string
  onViewSensors: () => void
  onViewScenarios: () => void
  onChooseScenario: (name: string) => void
}) {
  const decision = state.decision
  return (
    <div className="space-y-6">
      <section className={`overflow-hidden rounded-2xl border p-6 shadow-xl sm:p-8 ${style.card}`}>
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="max-w-2xl">
            <div className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${style.badge}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
              {decision.action === 'EXECUTE'
                ? decision.machine_action === 'SHUTDOWN'
                  ? 'ACTION RECOMMENDED'
                  : 'NORMAL OPERATION'
                : decision.action === 'REQUEST_DATA'
                  ? 'NEED MORE DATA'
                  : 'REVIEW NEEDED'}
            </div>
            <h2 className="mt-4 text-2xl font-semibold leading-tight text-white sm:text-3xl">
              {recommendation(state)}
            </h2>
            <p className="mt-2 text-sm text-slate-300">
              {decision.consensus_temperature == null
                ? 'No temperature estimate available.'
                : `Estimated temperature: ${decision.consensus_temperature.toFixed(1)}°C`}
            </p>
          </div>
          <div className="w-full max-w-xs rounded-xl border border-white/10 bg-black/15 p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-300">Decision confidence</span>
              <span className="font-semibold text-white">{percent(decision.confidence)}</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-black/30">
              <div className={`h-full rounded-full ${style.dot}`} style={{ width: percent(decision.confidence) }} />
            </div>
            <div className="mt-2 flex justify-between text-[10px] text-slate-500">
              <span>Need more data</span><span>Ready</span>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Sensor agreement"
          value={decision.conflict.level === 'LOW' ? 'Good' : decision.conflict.level === 'MEDIUM' ? 'Mixed' : 'Poor'}
          detail={`${Math.round(decision.conflict.score * 100)}% disagreement`}
          tone={decision.conflict.level === 'LOW' ? 'teal' : decision.conflict.level === 'MEDIUM' ? 'amber' : 'rose'}
        />
        <StatCard label="Sensors online" value={`${state.sensors.length}`} detail="Sending readings" tone="blue" />
        <StatCard label="Current example" value={activeScenario} detail={`Demo cycle ${state.cycle}`} tone="violet" />
        <StatCard
          label="Recommended action"
          value={decision.machine_action === 'HOLD' ? 'Wait' : decision.machine_action === 'SHUTDOWN' ? 'Stop machine' : decision.machine_action === 'WARN' ? 'Show warning' : 'Continue'}
          detail="Simulation only"
          tone="teal"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <div className="rounded-xl border border-white/10 bg-[#0b1820]/85 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-slate-100">Latest sensor readings</h3>
              <p className="mt-1 text-xs text-slate-500">Temperature and reading quality</p>
            </div>
            <button onClick={onViewSensors} className="text-sm text-teal-200 hover:text-teal-100">All sensors →</button>
          </div>
          <div className="mt-4 space-y-3">
            {state.sensors.map((sensor) => (
              <div key={sensor.sensor_id} className="flex items-center gap-3">
                <span className="w-10 text-xs font-medium text-slate-400">{sensor.sensor_id}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/5">
                  <div
                    className={`h-full rounded-full ${sensor.trust?.status === 'TRUSTED' ? 'bg-teal-300' : sensor.trust?.status === 'UNCERTAIN' ? 'bg-amber-300' : 'bg-rose-300'}`}
                    style={{ width: `${Math.max(4, Math.min(100, sensor.temperature))}%` }}
                  />
                </div>
                <span className="w-16 text-right font-mono text-sm text-slate-200">{sensor.temperature.toFixed(1)}°C</span>
                <span className={`hidden w-12 text-right text-xs sm:block ${statusColor(sensor.trust?.status ?? '')}`}>
                  {sensor.trust ? sensorStatus(sensor.trust.status) : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#0b1820]/85 p-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-slate-100">Try another example</h3>
              <p className="mt-1 text-xs text-slate-500">Change the sensor situation</p>
            </div>
            <button onClick={onViewScenarios} className="text-sm text-teal-200 hover:text-teal-100">See all →</button>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            {['normal', 'one_faulty', 'poor_network', 'emergency'].map((name) => (
              <button
                key={name}
                onClick={() => void onChooseScenario(name)}
                className="rounded-lg border border-white/10 bg-white/[0.025] px-3 py-3 text-left text-xs text-slate-300 hover:border-teal-300/30 hover:bg-teal-300/5"
              >
                {scenarioLabels[name]}
              </button>
            ))}
          </div>
        </div>
      </section>
      <p className="text-center text-xs text-slate-600">Virtual sensor simulation · Does not control real equipment</p>
    </div>
  )
}

function StatCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string
  value: string
  detail: string
  tone: 'teal' | 'amber' | 'rose' | 'blue' | 'violet'
}) {
  const accent = {
    teal: 'text-teal-200 bg-teal-300/10',
    amber: 'text-amber-200 bg-amber-300/10',
    rose: 'text-rose-200 bg-rose-300/10',
    blue: 'text-sky-200 bg-sky-300/10',
    violet: 'text-violet-200 bg-violet-300/10',
  }[tone]
  return (
    <article className="rounded-xl border border-white/10 bg-[#0b1820]/85 p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-2 inline-flex max-w-full rounded-md px-2 py-1 text-lg font-semibold ${accent}`}>{value}</p>
      <p className="mt-2 text-xs text-slate-500">{detail}</p>
    </article>
  )
}

function Sensors({ state }: { state: AppState }) {
  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-100">Sensor readings</h2>
          <p className="mt-1 text-sm text-slate-500">Latest temperature and connection details</p>
        </div>
        <span className="text-xs text-slate-500">{state.sensors.length} sensors · updates every 2 seconds</span>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {state.sensors.map((sensor) => (
          <article key={sensor.sensor_id} className="rounded-xl border border-white/10 bg-[#0b1820]/90 p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-wider text-slate-500">{String(sensor.context.location ?? 'Sensor')}</p>
                <h3 className="mt-1 text-lg font-semibold text-slate-100">{sensor.sensor_id}</h3>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${sensor.trust?.status === 'TRUSTED' ? 'bg-teal-300/10 text-teal-200' : sensor.trust?.status === 'UNCERTAIN' ? 'bg-amber-300/10 text-amber-200' : 'bg-rose-300/10 text-rose-200'}`}>
                {sensor.trust ? sensorStatus(sensor.trust.status) : 'Unknown'}
              </span>
            </div>
            <div className="mt-5 flex items-end justify-between border-b border-white/10 pb-4">
              <div>
                <p className="text-xs text-slate-500">Temperature</p>
                <p className="mt-1 text-3xl font-semibold text-white">{sensor.temperature.toFixed(1)}<span className="ml-1 text-base text-slate-400">°C</span></p>
              </div>
              <div className="text-right">
                <p className="text-xs text-slate-500">Reliability</p>
                <p className={`mt-1 text-lg font-semibold ${statusColor(sensor.trust?.status ?? '')}`}>
                  {sensor.trust ? percent(sensor.trust.trust_score) : '—'}
                </p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <Quality label="Reading age" value={sensor.trust?.freshness ?? 0} />
              <Quality label="Connection" value={sensor.network_quality} />
            </div>
            <p className={`mt-4 rounded-lg bg-white/[0.03] px-3 py-2 text-sm ${sensor.trust?.notes.length ? 'text-amber-200' : 'text-slate-400'}`}>
              {sensor.trust ? sensorNote(sensor.trust.notes) : 'No reading available'}
            </p>
          </article>
        ))}
      </div>
    </div>
  )
}

function Quality({ label, value }: { label: string; value: number }) {
  const state = value >= 0.8 ? 'Good' : value >= 0.5 ? 'Fair' : 'Poor'
  const color = value >= 0.8 ? 'text-teal-200' : value >= 0.5 ? 'text-amber-200' : 'text-rose-200'
  return (
    <div className="rounded-lg bg-white/[0.035] p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <div className="mt-1 flex items-baseline justify-between">
        <span className={`text-sm font-medium ${color}`}>{state}</span>
        <span className="font-mono text-xs text-slate-400">{percent(value)}</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full ${value >= 0.8 ? 'bg-teal-300' : value >= 0.5 ? 'bg-amber-300' : 'bg-rose-300'}`} style={{ width: percent(value) }} />
      </div>
    </div>
  )
}

function Scenarios({
  scenarios,
  activeScenario,
  onChoose,
}: {
  scenarios: ScenarioInfo[]
  activeScenario: string | null
  onChoose: (name: string) => void
}) {
  return (
    <div>
      <div className="mb-5">
        <h2 className="text-xl font-semibold text-slate-100">Choose a sensor situation</h2>
        <p className="mt-1 text-sm text-slate-500">Select an example to see how the recommendation changes.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {scenarios.map((scenario) => (
          <button
            key={scenario.id}
            onClick={() => onChoose(scenario.id)}
            aria-pressed={activeScenario === scenario.id}
            className={`group rounded-xl border p-5 text-left transition-all hover:-translate-y-0.5 ${
              activeScenario === scenario.id
                ? 'border-teal-300/50 bg-teal-300/[0.08] shadow-lg shadow-teal-950/20'
                : 'border-white/10 bg-[#0b1820]/90 hover:border-white/20 hover:bg-[#10212b]'
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="grid h-10 w-10 place-items-center rounded-lg bg-white/5 text-lg text-teal-200">
                {scenario.id === 'normal' ? '✓' : scenario.id === 'emergency' ? '!' : scenario.id === 'stale' ? '◷' : '⌁'}
              </div>
              {activeScenario === scenario.id && <span className="text-xs text-teal-200">Selected</span>}
            </div>
            <h3 className="mt-4 font-semibold text-slate-100">{scenarioLabels[scenario.id] ?? scenario.id}</h3>
            <p className="mt-1 text-sm leading-5 text-slate-400">
              {scenarioDescriptions[scenario.id] ?? scenario.description}
            </p>
            <span className="mt-4 inline-block text-sm font-medium text-teal-200 group-hover:text-teal-100">
              View result →
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}

function Trends({ data }: { data: Record<string, number>[] }) {
  const tooltipStyle = { background: '#102029', border: '1px solid #29404b', borderRadius: 8 }
  return (
    <div className="space-y-4">
      <div className="mb-5">
        <h2 className="text-xl font-semibold text-slate-100">History & trends</h2>
        <p className="mt-1 text-sm text-slate-500">See how sensor readings and confidence change over time.</p>
      </div>
      <section className="rounded-xl border border-white/10 bg-[#0b1820]/90 p-5">
        <h3 className="font-semibold text-slate-100">Temperature by sensor</h3>
        <p className="mt-1 text-xs text-slate-500">Temperature in °C · dashed line is the decision value</p>
        <div className="mt-4 h-72">
          {data.length < 2 ? (
            <div className="grid h-full place-items-center text-sm text-slate-500">Waiting for more readings…</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid stroke="rgba(255,255,255,0.07)" />
                <XAxis dataKey="cycle" stroke="#71838d" tickLine={false} />
                <YAxis stroke="#71838d" tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
                <Line type="monotone" dataKey="S01" name="Sensor 1" stroke="#f3b34c" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="S02" name="Sensor 2" stroke="#41c9b5" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="S03" name="Sensor 3" stroke="#8ea9ff" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="S04" name="Sensor 4" stroke="#ed7d83" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="consensus" name="Decision value" stroke="#f4f1de" strokeDasharray="5 4" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>
      <section className="rounded-xl border border-white/10 bg-[#0b1820]/90 p-5">
        <h3 className="font-semibold text-slate-100">Decision confidence</h3>
        <p className="mt-1 text-xs text-slate-500">Higher percentage means clearer support from the sensor readings.</p>
        <div className="mt-4 h-64">
          {data.length < 2 ? (
            <div className="grid h-full place-items-center text-sm text-slate-500">Waiting for more readings…</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid stroke="rgba(255,255,255,0.07)" />
                <XAxis dataKey="cycle" stroke="#71838d" tickLine={false} />
                <YAxis stroke="#71838d" domain={[0, 100]} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="confidence" name="Confidence %" stroke="#41c9b5" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>
    </div>
  )
}
