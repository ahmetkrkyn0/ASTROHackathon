import { useCallback, useEffect, useRef, useState } from "react";
import missionService from "../services/missionService";

export function useMissionPlannerState({
  initialMetadata,
  initialWeights,
  initialStartCoord,
  initialGoalCoord,
  gridToSvg,
  svgToGrid,
  toUiWeights,
  toPlanningWeights,
} = {}) {
  const [weights, setWeights] = useState(initialWeights);
  const [scenarios, setScenarios] = useState([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [selectedLayerId, setSelectedLayerId] = useState("thermal_risk");
  const [overlayOpacity, setOverlayOpacity] = useState(82);
  const [showGridOverlay, setShowGridOverlay] = useState(true);
  const [showRouteOverlay, setShowRouteOverlay] = useState(true);
  const [distanceUnit, setDistanceUnit] = useState("km");
  const [scenarioInfo, setScenarioInfo] = useState(null);
  const [runtimeMetadata, setRuntimeMetadata] = useState(initialMetadata);
  const [pathResult, setPathResult] = useState(null);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [serviceReplanResult, setServiceReplanResult] = useState(null);
  const [planningBusy, setPlanningBusy] = useState(true);
  const [panelError, setPanelError] = useState("");
  const [startCoord, setStartCoord] = useState(initialStartCoord);
  const [goalCoord, setGoalCoord] = useState(initialGoalCoord);
  const [replanning, setReplanning] = useState(false);
  const [replanned, setReplanned] = useState(false);
  const [replanStatus, setReplanStatus] = useState("OPTIMIZED");

  const initializedRef = useRef(false);
  const requestRef = useRef(0);

  const applySnapshotToUi = useCallback((snapshot) => {
    setScenarioInfo(snapshot.scenario);
    setSelectedScenarioId(snapshot.scenario.scenario_id);
    setRuntimeMetadata(snapshot.layers_metadata);
    setPathResult(snapshot.path_result);
    setComparisonResult(snapshot.comparison_result);
    setServiceReplanResult(snapshot.replan_result);
    setSelectedLayerId(snapshot.scenario.default_layer_id ?? snapshot.layers_metadata.layers?.[0]?.id ?? "thermal_risk");
    setOverlayOpacity(Math.round((snapshot.layers_metadata.overlay_opacity_default ?? 0.82) * 100));
    setStartCoord(gridToSvg(snapshot.scenario.start_grid, snapshot.layers_metadata));
    setGoalCoord(gridToSvg(snapshot.scenario.goal_grid, snapshot.layers_metadata));
    setWeights(toUiWeights(snapshot.scenario.default_weights));
    setDistanceUnit(snapshot.layers_metadata.alternate_coordinate_units === "kilometers" ? "km" : "m");
    setReplanned(false);
    setReplanStatus("OPTIMIZED");
    setPanelError("");
  }, [gridToSvg, toUiWeights]);

  const refreshMissionData = useCallback(async ({
    resetReplan = true,
    nextWeights,
    nextStartCoord,
    nextGoalCoord,
  } = {}) => {
    if (!scenarioInfo?.scenario_id) return null;

    const requestId = requestRef.current + 1;
    requestRef.current = requestId;
    setPlanningBusy(true);

    try {
      const effectiveWeights = nextWeights ?? weights;
      const effectiveStartCoord = nextStartCoord ?? startCoord;
      const effectiveGoalCoord = nextGoalCoord ?? goalCoord;
      const planningWeights = toPlanningWeights(effectiveWeights);
      const startGrid = svgToGrid(effectiveStartCoord, runtimeMetadata);
      const goalGrid = svgToGrid(effectiveGoalCoord, runtimeMetadata);

      const [nextPathResult, nextComparisonResult] = await Promise.all([
        missionService.getPathResult({
          scenarioId: scenarioInfo.scenario_id,
          start: startGrid,
          goal: goalGrid,
          weights: planningWeights,
        }),
        missionService.getComparisonResult({
          scenarioId: scenarioInfo.scenario_id,
          start: startGrid,
          goal: goalGrid,
          weights: planningWeights,
        }),
      ]);

      if (requestRef.current !== requestId) return null;

      setPathResult(nextPathResult);
      setComparisonResult(nextComparisonResult);
      setPanelError("");

      if (resetReplan) {
        setReplanned(false);
        setServiceReplanResult(null);
        setReplanStatus("OPTIMIZED");
      }

      return {
        pathResult: nextPathResult,
        comparisonResult: nextComparisonResult,
      };
    } catch (error) {
      if (requestRef.current !== requestId) return null;
      setPanelError(error instanceof Error ? error.message : "Mission data could not be synchronized.");
      return null;
    } finally {
      if (requestRef.current === requestId) {
        setPlanningBusy(false);
      }
    }
  }, [goalCoord, runtimeMetadata, scenarioInfo?.scenario_id, startCoord, svgToGrid, toPlanningWeights, weights]);

  useEffect(() => {
    let cancelled = false;

    async function bootstrapMission() {
      try {
        setPlanningBusy(true);
        const [scenarioList, snapshot] = await Promise.all([
          missionService.getScenarios(),
          missionService.getMissionControlSnapshot(),
        ]);

        if (cancelled) return;

        setScenarios(scenarioList);
        applySnapshotToUi(snapshot);
        initializedRef.current = true;
      } catch (error) {
        if (!cancelled) {
          setPanelError(error instanceof Error ? error.message : "Mission snapshot could not be loaded.");
        }
      } finally {
        if (!cancelled) {
          setPlanningBusy(false);
        }
      }
    }

    bootstrapMission();

    return () => {
      cancelled = true;
    };
  }, [applySnapshotToUi]);

  useEffect(() => {
    if (!initializedRef.current || !scenarioInfo?.scenario_id) return undefined;

    const timer = setTimeout(() => {
      refreshMissionData();
    }, 180);

    return () => clearTimeout(timer);
  }, [goalCoord, refreshMissionData, scenarioInfo?.scenario_id, startCoord, weights]);

  const applyScenarioSelection = useCallback(async (nextScenarioId) => {
    if (!nextScenarioId || nextScenarioId === selectedScenarioId) {
      return false;
    }

    setSelectedScenarioId(nextScenarioId);
    setPlanningBusy(true);

    try {
      const snapshot = await missionService.applyScenario(nextScenarioId);
      applySnapshotToUi(snapshot);
      return true;
    } catch (error) {
      setPanelError(error instanceof Error ? error.message : "Scenario could not be applied.");
      return false;
    } finally {
      setPlanningBusy(false);
    }
  }, [applySnapshotToUi, selectedScenarioId]);

  const compareRoutes = useCallback(async () => {
    setPlanningBusy(true);

    try {
      const planningWeights = toPlanningWeights(weights);
      const nextComparisonResult = await missionService.getComparisonResult({
        scenarioId: selectedScenarioId || scenarioInfo?.scenario_id,
        start: svgToGrid(startCoord, runtimeMetadata),
        goal: svgToGrid(goalCoord, runtimeMetadata),
        weights: planningWeights,
      });

      setComparisonResult(nextComparisonResult);
      setPanelError("");
      return nextComparisonResult;
    } catch (error) {
      setPanelError(error instanceof Error ? error.message : "Comparison could not be computed.");
      return null;
    } finally {
      setPlanningBusy(false);
    }
  }, [goalCoord, runtimeMetadata, scenarioInfo?.scenario_id, selectedScenarioId, startCoord, svgToGrid, toPlanningWeights, weights]);

  const triggerReplan = useCallback(async ({ triggerType, triggerLocationGrid } = {}) => {
    if (replanning || !scenarioInfo?.scenario_id) return null;

    setReplanning(true);
    setReplanStatus("REPLANNING...");

    try {
      const planningWeights = toPlanningWeights(weights);
      const nextReplanResult = await missionService.getReplanResult({
        scenarioId: scenarioInfo.scenario_id,
        start: svgToGrid(startCoord, runtimeMetadata),
        goal: svgToGrid(goalCoord, runtimeMetadata),
        weights: planningWeights,
        currentPath: comparisonResult?.safe_path ?? pathResult,
        triggerType,
        triggerLocation: triggerLocationGrid,
      });

      setServiceReplanResult(nextReplanResult);
      setReplanned(true);
      setReplanStatus("OPTIMIZED");
      setPanelError("");
      return nextReplanResult;
    } catch (error) {
      setPanelError(error instanceof Error ? error.message : "Replan could not be computed.");
      setReplanStatus("REVIEW");
      return null;
    } finally {
      setReplanning(false);
    }
  }, [comparisonResult?.safe_path, goalCoord, pathResult, replanning, runtimeMetadata, scenarioInfo?.scenario_id, startCoord, svgToGrid, toPlanningWeights, weights]);

  return {
    weights,
    setWeights,
    scenarios,
    selectedScenarioId,
    selectedLayerId,
    setSelectedLayerId,
    overlayOpacity,
    setOverlayOpacity,
    showGridOverlay,
    setShowGridOverlay,
    showRouteOverlay,
    setShowRouteOverlay,
    distanceUnit,
    setDistanceUnit,
    scenarioInfo,
    runtimeMetadata,
    pathResult,
    comparisonResult,
    serviceReplanResult,
    planningBusy,
    panelError,
    startCoord,
    setStartCoord,
    goalCoord,
    setGoalCoord,
    replanning,
    replanned,
    replanStatus,
    refreshMissionData,
    applyScenarioSelection,
    compareRoutes,
    triggerReplan,
  };
}

export default useMissionPlannerState;
