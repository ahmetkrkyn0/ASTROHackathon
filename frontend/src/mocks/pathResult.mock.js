import { buildPathResult, resolveScenario } from "../utils/mockMissionEngine";

const defaultScenario = resolveScenario("south_pole_demo_v1");

export const pathResultMock = buildPathResult({
  scenarioId: defaultScenario.scenario_id,
  start: defaultScenario.start_grid,
  goal: defaultScenario.goal_grid,
  weights: defaultScenario.default_weights,
  routeKind: "safe",
});

export default pathResultMock;
