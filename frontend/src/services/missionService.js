import comparisonResultMock, { shortestPathMock } from "../mocks/comparisonResult.mock";
import layersMetadataMock from "../mocks/layers.mock";
import pathResultMock from "../mocks/pathResult.mock";
import replanResultMock from "../mocks/replanResult.mock";
import scenariosMock from "../mocks/scenarios.mock";

function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

function createWeightedPathResult(weights) {
  const prefersSafety = weights.w_thermal >= 1.25 || weights.w_energy >= weights.w_dist;
  const basePath = prefersSafety ? pathResultMock : shortestPathMock;

  return {
    ...clone(basePath),
    route_label: prefersSafety ? "Mission Plan" : "Distance-Biased Plan",
    route_strategy: prefersSafety ? "Thermal-priority route" : "Distance-priority route",
  };
}

function createWeightedComparisonResult(scenarioId, weights) {
  const comparison = clone(comparisonResultMock);
  const thermalBias = weights.w_thermal - weights.w_dist;
  const slopeBias = weights.w_slope - 1;
  const recommendation = thermalBias >= 0.2 ? "safe_path_preferred" : "paths_equivalent";

  comparison.scenario_id = scenarioId;
  comparison.delta.recommendation = recommendation;
  comparison.delta.distance_overhead_pct = Number((22.9 + slopeBias * 1.4).toFixed(1));
  comparison.delta.thermal_reduction_pct = Number((68 + thermalBias * 8).toFixed(1));
  comparison.delta.energy_delta_pct = Number((-6.5 + (weights.w_energy - 1.2) * 7).toFixed(1));

  return comparison;
}

function createScenarioAwareReplanResult(scenarioId) {
  const result = clone(replanResultMock);
  result.scenario_id = scenarioId;
  return result;
}

export const missionService = {
  async getScenarios() {
    return clone(scenariosMock);
  },

  async getScenarioById(scenarioId) {
    const scenario = scenariosMock.find((item) => item.scenario_id === scenarioId) ?? scenariosMock[0];
    return clone(scenario);
  },

  async getLayersMetadata() {
    return clone(layersMetadataMock);
  },

  async getPathResult({ weights }) {
    return createWeightedPathResult(weights);
  },

  async getComparisonResult({ scenarioId, weights }) {
    return createWeightedComparisonResult(scenarioId, weights);
  },

  async getReplanResult({ scenarioId }) {
    return createScenarioAwareReplanResult(scenarioId);
  },

  async getMissionControlSnapshot({ scenarioId, weights }) {
    const [scenario, layers_metadata, path_result, comparison_result, replan_result] =
      await Promise.all([
        this.getScenarioById(scenarioId),
        this.getLayersMetadata(),
        this.getPathResult({ scenarioId, weights }),
        this.getComparisonResult({ scenarioId, weights }),
        this.getReplanResult({ scenarioId }),
      ]);

    return {
      scenario,
      layers_metadata,
      path_result,
      comparison_result,
      replan_result,
    };
  },
};

export default missionService;
