import { createScenario, createWeights } from "../models/missionModels";

export const scenariosMock = [
  createScenario({
    scenario_id: "south_pole_demo_v1",
    name: "Crater Rim Detour",
    description: "A baseline mission where the shorter line cuts across a cold crater pocket and the safer route skirts the rim.",
    grid_region: "south_pole_12x12_demo",
    start_grid: [1, 1],
    goal_grid: [10, 10],
    default_weights: createWeights({
      w_dist: 1.0,
      w_slope: 1.1,
      w_thermal: 1.6,
      w_energy: 1.2,
    }),
    default_layer_id: "thermal_risk",
    summary: "Use this as the default Mission Control view for safe-vs-short comparison.",
  }),
  createScenario({
    scenario_id: "ridge_crossing_demo_v1",
    name: "Ridge Crossing",
    description: "Highlights the tradeoff between a steeper direct climb and a longer corridor with lower energy demand.",
    grid_region: "south_pole_12x12_demo",
    start_grid: [1, 2],
    goal_grid: [10, 9],
    default_weights: createWeights({
      w_dist: 1.1,
      w_slope: 1.5,
      w_thermal: 1.2,
      w_energy: 1.4,
    }),
    default_layer_id: "slope",
    summary: "Useful for validating how slope and energy weights shift the route choice.",
  }),
  createScenario({
    scenario_id: "thermal_spike_demo_v1",
    name: "Thermal Spike Replan",
    description: "Focuses on event-triggered replanning after a new thermal hazard appears on the active corridor.",
    grid_region: "south_pole_12x12_demo",
    start_grid: [2, 1],
    goal_grid: [10, 10],
    default_weights: createWeights({
      w_dist: 0.9,
      w_slope: 1.0,
      w_thermal: 1.8,
      w_energy: 1.1,
    }),
    default_layer_id: "psr_mask",
    summary: "Best scenario for showing the manual replan trigger in the prototype.",
  }),
];

export default scenariosMock;
