import { useEffect, useState } from "react";
import ComparisonView from "../components/comparison/ComparisonView";
import ControlPanel from "../components/control/ControlPanel";
import EventLog from "../components/log/EventLog";
import PageShell from "../components/layout/PageShell";
import TopBar from "../components/layout/TopBar";
import MapView from "../components/map/MapView";
import MetricsPanel from "../components/metrics/MetricsPanel";
import ScenarioSelector from "../components/scenario/ScenarioSelector";
import { DEFAULT_WEIGHTS } from "../models/missionModels";
import missionService from "../services/missionService";

export default function MissionControlPage() {
  const [scenarios, setScenarios] = useState([]);
  const [activeScenarioId, setActiveScenarioId] = useState("");
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [selectedLayer, setSelectedLayer] = useState("thermal_risk");
  const [pathResult, setPathResult] = useState(null);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [replanResult, setReplanResult] = useState(null);
  const [layersMetadata, setLayersMetadata] = useState(null);

  useEffect(() => {
    async function loadInitialState() {
      const scenarioList = await missionService.getScenarios();
      const firstScenario = scenarioList[0];

      setScenarios(scenarioList);
      setActiveScenarioId(firstScenario.scenario_id);
      setWeights(firstScenario.default_weights);
      setSelectedLayer(firstScenario.default_layer_id);

      const snapshot = await missionService.getMissionControlSnapshot({
        scenarioId: firstScenario.scenario_id,
        weights: firstScenario.default_weights,
      });

      setPathResult(snapshot.path_result);
      setComparisonResult(snapshot.comparison_result);
      setReplanResult(snapshot.replan_result);
      setLayersMetadata(snapshot.layers_metadata);
    }

    loadInitialState();
  }, []);

  const activeScenario = scenarios.find((scenario) => scenario.scenario_id === activeScenarioId) ?? null;

  async function applyScenario(scenarioId) {
    const nextScenario = await missionService.getScenarioById(scenarioId);
    const snapshot = await missionService.getMissionControlSnapshot({
      scenarioId,
      weights: nextScenario.default_weights,
    });

    setActiveScenarioId(scenarioId);
    setWeights(nextScenario.default_weights);
    setSelectedLayer(nextScenario.default_layer_id);
    setPathResult(snapshot.path_result);
    setComparisonResult(snapshot.comparison_result);
    setReplanResult(snapshot.replan_result);
    setLayersMetadata(snapshot.layers_metadata);
  }

  async function applyWeights() {
    const snapshot = await missionService.getMissionControlSnapshot({
      scenarioId: activeScenarioId,
      weights,
    });

    setPathResult(snapshot.path_result);
    setComparisonResult(snapshot.comparison_result);
    setReplanResult(snapshot.replan_result);
  }

  async function previewReplan() {
    const nextReplan = await missionService.getReplanResult({ scenarioId: activeScenarioId });
    setReplanResult(nextReplan);
  }

  function handleWeightChange(key, value) {
    setWeights((current) => ({
      ...current,
      [key]: value,
    }));
  }

  if (!activeScenario || !pathResult || !comparisonResult || !replanResult || !layersMetadata) {
    return (
      <PageShell
        topBar={
          <TopBar
            title="Mission Control Panel"
            subtitle="Preparing LunaPath mock data foundation."
            scenarioName="Loading"
          />
        }
      >
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
          Loading mock mission data...
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell
      topBar={
        <TopBar
          title="Mission Control Panel"
          subtitle="Phase 1 foundation with modular placeholders and mock mission data."
          scenarioName={activeScenario.name}
        />
      }
    >
      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-6">
          <ScenarioSelector
            scenarios={scenarios}
            activeScenarioId={activeScenarioId}
            onSelect={applyScenario}
          />
          <ControlPanel
            weights={weights}
            selectedLayer={selectedLayer}
            layerOptions={layersMetadata.layers}
            onWeightChange={handleWeightChange}
            onLayerChange={setSelectedLayer}
            onApplyWeights={applyWeights}
            onPreviewReplan={previewReplan}
          />
          <EventLog events={replanResult.event_log} />
        </div>

        <div className="space-y-6">
          <MapView
            gridMetadata={layersMetadata}
            selectedLayer={selectedLayer}
            pathResult={pathResult}
            comparisonResult={comparisonResult}
            replanResult={replanResult}
          />
          <div className="grid gap-6 xl:grid-cols-2">
            <MetricsPanel pathResult={pathResult} comparisonResult={comparisonResult} />
            <ComparisonView comparisonResult={comparisonResult} />
          </div>
        </div>
      </div>
    </PageShell>
  );
}
