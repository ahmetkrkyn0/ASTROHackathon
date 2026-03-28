import { createPathResult } from "../models/missionModels";

export const pathResultMock = createPathResult({
  route_id: "safe-route-primary",
  route_label: "Mission Plan",
  route_strategy: "Thermal-priority route",
  start_grid: [1, 1],
  goal_grid: [10, 10],
  path_grid: [
    [1, 1],
    [2, 1],
    [3, 2],
    [4, 2],
    [5, 3],
    [6, 4],
    [7, 5],
    [8, 6],
    [9, 7],
    [10, 8],
    [10, 9],
    [10, 10],
  ],
  path_geo: [
    [-89.52, 31.95],
    [-89.515, 31.97],
    [-89.509, 31.99],
    [-89.503, 32.01],
    [-89.498, 32.03],
    [-89.493, 32.06],
    [-89.488, 32.09],
    [-89.482, 32.12],
    [-89.476, 32.15],
    [-89.471, 32.18],
    [-89.468, 32.21],
    [-89.465, 32.24],
  ],
  total_distance_m: 1450,
  total_thermal_exposure: 18.6,
  total_energy_cost: 67.4,
  max_slope_deg: 12.3,
  risk_breakdown: {
    safe_cells: 9,
    caution_cells: 3,
    danger_cells: 0,
  },
  computation_time_ms: 164,
});

export default pathResultMock;
