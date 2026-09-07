import type { PlanWeights } from '../api'

/** Ranked SYNTHETIC < DERIVED < MODEL < MEASURED (traversability.py:109). */
export type Validity = 'SYNTHETIC' | 'DERIVED' | 'MODEL' | 'MEASURED'

export const VALIDITY_RANK: Record<Validity, number> = {
  SYNTHETIC: 0,
  DERIVED: 1,
  MODEL: 2,
  MEASURED: 3,
}

// ── GET /api/terrain ───────────────────────────────────────────────────────

export interface LayerManifestEntry {
  units: string
  description: string
  /** null when the grid metadata carried no label for this layer. */
  validity: Validity | null
  /** null when the layer holds no finite value. */
  min: number | null
  max: number | null
  nodata: number
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
    /** Projected CRS metres of the window's north-west corner. */
    origin: { x: number; y: number } | null
    crs: string | null
    window_offset: { row: number; col: number } | null
    row_axis: 'north-to-south'
    col_axis: 'west-to-east'
  }
  elevation: {
    min_m: number
    max_m: number
    relief_m: number
    vertical_exaggeration_suggested: number
  }
  binary_format: {
    dtype: string
    endian: string
    order: string
    nodata: string
    bytes_per_layer: number
    decode: string
  }
  rover: { id: string; name: string }
  weights: PlanWeights | null
  layers: Record<string, LayerManifestEntry>
  /**
   * B3 pedigree. Present only where the DEM clone cache exists, which is
   * also the only case in which the four uncertainty layers appear above.
   *
   * Worth publishing in full because the three `*_held_fixed` flags are
   * what the layers do NOT cover: the thermal field, the far-field horizon
   * and Earth visibility were not re-derived per clone, so an uncertainty
   * band drawn from these layers is a band over terrain alone.
   */
  dem_uncertainty?: DemUncertaintyPedigree
}

export interface DemUncertaintyPedigree {
  /** `nasa_pgda_clones` for the real product, `synthetic` for a stand-in. */
  model: string
  site: string
  product_url: string
  reference: string
  n_clones: number
  clone_indices?: number[]
  near_range_m: number
  /** NASA's own toterr/slperr statistics and their source URLs. */
  sigma?: Record<string, unknown>
  /** These three say what the ensemble did NOT vary. */
  thermal_field_held_fixed: boolean
  far_field_held_fixed: boolean
  earth_visibility_cloned: boolean
  rover_id?: string
  slope_max_deg?: number
  [key: string]: unknown
}

// ── GET /api/cell-telemetry ────────────────────────────────────────────────

/**
 * Weighted contribution per cost layer, plus the total.
 *
 * null means an INFINITE contribution -- the cell is IMPASSABLE. Starlette
 * renders JSON with allow_nan=False, so costmap.explain() maps inf to null
 * (costmap.py:143-158). It never means "no data".
 */
export interface CostBreakdown {
  slope: number | null
  energy: number | null
  shadow: number | null
  thermal: number | null
  /** C4's fifth slice. Absent, not null, where the roughness layer is unloaded. */
  roughness?: number | null
  total: number | null
}

/**
 * The `{model, reason}` shape several endpoints publish to say, inside a
 * 200 response, that they could not compute anything. A 200 is not
 * evidence the data is there.
 */
export interface ModelStatus {
  model: string
  reason?: string | null
  [key: string]: unknown
}

/** A1: the safe-haven verdict for one cell. Present only with a start epoch. */
export interface CellSafeHaven {
  is_safe_haven: boolean
  max_dark_hours_without_dte_h: number | null
  earth_below_hours: number | null
  /**
   * Driving hours to the nearest reachable haven.
   *
   * `null` means NO REACHABLE SAFE HAVEN -- the same fact the binary grid
   * encodes as NaN. It is never 0.0 h: zero means the cell IS a haven,
   * which is the opposite statement.
   */
  time_to_safe_haven_h: number | null
  h_max_shadow_h: number | null
}

/** B1 for one cell: the policy's verdict where the rover is standing. */
export interface CellSurvival {
  /** Probability of reaching the safe set from here. Zero is a real answer. */
  p_safe: number
  p_safe_next: number | null
  /** 0-7 a compass move, 8 wait, 254 already safe, 255 nothing helps. */
  best_action: number
  /** The same code in words -- `N`, `wait`, `safe`, `none`. */
  best_action_name: string
  next_block: [number, number] | null
  next_pixel: [number, number] | null
  /** The coarse block this fine cell falls in. */
  block: [number, number]
  coarsen: number
  soc_frac: number
  t_hours: number
  safe_set: string
  step_hours: number
  horizon_hours: number
}

/** C6 for one cell. */
export interface CellThermalDwell {
  /**
   * Hours before the inner temperature leaves the envelope.
   *
   * Read `open_ended` first: where it is true this number was CLIPPED to
   * `lookahead_h` and means "at least", not "exactly".
   */
  max_dwell_h: number | null
  open_ended: boolean
  side: 'cold' | 'hot' | null
  component: string | null
  initial_inner_c: number
  heater_model: string
  heater_source: string | null
  lookahead_h: number
  slice_hours: number
  inner_equilibrium_c?: { peak: number | null; cold_end: number | null }
  surface_c?: Record<string, number | null>
  envelope: { lo_c: number; hi_c: number; lo_component: string; hi_component: string }
  envelope_verdict?: { peak: string | null; cold_end: string | null }
  /** UNCALIBRATED. Shown beside every hour above. */
  thermal_lag_validity: string
  initial_outside_envelope: boolean
  /** Two independent countdowns: thermal, and the safe-haven window. */
  tolerable_entrenched?: Record<string, Record<string, unknown>>
  [key: string]: unknown
}

export interface CellTelemetryResponse {
  row: number
  col: number
  lon: number
  lat: number
  altitude_m: number | null
  thermal_c: number | null
  thermal_min_c: number | null
  resolution_m: number
  span_km: number
  cost_breakdown: CostBreakdown
  layer_validity: Record<string, Validity>
  /** C4. Metres, from the covering 50 m LDRM pixel. Null when unloaded. */
  roughness_m?: number | null
  /** C4. The criterion in [0, 1] -- a regional percentile rank, not a rover tolerance. */
  f_roughness?: number | null
  /** C4. Inside NASA's PGDA PSR mask. Analysis data, not a no-go area. */
  in_psr?: boolean | null
  /** A1. Null without a start epoch; `safe_haven_model.reason` says why. */
  safe_haven?: CellSafeHaven | null
  safe_haven_model?: ModelStatus | null
  /** B1. Null unless `survival=true`; needs an epoch and a goal. */
  survival?: CellSurvival | null
  survival_model?: ModelStatus | null
  /** C6. Null unless `thermal_dwell=true`. */
  thermal_dwell?: CellThermalDwell | null
  thermal_dwell_model?: ModelStatus | null
}

// ── POST /api/plan -> corridor, route_statistics ───────────────────────────

export interface Corridor {
  /** Projected CRS metres (x, y), one per path pixel. */
  waypoints: Array<[number, number]>
  half_width_m: number[]
  max_slope_deg: number[]
  energy_budget_wh: number[]
  thermal_budget_K_s: number[]
  fallback_points: Array<[number, number]>
  crs: string
  corridor_id: string
}

export interface SlopeBin {
  /** Field names are bin_low_deg / bin_high_deg, not from_deg / to_deg. */
  bin_low_deg: number
  bin_high_deg: number
  count: number
  /** Share of waypoints in this bin, already computed by the backend. */
  pct: number
}

export interface RouteStatistics {
  waypoint_count: number
  slope_histogram: SlopeBin[]
  risk_breakdown_pct: Record<string, number>
  min_surface_temp_c: number | null
  max_surface_temp_c: number | null
}

// ── POST /api/replan ───────────────────────────────────────────────────────

export type TriggerId =
  | 'soc_deviation'
  | 'inner_temperature'
  | 'time_drift'
  | 'corridor_violation'
  | 'comm_window'
  | 'localization_uncertainty'
  | 'slip_accumulation'

export interface TriggerRef {
  trigger_id: TriggerId
  detail: string
}

/**
 * A check that could NOT run, and the telemetry keys it wanted.
 *
 * An object, not a bare id: replan_triggers.evaluate_triggers_detailed
 * appends `{trigger_id, missing}` (replan_triggers.py:219-223), and
 * /api/pose adds `reason` when it can explain why the keys are absent
 * (localization.py:317-327). Typing this as string[] makes every
 * membership test silently false, which renders an unevaluated trigger as
 * clear -- the exact failure `skipped` exists to prevent.
 */
export interface SkippedTrigger {
  trigger_id: TriggerId
  missing: string[]
  reason?: string
}

export interface ReplanResponse {
  replanned: boolean
  triggers: TriggerRef[]
  /** Trigger ids that WERE evaluated. */
  evaluated: string[]
  /** Checks that could NOT be evaluated -- telemetry fields missing. */
  skipped: SkippedTrigger[]
  reason?: string
  plan?: unknown
}

// ── POST /api/plan-4d ──────────────────────────────────────────────────────

export interface ShadowModel {
  /**
   * "static" means the cube did NOT vary with time -- do not animate it.
   * The usual cause is a request with no start_utc: illumination is a
   * function of time and the backend says so in `reason`.
   */
  model: string
  time_varying?: boolean
  reason?: string
  horizon_cache?: string
  /** Echoed back only when the series is time-varying. */
  start_utc?: string
}

export interface Plan4DResponse {
  /** FINE grid pixels -- this is what gets drawn. */
  path_pixels: Array<[number, number]>
  /** COARSE grid pixels, cell size = effective_resolution_m. */
  path_pixels_coarse: Array<[number, number]>
  path_states: Array<[number, number, number]>
  metrics: {
    wait_steps: number
    move_steps: number
    arrival_slice: number | null
    arrival_hours: number | null
    [key: string]: unknown
  }
  shadow_model: ShadowModel
  n_slices: number
  slice_hours: number
  slice_hours_source: string
  horizon_hours: number
  coarsen: number
  effective_resolution_m: number
  rover_id: string
}

// ── GET /api/illumination-series ───────────────────────────────────────────

export interface SunSample {
  index: number
  utc: string
  azimuth_true_deg: number
  azimuth_grid_deg: number
  elevation_deg: number
}

export interface SeriesManifest {
  slices: number
  slice_hours: number
  start_utc: string | null
  grid: { rows: number; cols: number; resolution_m: number; downsample: number }
  shadow_model: ShadowModel
  thermal_model: { recipe: string; tau_s: number; validity: string }
  sun: SunSample[]
  fields: Record<
    'shadow' | 'surface_temp_c',
    { units: string; min: number | null; max: number | null; binary_url: string }
  >
  binary_format: {
    dtype: string
    endian: string
    /** "slice-major, then row-major" */
    order: string
    shape: [number, number, number]
    nodata: string
  }
}

// ── POST /api/pose ─────────────────────────────────────────────────────────

/**
 * Where a pose sits relative to the corridor it is judged against.
 *
 * The clearance field is `half_width_at_pose_m`, not `half_width_m`: the
 * corridor publishes a half-width per SEGMENT, and this is the one at the
 * segment the pose projected onto. `inside` is the backend's own verdict --
 * comparing the offset against the width here would re-derive a decision it
 * has already made, and disagree with it at the boundary.
 */
export interface CorridorFix {
  segment_index: number
  lateral_offset_m: number
  along_track_m: number
  progress_fraction: number
  half_width_at_pose_m: number
  inside: boolean
  [key: string]: unknown
}

export interface PoseResponse {
  corridor_id: string | null
  corridor_rover_id: string | null
  corridor_fix: CorridorFix
  pose_source: string
  fired_triggers: TriggerRef[]
  evaluated: string[]
  skipped: SkippedTrigger[]
  trigger_state: Record<string, number>
  recommended_action: string
}

// ── POST /api/plan-multi, POST /api/compare ────────────────────────────────

export interface ProfileResult {
  profile_id: string
  profile_name: string | null
  color: string
  path_pixels: Array<[number, number]>
  metrics: Record<string, unknown>
  constraint_check?: Record<string, unknown>
  simulation_summary?: Record<string, unknown> | null
  error?: string
}

export interface CompareResponse {
  start: [number, number]
  goal: [number, number]
  results: ProfileResult[]
  comparison: Record<string, unknown>
}

export interface PlanMultiResponse {
  results: ProfileResult[]
}

// ── GET /api/reference-missions ────────────────────────────────────────────

export interface ReferenceMissions {
  note: string
  missions: Array<{
    mission: string
    total_distance_m: number
    as_of: string
    lower_bound_rate_m_per_calendar_day: number
    milestones: Array<Record<string, unknown>>
    [key: string]: unknown
  }>
}

// ── GET /api/profiles ──────────────────────────────────────────────────────

/** The four constraints every mission profile declares (scenarios.py). */
export interface ProfileConstraints {
  max_shadow_h: number
  max_slope_deg: number
  max_energy_wh: number
  min_soc: number
}

/**
 * Where each constraint is checked. `enforced_in_search` means the A* solver
 * already refuses cells that violate it, so the returned route cannot break it;
 * `verified_after_simulation` means it is only reported against the simulated
 * route, and a plan CAN come back marked as exceeding it. The backend computes
 * this per constraint and the panel surfaces it -- an enforced limit and a
 * checked-afterward limit are not the same promise.
 */
export type ConstraintHandling = 'enforced_in_search' | 'verified_after_simulation'

export interface MissionProfile {
  /** Turkish display name, e.g. "Enerji Tasarrufu". */
  name: string
  description: string
  weights: PlanWeights
  constraints: ProfileConstraints
  /** Hex accent the backend assigns the profile, reused for the chip. */
  color: string
  constraint_handling: Record<keyof ProfileConstraints, ConstraintHandling>
}

/** Keyed by profile id: balanced, energy_saver, fast_recon, shadow_traverse. */
export type MissionProfiles = Record<string, MissionProfile>
