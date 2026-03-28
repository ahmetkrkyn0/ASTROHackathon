import { useCallback, useEffect, useState } from "react";
import { createWeights } from "../models/missionModels";
import missionService from "../services/missionService";
import useMapLayers from "./useMapLayers";
import useScenarioState from "./useScenarioState";

export function useMissionControl(initialScenarioId = null) {
  const scenarioState = useScenarioState(initialScenarioId);
  const activeScenario = scenarioState.activeScenario;
  const mapLayers = useMapLayers({
    region: activeScenario?.grid_region,
    scenarioId: scenarioState.scenarioId,
  });

  const [weights, setWeights] = useState(createWeights());
  const [start, setStart] = useState(null);
  const [goal, setGoal] = useState(null);
  const [pathResult, setPathResult] = useState(null);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [replanResult, setReplanResult] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!activeScenario) return;

    setWeights(createWeights(activeScenario.default_weights));
    setStart(activeScenario.start_grid);
    setGoal(activeScenario.goal_grid);
  }, [activeScenario]);

  const refreshSnapshot = useCallback(async (overrides = {}) => {
    if (!scenarioState.scenarioId) return null;

    const payload = {
      scenarioId: scenarioState.scenarioId,
      start: overrides.start ?? start ?? activeScenario?.start_grid,
      goal: overrides.goal ?? goal ?? activeScenario?.goal_grid,
      weights: createWeights({
        ...(activeScenario?.default_weights ?? {}),
        ...(overrides.weights ?? weights),
      }),
      currentPath: overrides.currentPath ?? null,
      triggerType: overrides.triggerType,
      triggerLocation: overrides.triggerLocation,
    };

    setLoading(true);

    try {
      const nextSnapshot = await missionService.getMissionControlSnapshot(payload);
      setSnapshot(nextSnapshot);
      setPathResult(nextSnapshot.path_result);
      setComparisonResult(nextSnapshot.comparison_result);
      setReplanResult(nextSnapshot.replan_result);
      setError("");
      return nextSnapshot;
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Mission control data could not be refreshed.");
      return null;
    } finally {
      setLoading(false);
    }
  }, [activeScenario, goal, scenarioState.scenarioId, start, weights]);

  useEffect(() => {
    if (!activeScenario) return;

    refreshSnapshot({
      start: activeScenario.start_grid,
      goal: activeScenario.goal_grid,
      weights: activeScenario.default_weights,
      currentPath: null,
    });
  }, [activeScenario, refreshSnapshot]);

  const updateWeights = useCallback(async (nextWeights, { autoPlan = true } = {}) => {
    const mergedWeights = createWeights({
      ...(activeScenario?.default_weights ?? {}),
      ...nextWeights,
    });
    setWeights(mergedWeights);

    if (!autoPlan) {
      return null;
    }

    return refreshSnapshot({
      weights: mergedWeights,
      currentPath: null,
    });
  }, [activeScenario, refreshSnapshot]);

  const planRoute = useCallback(async (overrides = {}) => {
    const result = await missionService.planRoute({
      scenarioId: scenarioState.scenarioId,
      start: overrides.start ?? start ?? activeScenario?.start_grid,
      goal: overrides.goal ?? goal ?? activeScenario?.goal_grid,
      weights: overrides.weights ?? weights,
    });

    setPathResult(result);
    return result;
  }, [activeScenario, goal, scenarioState.scenarioId, start, weights]);

  const compareRoutes = useCallback(async (overrides = {}) => {
    const result = await missionService.compareRoutes({
      scenarioId: scenarioState.scenarioId,
      start: overrides.start ?? start ?? activeScenario?.start_grid,
      goal: overrides.goal ?? goal ?? activeScenario?.goal_grid,
      weights: overrides.weights ?? weights,
    });

    setComparisonResult(result);
    return result;
  }, [activeScenario, goal, scenarioState.scenarioId, start, weights]);

  const triggerReplan = useCallback(async ({
    triggerType = "thermal_spike",
    triggerLocation = null,
    currentPath = pathResult,
  } = {}) => {
    const result = await missionService.replanRoute({
      scenarioId: scenarioState.scenarioId,
      start: start ?? activeScenario?.start_grid,
      goal: goal ?? activeScenario?.goal_grid,
      weights,
      currentPath,
      triggerType,
      triggerLocation,
    });

    setReplanResult(result);
    return result;
  }, [activeScenario, goal, pathResult, scenarioState.scenarioId, start, weights]);

  return {
    ...scenarioState,
    mapLayers,
    weights,
    setWeights,
    updateWeights,
    start,
    setStart,
    goal,
    setGoal,
    pathResult,
    comparisonResult,
    replanResult,
    snapshot,
    loading: loading || scenarioState.loading || mapLayers.loading,
    error: error || scenarioState.error || mapLayers.error,
    refreshSnapshot,
    planRoute,
    compareRoutes,
    triggerReplan,
  };
}

export default useMissionControl;
