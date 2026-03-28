import { createWeights } from "../../models/missionModels";
import { apiPost, isMockApiEnabled } from "./client";
import { buildComparisonResult, resolveScenario } from "../../utils/mockMissionEngine";
import { validateComparisonResult } from "./validators";

function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

function withLatency(data, latencyMs = 110) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(clone(data)), latencyMs);
  });
}

export async function postCompare(payload = {}) {
  if (!isMockApiEnabled()) {
    return validateComparisonResult(await apiPost("/compare", {
      start: payload.start,
      goal: payload.goal,
      weights: payload.weights,
    }));
  }

  const scenario = resolveScenario(payload.scenarioId);
  const weights = createWeights({
    ...scenario.default_weights,
    ...(payload.weights ?? {}),
  });

  return withLatency(validateComparisonResult(buildComparisonResult({
    scenarioId: scenario.scenario_id,
    start: payload.start ?? scenario.start_grid,
    goal: payload.goal ?? scenario.goal_grid,
    weights,
  })));
}

export default {
  postCompare,
};
