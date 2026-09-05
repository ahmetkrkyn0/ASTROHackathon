/**
 * The legacy endpoint client.
 *
 * Frozen, not deprecated: everything here works and keeps working. New endpoint
 * families do not come here -- they go to api/<family>.ts, alongside
 * api/assistant.ts, so that adding one is not an edit to a file five other
 * people are also editing. The shared transport primitives live in api/client.ts
 * so a new family never has to import this module to get them.
 */
import { BASE } from './api/client'
// Type-only, so it is erased at build time and creates no runtime cycle
// with net/types.ts importing PlanWeights back from here.
import type { CellTelemetryResponse } from './net/types'

// Transitional re-export for callers that still reach for it here. New code
// imports ApiError from api/client, or from its own api/<family> module.
export { ApiError } from './api/client'

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
  max_segment_slope_deg: number
  total_energy_consumed_wh: number
  // The backend sends this, but its unit is not stated anywhere in the
  // codebase and max_continuous_shadow_h is a separate field in hours, so it
  // is probably a different quantity. Typed so it is not mistaken for a
  // missing field; never displayed, and never sent to the AI layer.
  total_shadow_exposure: number
  critical_steps_count: number
  high_or_above_steps_count: number
  waypoint_count: number
  total_recharges: number
  stranded: boolean
  stranded_at_step: number | null
  // The real continuous-shadow figure. astar_metrics.total_shadow_hours is
  // always null; this is what any shadow claim must come from.
  max_continuous_shadow_h: number
  shadow_limit_h: number | null
  shadow_limit_exceeded: boolean | null
  peak_power_exceeded_steps: number
}

export interface AstarMetrics {
  path_length_nodes: number
  total_distance_m: number
  total_weighted_cost: number
  total_weighted_cost_cells_only: number
  barrier_share: number | null
  cost_units: string
  // Both are always null: pathfinder.py emits None for these and points at
  // the simulation summary instead, where the real numbers are
  // (summary.total_energy_consumed_wh, summary.total_shadow_exposure).
  // Typed as null-only so reaching for one is a type error rather than a
  // plausible-looking zero.
  total_energy_wh: null
  total_shadow_hours: null
  max_slope_deg: number
  max_segment_slope_deg: number
  max_cell_slope_deg: number
  max_thermal_risk: number
  min_surface_temp_c: number
  max_surface_temp_c: number
  nodes_expanded: number
  computation_time_ms: number
  edges_rejected: Record<string, number>
  [key: string]: unknown
}

export interface RouteStatistics {
  [key: string]: unknown
}

export interface PlanExecution {
  stranded: boolean
  planned_nodes: number
  executable_nodes: number
  truncated: boolean
  reason: string | null
}

export interface PlanResponse {
  status: string
  astar_metrics: AstarMetrics
  summary: SimSummary
  geojson: object
  waypoints: Waypoint[]
  route_statistics?: RouteStatistics
  execution?: PlanExecution
  rover?: {
    id: string
    name: string
  }
}

export interface LayerResponse {
  layer: string
  shape: [number, number]
  data: (number | null)[][]
  /** Per-layer header block from the binary path. Absent on older callers. */
  metadata?: {
    resolution_m: number
    validity: string | null
    min: number
    max: number
    nodata: number
  }
}

export interface PlanWeights {
  w_slope: number
  w_energy: number
  w_shadow: number
  w_thermal: number
}

// ── 3-D scene contract (docs/frontend/3b-veri-sozlesmesi.md) ──────────────────

export interface TerrainLayerEntry {
  units: string
  description: string
  validity: string
  min: number
  max: number
  binary_url: string
  json_url: string
}

export interface TerrainManifest {
  grid: {
    rows: number
    cols: number
    resolution_m: number
    span_m: [number, number]
    cells: number
  }
  georeference: {
    origin: { x: number; y: number }
    crs: string
    window_offset: { row: number; col: number }
    // Row 0 is the NORTH edge, col 0 the WEST edge. Ignoring this draws a
    // mirrored site that looks entirely plausible.
    row_axis: string
    col_axis: string
  }
  elevation: {
    min_m: number
    max_m: number
    relief_m: number
    vertical_exaggeration_suggested: number
  }
  layers: Record<string, TerrainLayerEntry>
}

export interface SunSample {
  index: number
  utc: string
  azimuth_true_deg: number
  azimuth_grid_deg: number
  elevation_deg: number
}

export interface IlluminationSeries {
  slices: number
  slice_hours: number
  start_utc: string
  grid: { rows: number; cols: number; resolution_m: number; downsample: number }
  // model "static" means the horizon cache is missing and the cube is frozen.
  // Never animate a frozen cube and call it physics -- `reason` says why.
  shadow_model: {
    model: string
    time_varying: boolean
    reason?: string
  }
  sun: SunSample[]
  fields: Record<string, { units: string; min: number; max: number; binary_url: string }>
  binary_format: { shape: [number, number, number] }
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

// Reshape a row-major Float32Array into the nested array every consumer is
// typed against. Non-finite cells become null, not NaN: the JSON path sent
// null (`np.where(np.isfinite(...), layer, None)`) and every reader branches
// on `typeof value === 'number'`, which is true for NaN. Leaving NaN in
// would poison the colour ramps and range scans silently rather than
// visibly -- cost alone carries about 60 000 impassable cells in the current grid.
function reshapeF32(buf: Float32Array, rows: number, cols: number): (number | null)[][] {
  const grid: (number | null)[][] = new Array(rows)
  for (let row = 0; row < rows; row += 1) {
    const line: (number | null)[] = new Array(cols)
    const base = row * cols
    for (let col = 0; col < cols; col += 1) {
      const value = buf[base + col]
      line[col] = Number.isFinite(value) ? value : null
    }
    grid[row] = line
  }
  return grid
}

// Layers arrive as float32, not JSON. The JSON representation carries the
// 500x500 grid as ~4.25 MB of text and is capped server-side at
// MAX_LAYER_CELLS (65 536), which forced downsample=2 and a 250x250
// preview. The same grid as float32 is 1.00 MB -- smaller than the capped
// preview -- and the ceiling is deliberately not applied to the binary path
// (backend/app/main.py, the `format == "f32"` branch). Hence downsample=1.
// See docs/frontend/3b-veri-sozlesmesi.md.
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

  const rows = Number(r.headers.get('X-Layer-Rows'))
  const cols = Number(r.headers.get('X-Layer-Cols'))
  const buf = new Float32Array(await r.arrayBuffer())
  if (!Number.isFinite(rows) || !Number.isFinite(cols) || buf.length !== rows * cols) {
    // A short buffer read into a full-resolution geometry looks plausible
    // and is wrong. Fail loudly instead.
    throw new Error(
      `Layer ${name}: expected ${rows}x${cols} = ${rows * cols} floats, got ${buf.length}`,
    )
  }


  return {
    layer: name,
    shape: [rows, cols],
    data: reshapeF32(buf, rows, cols),
    metadata: {
      resolution_m: Number(r.headers.get('X-Layer-Resolution-M')),
      validity: r.headers.get('X-Layer-Validity'),
      min: Number(r.headers.get('X-Layer-Min')),
      max: Number(r.headers.get('X-Layer-Max')),
      nodata: Number(r.headers.get('X-Layer-Nodata')),
    },
  }
}

// One call, before a byte of grid is fetched: mesh dimensions, the
// georeference, the elevation range the displacement scales by, and a
// binary_url per layer. Fetch those URLs verbatim -- cost and traversable
// are rover- and weight-dependent and the manifest has already embedded
// the right query string.
export async function fetchTerrainManifest(
  options?: { roverId?: string; weights?: PlanWeights; signal?: AbortSignal },
): Promise<TerrainManifest> {
  const query = new URLSearchParams()
  if (options?.roverId) query.set('rover_id', options.roverId)
  if (options?.weights) {
    query.set('w_slope', String(options.weights.w_slope))
    query.set('w_energy', String(options.weights.w_energy))
    query.set('w_shadow', String(options.weights.w_shadow))
    query.set('w_thermal', String(options.weights.w_thermal))
  }
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const r = await fetch(`${BASE}/terrain${suffix}`, { signal: options?.signal })
  if (!r.ok) throw new Error(`Terrain manifest failed (${r.status})`)
  return r.json() as Promise<TerrainManifest>
}

export async function fetchIlluminationSeries(
  params: { startUtc: string; nSlices: number; sliceHours: number; downsample: number },
  signal?: AbortSignal,
): Promise<IlluminationSeries> {
  const query = new URLSearchParams({
    start_utc: params.startUtc,
    n_slices: String(params.nSlices),
    slice_hours: String(params.sliceHours),
    downsample: String(params.downsample),
  })
  const r = await fetch(`${BASE}/illumination-series?${query.toString()}`, { signal })
  if (!r.ok) throw new Error(`Illumination series failed (${r.status})`)
  return r.json() as Promise<IlluminationSeries>
}

// Raw float32 straight off a manifest-supplied binary_url. `expected` is the
// element count the caller's geometry assumes; a mismatch means a
// downsampled grid is about to be read into a full-resolution mesh, which
// renders plausibly and is wrong.
export async function fetchBinaryGrid(
  url: string,
  expected?: number,
  signal?: AbortSignal,
): Promise<Float32Array> {
  const r = await fetch(url, { signal })
  if (!r.ok) throw new Error(`Binary grid fetch failed: ${url} (${r.status})`)
  const buf = new Float32Array(await r.arrayBuffer())
  if (expected !== undefined && buf.length !== expected) {
    throw new Error(`Binary grid ${url}: expected ${expected} floats, got ${buf.length}`)
  }
  return buf
}

export async function planRoute(
  start: [number, number],
  goal: [number, number],
  weights: PlanWeights,
  roverId: string,
  /**
   * The same rock cells the 3D scene renders as obstacles (see
   * TerrainCanvas3D's use of generateRockField), computed by the caller
   * BEFORE planning and passed through here so the backend's A* actually
   * routes around them instead of the route being decided first and the
   * rocks drawn on top of it afterwards.
   */
  obstacleCells?: Array<[number, number]>,
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
      ...(obstacleCells && obstacleCells.length > 0
        ? { obstacle_cells: obstacleCells.map(([row, col]) => ({ row, col })) }
        : {}),
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
