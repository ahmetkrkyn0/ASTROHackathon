/**
 * LunaPath mission control data contracts for the mock-first frontend phase.
 * The shapes follow the project reference document so the UI can switch to a
 * real API later with minimal churn.
 */

/**
 * @typedef {[number, number]} GridCoord
 * @typedef {[number, number]} GeoCoord
 */

export const DEFAULT_WEIGHTS = Object.freeze({
  w_dist: 1.0,
  w_slope: 1.1,
  w_thermal: 1.6,
  w_energy: 1.2,
});

/**
 * @param {Partial<typeof DEFAULT_WEIGHTS>} overrides
 */
export function createWeights(overrides = {}) {
  return {
    ...DEFAULT_WEIGHTS,
    ...overrides,
  };
}

export function createPathResult(overrides = {}) {
  return {
    route_id: "",
    route_label: "",
    route_strategy: "",
    start_grid: [0, 0],
    goal_grid: [0, 0],
    path_grid: [],
    path_geo: [],
    total_distance_m: 0,
    total_thermal_exposure: 0,
    total_energy_cost: 0,
    max_slope_deg: 0,
    risk_breakdown: {
      safe_cells: 0,
      caution_cells: 0,
      danger_cells: 0,
    },
    computation_time_ms: 0,
    ...overrides,
  };
}

export function createComparisonResult(overrides = {}) {
  return {
    comparison_id: "",
    scenario_id: "",
    safe_path: createPathResult(),
    shortest_path: createPathResult(),
    delta: {
      distance_overhead_pct: 0,
      thermal_reduction_pct: 0,
      energy_delta_pct: 0,
      recommendation: "paths_equivalent",
    },
    ...overrides,
  };
}

export function createReplanResult(overrides = {}) {
  return {
    replan_needed: false,
    scenario_id: "",
    trigger_type: "",
    affected_segment_start: 0,
    baseline_path: null,
    replanned_path: null,
    old_segment: [],
    new_segment: [],
    reason: "",
    metrics_delta: {
      distance_delta_m: 0,
      thermal_delta: 0,
      energy_delta: 0,
    },
    computation_time_ms: 0,
    event_log: [],
    ...overrides,
  };
}

export function createGridMetadata(overrides = {}) {
  return {
    region_id: "",
    region_name: "",
    resolution_m: 80,
    shape: [500, 500],
    origin_m: {
      x: 176000,
      y: 48000,
    },
    extent_m: {
      width: 40000,
      height: 40000,
    },
    projection: "Moon 2015 Polar Stereographic",
    start_grid: [0, 0],
    goal_grid: [0, 0],
    layers: [],
    ...overrides,
  };
}

export function createScenario(overrides = {}) {
  return {
    scenario_id: "",
    name: "",
    description: "",
    grid_region: "",
    start_grid: [0, 0],
    goal_grid: [0, 0],
    default_weights: createWeights(),
    default_layer_id: "thermal_risk",
    status: "ready",
    summary: "",
    ...overrides,
  };
}
