import { createComparisonResult, createPathResult } from "../models/missionModels";
import { pathResultMock } from "./pathResult.mock";

const shortestPathMock = createPathResult({
  route_id: "short-route-baseline",
  route_label: "Shortest Path",
  route_strategy: "Distance-priority route",
  start_grid: [1, 1],
  goal_grid: [10, 10],
  path_grid: [
    [1, 1],
    [2, 2],
    [3, 3],
    [4, 4],
    [5, 5],
    [6, 6],
    [7, 7],
    [8, 8],
    [9, 9],
    [10, 10],
  ],
  path_geo: [
    [-89.52, 31.95],
    [-89.513, 31.98],
    [-89.506, 32.01],
    [-89.499, 32.04],
    [-89.492, 32.07],
    [-89.485, 32.1],
    [-89.478, 32.13],
    [-89.471, 32.16],
    [-89.468, 32.2],
    [-89.465, 32.24],
  ],
  total_distance_m: 1180,
  total_thermal_exposure: 58.2,
  total_energy_cost: 72.1,
  max_slope_deg: 17.9,
  risk_breakdown: {
    safe_cells: 4,
    caution_cells: 4,
    danger_cells: 2,
  },
  computation_time_ms: 149,
});

export const comparisonResultMock = createComparisonResult({
  comparison_id: "compare-south-pole-demo",
  scenario_id: "south_pole_demo_v1",
  safe_path: pathResultMock,
  shortest_path: shortestPathMock,
  delta: {
    distance_overhead_pct: 22.9,
    thermal_reduction_pct: 68.0,
    energy_delta_pct: -6.5,
    recommendation: "safe_path_preferred",
  },
});

export { shortestPathMock };
export default comparisonResultMock;
