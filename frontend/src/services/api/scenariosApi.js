import scenariosMock from "../../mocks/scenarios.mock";
import { applyScenarioSnapshot, resolveScenario } from "../../utils/mockMissionEngine";

function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

function withLatency(data, latencyMs = 85) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(clone(data)), latencyMs);
  });
}

export async function getScenarios() {
  return withLatency(scenariosMock);
}

export async function getScenarioById(scenarioId) {
  return withLatency(resolveScenario(scenarioId));
}

export async function applyScenario(payload = {}) {
  const scenario = resolveScenario(payload.scenarioId);
  return withLatency(applyScenarioSnapshot(scenario.scenario_id), 120);
}

export default {
  getScenarios,
  getScenarioById,
  applyScenario,
};
