// Type-only, so it is erased at build time and creates no runtime cycle
// with net/types.ts importing PlanWeights back from here.
import type { CellTelemetryResponse } from './net/types'

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
  // Always null: pathfinder.py:734-735 and 790-791 emit these as None and
  // point at the simulation summary instead. Real energy is
  // summary.total_energy_consumed_wh; real shadow exposure is
  // summary.total_shadow_exposure / summary.max_continuous_shadow_h.
  total_energy_wh: number | null
  total_shadow_hours: number | null
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

/**
 * The eight fields the telemetry wells read.
 *
 * /api/cell-telemetry sends three more -- thermal_min_c, cost_breakdown and
 * layer_validity (main.py:554-573) -- so this is a view of the response, not
 * the response. fetchCellTelemetry therefore returns the full
 * CellTelemetryResponse and callers that only need these eight keep using
 * this type; a narrower parameter accepts the wider object.
 */
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

/**
 * One grid layer, fetched over the binary (f32) path.
 *
 * The JSON representation of the same endpoint is capped at MAX_LAYER_CELLS
 * (65 536 cells, a 256x256 preview), so on the shipped 500x500 grid it rejects
 * downsample=1 with a 422 and the map renders nothing. The f32 path carries no
 * such cap -- the whole field is 1 MB of float32, less than the capped JSON
 * preview costs -- so full resolution is both available and cheaper here.
 *
 * NaN is the binary path's only no-data value (the server folds +inf in `cost`
 * into it), and it is mapped to null so the shape matches what the JSON path
 * used to return and MapCanvas already expects.
 */
export async function fetchLayer(
  name: string,
  downsample = 1,
  options?: {
    weights?: PlanWeights
    roverId?: string
    signal?: AbortSignal
  },
): Promise<LayerResponse> {
  const query = new URLSearchParams({
    downsample: String(downsample),
    format: 'f32',
  })
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

  // Shape comes from the headers rather than being inferred from the payload
  // length: a square grid would make a swapped rows/cols invisible.
  const rows = Number(r.headers.get('X-Layer-Rows'))
  const cols = Number(r.headers.get('X-Layer-Cols'))
  const flat = new Float32Array(await r.arrayBuffer())
  if (!rows || !cols || flat.length !== rows * cols) {
    throw new Error(
      `Layer ${name}: ${flat.length} values do not fill ${rows}x${cols}`,
    )
  }

  const data: (number | null)[][] = new Array(rows)
  for (let r0 = 0; r0 < rows; r0++) {
    const row: (number | null)[] = new Array(cols)
    const base = r0 * cols
    for (let c = 0; c < cols; c++) {
      const v = flat[base + c]
      row[c] = Number.isNaN(v) ? null : v
    }
    data[r0] = row
  }

  return { layer: name, shape: [rows, cols], data }
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
): Promise<CellTelemetryResponse> {
  const query = new URLSearchParams({
    row: String(row),
    col: String(col),
  })
  const r = await fetch(`${BASE}/cell-telemetry?${query.toString()}`, { signal })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error((err as { detail?: string }).detail ?? 'Cell telemetry request failed')
  }
  return r.json() as Promise<CellTelemetryResponse>
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
