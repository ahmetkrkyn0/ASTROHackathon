/**
 * Typed fetchers for the A-track analysis endpoints.
 *
 * New endpoint families go here rather than into `api.ts`, which is frozen.
 * Each of these answers with either its data or an honest statement that it
 * has none, so the types below carry the `model`/`reason` shape as a first
 * class member rather than as an afterthought.
 */

import { getJson } from './client'
import type { ModelStatus, Validity } from './types'

// ── GET /api/psr-validation ─────────────────────────────────────────────────

/**
 * How well our own shadow model agrees with NASA's measured PSR mask.
 *
 * This is a validation record, not a layer. Its value is that it is a check we
 * can lose: publishing a Jaccard of 0.61 next to the mask is the difference
 * between showing evidence and claiming agreement.
 */
export interface PsrValidation {
  threshold: number
  n_cells: number
  n_psr: number
  psr_fraction: number
  n_dark: number
  n_intersection: number
  n_union: number
  jaccard: number
  /** Share of NASA's PSR cells our model calls dark. */
  psr_recall: number
  /** Share of our dark cells NASA calls PSR. */
  dark_precision: number
  false_positive_fraction: number
  mean_shadow_inside_psr: number
  mean_shadow_outside_psr: number
  thermal_min_median_inside_psr: number
  thermal_min_median_outside_psr: number
  product: string
  resolution_m: number
  product_url: string
  /** Per-layer provenance: the mask is MEASURED, our shadow is DERIVED. */
  validity: Record<string, Validity>
  /** The backend's own statement of what the product is and is not. */
  claim: string
  /** The backend's own guide to reading these numbers. */
  reading: string
}

export function fetchPsrValidation(
  threshold = 0.99,
  signal?: AbortSignal,
): Promise<PsrValidation> {
  return getJson<PsrValidation>(`/psr-validation?threshold=${threshold}`, signal)
}

// ── GET /api/safe-haven ─────────────────────────────────────────────────────

export interface SafeHavenField {
  units: string
  min: number
  max: number
  /** A COUNT of nodata cells, not a sentinel. The payload's sentinel is NaN. */
  nodata: number
  binary_url: string
}

export interface SafeHavenManifest {
  rover_id: string
  rover_name: string
  /** The rover's continuous-shadow limit, in hours. */
  h_max_shadow_h: number
  start_utc: string | null
  span_hours: number
  step_hours: number
  n_steps: number
  /** `spice_horizon` | `static` | `unavailable`, with a reason for the last. */
  safe_haven_model: ModelStatus
  safe_haven_fraction: number
  safe_haven_cells: number
  traversable_cells: number
  earth_below_fraction: number
  grid: { rows: number; cols: number; resolution_m: number; downsample: number }
  /**
   * Empty when the model is unavailable. There is then no `binary_url` to
   * fetch, and a binary request answers 404 rather than returning a grid of
   * zeros -- which is the only honest option, since zero is a real value in
   * three of these four fields.
   */
  fields: Partial<Record<SafeHavenFieldName, SafeHavenField>>
  binary_format: {
    dtype: string
    endian: string
    order: string
    shape: [number, number]
    /** "NaN" -- the sentinel in the payload, as opposed to `fields.*.nodata`. */
    nodata: string
  }
}

export type SafeHavenFieldName =
  | 'safe_haven'
  | 'max_dark_hours_without_dte'
  | 'earth_below_hours'
  | 'time_to_safe_haven'

export interface SafeHavenParams {
  startUtc: string
  roverId?: string
  spanHours?: number
  stepHours?: number
  downsample?: number
}

export function fetchSafeHaven(
  params: SafeHavenParams,
  signal?: AbortSignal,
): Promise<SafeHavenManifest> {
  const query = new URLSearchParams({ start_utc: params.startUtc })
  if (params.roverId) query.set('rover_id', params.roverId)
  if (params.spanHours) query.set('span_hours', String(params.spanHours))
  if (params.stepHours) query.set('step_hours', String(params.stepHours))
  if (params.downsample && params.downsample > 1) {
    query.set('downsample', String(params.downsample))
  }
  return getJson<SafeHavenManifest>(`/safe-haven?${query}`, signal)
}

// ── GET /api/comm-window ────────────────────────────────────────────────────

/**
 * When the direct-to-Earth link at one cell opens or closes.
 *
 * Every duration is nullable and they mean different things. `visible_now`
 * with a null `minutes_remaining` means the link is up and the search horizon
 * ended before it went down -- `search_limited` says so. Rendering that as
 * "0 minutes remaining" would report an imminent loss of signal that the data
 * does not support.
 */
export interface CommWindow {
  utc: string
  row: number
  col: number
  visible_now: boolean
  /** Null when the search horizon ended first. Never zero for "unknown". */
  minutes_remaining: number | null
  minutes_until_visible: number | null
  next_change_utc: string | null
  /** True when the answer is bounded by `searched_hours`, not by geometry. */
  search_limited: boolean
  searched_hours: number
  step_minutes: number
  trigger_minutes_remaining: number | null
  earth_elevation_deg: number
  earth_azimuth_true_deg: number
  earth_azimuth_grid_deg: number
  horizon_deg: number
}

export function fetchCommWindow(
  row: number,
  col: number,
  utc: string,
  signal?: AbortSignal,
): Promise<CommWindow> {
  const query = new URLSearchParams({ row: String(row), col: String(col), utc })
  return getJson<CommWindow>(`/comm-window?${query}`, signal)
}

// ── GET /api/earth-series ───────────────────────────────────────────────────

export interface EarthSlice {
  index: number
  utc: string
  azimuth_true_deg: number
  azimuth_grid_deg: number
  elevation_deg: number
  /** Share of the grid with a link at this slice. The timeline reads this. */
  visible_fraction: number
}

export interface EarthSeriesManifest {
  slices: number
  slice_hours: number
  start_utc: string | null
  grid: { rows: number; cols: number; resolution_m: number; downsample: number }
  /** `spice_horizon` | `static` | `unavailable`. Check before drawing. */
  earth_model: ModelStatus
  earth: EarthSlice[]
  /** Empty when the model is unavailable; the binary request then 404s. */
  fields: Partial<Record<'earth_visible', { units: string; min: number; max: number; binary_url: string }>>
  binary_format: {
    dtype: string
    endian: string
    order: string
    shape: [number, number, number]
  }
}

export interface EarthSeriesParams {
  startUtc: string
  nSlices?: number
  sliceHours?: number
  downsample?: number
}

export function fetchEarthSeries(
  params: EarthSeriesParams,
  signal?: AbortSignal,
): Promise<EarthSeriesManifest> {
  const query = new URLSearchParams({ start_utc: params.startUtc })
  if (params.nSlices) query.set('n_slices', String(params.nSlices))
  if (params.sliceHours) query.set('slice_hours', String(params.sliceHours))
  if (params.downsample && params.downsample > 1) {
    query.set('downsample', String(params.downsample))
  }
  return getJson<EarthSeriesManifest>(`/earth-series?${query}`, signal)
}

// ── GET /api/survival ───────────────────────────────────────────────────────

/**
 * B1 -- reach-avoid value iteration over the coarse grid.
 *
 * `p_safe` is the probability the rover reaches the safe set from this block at
 * this time and state of charge; `best_action` is the arg-min action code that
 * achieves it. Both MODEL: this is a computed policy, not an observation.
 */
export interface SurvivalManifest {
  rover_id: string
  rover_name?: string
  start_utc: string | null
  t_hours: number
  soc_pct: number
  goal: [number, number] | null
  survival_model: ModelStatus
  summary: {
    traversable_blocks: number
    mean_p_safe: number
    fraction_at_least_0_95: number
    fraction_at_least_0_5: number
    /**
     * Blocks with P_safe exactly zero -- nothing the policy can do reaches the
     * safe set. About 28% of this window, which is the finding rather than a
     * footnote.
     */
    fraction_zero: number
    time_bin: [number, number]
    soc_bin?: number
  }
  grid: {
    rows: number
    cols: number
    resolution_m: number
    coarsen: number
    downsample: number
  }
  fields: Partial<Record<'p_safe' | 'best_action', SafeHavenField>>
  binary_format: {
    dtype: string
    endian: string
    order: string
    shape: [number, number]
    nodata: string
  }
  claim: string
}

export interface SurvivalParams {
  startUtc: string
  roverId?: string
  /** Required for the `leg` safe set. Without it the backend answers 422. */
  goalRow?: number
  goalCol?: number
  tHours?: number
  socPct?: number
  coarsen?: number
}

export function fetchSurvival(
  params: SurvivalParams,
  signal?: AbortSignal,
): Promise<SurvivalManifest> {
  const query = new URLSearchParams({ start_utc: params.startUtc })
  if (params.roverId) query.set('rover_id', params.roverId)
  if (params.goalRow !== undefined) query.set('goal_row', String(params.goalRow))
  if (params.goalCol !== undefined) query.set('goal_col', String(params.goalCol))
  if (params.tHours !== undefined) query.set('t_hours', String(params.tHours))
  if (params.socPct !== undefined) query.set('soc_pct', String(params.socPct))
  if (params.coarsen !== undefined) query.set('coarsen', String(params.coarsen))
  return getJson<SurvivalManifest>(`/survival?${query}`, signal)
}

// ── GET /api/thermal-dwell ──────────────────────────────────────────────────

/**
 * C6 -- how long a rover arriving at each block may stand there.
 *
 * `open_ended` is the field to read before `max_dwell_h`: where it is 1, the
 * dwell was CLIPPED to the lookahead rather than measured, so 24.0 means "at
 * least 24 h" and not "24 h". On this window the two agree exactly with
 * `side == 0` -- a block that never leaves the envelope has no finite dwell.
 */
export interface ThermalDwellManifest {
  rover_id: string
  rover_name: string
  start_utc: string | null
  t_hours: number
  lookahead_hours: number
  dwell_model: ModelStatus
  shadow_model: ModelStatus
  summary: {
    slice: number
    traversable_blocks: number
    lookahead_h: number
    fraction_unlimited: number
    fraction_cold_limited: number
    fraction_hot_limited: number
    finite_median_h: number
    finite_p5_h: number
    finite_p95_h: number
  }
  grid: {
    rows: number
    cols: number
    resolution_m: number
    coarsen: number
    downsample: number
  }
  fields: Partial<Record<'max_dwell_h' | 'side' | 'open_ended', SafeHavenField>>
  binary_format: {
    dtype: string
    endian: string
    order: string
    shape: [number, number]
    nodata: string
  }
  quoted?: Record<string, unknown>
  claim: string
}

export interface ThermalDwellParams {
  startUtc: string
  roverId?: string
  tHours?: number
  lookaheadHours?: number
  coarsen?: number
}

export function fetchThermalDwell(
  params: ThermalDwellParams,
  signal?: AbortSignal,
): Promise<ThermalDwellManifest> {
  const query = new URLSearchParams({ start_utc: params.startUtc })
  if (params.roverId) query.set('rover_id', params.roverId)
  if (params.tHours !== undefined) query.set('t_hours', String(params.tHours))
  if (params.lookaheadHours !== undefined) {
    query.set('lookahead_hours', String(params.lookaheadHours))
  }
  if (params.coarsen !== undefined) query.set('coarsen', String(params.coarsen))
  return getJson<ThermalDwellManifest>(`/thermal-dwell?${query}`, signal)
}

// ── GET /api/thermal-envelope ───────────────────────────────────────────────

export type EnvelopeVerdict = 'unlimited' | 'cold_limited' | 'hot_limited' | 'unsampled'

/**
 * One bin of the operating-envelope matrix.
 *
 * `dwell_h`, `side` and `component` are null for two opposite reasons and the
 * panel must not merge them: `unlimited` means the inner temperature never
 * leaves the envelope, so there is no hour to report; `unsampled` means the
 * heat1d trace never visited this geometry, so there is nothing at all. One is
 * the best possible answer, the other is no answer.
 */
export interface EnvelopeCell {
  el_bin: number
  s_par_bin: number
  el_mid_deg: number
  s_par_mid_deg: number
  /** Zero exactly when `verdict` is `unsampled`. */
  samples: number
  surface_c_max: number | null
  surface_c_mean: number | null
  inner_c: number | null
  verdict: EnvelopeVerdict
  /** Hours to the limit. Null when unlimited or unsampled. */
  dwell_h: number | null
  side: 'cold' | 'hot' | null
  component: string | null
}

export interface ThermalEnvelope {
  rover_id: string
  rover_name: string
  model: string
  validity: Validity
  /** UNCALIBRATED on every rover today. Shown beside every number below. */
  thermal_lag_validity: string
  dwell_model: ModelStatus
  envelope: {
    lo_c: number
    hi_c: number
    lo_component: string
    hi_component: string
  }
  initial_inner_c: number
  heater_model: string
  heater_source: string | null
  axes: {
    el_deg: { edges: number[]; label: string }
    s_par_deg: { edges: number[]; label: string }
  }
  counts: Record<EnvelopeVerdict, number>
  cells: EnvelopeCell[]
  verdicts: EnvelopeVerdict[]
  method: string
  meta: Record<string, unknown>
  quoted?: Record<string, unknown>
  claim: string
}

export function fetchThermalEnvelope(
  params: { roverId?: string; initialInnerC?: number; heaterModel?: string } = {},
  signal?: AbortSignal,
): Promise<ThermalEnvelope> {
  const query = new URLSearchParams()
  if (params.roverId) query.set('rover_id', params.roverId)
  if (params.initialInnerC !== undefined) {
    query.set('initial_inner_c', String(params.initialInnerC))
  }
  if (params.heaterModel) query.set('heater_model', params.heaterModel)
  const suffix = query.toString()
  return getJson<ThermalEnvelope>(`/thermal-envelope${suffix ? `?${suffix}` : ''}`, signal)
}

// ── GET /api/illumination-corridor ──────────────────────────────────────────

export type CorridorFieldName = 'corridor' | 'lit_safe' | 'dwell_hours'

/**
 * A2 -- the volume of (block, slice) that is lit, passable, and connected to
 * both ends of the horizon.
 *
 * `enforced` is the field to read first. It says whether the planner was
 * actually gated on this corridor; false means the cube is a picture of where
 * a corridor exists, not a description of where the route went.
 */
export interface CorridorBlock {
  enforced: boolean
  lit_rule: string
  /** The backend's own definition, quoted rather than paraphrased. */
  lit_rule_definition: string
  edge_rule: string
  pruning: string
  n_slices: number
  slice_hours: number
  grid: { rows: number; cols: number; resolution_m: number }
  voxels: {
    traversable: number
    lit_safe: number
    corridor: number
    corridor_fraction_of_lit_safe: number
    pruned_fraction: number
    [key: string]: number
  }
  slices: {
    first_lit: number | null
    last_lit: number | null
    corridor_cells_t0: number
    [key: string]: number | null
  }
  components: {
    method: string
    count: number
    largest_voxels: number
    largest_fraction: number
    [key: string]: unknown
  }
  /** Null when no endpoints were supplied -- the layer-only case. */
  start: Record<string, unknown> | null
  goal: Record<string, unknown> | null
  route: Record<string, unknown>
  provenance: Record<string, unknown>
  timings_ms?: Record<string, number>
}

export interface CorridorManifest {
  start_utc: string | null
  rover_id: string
  n_slices: number
  slice_hours: number
  /** `auto` when the backend derived it from the grid, `request` when we set it. */
  slice_hours_source: string
  horizon_hours: number
  coarsen: number
  lit_rule: string
  grid: { rows: number; cols: number; resolution_m: number; coarsen: number }
  shadow_model: ModelStatus
  corridor: CorridorBlock
  fields: Partial<
    Record<CorridorFieldName, { units: string; min: number; max: number; binary_url: string }>
  >
  binary_format: {
    dtype: string
    endian: string
    /** "slice-major, then row-major" -- the cube is [T, rows, cols]. */
    order: string
    shape: [number, number, number]
    nodata: string
  }
}

export interface CorridorParams {
  startUtc: string
  roverId?: string
  nSlices?: number
  sliceHours?: number
  coarsen?: number
  litRule?: string
}

export function fetchIlluminationCorridor(
  params: CorridorParams,
  signal?: AbortSignal,
): Promise<CorridorManifest> {
  const query = new URLSearchParams({ start_utc: params.startUtc })
  if (params.roverId) query.set('rover_id', params.roverId)
  if (params.nSlices) query.set('n_slices', String(params.nSlices))
  if (params.sliceHours) query.set('slice_hours', String(params.sliceHours))
  if (params.coarsen) query.set('coarsen', String(params.coarsen))
  if (params.litRule) query.set('lit_rule', params.litRule)
  return getJson<CorridorManifest>(`/illumination-corridor?${query}`, signal)
}

// ── GET /api/uncertainty-series ─────────────────────────────────────────────

/**
 * B3's time half -- P(illuminated) per slice across NASA's DEM clones.
 *
 * The grid keys differ from every other coarse product here: `stride`,
 * `row_offset` and `col_offset` rather than `coarsen`/`downsample`. The offsets
 * matter -- the first sampled cell is at (2, 2) in fine coordinates, not (0, 0),
 * because the clone horizons were built at block centres. Reusing the coarsen
 * shape would place the whole field two cells off.
 */
export interface UncertaintySeriesManifest {
  /** `clone_horizon` or `unavailable` with a reason. Answers 200 either way. */
  model: string
  reason?: string | null
  n_clones?: number
  clone_indices?: number[]
  slices: number
  slice_hours: number
  start_utc: string | null
  grid?: {
    rows: number
    cols: number
    resolution_m: number
    stride: number
    row_offset: number
    col_offset: number
  }
  near_range_m?: number
  /** What the clones did NOT vary, and by how much that could matter. */
  far_field_held_fixed?: boolean
  neglected_horizon_shift_deg_max?: number
  sun?: unknown[]
  /**
   * Two arrays, one entry per slice -- NOT one object per slice.
   *
   * `mean` is the average P(illuminated) over the grid; `uncertain_fraction` is
   * the share of cells where the clones actually disagree (0.05 < P < 0.95).
   * The second is the interesting one: a high mean with a low uncertain
   * fraction is a confident answer, the same mean with a high one is not.
   */
  per_slice?: { mean: number[]; uncertain_fraction: number[] }
  fields?: Partial<
    Record<'p_illuminated', { units: string; min: number; max: number; binary_url: string }>
  >
  binary_format?: {
    dtype: string
    endian: string
    order: string
    shape: [number, number, number]
  }
}

export interface UncertaintySeriesParams {
  startUtc: string
  nSlices?: number
  sliceHours?: number
  nClones?: number
}

export function fetchUncertaintySeries(
  params: UncertaintySeriesParams,
  signal?: AbortSignal,
): Promise<UncertaintySeriesManifest> {
  const query = new URLSearchParams({ start_utc: params.startUtc })
  if (params.nSlices) query.set('n_slices', String(params.nSlices))
  if (params.sliceHours) query.set('slice_hours', String(params.sliceHours))
  if (params.nClones) query.set('n_clones', String(params.nClones))
  return getJson<UncertaintySeriesManifest>(`/uncertainty-series?${query}`, signal)
}
