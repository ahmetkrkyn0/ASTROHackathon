import { createWeights } from "../../models/missionModels";
import { buildReplanResult, resolveScenario } from "../../utils/mockMissionEngine";

function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

function withLatency(data, latencyMs = 135) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(clone(data)), latencyMs);
  });
}

export async function postReplan(payload = {}) {
  const scenario = resolveScenario(payload.scenarioId);
  const weights = createWeights({
    ...scenario.default_weights,
    ...(payload.weights ?? {}),
  });

  return withLatency(buildReplanResult({
    scenarioId: scenario.scenario_id,
    start: payload.start ?? scenario.start_grid,
    goal: payload.goal ?? scenario.goal_grid,
    weights,
    currentPath: payload.current_path ?? null,
    triggerType: payload.trigger_type ?? "thermal_spike",
    triggerLocation: payload.trigger_location ?? null,
  }));
}

export default {
  postReplan,
};
