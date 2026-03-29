const BASE = '/api'

// ── Types ──────────────────────────────────────────────────────────────────────

export interface Waypoint {
  step: number
  row: number
  col: number
  lon: number
  lat: number
  altitude_m: number | null
  battery_pct: number
  recharge_count: number
  recharged_this_step: boolean
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  slope_deg: number
  surface_temp_c: number
  shadow_ratio: number
  node_cost: number
  elapsed_hours: number
  distance_m: number
  step_energy_wh: number
}

export interface SimSummary {
  total_distance_km: number
  total_elapsed_hours: number
  final_battery_pct: number
  min_battery_pct: number
  max_slope_deg: number
  total_energy_consumed_wh: number
  total_shadow_exposure: number
  critical_steps_count: number
  high_or_above_steps_count: number
  waypoint_count: number
  total_recharges: number
}

export interface AstarMetrics {
  path_length_nodes: number
  total_distance_m: number
  total_weighted_cost: number
  total_energy_wh: number
  total_shadow_hours: number
  max_slope_deg: number
  max_thermal_risk: number
  min_surface_temp_c: number
  nodes_expanded: number
  computation_time_ms: number
  [key: string]: unknown
}

export interface PlanResponse {
  status: string
  astar_metrics: AstarMetrics
  summary: SimSummary
  geojson: object
  waypoints: Waypoint[]
  rover?: {
    id: string
    name: string
  }
}

export interface LayerResponse {
  layer: string
  shape: [number, number]
  data: (number | null)[][]
  metadata: Record<string, unknown>
}

export interface PlanWeights {
  w_slope: number
  w_energy: number
  w_shadow: number
  w_thermal: number
}

export interface ProfileEntry {
  id: string
  name: string
  weights: PlanWeights
  color: string
}

export interface FocusTelemetryResponse {
  row: number
  col: number
  lon: number
  lat: number
  altitude_m: number | null
  thermal_c: number | null
  resolution_m: number
  span_km: number
}

export interface RoverEntry {
  id: string
  name: string
  mass_kg: number
  v_max_ms: number
  e_cap_wh: number
  slope_max_deg: number
  h_max_shadow_h: number
  default_weights: PlanWeights
}

export interface RoverCatalogResponse {
  default_rover_id: string
  rovers: RoverEntry[]
}

// ── API calls ──────────────────────────────────────────────────────────────────

export async function fetchLayer(
  name: string,
  downsample = 2,
  options?: {
    weights?: PlanWeights
    roverId?: string
    signal?: AbortSignal
  },
): Promise<LayerResponse> {
  const query = new URLSearchParams({ downsample: String(downsample) })
  if (options?.roverId) {
    query.set('rover_id', options.roverId)
  }
  if (options?.weights) {
    query.set('w_slope', String(options.weights.w_slope))
    query.set('w_energy', String(options.weights.w_energy))
    query.set('w_shadow', String(options.weights.w_shadow))
    query.set('w_thermal', String(options.weights.w_thermal))
  }

  const r = await fetch(`${BASE}/layers/${name}?${query.toString()}`, {
    signal: options?.signal,
  })
  if (!r.ok) throw new Error(`Layer fetch failed: ${name} (${r.status})`)
  return r.json() as Promise<LayerResponse>
}

export async function planRoute(
  start: [number, number],
  goal: [number, number],
  weights: PlanWeights,
  roverId: string,
): Promise<PlanResponse> {
  const r = await fetch(`${BASE}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      start: { row: start[0], col: start[1] },
      goal: { row: goal[0], col: goal[1] },
      rover_id: roverId,
      weights,
      include_simulation: true,
    }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error((err as { detail?: string }).detail ?? 'Plan request failed')
  }
  return r.json() as Promise<PlanResponse>
}

export async function fetchProfiles(): Promise<ProfileEntry[]> {
  const r = await fetch(`${BASE}/profiles`)
  if (!r.ok) throw new Error('Failed to fetch profiles')
  const data = await r.json() as Record<string, Omit<ProfileEntry, 'id'>>
  return Object.entries(data).map(([id, profile]) => ({ id, ...profile }))
}

export async function fetchRovers(): Promise<RoverCatalogResponse> {
  const r = await fetch(`${BASE}/rovers`)
  if (!r.ok) throw new Error('Failed to fetch rovers')
  return r.json() as Promise<RoverCatalogResponse>
}

export async function fetchCellTelemetry(
  row: number,
  col: number,
  signal?: AbortSignal,
): Promise<FocusTelemetryResponse> {
  const query = new URLSearchParams({
    row: String(row),
    col: String(col),
  })
  const r = await fetch(`${BASE}/cell-telemetry?${query.toString()}`, { signal })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error((err as { detail?: string }).detail ?? 'Cell telemetry request failed')
  }
  return r.json() as Promise<FocusTelemetryResponse>
}

export async function checkHealth(): Promise<{ dem_loaded: boolean }> {
  const r = await fetch(`${BASE}/health`)
  if (!r.ok) throw new Error('Health check failed')
  return r.json() as Promise<{ dem_loaded: boolean }>
}

export async function loadPreprocessed(): Promise<void> {
  const r = await fetch(`${BASE}/load-preprocessed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(
      (err as { detail?: string }).detail ?? 'Load preprocessed failed',
    )
  }
}
