import { createWeights } from "../../models/missionModels";
import { buildPathResult, resolveScenario } from "../../utils/mockMissionEngine";

function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

function withLatency(data, latencyMs = 90) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(clone(data)), latencyMs);
  });
}

export async function postPlan(payload = {}) {
  const scenario = resolveScenario(payload.scenarioId);
  const weights = createWeights({
    ...scenario.default_weights,
    ...(payload.weights ?? {}),
  });

  return withLatency(buildPathResult({
    scenarioId: scenario.scenario_id,
    start: payload.start ?? scenario.start_grid,
    goal: payload.goal ?? scenario.goal_grid,
    weights,
  }), 110);
}

export default {
  postPlan,
};
