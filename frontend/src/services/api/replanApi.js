import { createWeights } from "../../models/missionModels";
import { apiPost, isMockApiEnabled } from "./client";
import { buildReplanResult, resolveScenario } from "../../utils/mockMissionEngine";
import { validateReplanResult } from "./validators";

function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

function withLatency(data, latencyMs = 135) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(clone(data)), latencyMs);
  });
}

export async function postReplan(payload = {}) {
  if (!isMockApiEnabled()) {
    return validateReplanResult(await apiPost("/replan", {
      current_path: payload.current_path ?? null,
      trigger_type: payload.trigger_type ?? "thermal_spike",
      trigger_location: payload.trigger_location ?? null,
    }));
  }

  const scenario = resolveScenario(payload.scenarioId);
  const weights = createWeights({
    ...scenario.default_weights,
    ...(payload.weights ?? {}),
  });

  return withLatency(validateReplanResult(buildReplanResult({
    scenarioId: scenario.scenario_id,
    start: payload.start ?? scenario.start_grid,
    goal: payload.goal ?? scenario.goal_grid,
    weights,
    currentPath: payload.current_path ?? null,
    triggerType: payload.trigger_type ?? "thermal_spike",
    triggerLocation: payload.trigger_location ?? null,
  })));
}

export default {
  postReplan,
};
