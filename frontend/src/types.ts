export type TrustBreakdown = {
  sensor_id: string
  temperature: number
  historical_reliability: number
  temporal_consistency: number
  source_agreement: number
  freshness: number
  communication_quality: number
  contextual_relevance: number
  evidence_quality: number
  trust_score: number
  status: string
  notes: string[]
}

export type Cluster = {
  sensor_ids: string[]
  centroid: number
  trust_mass: number
  size: number
}

export type DecisionPayload = {
  action: 'EXECUTE' | 'REQUEST_DATA' | 'DEFER'
  machine_action: 'NORMAL' | 'WARN' | 'SHUTDOWN' | 'HOLD'
  confidence: number
  consensus_temperature: number | null
  reason: string
  recommended: string
  factors: Record<string, number>
  scenario: string | null
  trusts: TrustBreakdown[]
  conflict: {
    level: 'LOW' | 'MEDIUM' | 'HIGH'
    score: number
    pairs: Array<{
      a: string
      b: string
      gap: number
      agreement: number
      conflict: boolean
    }>
    clusters: Cluster[]
    dominant_cluster_ids: string[]
  }
}

export type SensorRow = {
  sensor_id: string
  temperature: number
  humidity: number
  battery: number
  vibration: number
  current: number
  network_quality: number
  signal_quality: number
  timestamp: number
  historical_reliability: number
  context: Record<string, unknown>
  trust: TrustBreakdown | null
}

export type AppState = {
  cycle: number
  created_at: string
  naive_average: number | null
  simulator: {
    tick: number
    mode: string
    true_temperature: number
    scenario: string | null
    faults: Array<{ sensor_id: string; kind: string; remaining_ticks: number }>
    sensors: Array<{
      sensor_id: string
      location: string
      role: string
      historical_reliability: number
    }>
  }
  sensors: SensorRow[]
  decision: DecisionPayload
}

export type ScenarioInfo = { id: string; description: string }

export type ConfiguredSensor = {
  sensor_id: string
  name: string
  measurement: string
  unit: string
  location: string
  expected_interval_seconds: number
  baseline_tolerance: number | null
  created_at: string | null
  sample_count?: number
  baseline_samples_required?: number
  latest_value?: number | null
  latest_timestamp?: number | null
  network_quality?: number | null
  baseline_median?: number | null
  baseline_spread?: number | null
  deviation_score?: number | null
  reliability?: number | null
  age_seconds?: number | null
  status?: 'NO_DATA' | 'CALIBRATING' | 'NORMAL' | 'UNUSUAL' | 'LOW_QUALITY' | 'STALE'
  message?: string
}

export type ConfiguredDashboard = {
  summary: {
    status: 'NO_SENSORS' | 'NO_DATA' | 'CHECK' | 'LEARNING' | 'LOW_QUALITY' | 'STALE' | 'NORMAL'
    message: string
    unusual_count: number
    calibrating_count: number
  }
  sensors: ConfiguredSensor[]
}
