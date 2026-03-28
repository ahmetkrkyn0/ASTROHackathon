function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function isCoordPair(value) {
  return Array.isArray(value)
    && value.length === 2
    && value.every((entry) => isFiniteNumber(entry));
}

function validateRiskBreakdown(value, label) {
  assert(value && typeof value === "object", `${label}.risk_breakdown is required`);
  assert(Number.isInteger(value.safe_cells), `${label}.risk_breakdown.safe_cells must be an integer`);
  assert(Number.isInteger(value.caution_cells), `${label}.risk_breakdown.caution_cells must be an integer`);
  assert(Number.isInteger(value.danger_cells), `${label}.risk_breakdown.danger_cells must be an integer`);
}

export function validatePathResult(value, label = "path_result") {
  assert(value && typeof value === "object", `${label} is required`);
  assert(isCoordPair(value.start_grid), `${label}.start_grid must be [row, col]`);
  assert(isCoordPair(value.goal_grid), `${label}.goal_grid must be [row, col]`);
  assert(Array.isArray(value.path_grid), `${label}.path_grid must be an array`);
  assert(Array.isArray(value.path_geo), `${label}.path_geo must be an array`);
  assert(value.path_grid.every(isCoordPair), `${label}.path_grid contains invalid coordinates`);
  assert(value.path_geo.every(isCoordPair), `${label}.path_geo contains invalid coordinates`);
  assert(isFiniteNumber(value.total_distance_m), `${label}.total_distance_m must be numeric`);
  assert(isFiniteNumber(value.total_thermal_exposure), `${label}.total_thermal_exposure must be numeric`);
  assert(isFiniteNumber(value.total_energy_cost), `${label}.total_energy_cost must be numeric`);
  assert(isFiniteNumber(value.max_slope_deg), `${label}.max_slope_deg must be numeric`);
  assert(Number.isInteger(value.computation_time_ms), `${label}.computation_time_ms must be an integer`);
  validateRiskBreakdown(value.risk_breakdown, label);
  return value;
}

export function validateComparisonResult(value, label = "comparison_result") {
  assert(value && typeof value === "object", `${label} is required`);
  validatePathResult(value.safe_path, `${label}.safe_path`);
  validatePathResult(value.shortest_path, `${label}.shortest_path`);
  assert(value.delta && typeof value.delta === "object", `${label}.delta is required`);
  assert(isFiniteNumber(value.delta.distance_overhead_pct), `${label}.delta.distance_overhead_pct must be numeric`);
  assert(isFiniteNumber(value.delta.thermal_reduction_pct), `${label}.delta.thermal_reduction_pct must be numeric`);
  assert(isFiniteNumber(value.delta.energy_delta_pct), `${label}.delta.energy_delta_pct must be numeric`);
  assert(typeof value.delta.recommendation === "string", `${label}.delta.recommendation must be a string`);
  return value;
}

export function validateReplanResult(value, label = "replan_result") {
  assert(value && typeof value === "object", `${label} is required`);
  assert(typeof value.replan_needed === "boolean", `${label}.replan_needed must be boolean`);
  assert(typeof value.trigger_type === "string", `${label}.trigger_type must be a string`);
  assert(Number.isInteger(value.affected_segment_start), `${label}.affected_segment_start must be an integer`);
  assert(Array.isArray(value.old_segment), `${label}.old_segment must be an array`);
  assert(Array.isArray(value.new_segment), `${label}.new_segment must be an array`);
  assert(value.old_segment.every(isCoordPair), `${label}.old_segment contains invalid coordinates`);
  assert(value.new_segment.every(isCoordPair), `${label}.new_segment contains invalid coordinates`);
  assert(typeof value.reason === "string", `${label}.reason must be a string`);
  assert(value.metrics_delta && typeof value.metrics_delta === "object", `${label}.metrics_delta is required`);
  assert(isFiniteNumber(value.metrics_delta.distance_delta_m), `${label}.metrics_delta.distance_delta_m must be numeric`);
  assert(isFiniteNumber(value.metrics_delta.thermal_delta), `${label}.metrics_delta.thermal_delta must be numeric`);
  assert(isFiniteNumber(value.metrics_delta.energy_delta), `${label}.metrics_delta.energy_delta must be numeric`);
  assert(Number.isInteger(value.computation_time_ms), `${label}.computation_time_ms must be an integer`);
  assert(Array.isArray(value.event_log), `${label}.event_log must be an array`);

  if (value.baseline_path) {
    validatePathResult(value.baseline_path, `${label}.baseline_path`);
  }

  if (value.replanned_path) {
    validatePathResult(value.replanned_path, `${label}.replanned_path`);
  }

  return value;
}

export function validateGridMetadata(value, label = "layers_metadata") {
  assert(value && typeof value === "object", `${label} is required`);
  assert(Array.isArray(value.shape) && value.shape.length === 2, `${label}.shape must contain rows and columns`);
  assert(Number.isInteger(value.shape[0]) && Number.isInteger(value.shape[1]), `${label}.shape must contain integers`);
  assert(isFiniteNumber(value.resolution_m), `${label}.resolution_m must be numeric`);
  assert(value.origin_m && isFiniteNumber(value.origin_m.x) && isFiniteNumber(value.origin_m.y), `${label}.origin_m is invalid`);
  assert(value.extent_m && isFiniteNumber(value.extent_m.width) && isFiniteNumber(value.extent_m.height), `${label}.extent_m is invalid`);
  assert(Array.isArray(value.layers), `${label}.layers must be an array`);
  assert(value.layers.every((layer) => typeof layer.id === "string" && typeof layer.label === "string"), `${label}.layers contains invalid entries`);
  return value;
}

export function validateScenario(value, label = "scenario") {
  assert(value && typeof value === "object", `${label} is required`);
  assert(typeof value.scenario_id === "string" && value.scenario_id.length > 0, `${label}.scenario_id is required`);
  assert(typeof value.name === "string" && value.name.length > 0, `${label}.name is required`);
  assert(typeof value.grid_region === "string" && value.grid_region.length > 0, `${label}.grid_region is required`);
  assert(isCoordPair(value.start_grid), `${label}.start_grid must be [row, col]`);
  assert(isCoordPair(value.goal_grid), `${label}.goal_grid must be [row, col]`);
  assert(value.default_weights && typeof value.default_weights === "object", `${label}.default_weights is required`);
  return value;
}

export function validateScenarioList(value, label = "scenarios") {
  assert(Array.isArray(value), `${label} must be an array`);
  value.forEach((scenario, index) => validateScenario(scenario, `${label}[${index}]`));
  return value;
}

export function validateSnapshot(value, label = "snapshot") {
  assert(value && typeof value === "object", `${label} is required`);
  validateScenario(value.scenario, `${label}.scenario`);
  validateGridMetadata(value.layers_metadata, `${label}.layers_metadata`);
  validatePathResult(value.path_result, `${label}.path_result`);
  validateComparisonResult(value.comparison_result, `${label}.comparison_result`);
  validateReplanResult(value.replan_result, `${label}.replan_result`);
  return value;
}

export default {
  validateComparisonResult,
  validateGridMetadata,
  validatePathResult,
  validateReplanResult,
  validateScenario,
  validateScenarioList,
  validateSnapshot,
};
