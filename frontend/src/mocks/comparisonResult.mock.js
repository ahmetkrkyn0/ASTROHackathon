import { buildComparisonResult, resolveScenario } from "../utils/mockMissionEngine";

const defaultScenario = resolveScenario("south_pole_demo_v1");

export const comparisonResultMock = buildComparisonResult({
  scenarioId: defaultScenario.scenario_id,
  start: defaultScenario.start_grid,
  goal: defaultScenario.goal_grid,
  weights: defaultScenario.default_weights,
});

const shortestPathMock = comparisonResultMock.shortest_path;

export { shortestPathMock };
export default comparisonResultMock;
