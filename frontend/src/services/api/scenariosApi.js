import { apiGet, apiPost, isMockApiEnabled } from "./client";
import scenariosMock from "../../mocks/scenarios.mock";
import { applyScenarioSnapshot, resolveScenario } from "../../utils/mockMissionEngine";
import { validateScenario, validateScenarioList, validateSnapshot } from "./validators";

function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

function withLatency(data, latencyMs = 85) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(clone(data)), latencyMs);
  });
}

export async function getScenarios() {
  if (!isMockApiEnabled()) {
    return validateScenarioList(await apiGet("/scenarios"));
  }

  return withLatency(validateScenarioList(scenariosMock));
}

export async function getScenarioById(scenarioId) {
  if (!isMockApiEnabled()) {
    const scenarios = await getScenarios();
    const scenario = scenarios.find((entry) => entry.scenario_id === scenarioId);

    if (!scenario) {
      throw new Error(`Scenario not found: ${scenarioId}`);
    }

    return validateScenario(scenario);
  }

  return withLatency(validateScenario(resolveScenario(scenarioId)));
}

export async function applyScenario(payload = {}) {
  if (!isMockApiEnabled()) {
    return validateSnapshot(await apiPost(`/scenarios/${payload.scenarioId}/apply`));
  }

  const scenario = resolveScenario(payload.scenarioId);
  return withLatency(validateSnapshot(applyScenarioSnapshot(scenario.scenario_id)), 120);
}

export default {
  getScenarios,
  getScenarioById,
  applyScenario,
};
