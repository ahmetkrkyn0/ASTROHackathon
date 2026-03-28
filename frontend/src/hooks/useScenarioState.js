import { useCallback, useEffect, useState } from "react";
import missionService from "../services/missionService";

export function useScenarioState(initialScenarioId = null) {
  const [scenarios, setScenarios] = useState([]);
  const [scenarioId, setScenarioId] = useState(initialScenarioId);
  const [activeScenario, setActiveScenario] = useState(null);
  const [appliedSnapshot, setAppliedSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadScenarios() {
      try {
        setLoading(true);
        const scenarioList = await missionService.getScenarios();
        if (cancelled) return;

        setScenarios(scenarioList);

        if (!scenarioId && scenarioList[0]) {
          setScenarioId(scenarioList[0].scenario_id);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Scenario list could not be loaded.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadScenarios();

    return () => {
      cancelled = true;
    };
  }, [initialScenarioId]);

  useEffect(() => {
    if (!scenarioId) return undefined;

    let cancelled = false;

    async function syncScenario() {
      try {
        setLoading(true);
        const [scenario, snapshot] = await Promise.all([
          missionService.getScenarioById(scenarioId),
          missionService.applyScenario(scenarioId),
        ]);

        if (cancelled) return;

        setActiveScenario(scenario);
        setAppliedSnapshot(snapshot);
        setError("");
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Scenario state could not be synchronized.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    syncScenario();

    return () => {
      cancelled = true;
    };
  }, [scenarioId]);

  const applyScenario = useCallback(async (nextScenarioId) => {
    const snapshot = await missionService.applyScenario(nextScenarioId);
    setScenarioId(nextScenarioId);
    setAppliedSnapshot(snapshot);
    return snapshot;
  }, []);

  return {
    scenarios,
    scenarioId,
    setScenarioId,
    activeScenario,
    appliedSnapshot,
    loading,
    error,
    applyScenario,
  };
}

export default useScenarioState;
