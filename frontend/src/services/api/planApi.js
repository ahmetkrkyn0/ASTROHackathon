import { createWeights } from "../../models/missionModels";
import { apiPost, isMockApiEnabled } from "./client";
import { buildPathResult, resolveScenario } from "../../utils/mockMissionEngine";
import { validatePathResult } from "./validators";

function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

function withLatency(data, latencyMs = 90) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(clone(data)), latencyMs);
  });
}

export async function postPlan(payload = {}) {
  if (!isMockApiEnabled()) {
    return validatePathResult(await apiPost("/plan", {
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

  return withLatency(validatePathResult(buildPathResult({
    scenarioId: scenario.scenario_id,
    start: payload.start ?? scenario.start_grid,
    goal: payload.goal ?? scenario.goal_grid,
    weights,
  })), 110);
}

export default {
  postPlan,
};
