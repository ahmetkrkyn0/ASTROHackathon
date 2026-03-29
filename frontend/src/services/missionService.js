import { createWeights } from "../models/missionModels";
import { postCompare } from "./api/compareApi";
import { getLayers } from "./api/layersApi";
import { postPlan } from "./api/planApi";
import { postReplan } from "./api/replanApi";
import {
  applyScenario as applyScenarioApi,
  getScenarioById as getScenarioByIdApi,
  getScenarios as getScenariosApi,
} from "./api/scenariosApi";

function mergeWeights(baseWeights = {}, overrides = {}) {
  return createWeights({
    ...baseWeights,
    ...overrides,
  });
}

export const missionService = {
  async getScenarios() {
    return getScenariosApi();
  },

  async getScenarioById(scenarioId) {
    return getScenarioByIdApi(scenarioId);
  },

  async applyScenario(scenarioId) {
    return applyScenarioApi({ scenarioId });
  },

  async getLayersMetadata({ region, scenarioId } = {}) {
    return getLayers({ region, scenarioId });
  },

  async getPathResult({ scenarioId, start, goal, weights } = {}) {
    const scenario = await this.getScenarioById(scenarioId);
    return postPlan({
      scenarioId: scenario.scenario_id,
      start: start ?? scenario.start_grid,
      goal: goal ?? scenario.goal_grid,
      weights: mergeWeights(scenario.default_weights, weights),
    });
  },

  async getComparisonResult({ scenarioId, start, goal, weights } = {}) {
    const scenario = await this.getScenarioById(scenarioId);
    return postCompare({
      scenarioId: scenario.scenario_id,
      start: start ?? scenario.start_grid,
      goal: goal ?? scenario.goal_grid,
      weights: mergeWeights(scenario.default_weights, weights),
    });
  },

  async getReplanResult({
    scenarioId,
    start,
    goal,
    weights,
    currentPath,
    triggerType,
    triggerLocation,
  } = {}) {
    const scenario = await this.getScenarioById(scenarioId);
    return postReplan({
      scenarioId: scenario.scenario_id,
      start: start ?? scenario.start_grid,
      goal: goal ?? scenario.goal_grid,
      weights: mergeWeights(scenario.default_weights, weights),
      current_path: currentPath ?? null,
      trigger_type: triggerType ?? "thermal_spike",
      trigger_location: triggerLocation ?? null,
    });
  },

  async planRoute(payload = {}) {
    return this.getPathResult(payload);
  },

  async compareRoutes(payload = {}) {
    return this.getComparisonResult(payload);
  },

  async replanRoute(payload = {}) {
    return this.getReplanResult(payload);
  },

  async getMissionControlSnapshot({
    scenarioId,
    start,
    goal,
    weights,
    currentPath,
    triggerType,
    triggerLocation,
  } = {}) {
    const scenario = await this.getScenarioById(scenarioId);
    const mergedWeights = mergeWeights(scenario.default_weights, weights);
    const effectiveStart = start ?? scenario.start_grid;
    const effectiveGoal = goal ?? scenario.goal_grid;

    const [layers_metadata, path_result, comparison_result, replan_result] = await Promise.all([
      this.getLayersMetadata({ region: scenario.grid_region, scenarioId: scenario.scenario_id }),
      this.getPathResult({
        scenarioId: scenario.scenario_id,
        start: effectiveStart,
        goal: effectiveGoal,
        weights: mergedWeights,
      }),
      this.getComparisonResult({
        scenarioId: scenario.scenario_id,
        start: effectiveStart,
        goal: effectiveGoal,
        weights: mergedWeights,
      }),
      this.getReplanResult({
        scenarioId: scenario.scenario_id,
        start: effectiveStart,
        goal: effectiveGoal,
        weights: mergedWeights,
        currentPath,
        triggerType,
        triggerLocation,
      }),
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
