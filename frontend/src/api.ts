const BASE = '/api'

// ── Types ──────────────────────────────────────────────────────────────────────

export interface Waypoint {
  step: number
  row: number
  col: number
  lon: number
  lat: number
  battery_pct: number
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
}

export interface AstarMetrics {
  path_steps: number
  total_distance_m: number
  total_cost: number
  nodes_expanded: number
  comp_time_ms: number
  [key: string]: unknown
}

export interface PlanResponse {
  status: string
  astar_metrics: AstarMetrics
  summary: SimSummary
  geojson: object
  waypoints: Waypoint[]
  rover_id?: string
  rover_name?: string
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

export interface RoverEntry {
  name: string
  mass_kg: number
  v_max_ms: number
  e_cap_wh: number
  slope_max_deg: number
  w_slope: number
  w_energy: number
  w_shadow: number
  w_thermal: number
}

export interface RoversResponse {
  default: string
  rovers: Record<string, RoverEntry>
}

type ProfileMapEntry = {
  name?: string
  weights: PlanWeights
  color?: string
}

const FALLBACK_ROVERS: RoversResponse = {
  default: 'lpr_1',
  rovers: {
    lpr_1: {
      name: 'LPR-1 (Default)',
      mass_kg: 450,
      v_max_ms: 0.2,
      e_cap_wh: 5420,
      slope_max_deg: 25,
      w_slope: 0.409,
      w_energy: 0.259,
      w_shadow: 0.142,
      w_thermal: 0.190,
    },
  },
}

function normalizeProfiles(
  payload: ProfileEntry[] | Record<string, ProfileMapEntry>,
): ProfileEntry[] {
  if (Array.isArray(payload)) return payload
  return Object.entries(payload).map(([id, profile]) => ({
    id,
    name: profile.name ?? id,
    weights: profile.weights,
    color: profile.color ?? '#64748B',
  }))
}

async function readErrorDetail(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const payload = await response.clone().json() as { detail?: string }
    if (typeof payload.detail === 'string' && payload.detail.trim()) {
      return payload.detail
    }
  } catch {
    // Vite proxy failures can come back as plain text instead of JSON.
  }

  const text = (await response.text()).trim()
  if (text) return text.slice(0, 280)
  return fallback
}

// ── API calls ──────────────────────────────────────────────────────────────────

export async function fetchLayer(
  name: string,
  downsample = 2,
  roverId?: string,
): Promise<LayerResponse> {
  const params = new URLSearchParams({ downsample: String(downsample) })
  if (roverId) params.set('rover_id', roverId)
  const r = await fetch(`${BASE}/layers/${name}?${params}`)
  if (!r.ok) {
    throw new Error(await readErrorDetail(r, `Layer fetch failed: ${name} (${r.status})`))
  }
  return r.json() as Promise<LayerResponse>
}

export async function planRoute(
  start: [number, number],
  goal: [number, number],
  weights: PlanWeights,
  roverId?: string,
): Promise<PlanResponse> {
  const r = await fetch(`${BASE}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      start: { row: start[0], col: start[1] },
      goal: { row: goal[0], col: goal[1] },
      weights,
      include_simulation: true,
      rover_id: roverId || null,
    }),
  })
  if (!r.ok) {
    throw new Error(await readErrorDetail(r, 'Plan request failed'))
  }
  return r.json() as Promise<PlanResponse>
}

export async function fetchProfiles(roverId?: string): Promise<ProfileEntry[]> {
  const params = roverId ? `?rover_id=${roverId}` : ''
  const r = await fetch(`${BASE}/profiles${params}`)
  if (!r.ok) throw new Error(await readErrorDetail(r, 'Failed to fetch profiles'))
  const payload = await r.json() as ProfileEntry[] | Record<string, ProfileMapEntry>
  return normalizeProfiles(payload)
}

export async function fetchRovers(): Promise<RoversResponse> {
  const r = await fetch(`${BASE}/rovers`)
  if (r.status === 404) {
    console.warn('GET /api/rovers not found; falling back to the default single-rover mode.')
    return FALLBACK_ROVERS
  }
  if (!r.ok) throw new Error(await readErrorDetail(r, 'Failed to fetch rovers'))
  return r.json() as Promise<RoversResponse>
}

export async function checkHealth(): Promise<{ dem_loaded: boolean }> {
  const r = await fetch(`${BASE}/health`)
  if (!r.ok) throw new Error(await readErrorDetail(r, 'Health check failed'))
  return r.json() as Promise<{ dem_loaded: boolean }>
}

export async function loadPreprocessed(roverId?: string): Promise<void> {
  const r = await fetch(`${BASE}/load-preprocessed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rover_id: roverId || null }),
  })
  if (!r.ok) {
    throw new Error(await readErrorDetail(r, 'Load preprocessed failed'))
  }
}
