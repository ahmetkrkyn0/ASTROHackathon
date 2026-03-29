import { apiGet, isMockApiEnabled } from "./client";
import { resolveGridMetadata, resolveScenario } from "../../utils/mockMissionEngine";
import { validateGridMetadata } from "./validators";

const REGION_ALIASES = Object.freeze({
  south_pole_demo: "south_pole_demo_sector",
});

function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

function withLatency(data, latencyMs = 70) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(clone(data)), latencyMs);
  });
}

function resolveScenarioForRegion(region, scenarioId) {
  if (scenarioId) {
    return resolveScenario(scenarioId);
  }

  const requestedRegion = REGION_ALIASES[region] ?? region;
  const fallbackScenario = resolveScenario();

  if (!requestedRegion || fallbackScenario.grid_region === requestedRegion) {
    return fallbackScenario;
  }

  return fallbackScenario;
}

export async function getLayers(payload = {}) {
  if (!isMockApiEnabled()) {
    return validateGridMetadata(await apiGet("/layers", {
      query: {
        region: payload.region,
      },
    }));
  }

  const scenario = resolveScenarioForRegion(payload.region, payload.scenarioId);
  return withLatency(validateGridMetadata(resolveGridMetadata(scenario.scenario_id)));
}

export default {
  getLayers,
};
