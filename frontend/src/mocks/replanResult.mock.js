import { buildReplanResult, resolveScenario } from "../utils/mockMissionEngine";

const defaultScenario = resolveScenario("thermal_spike_demo_v1");

export const replanResultMock = buildReplanResult({
  scenarioId: defaultScenario.scenario_id,
  start: defaultScenario.start_grid,
  goal: defaultScenario.goal_grid,
  weights: defaultScenario.default_weights,
  triggerType: "thermal_spike",
  triggerLocation: [248, 252],
});

export default replanResultMock;
