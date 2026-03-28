import { useState, useRef, useEffect, useCallback } from "react";
import useMissionPlannerState from "../hooks/useMissionPlannerState";
import layersMetadataMock from "../mocks/layers.mock";

// ─── Tool config ─────────────────────────────────────────────────────────────
const TOOLS = [
  { id: "start",   icon: "flag",       label: "Start",   desc: "Click to set Start location" },
  { id: "goal",    icon: "sports_score", label: "Goal",  desc: "Click to set Goal location" },
  { id: "thermal", icon: "thermostat", label: "Thermal", desc: "Click to place thermal hazard zone" },
  { id: "crater",  icon: "terrain",    label: "Slope",   desc: "Click to place crater" },
  { id: "shadow",  icon: "layers",     label: "Shadow",  desc: "Click to place PSR shadow region" },
];

const MAP_METADATA = layersMetadataMock;
const VIEWBOX_SIZE = 1000;
const STATIC_THERMAL_FIELDS = [
  { x: 450, y: 500, baseRadius: 132, intensity: 1.0 },
  { x: 550, y: 450, baseRadius: 92, intensity: 0.72 },
];

function lerp(start, end, factor) {
  return start + ((end - start) * factor);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function gridToSvg([row, col], metadata = MAP_METADATA) {
  const rowMax = Math.max(1, metadata.shape[0] - 1);
  const colMax = Math.max(1, metadata.shape[1] - 1);

  return {
    x: (col / colMax) * VIEWBOX_SIZE,
    y: (row / rowMax) * VIEWBOX_SIZE,
  };
}

function svgToGrid(point, metadata = MAP_METADATA) {
  const rowMax = Math.max(1, metadata.shape[0] - 1);
  const colMax = Math.max(1, metadata.shape[1] - 1);

  return [
    clamp(Math.round((point.y / VIEWBOX_SIZE) * rowMax), 0, rowMax),
    clamp(Math.round((point.x / VIEWBOX_SIZE) * colMax), 0, colMax),
  ];
}

function gridToProjected([row, col], metadata = MAP_METADATA) {
  return {
    x: metadata.origin_m.x + (col * metadata.resolution_m),
    y: metadata.origin_m.y + (row * metadata.resolution_m),
  };
}

function formatDistanceLabel(valueM, unit) {
  if (unit === "km") {
    return `${(valueM / 1000).toFixed(valueM % 10000 === 0 ? 0 : 1)} km`;
  }

  return `${Math.round(valueM).toLocaleString()} m`;
}

function toPlanningWeights(uiWeights) {
  return {
    w_dist: Number((uiWeights.distance / 50).toFixed(2)),
    w_slope: Number((uiWeights.slope / 50).toFixed(2)),
    w_thermal: Number((uiWeights.thermal / 50).toFixed(2)),
    w_energy: Number((uiWeights.energy / 50).toFixed(2)),
  };
}

function toUiWeights(planningWeights) {
  return {
    distance: Math.round(clamp((planningWeights.w_dist ?? 1) * 50, 0, 100)),
    thermal: Math.round(clamp((planningWeights.w_thermal ?? 1.6) * 50, 0, 100)),
    slope: Math.round(clamp((planningWeights.w_slope ?? 1.1) * 50, 0, 100)),
    energy: Math.round(clamp((planningWeights.w_energy ?? 1.2) * 50, 0, 100)),
  };
}

function createDisplayMetrics(pathResult) {
  if (!pathResult) return null;

  return {
    distanceM: pathResult.total_distance_m,
    thermalExposure: pathResult.total_thermal_exposure,
    maxSlope: pathResult.max_slope_deg,
    compute: pathResult.computation_time_ms,
    energyCost: pathResult.total_energy_cost,
    riskBreakdown: {
      safeCells: pathResult.risk_breakdown?.safe_cells ?? 0,
      cautionCells: pathResult.risk_breakdown?.caution_cells ?? 0,
      dangerCells: pathResult.risk_breakdown?.danger_cells ?? 0,
    },
  };
}

function getPercentReduction(baseline, current) {
  if (!baseline) return 0;
  return Number((((baseline - current) / baseline) * 100).toFixed(1));
}

function getPercentDelta(current, baseline) {
  if (!baseline) return 0;
  return Number((((current - baseline) / baseline) * 100).toFixed(1));
}

const PANEL_MONO_STYLE = {
  fontFamily: "'JetBrains Mono', 'IBM Plex Mono', 'Fira Code', 'SFMono-Regular', Consolas, monospace",
};

const EMPTY_DISPLAY_METRICS = Object.freeze({
  distanceM: 0,
  thermalExposure: 0,
  maxSlope: 0,
  compute: 0,
  energyCost: 0,
  riskBreakdown: {
    safeCells: 0,
    cautionCells: 0,
    dangerCells: 0,
  },
});

const LAYER_VISUALS = Object.freeze({
  elevation: {
    swatch: ["#58a6ff", "#3fb950", "#d29922", "#f8fafc"],
    badge: "terrain",
    chipTone: "border-sky-200 bg-sky-50 text-sky-700",
  },
  slope: {
    swatch: ["#111827", "#6b21a8", "#f97316", "#facc15"],
    badge: "magma",
    chipTone: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700",
  },
  thermal_risk: {
    swatch: ["#111827", "#f85149", "#ffb347", "#fff7d6"],
    badge: "hot",
    chipTone: "border-red-200 bg-red-50 text-red-700",
  },
  traversability: {
    swatch: ["#f85149", "#d29922", "#3fb950"],
    badge: "RdYlGn",
    chipTone: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  psr_mask: {
    swatch: ["#0f172a", "#64748b", "#cbd5e1", "#f8fafc"],
    badge: "bone",
    chipTone: "border-slate-200 bg-slate-100 text-slate-700",
  },
});

function getGradientCss(stops) {
  return `linear-gradient(90deg, ${stops.join(", ")})`;
}

function formatLayerRange(layer) {
  if (!layer?.value_range) return "Range unavailable";

  const [min, max] = layer.value_range;

  if (layer.unit === "m") {
    return `${Math.round(min).toLocaleString()} to ${Math.round(max).toLocaleString()} m`;
  }

  if (layer.unit === "deg") {
    return `${Number(min).toFixed(0)}° to ${Number(max).toFixed(0)}°`;
  }

  if (layer.unit === "boolean") {
    return `${min} to ${max} mask`;
  }

  return `${Number(min).toFixed(1)} to ${Number(max).toFixed(1)} ${layer.unit}`;
}

function formatProjectedMeters(value) {
  return `${Math.round(value).toLocaleString()} m`;
}

function formatProjectedKilometers(value) {
  return `${(value / 1000).toFixed(1)} km`;
}

export default function MissionControlPage() {
  // Pan/zoom
  const svgRef       = useRef(null);
  const isPanning    = useRef(false);
  const didMove      = useRef(false);
  const lastPos      = useRef({ x: 0, y: 0 });
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: 1000, h: 1000 });

  // Tooltip hover tracked to mouse position
  const [tooltipData, setTooltipData] = useState(null);

  // Active tool + placed elements
  const [activeTool,    setActiveTool]    = useState(null);
  const [thermalZones,  setThermalZones]  = useState([]);
  const [craters,       setCraters]       = useState([]);
  const [shadowRegions, setShadowRegions] = useState([]);

  const {
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
  } = useMissionPlannerState({
    initialMetadata: MAP_METADATA,
    initialWeights: { distance: 52, thermal: 80, slope: 55, energy: 60 },
    initialStartCoord: { x: 250, y: 850 },
    initialGoalCoord: { x: 750, y: 250 },
    gridToSvg,
    svgToGrid,
    toUiWeights,
    toPlanningWeights,
  });

  // Convert screen → SVG coordinates
  const screenToSVG = useCallback((clientX, clientY) => {
    const el = svgRef.current;
    if (!el) return { x: 500, y: 500 };
    const point = el.createSVGPoint();
    const ctm = el.getScreenCTM();

    if (!ctm) return { x: 500, y: 500 };

    point.x = clientX;
    point.y = clientY;

    const position = point.matrixTransform(ctm.inverse());
    return { x: position.x, y: position.y };
  }, []);

  // ─── Pan ────────────────────────────────────────────────────────────────
  const onMouseDown = useCallback((e) => {
    if (e.target.closest(".map-panel")) return;
    if (activeTool) {
      didMove.current = false;
      return;
    }
    isPanning.current = true;
    didMove.current   = false;
    lastPos.current   = { x: e.clientX, y: e.clientY };
  }, [activeTool]);

  const onMouseMove = useCallback((e) => {
    if (!isPanning.current) return;
    const dx = e.clientX - lastPos.current.x;
    const dy = e.clientY - lastPos.current.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) didMove.current = true;
    lastPos.current = { x: e.clientX, y: e.clientY };
    setViewBox((vb) => {
      const scale = vb.w / (svgRef.current?.clientWidth || 1000);
      return { ...vb, x: vb.x - dx * scale, y: vb.y - dy * scale };
    });
  }, []);

  const onMouseUp = useCallback(() => { isPanning.current = false; }, []);

  // ─── Zoom ───────────────────────────────────────────────────────────────
  const onWheel = useCallback((e) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 1.12 : 0.88;
    const zoomPoint = screenToSVG(e.clientX, e.clientY);
    setViewBox((vb) => {
      const nw = Math.min(Math.max(vb.w * factor, 200), 2000);
      const nh = Math.min(Math.max(vb.h * factor, 200), 2000);
      return {
        x: zoomPoint.x - ((zoomPoint.x - vb.x) * (nw / vb.w)),
        y: zoomPoint.y - ((zoomPoint.y - vb.y) * (nh / vb.h)),
        w: nw,
        h: nh,
      };
    });
  }, [screenToSVG]);

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [onWheel]);

  // ─── Map click → place element ──────────────────────────────────────────
  const onMapClick = useCallback((e) => {
    if (didMove.current || !activeTool) return;
    if (e.target.closest(".map-panel")) return;
    const pos = screenToSVG(e.clientX, e.clientY);
    
    if (activeTool === "start")   setStartCoord(pos);
    if (activeTool === "goal")    setGoalCoord(pos);
    if (activeTool === "thermal") setThermalZones ((p) => [...p, { ...pos, r: 80 + Math.random()*40, tempDelta: Math.floor(Math.random() * 80) + 10 }]);
    if (activeTool === "crater")  setCraters       ((p) => [...p, { ...pos, slope: Math.floor(Math.random() * 25) + 5, depth: Math.floor(Math.random() * 200) + 50 }]);
    if (activeTool === "shadow")  setShadowRegions ((p) => [...p, { ...pos, temp: -Math.floor(Math.random() * 50) - 150 }]);
  }, [activeTool, screenToSVG]);

  // ─── Dynamic Paths based on Start/Goal ────────────────────────────────
  const planningWeights = toPlanningWeights(weights);

  const handleScenarioChange = useCallback(async (event) => {
    const applied = await applyScenarioSelection(event.target.value);

    if (!applied) return;

    setThermalZones([]);
    setCraters([]);
    setShadowRegions([]);
    setActiveTool(null);
  }, [applyScenarioSelection]);

  const handlePlanRoute = useCallback(async () => {
    await refreshMissionData();
  }, [refreshMissionData]);

  const handleCompareRoutes = useCallback(async () => {
    await compareRoutes();
  }, [compareRoutes]);

  const midX = (startCoord.x + goalCoord.x) / 2;
  const midY = (startCoord.y + goalCoord.y) / 2;
  const thermalOffset = 56 + (planningWeights.w_thermal * 42);
  const slopeOffset = 16 + (planningWeights.w_slope * 18);
  const safeControlPoint = {
    x: midX + thermalOffset - (planningWeights.w_slope * 14),
    y: midY + thermalOffset - slopeOffset,
  };
  const replannedControlPoint = {
    x: midX - (210 + (planningWeights.w_thermal * 18)),
    y: midY - (108 + (planningWeights.w_slope * 18)),
  };
  const sectorNode = {
    x: lerp(startCoord.x, goalCoord.x, 0.56),
    y: lerp(startCoord.y, goalCoord.y, 0.56),
  };
  const safePath = `M ${startCoord.x} ${startCoord.y} Q ${safeControlPoint.x} ${safeControlPoint.y} ${goalCoord.x} ${goalCoord.y}`;
  const highRiskPath = `M ${startCoord.x} ${startCoord.y} L ${goalCoord.x} ${goalCoord.y}`;
  const replannedPath = `M ${startCoord.x} ${startCoord.y} Q ${replannedControlPoint.x} ${replannedControlPoint.y} ${goalCoord.x} ${goalCoord.y}`;
  const safePathMetrics = createDisplayMetrics(comparisonResult?.safe_path ?? pathResult) ?? EMPTY_DISPLAY_METRICS;
  const shortestPathMetrics = createDisplayMetrics(comparisonResult?.shortest_path) ?? EMPTY_DISPLAY_METRICS;
  const replannedPathMetrics = createDisplayMetrics(serviceReplanResult?.replanned_path) ?? safePathMetrics;
  const activeMetrics = replanned && serviceReplanResult?.replanned_path ? replannedPathMetrics : safePathMetrics;
  const distanceKm = Number((activeMetrics.distanceM / 1000).toFixed(1));
  const distanceDeltaPct = comparisonResult?.delta?.distance_overhead_pct ?? 0;
  const activeThermalReductionPct = replanned && serviceReplanResult?.replanned_path
    ? getPercentReduction(shortestPathMetrics.thermalExposure, activeMetrics.thermalExposure)
    : comparisonResult?.delta?.thermal_reduction_pct ?? 0;
  const activeEnergyDeltaPct = replanned
    ? getPercentDelta(replannedPathMetrics.energyCost, shortestPathMetrics.energyCost)
    : comparisonResult?.delta?.energy_delta_pct ?? 0;
  const confidencePct = Number(clamp(
    88.4
      + Math.min(10, activeThermalReductionPct * 0.12)
      - ((activeMetrics.riskBreakdown?.dangerCells ?? 0) * 0.15)
      + (replanned ? 1.8 : 0),
    74,
    99.6,
  ).toFixed(1));
  const safePathRecommended = comparisonResult?.delta?.recommendation === "safe_path_preferred";
  const triggerTypeLabel = (serviceReplanResult?.trigger_type ?? "thermal_spike").replaceAll("_", " ").toUpperCase();

  // ─── Replan ─────────────────────────────────────────────────────────────
  const handleReplan = useCallback(async () => {
    const latestThermal = thermalZones[thermalZones.length - 1];
    const triggerPoint = latestThermal ?? sectorNode;
    const triggerType = thermalZones.length
      ? "thermal_spike"
      : craters.length
        ? "new_obstacle"
        : shadowRegions.length
          ? "energy_budget"
          : "thermal_spike";

    await triggerReplan({
      triggerType,
      triggerLocationGrid: svgToGrid(triggerPoint, runtimeMetadata),
    });
  }, [craters.length, runtimeMetadata, sectorNode, shadowRegions.length, thermalZones, triggerReplan]);

  // ─── Derived visuals ─────────────────────────────────────────────────────
  const routeW   = (2 + (weights.thermal / 100) * 2).toFixed(1);
  const routeOp  = (((0.5 + (weights.thermal / 100) * 0.5) * (overlayOpacity / 100))).toFixed(2);
  const cursor   = activeTool ? "crosshair" : "grab";
  const vbStr    = `${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`;
  const comparisonDelta = comparisonResult?.delta;
  const eventEntries = serviceReplanResult?.event_log ?? [];
  const displayDistanceValue = distanceUnit === "m"
    ? Math.round(activeMetrics.distanceM).toLocaleString()
    : distanceKm.toFixed(1);
  const displayDistanceUnit = distanceUnit;
  const activeLayer = runtimeMetadata.layers?.find((layer) => layer.id === selectedLayerId) ?? runtimeMetadata.layers?.[0];
  const activeLayerLabel = activeLayer?.label ?? "Thermal Risk";
  const activeLayerVisual = LAYER_VISUALS[activeLayer?.id] ?? LAYER_VISUALS.thermal_risk;
  const activeLayerRangeLabel = formatLayerRange(activeLayer);
  const startGridCoord = svgToGrid(startCoord, runtimeMetadata);
  const goalGridCoord = svgToGrid(goalCoord, runtimeMetadata);
  const startProjected = gridToProjected(startGridCoord, runtimeMetadata);
  const goalProjected = gridToProjected(goalGridCoord, runtimeMetadata);
  const axisTicks = Array.from({ length: 5 }, (_, index) => (
    (runtimeMetadata.extent_m.width / 4) * index
  ));
  const layerOverlayOpacity = Number(clamp((overlayOpacity / 100) * 0.76, 0.18, 0.92).toFixed(2));
  const mapExtentLabel = `${(runtimeMetadata.extent_m.width / 1000).toFixed(0)} km x ${(runtimeMetadata.extent_m.height / 1000).toFixed(0)} km`;
  const resolutionLabel = `${runtimeMetadata.resolution_m} m/cell`;
  const secondaryDistanceLabel = distanceUnit === "km"
    ? `${Math.round(activeMetrics.distanceM).toLocaleString()} m`
    : `${(activeMetrics.distanceM / 1000).toFixed(1)} km`;
  const routeStrategyLabel = replanned
    ? "replanned corridor"
    : safePathRecommended
      ? "safe corridor"
      : "shortest viable";
  const maxSlopeDelta = Number((activeMetrics.maxSlope - shortestPathMetrics.maxSlope).toFixed(1));
  const computeDelta = activeMetrics.compute - shortestPathMetrics.compute;
  const bottomMetricCards = [
    {
      label: "Distance",
      value: displayDistanceValue,
      unit: displayDistanceUnit,
      secondary: secondaryDistanceLabel,
      delta: `${distanceDeltaPct >= 0 ? "+" : ""}${distanceDeltaPct.toFixed(1)}% vs shortest`,
      deltaTone: distanceDeltaPct > 0 ? "text-amber-600" : "text-emerald-600",
    },
    {
      label: "Thermal Exposure",
      value: activeMetrics.thermalExposure.toFixed(1),
      unit: "score",
      secondary: `Shortest ${shortestPathMetrics.thermalExposure.toFixed(1)}`,
      delta: `-${Math.abs(activeThermalReductionPct).toFixed(1)}% safer`,
      deltaTone: "text-emerald-600",
    },
    {
      label: "Max Slope",
      value: activeMetrics.maxSlope.toFixed(1),
      unit: "°",
      secondary: `Shortest ${shortestPathMetrics.maxSlope.toFixed(1)}°`,
      delta: `${maxSlopeDelta >= 0 ? "+" : ""}${maxSlopeDelta.toFixed(1)}° corridor delta`,
      deltaTone: maxSlopeDelta <= 0 ? "text-emerald-600" : "text-amber-600",
    },
    {
      label: "Compute Time",
      value: activeMetrics.compute,
      unit: "ms",
      secondary: routeStrategyLabel,
      delta: `${computeDelta >= 0 ? "+" : ""}${computeDelta} ms vs shortest`,
      deltaTone: computeDelta <= 0 ? "text-emerald-600" : "text-sky-600",
    },
  ];
  const staticPsrOpacity = selectedLayerId === "psr_mask" ? 0.95 : 0.58;
  const staticThermalPrimaryOpacity = selectedLayerId === "thermal_risk"
    ? 0.42 + (weights.thermal / 100) * 0.28
    : 0.22 + (weights.thermal / 100) * 0.14;
  const staticThermalSecondaryOpacity = selectedLayerId === "thermal_risk"
    ? 0.3 + (weights.thermal / 100) * 0.2
    : 0.16 + (weights.thermal / 100) * 0.1;

  // Toggle tool (second click = deactivate)
  const toggleTool = (id) => setActiveTool((curr) => curr === id ? null : id);

  return (
    <div className="bg-slate-50 text-slate-900 overflow-hidden select-none" style={{ height: "100vh", width: "100vw" }}>

      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <header className="fixed top-0 left-0 right-0 h-16 bg-white/80 backdrop-blur-md border-b border-slate-200 z-50 px-6 flex items-center justify-between">
        <div className="flex items-center gap-10">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-slate-900 rounded-lg flex items-center justify-center">
              <span className="material-symbols-outlined text-white text-xl">navigation</span>
            </div>
            <h1 className="text-sm font-bold tracking-tight uppercase">
              LunaPath <span className="font-normal opacity-50">Mission Control</span>
            </h1>
          </div>
          <nav className="hidden lg:flex gap-1 items-center">
            <a className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-900 transition-colors" href="#">Telemetry</a>
            <a className="px-4 py-2 text-xs font-bold text-slate-900 bg-slate-100 rounded-full" href="#">Route Planner</a>
            <a className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-900 transition-colors" href="#">Surface Ops</a>
            <a className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-900 transition-colors" href="#">Archive</a>
          </nav>
        </div>
        <div className="flex items-center gap-6">
          <div className="h-10 flex flex-col justify-center items-end border-r border-slate-200 pr-6">
            <span className="text-[0.6rem] font-bold uppercase tracking-widest text-slate-400">Active Scenario</span>
            <span className="text-xs font-bold">{runtimeMetadata.region_name ?? "Shackleton Crater - South Rim"}</span>
          </div>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-2 px-3 py-1.5 text-[0.65rem] font-bold rounded-md border ${replanning || planningBusy ? "bg-emerald-50 text-emerald-700 border-emerald-100" : "bg-slate-100 text-slate-600 border-slate-200"}`}>
              <span className="relative flex h-2 w-2">
                {(replanning || planningBusy) && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />}
                <span className={`relative inline-flex rounded-full h-2 w-2 ${replanning || planningBusy ? "bg-emerald-500" : "bg-slate-400"}`} />
              </span>
              {replanning ? "REPLANNING: ACTIVE" : planningBusy ? "MODEL: SYNCING" : "MODEL: READY"}
            </div>
            <button className="p-2 hover:bg-slate-100 rounded-lg text-slate-500 transition-colors">
              <span className="material-symbols-outlined text-lg">settings</span>
            </button>
            <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 overflow-hidden">
              <img alt="Commander" src="https://lh3.googleusercontent.com/aida-public/AB6AXuC9g198cssrJ-P3H6YFAjzymWu8m0OldNqRnKPx1A-6vAKL38-9NkQkMOH3N5Qwtuid-VP1OUan4esLfR4HGsHMsAfyB8zS-gT6LeN-ryJbBfWDk6aFDjJCouDa7uj9J86WrFxyvA60DTfYgeov8lwCh-rKBGAp0RdI2op6RbfOiG8jEKcSbGLf_u_er2CZG8__umXx_GC18xq0LaHmxADKuANWdEirBC5uz-fZB0qjpVEWHo-nqxFNL991cajZLhrZDB07hHXSZOAc" />
            </div>
          </div>
        </div>
      </header>

      {/* ── Main canvas ──────────────────────────────────────────────────── */}
      <main
        className="relative w-screen h-screen pt-16 bg-slate-100 overflow-hidden"
        style={{ cursor }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        onClick={onMapClick}
      >
        <div className="absolute inset-0 map-background">
          <div className="absolute inset-0 topo-shading" />

          {/* ── Active tool hint banner ────────────────────────────────── */}
          {activeTool && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 px-4 py-2 bg-slate-900/90 text-white text-xs font-bold rounded-full backdrop-blur-sm shadow-lg flex items-center gap-2">
              <span className="material-symbols-outlined text-sm">
                {TOOLS.find(t => t.id === activeTool)?.icon}
              </span>
              {TOOLS.find(t => t.id === activeTool)?.desc}
              <button
                onClick={(e) => { e.stopPropagation(); setActiveTool(null); }}
                className="ml-2 w-4 h-4 bg-white/20 rounded-full text-[0.6rem] flex items-center justify-center hover:bg-white/30"
              >✕</button>
            </div>
          )}

          {/* ── SVG map ───────────────────────────────────────────────── */}
          <svg
            ref={svgRef}
            className="absolute inset-0 w-full h-full"
            viewBox={vbStr}
            preserveAspectRatio="xMidYMid slice"
            style={{ userSelect: "none" }}
          >
            <defs>
              <radialGradient id="thermalGradient">
                <stop offset="0%" stopColor="#ef4444" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
              </radialGradient>
              <radialGradient id="thermalOverlayGradient">
                <stop offset="0%" stopColor="#fff7d6" stopOpacity="0.95" />
                <stop offset="42%" stopColor="#ffb347" stopOpacity="0.65" />
                <stop offset="72%" stopColor="#f85149" stopOpacity="0.42" />
                <stop offset="100%" stopColor="#111827" stopOpacity="0" />
              </radialGradient>
              <linearGradient id="thermalRouteGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#111827" stopOpacity="0" />
                <stop offset="25%" stopColor="#f85149" stopOpacity="0.18" />
                <stop offset="70%" stopColor="#ffb347" stopOpacity="0.16" />
                <stop offset="100%" stopColor="#fff7d6" stopOpacity="0.1" />
              </linearGradient>
              <linearGradient id="terrainOverlayGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#58a6ff" stopOpacity="0.22" />
                <stop offset="38%" stopColor="#3fb950" stopOpacity="0.18" />
                <stop offset="72%" stopColor="#d29922" stopOpacity="0.22" />
                <stop offset="100%" stopColor="#f8fafc" stopOpacity="0.34" />
              </linearGradient>
              <linearGradient id="terrainContourGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#4a6fa5" stopOpacity="0.18" />
                <stop offset="50%" stopColor="#8d6b2f" stopOpacity="0.34" />
                <stop offset="100%" stopColor="#f8fafc" stopOpacity="0.16" />
              </linearGradient>
              <linearGradient id="slopeOverlayGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#111827" stopOpacity="0.28" />
                <stop offset="35%" stopColor="#6b21a8" stopOpacity="0.24" />
                <stop offset="70%" stopColor="#f97316" stopOpacity="0.34" />
                <stop offset="100%" stopColor="#facc15" stopOpacity="0.2" />
              </linearGradient>
              <linearGradient id="traversabilityOverlayGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#f85149" stopOpacity="0.36" />
                <stop offset="50%" stopColor="#d29922" stopOpacity="0.32" />
                <stop offset="100%" stopColor="#3fb950" stopOpacity="0.36" />
              </linearGradient>
              <linearGradient id="psrOverlayGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#0f172a" stopOpacity="0.2" />
                <stop offset="55%" stopColor="#94a3b8" stopOpacity="0.18" />
                <stop offset="100%" stopColor="#f8fafc" stopOpacity="0.14" />
              </linearGradient>
              <pattern id="psrHatch" width="20" height="20" patternUnits="userSpaceOnUse" patternTransform="rotate(24)">
                <rect width="20" height="20" fill="rgba(248,250,252,0.22)" />
                <line x1="0" y1="0" x2="0" y2="20" stroke="rgba(71,85,105,0.18)" strokeWidth="6" />
              </pattern>
              <filter id="glow"><feGaussianBlur stdDeviation="3" result="c"/><feMerge><feMergeNode in="c"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
              
              <pattern id="smallGrid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 40 40 M 0 40 L 40 40" fill="none" stroke="rgba(0,0,0,0.02)" strokeWidth="0.5"/>
              </pattern>
              <pattern id="gridPattern" width="200" height="200" patternUnits="userSpaceOnUse">
                <rect width="200" height="200" fill="url(#smallGrid)"/>
                <path d="M 200 0 L 200 200 M 0 200 L 200 200" fill="none" stroke="rgba(0,0,0,0.06)" strokeWidth="1"/>
              </pattern>
            </defs>

            {/* Infinite Grid */}
            {showGridOverlay && (
              <rect x="-50000" y="-50000" width="100000" height="100000" fill="url(#gridPattern)" opacity={overlayOpacity / 100} />
            )}

            {selectedLayerId === "elevation" && (
              <g opacity={layerOverlayOpacity}>
                <rect x="0" y="0" width={VIEWBOX_SIZE} height={VIEWBOX_SIZE} fill="url(#terrainOverlayGradient)" opacity="0.42" />
                {[
                  "M 20 158 C 180 110 318 212 468 168 S 764 78 980 148",
                  "M -10 302 C 184 252 302 360 480 322 S 812 224 1030 318",
                  "M -20 468 C 212 420 340 548 560 508 S 846 404 1020 468",
                  "M 10 642 C 176 596 342 704 540 670 S 844 570 1010 626",
                  "M 60 812 C 214 764 380 858 586 820 S 850 724 968 782",
                ].map((d, index) => (
                  <path
                    key={`elevation-contour-${index}`}
                    d={d}
                    fill="none"
                    stroke="url(#terrainContourGradient)"
                    strokeLinecap="round"
                    strokeWidth={index % 2 === 0 ? 5 : 2.5}
                    opacity={0.28 + (index * 0.06)}
                  />
                ))}
              </g>
            )}

            {selectedLayerId === "slope" && (
              <g opacity={layerOverlayOpacity}>
                <rect x="0" y="0" width={VIEWBOX_SIZE} height={VIEWBOX_SIZE} fill="url(#slopeOverlayGradient)" opacity="0.18" />
                {[
                  { d: "M 40 120 C 212 76 370 214 506 186 S 820 42 980 120", width: 88, opacity: 0.14 },
                  { d: "M -30 286 C 194 228 338 390 548 330 S 830 236 1028 294", width: 102, opacity: 0.18 },
                  { d: "M 40 520 C 210 470 394 624 598 552 S 828 442 1000 500", width: 110, opacity: 0.2 },
                  { d: "M 86 796 C 260 738 412 898 648 834 S 866 706 974 758", width: 92, opacity: 0.16 },
                ].map((band, index) => (
                  <path
                    key={`slope-band-${index}`}
                    d={band.d}
                    fill="none"
                    stroke="url(#slopeOverlayGradient)"
                    strokeLinecap="round"
                    strokeWidth={band.width}
                    opacity={band.opacity}
                  />
                ))}
              </g>
            )}

            {selectedLayerId === "thermal_risk" && (
              <g opacity={layerOverlayOpacity}>
                <path d={highRiskPath} fill="none" stroke="url(#thermalRouteGradient)" strokeWidth="84" strokeLinecap="round" opacity="0.12" />
                {STATIC_THERMAL_FIELDS.map((field, index) => (
                  <circle
                    key={`thermal-overlay-${index}`}
                    fill="url(#thermalOverlayGradient)"
                    cx={field.x}
                    cy={field.y}
                    r={field.baseRadius + ((weights.thermal / 100) * 44)}
                    opacity={index === 0 ? 0.44 : 0.3}
                  />
                ))}
                {thermalZones.map((zone, index) => (
                  <circle
                    key={`thermal-user-overlay-${index}`}
                    fill="url(#thermalOverlayGradient)"
                    cx={zone.x}
                    cy={zone.y}
                    r={zone.r * 1.12}
                    opacity="0.36"
                  />
                ))}
              </g>
            )}

            {selectedLayerId === "traversability" && (
              <g opacity={layerOverlayOpacity}>
                <path d={safePath} fill="none" stroke="url(#traversabilityOverlayGradient)" strokeWidth="112" strokeLinecap="round" opacity="0.12" />
                <path d={safePath} fill="none" stroke="url(#traversabilityOverlayGradient)" strokeWidth="34" strokeLinecap="round" opacity="0.34" />
                <circle cx={safeControlPoint.x} cy={safeControlPoint.y} r="84" fill="#3fb950" opacity="0.12" />
                <circle cx={sectorNode.x} cy={sectorNode.y} r="52" fill="#d29922" opacity="0.14" />
              </g>
            )}

            {selectedLayerId === "psr_mask" && (
              <g opacity={layerOverlayOpacity}>
                <rect x="0" y="0" width={VIEWBOX_SIZE} height={VIEWBOX_SIZE} fill="url(#psrOverlayGradient)" opacity="0.18" />
                <path d="M 100 100 Q 150 80 200 150 T 300 100 L 280 250 Q 200 280 120 230 Z" fill="url(#psrHatch)" stroke="rgba(71,85,105,0.28)" strokeWidth="1.4" />
                <path d="M 750 600 Q 850 550 900 650 T 800 800 Q 700 750 750 600" fill="url(#psrHatch)" stroke="rgba(71,85,105,0.28)" strokeWidth="1.4" />
                {shadowRegions.map((region, index) => (
                  <ellipse
                    key={`shadow-overlay-${index}`}
                    cx={region.x}
                    cy={region.y}
                    rx="82"
                    ry="58"
                    fill="url(#psrHatch)"
                    stroke="rgba(71,85,105,0.28)"
                    strokeWidth="1.2"
                    strokeDasharray="4 2"
                  />
                ))}
              </g>
            )}

            {/* ── Static PSR regions ──────────────────────────────────── */}
            <path className="psr-region" d="M 100 100 Q 150 80 200 150 T 300 100 L 280 250 Q 200 280 120 230 Z" opacity={staticPsrOpacity} />
            <path className="psr-region" d="M 750 600 Q 850 550 900 650 T 800 800 Q 700 750 750 600" opacity={staticPsrOpacity} />

            {/* ── Static thermal hazards ──────────────────────────────── */}
            <circle fill="url(#thermalGradient)" opacity={staticThermalPrimaryOpacity} cx="450" cy="500" r={130 + (weights.thermal/100)*40} />
            <circle fill="url(#thermalGradient)" opacity={staticThermalSecondaryOpacity} cx="550" cy="450" r={80  + (weights.thermal/100)*30} />

            {/* ── USER-placed thermal zones ────────────────────────────── */}
            {thermalZones.map((z, i) => (
              <g key={`th-${i}`}
                 style={{ cursor: "pointer" }}
                 onMouseEnter={(e) => setTooltipData({ x: e.clientX, y: e.clientY, title: `THERMAL ZONE ${i+1}`, lines: [{label: "Temp Delta", value: `+${z.tempDelta} K`}, {label:"Radius", value:`${Math.round(z.r)} m`}], risk: "CRITICAL" })}
                 onMouseMove={(e) => setTooltipData(prev => prev ? { ...prev, x: e.clientX, y: e.clientY } : null)}
                 onMouseLeave={() => setTooltipData(null)}>
                <circle fill="url(#thermalGradient)" opacity="0.55" cx={z.x} cy={z.y} r={z.r} />
                <circle fill="none" stroke="#ef4444" strokeWidth="0.8" strokeDasharray="4 2" opacity="0.5" cx={z.x} cy={z.y} r={z.r} />
                <text x={z.x} y={z.y - z.r - 6} fontSize="11" fill="#ef4444" textAnchor="middle" fontWeight="bold">THERMAL</text>
              </g>
            ))}

            {/* ── USER-placed craters ──────────────────────────────────── */}
            {craters.map((c, i) => (
              <g key={`cr-${i}`}
                 style={{ cursor: "pointer" }}
                 onMouseEnter={(e) => setTooltipData({ x: e.clientX, y: e.clientY, title: `CRATER ${i+1}`, lines: [{label: "Slope", value: `${c.slope}\u00b0`}, {label:"Depth", value:`${c.depth} m`}], risk: "HIGH" })}
                 onMouseMove={(e) => setTooltipData(prev => prev ? { ...prev, x: e.clientX, y: e.clientY } : null)}
                 onMouseLeave={() => setTooltipData(null)}>
                <ellipse cx={c.x} cy={c.y} rx="60" ry="40" fill="rgba(30,41,59,0.18)" stroke="rgba(30,41,59,0.35)" strokeWidth="1" strokeDasharray="4 2" />
                <ellipse cx={c.x} cy={c.y} rx="30" ry="20" fill="rgba(30,41,59,0.28)" />
                <text x={c.x} y={c.y - 48} fontSize="11" fill="#475569" textAnchor="middle" fontWeight="bold">CRATER</text>
              </g>
            ))}

            {/* ── USER-placed shadow / PSR regions ───────────────────── */}
            {shadowRegions.map((s, i) => (
              <g key={`sh-${i}`}
                 style={{ cursor: "pointer" }}
                 onMouseEnter={(e) => setTooltipData({ x: e.clientX, y: e.clientY, title: `PSR REGION ${i+1}`, lines: [{label: "Surface Temp", value: `${s.temp} C`}], risk: "MODERATE" })}
                 onMouseMove={(e) => setTooltipData(prev => prev ? { ...prev, x: e.clientX, y: e.clientY } : null)}
                 onMouseLeave={() => setTooltipData(null)}>
                <ellipse cx={s.x} cy={s.y} rx="70" ry="50" fill="rgba(30,41,59,0.15)" stroke="rgba(30,41,59,0.3)" strokeWidth="1" strokeDasharray="4 2" />
                <text x={s.x} y={s.y - 56} fontSize="11" fill="#64748b" textAnchor="middle" fontWeight="bold">PSR SHADOW</text>
              </g>
            ))}

            {/* ── Routes ──────────────────────────────────────────────── */}
            {/* Short / high risk */}
            {showRouteOverlay && (
              <path d={highRiskPath} fill="none" opacity={replanned ? 0.2 : 0.55 * (overlayOpacity / 100)} stroke="#ef4444" strokeDasharray="6,4" strokeWidth="1.5" style={{ transition: "d 0.3s, opacity 0.8s" }} />
            )}

            {/* Safe route */}
            {showRouteOverlay && (
              <path d={safePath} fill="none" stroke="#10b981" strokeWidth={routeW} opacity={routeOp} style={{ transition: "d 0.3s, stroke-width 0.3s, opacity 0.3s" }} />
            )}

            {/* Replanned segment */}
            {!replanned && showRouteOverlay && <path d={safePath} fill="none" stroke="#f59e0b" strokeLinecap="round" strokeWidth="3" opacity="0" />}
            {replanned && showRouteOverlay && (
              <>
                <path d={replannedPath} fill="none" stroke="#f59e0b" strokeLinecap="round" strokeWidth="3.5" filter="url(#glow)" style={{ transition: "d 0.3s" }} />
                <circle cx={(startCoord.x + goalCoord.x)/2 - 125} cy={(startCoord.y + goalCoord.y)/2 - 50} fill="#f59e0b" r="6" stroke="white" strokeWidth="2" filter="url(#glow)" />
                <text x={(startCoord.x + goalCoord.x)/2 - 105} y={(startCoord.y + goalCoord.y)/2 - 47} fontSize="12" fill="#f59e0b" fontWeight="bold">NEW SEGMENT</text>
              </>
            )}

            {/* Goal Marker */}
            <circle cx={goalCoord.x} cy={goalCoord.y} fill="#10b981" r="14" stroke="white" strokeWidth="3" filter="url(#glow)" />
            <text x={goalCoord.x} y={goalCoord.y - 20} fontSize="13" fill="#10b981" textAnchor="middle" fontWeight="bold">GOAL</text>

            {/* Start Marker & Rover Icon */}
            <g transform={`translate(${startCoord.x}, ${startCoord.y})`} style={{ pointerEvents: "none" }}>
              <ellipse cx="0" cy="18" rx="24" ry="12" fill="rgba(0,0,0,0.15)" />
              {/* Wheels */}
              <rect x="-16" y="8" width="8" height="12" rx="2" fill="#334155" />
              <rect x="8" y="8" width="8" height="12" rx="2" fill="#334155" />
              <rect x="-18" y="0" width="6" height="10" rx="1.5" fill="#475569" />
              <rect x="12" y="0" width="6" height="10" rx="1.5" fill="#475569" />
              {/* Body */}
              <rect x="-12" y="-4" width="24" height="16" rx="3" fill="#f8fafc" stroke="#cbd5e1" strokeWidth="1" />
              {/* Solar Panel */}
              <rect x="-8" y="-10" width="16" height="10" rx="1" fill="#0ea5e9" opacity="0.9" />
              <path d="M-8 -6 L8 -6 M-4 -10 L-4 0 M4 -10 L4 0" stroke="rgba(255,255,255,0.3)" strokeWidth="0.5" />
              {/* Antenna */}
              <line x1="-10" y1="-4" x2="-14" y2="-16" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" />
              <circle cx="-14" cy="-16" r="2" fill="#ef4444" />
              <text x="0" y="42" fontSize="13" fill="#1e293b" textAnchor="middle" fontWeight="bold">START / ROVER</text>
            </g>

            {/* Hazard marker — hover triggers tooltip */}
            <circle
              cx={sectorNode.x} cy={sectorNode.y} fill="#ef4444" r="8" stroke="white" strokeWidth="2"
              style={{ cursor: "pointer" }}
              onMouseEnter={(e) => setTooltipData({ x: e.clientX, y: e.clientY, title: `NODE: 4-B`, lines: [{label: "Thermal Delta", value: `${activeThermalReductionPct}% safer`}, {label:"Projection", value: runtimeMetadata.projection ?? "South Pole"}], risk: "CRITICAL" })}
              onMouseMove={(e) => setTooltipData(prev => prev ? { ...prev, x: e.clientX, y: e.clientY } : null)}
              onMouseLeave={() => setTooltipData(null)}
            />
            <text x={sectorNode.x + 14} y={sectorNode.y + 4} fontSize="11" fill="#b91c1c" fontWeight="bold">SECTOR 4-B</text>
          </svg>

          {/* ── Cursor-tracking Tooltip ─────────────────────────────────── */}
          <div className="map-panel pointer-events-none absolute left-24 right-40 bottom-24 z-10 flex items-center justify-between px-4" style={PANEL_MONO_STYLE}>
            {axisTicks.map((tick) => (
              <div key={`x-${tick}`} className="rounded-full bg-white/70 px-2 py-1 text-[0.55rem] font-black uppercase tracking-[0.14em] text-slate-500 shadow-sm">
                {formatDistanceLabel(tick, distanceUnit)}
              </div>
            ))}
          </div>
          <div className="map-panel pointer-events-none absolute left-4 top-32 bottom-44 z-10 flex flex-col items-center justify-between py-2" style={PANEL_MONO_STYLE}>
            {[...axisTicks].reverse().map((tick) => (
              <div key={`y-${tick}`} className="rounded-full bg-white/70 px-2 py-1 text-[0.55rem] font-black uppercase tracking-[0.14em] text-slate-500 shadow-sm">
                {formatDistanceLabel(tick, distanceUnit)}
              </div>
            ))}
          </div>

          {tooltipData && (
            <div
              className="map-panel absolute glass-panel px-4 py-3 rounded-xl shadow-xl z-50 min-w-[200px] pointer-events-none backdrop-blur-md"
              style={{ ...PANEL_MONO_STYLE, top: tooltipData.y + 15, left: tooltipData.x + 15, transform: "translate(0, 0)" }}
            >
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-2 h-2 rounded-full animate-pulse ${tooltipData.risk === 'CRITICAL' ? 'bg-red-500' : tooltipData.risk === 'SAFE' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                <span className="text-[0.65rem] font-black uppercase tracking-widest">{tooltipData.title}</span>
              </div>
              <div className="space-y-1.5 text-[0.7rem]">
                {tooltipData.lines.map((line, idx) => (
                  <div key={idx} className="flex justify-between text-slate-500 gap-4">
                    <span>{line.label}</span><span className="font-bold text-slate-900">{line.value}</span>
                  </div>
                ))}
                <div className="pt-1.5 mt-1.5 border-t border-slate-100 flex justify-between items-center">
                  <span className="text-[0.6rem] font-bold text-slate-400 uppercase tracking-widest">RISK FACTOR</span>
                  <span className={`text-[0.65rem] font-black uppercase tracking-widest ${tooltipData.risk === 'CRITICAL' ? 'text-red-600' : tooltipData.risk === 'SAFE' ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {tooltipData.risk}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* ── Map Legend ───────────────────────────────────────────────── */}
          <div className="map-panel absolute bottom-36 left-8 glass-panel p-4 rounded-xl border border-slate-200 text-[0.65rem] font-bold space-y-2.5 z-10" style={PANEL_MONO_STYLE}>
            <h4 className="uppercase tracking-widest text-slate-400 mb-1">Map Legend</h4>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-[0.56rem] font-black uppercase tracking-[0.16em] text-slate-400">Active Layer</span>
                <span className={`rounded-full border px-2 py-1 text-[0.5rem] font-black uppercase tracking-[0.16em] ${activeLayerVisual.chipTone}`}>{activeLayerVisual.badge}</span>
              </div>
              <div className="mt-2 text-[0.68rem] font-black text-slate-900">{activeLayerLabel}</div>
              <div className="mt-2 h-2 rounded-full" style={{ background: getGradientCss(activeLayerVisual.swatch) }} />
              <div className="mt-2 text-[0.56rem] font-bold uppercase tracking-[0.14em] text-slate-500">{activeLayerRangeLabel}</div>
              <div className="mt-1 text-[0.55rem] font-bold uppercase tracking-[0.14em] text-slate-400">{resolutionLabel} / {mapExtentLabel}</div>
            </div>
            <div className="flex items-center gap-2"><span className="w-3 h-0.5 bg-emerald-500"/><span>SAFE PATH</span></div>
            <div className="flex items-center gap-2"><span className="w-3 h-0.5 bg-amber-500"/><span>REPLANNED SEGMENT</span></div>
            <div className="flex items-center gap-2"><span className="w-3 h-0.5 bg-red-400"/><span className="text-slate-400">HIGH RISK</span></div>
            <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-slate-300 opacity-50 border border-slate-400 border-dashed"/><span>PSR REGION</span></div>
            <div className="pt-2 border-t border-slate-100 text-slate-400 space-y-0.5">
              <span className="block">Drag to pan</span><span className="block">Scroll to zoom</span>
            </div>
          </div>
        </div>

        {/* ── System Intelligence Panel ─────────────────────────────────── */}
        <div className="map-panel absolute left-8 w-80 z-20" style={{ top: "calc(4rem + 1.5rem)" }}>
          <div className="glass-panel p-5 rounded-2xl shadow-2xl border border-slate-200/50">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center flex-shrink-0">
                  <span className="material-symbols-outlined text-white text-base">psychology</span>
                </div>
                <div>
                  <h3 className="text-[0.65rem] font-black uppercase tracking-widest text-slate-900">System Intelligence</h3>
                  <p className="text-[0.6rem] text-slate-400">AI AGENT: LUNA-42</p>
                </div>
              </div>
              <span className="px-2 py-0.5 bg-slate-100 rounded text-[0.6rem] font-bold text-slate-500 flex-shrink-0">T+04:22:12</span>
            </div>
            <div className={`p-3 rounded-xl border text-xs leading-relaxed font-medium transition-colors duration-500 ${panelError ? "bg-amber-50 border-amber-100 text-slate-700" : replanned ? "bg-emerald-50 border-emerald-100 text-slate-700" : "bg-red-50 border-red-100 text-slate-700"}`}>
              {panelError
                ? <><span className="text-amber-600 font-bold uppercase text-[0.65rem]">Sync: </span>{panelError}</>
                : replanned
                  ? <><span className="text-emerald-600 font-bold uppercase text-[0.65rem]">Resolved: </span>{serviceReplanResult?.reason ?? "Route recomputed around sector 4-B."} Thermal exposure shifted by <span className="text-emerald-600 font-bold">{Math.abs(serviceReplanResult?.metrics_delta?.thermal_delta ?? 0).toFixed(1)}</span> points with a <span className="font-bold">{Math.abs(serviceReplanResult?.metrics_delta?.distance_delta_m ?? 0).toLocaleString()}</span> m route delta.</>
                  : <><span className="text-red-600 font-bold uppercase text-[0.65rem]">Alert: </span>Thermal spike in <span className="font-bold underline decoration-red-200">sector 4-B</span>. Safe corridor reduces exposure by <span className="text-emerald-600 font-bold">{activeThermalReductionPct}%</span> versus the shortest route.</>
              }
            </div>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div className="text-[0.6rem] font-bold text-slate-400 uppercase mb-1">Trigger Type</div>
                <div className="text-[0.7rem] font-bold text-slate-700">{triggerTypeLabel}</div>
              </div>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div className="text-[0.6rem] font-bold text-slate-400 uppercase mb-1">Confidence</div>
                <div className="text-[0.7rem] font-bold text-emerald-600">{confidencePct}%</div>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
              <span className="text-[0.65rem] font-bold text-slate-400 uppercase tracking-tighter">Status</span>
              <span className={`flex items-center gap-1.5 text-[0.65rem] font-black transition-colors ${panelError ? "text-amber-600" : replanning || planningBusy ? "text-amber-500" : "text-emerald-600"}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${panelError ? "bg-amber-500" : replanning || planningBusy ? "bg-amber-400 animate-pulse" : "bg-emerald-500"}`} />
                {panelError ? "SYNCED WITH WARNINGS" : replanStatus}
              </span>
            </div>
          </div>
        </div>

        {/* ── Right Control Rail ───────────────────────────────────────────── */}
        <aside className="map-panel fixed right-6 top-24 bottom-24 w-20 glass-panel rounded-3xl shadow-2xl flex flex-col items-center py-6 z-40">
          <div className="flex flex-col items-center gap-1 mb-6">
            <div className="w-10 h-10 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center mb-0.5">
              <span className="material-symbols-outlined text-slate-600">precision_manufacturing</span>
            </div>
            <span className="text-[0.55rem] font-black uppercase text-slate-400">ALPHA-1</span>
          </div>

          <div className="flex flex-col gap-4 flex-1 w-full px-3">
            {TOOLS.map(({ id, icon, label }) => {
              const isActive = activeTool === id;
              return (
                <button
                  key={id}
                  onClick={(e) => { e.stopPropagation(); toggleTool(id); }}
                  title={`${label} — click to ${isActive ? "deactivate" : "activate"}`}
                  className="flex flex-col items-center gap-1 group relative"
                >
                  <div className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-all shadow-sm border
                    ${isActive
                      ? "bg-slate-900 border-slate-900 text-white shadow-md scale-110"
                      : "bg-white border-slate-200 text-slate-400 group-hover:bg-slate-50 group-hover:text-slate-900"}`}>
                    <span className="material-symbols-outlined">{icon}</span>
                  </div>
                  <span className={`text-[0.55rem] font-bold uppercase tracking-tighter ${isActive ? "text-slate-900" : "text-slate-400"}`}>{label}</span>
                  {isActive && <span className="absolute -left-1 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-slate-900" />}
                </button>
              );
            })}
          </div>

          <button
            onClick={(e) => { e.stopPropagation(); handleReplan(); }}
            className="w-12 h-12 bg-red-500 text-white rounded-2xl shadow-lg shadow-red-200 hover:bg-red-600 transition-all flex flex-col items-center justify-center gap-0.5 active:scale-95"
          >
            <span className="material-symbols-outlined text-lg">bolt</span>
            <span className="text-[0.4rem] font-black">TRIGGER</span>
          </button>
        </aside>

        {/* ── Weighting Parameters ─────────────────────────────────────────── */}
        <div className="map-panel absolute right-32 top-24 bottom-32 w-80 z-20">
          <div className="glass-panel h-full rounded-2xl shadow-xl border border-slate-200/50 overflow-hidden" style={PANEL_MONO_STYLE}>
            <div className="h-full overflow-y-auto px-5 py-5 space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-[0.65rem] font-black uppercase tracking-[0.22em] text-slate-900">Mission Controls</h3>
                  <p className="mt-1 text-[0.62rem] font-bold uppercase tracking-[0.18em] text-slate-400">{activeLayerLabel} layer active</p>
                </div>
                <div className={`rounded-full border px-2.5 py-1 text-[0.58rem] font-black uppercase tracking-[0.18em] ${planningBusy ? "border-amber-200 bg-amber-50 text-amber-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
                  {planningBusy ? "syncing" : "ready"}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white/80 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-[0.62rem] font-black uppercase tracking-[0.18em] text-slate-400">Scenario Selector</span>
                  <span className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-slate-500">{runtimeMetadata.projection?.includes("Moon") ? "polar stereo" : "demo"}</span>
                </div>
                <select
                  value={selectedScenarioId}
                  onChange={handleScenarioChange}
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-[0.72rem] font-bold text-slate-800 outline-none transition focus:border-slate-300"
                >
                  {scenarios.map((scenario) => (
                    <option key={scenario.scenario_id} value={scenario.scenario_id}>
                      {scenario.name}
                    </option>
                  ))}
                </select>
                <div className="mt-3 flex items-center justify-between text-[0.62rem]">
                  <span className="font-bold uppercase tracking-[0.14em] text-slate-400">Units</span>
                  <div className="flex rounded-full border border-slate-200 bg-slate-50 p-1">
                    {["m", "km"].map((unit) => (
                      <button
                        key={unit}
                        onClick={(e) => { e.stopPropagation(); setDistanceUnit(unit); }}
                        className={`rounded-full px-2.5 py-1 text-[0.58rem] font-black uppercase tracking-[0.16em] transition ${distanceUnit === unit ? "bg-slate-900 text-white" : "text-slate-500"}`}
                      >
                        {unit}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white/80 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-[0.62rem] font-black uppercase tracking-[0.18em] text-slate-400">Layer Switcher</span>
                  <span className="text-[0.56rem] font-bold uppercase tracking-[0.16em] text-slate-500">{Math.round(overlayOpacity)}%</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {(runtimeMetadata.layers ?? []).map((layer) => (
                    <button
                      key={layer.id}
                      onClick={(e) => { e.stopPropagation(); setSelectedLayerId(layer.id); }}
                      className={`rounded-xl border px-3 py-2 text-left text-[0.6rem] font-black uppercase tracking-[0.14em] transition ${selectedLayerId === layer.id ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-slate-50 text-slate-500 hover:text-slate-900"}`}
                    >
                      {layer.label}
                    </button>
                  ))}
                </div>
                <div className="mt-4 space-y-3">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-[0.6rem] font-bold uppercase tracking-[0.14em]">
                      <span className="text-slate-400">Overlay Opacity</span>
                      <span className="text-slate-900">{Math.round(overlayOpacity)}%</span>
                    </div>
                    <input
                      type="range"
                      min="20"
                      max="100"
                      value={overlayOpacity}
                      onChange={(e) => setOverlayOpacity(Number(e.target.value))}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full h-1 appearance-none rounded-full outline-none cursor-pointer"
                      style={{ background: `linear-gradient(to right, #0f172a ${overlayOpacity}%, #e2e8f0 ${overlayOpacity}%)` }}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowGridOverlay((value) => !value); }}
                      className={`rounded-xl px-3 py-2 text-[0.58rem] font-black uppercase tracking-[0.14em] transition ${showGridOverlay ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-500"}`}
                    >
                      Grid {showGridOverlay ? "On" : "Off"}
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowRouteOverlay((value) => !value); }}
                      className={`rounded-xl px-3 py-2 text-[0.58rem] font-black uppercase tracking-[0.14em] transition ${showRouteOverlay ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-500"}`}
                    >
                      Route {showRouteOverlay ? "On" : "Off"}
                    </button>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[0.56rem] font-black uppercase tracking-[0.16em] text-slate-400">Layer Readout</span>
                      <span className={`rounded-full border px-2 py-1 text-[0.5rem] font-black uppercase tracking-[0.16em] ${activeLayerVisual.chipTone}`}>{activeLayerVisual.badge}</span>
                    </div>
                    <div className="mt-3 h-2 rounded-full" style={{ background: getGradientCss(activeLayerVisual.swatch) }} />
                    <div className="mt-3 grid grid-cols-2 gap-2 text-[0.56rem] font-bold uppercase tracking-[0.14em]">
                      <div className="rounded-lg bg-white px-2.5 py-2">
                        <div className="text-slate-400">Range</div>
                        <div className="mt-1 normal-case tracking-normal text-slate-900">{activeLayerRangeLabel}</div>
                      </div>
                      <div className="rounded-lg bg-white px-2.5 py-2">
                        <div className="text-slate-400">Resolution</div>
                        <div className="mt-1 normal-case tracking-normal text-slate-900">{resolutionLabel}</div>
                      </div>
                      <div className="rounded-lg bg-white px-2.5 py-2">
                        <div className="text-slate-400">Extent</div>
                        <div className="mt-1 normal-case tracking-normal text-slate-900">{mapExtentLabel}</div>
                      </div>
                      <div className="rounded-lg bg-white px-2.5 py-2">
                        <div className="text-slate-400">Overlay</div>
                        <div className="mt-1 normal-case tracking-normal text-slate-900">{Math.round(layerOverlayOpacity * 100)}% visual</div>
                      </div>
                    </div>
                    <p className="mt-3 text-[0.58rem] leading-relaxed text-slate-500">{activeLayer?.description}</p>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white/80 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <span className="text-[0.62rem] font-black uppercase tracking-[0.18em] text-slate-400">Weight Profile</span>
                  <span className="text-[0.58rem] font-bold uppercase tracking-[0.16em] text-slate-500">0.0 - 2.0 mapped</span>
                </div>
                <div className="space-y-4">
                  {[
                    { key: "distance", label: "DISTANCE", color: "#64748b", metricKey: "w_dist" },
                    { key: "slope", label: "SLOPE", color: "#94a3b8", metricKey: "w_slope" },
                    { key: "thermal", label: "THERMAL", color: "#1e293b", metricKey: "w_thermal" },
                    { key: "energy", label: "ENERGY", color: "#0f766e", metricKey: "w_energy" },
                  ].map(({ key, label, color, metricKey }) => (
                    <div key={key} className="space-y-2">
                      <div className="flex items-center justify-between text-[0.62rem] font-bold uppercase tracking-[0.16em]">
                        <span className="text-slate-400">{label}</span>
                        <span className="tabular-nums text-slate-900">{planningWeights[metricKey].toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={weights[key]}
                        onChange={(e) => setWeights((current) => ({ ...current, [key]: Number(e.target.value) }))}
                        onClick={(e) => e.stopPropagation()}
                        className="w-full h-1 appearance-none rounded-full outline-none cursor-pointer"
                        style={{ background: `linear-gradient(to right, ${color} ${weights[key]}%, #e2e8f0 ${weights[key]}%)` }}
                      />
                    </div>
                  ))}
                </div>
                <div className="mt-5 grid grid-cols-3 gap-2">
                  <button
                    onClick={(e) => { e.stopPropagation(); handlePlanRoute(); }}
                    className="rounded-xl bg-slate-100 px-3 py-2 text-[0.6rem] font-black uppercase tracking-[0.16em] text-slate-900 transition hover:bg-slate-200"
                  >
                    Plan
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleCompareRoutes(); }}
                    className="rounded-xl bg-slate-100 px-3 py-2 text-[0.6rem] font-black uppercase tracking-[0.16em] text-slate-900 transition hover:bg-slate-200"
                  >
                    Compare
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleReplan(); }}
                    disabled={replanning}
                    className="rounded-xl bg-slate-900 px-3 py-2 text-[0.6rem] font-black uppercase tracking-[0.16em] text-white transition hover:bg-slate-800 disabled:opacity-60"
                  >
                    Replan
                  </button>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white/80 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-[0.62rem] font-black uppercase tracking-[0.18em] text-slate-400">Comparison View</span>
                  <span className={`rounded-full px-2 py-1 text-[0.55rem] font-black uppercase tracking-[0.16em] ${safePathRecommended ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                    {safePathRecommended ? "safe route" : "shortest viable"}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[0.66rem]">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <div className="mb-1 font-black uppercase tracking-[0.16em] text-slate-400">Shortest</div>
                    <div className="text-sm font-black text-slate-900">{(shortestPathMetrics.distanceM / 1000).toFixed(1)} km</div>
                    <div className="mt-1 text-slate-500">Thermal {shortestPathMetrics.thermalExposure.toFixed(1)}</div>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <div className="mb-1 font-black uppercase tracking-[0.16em] text-slate-400">Safe</div>
                    <div className="text-sm font-black text-slate-900">{(safePathMetrics.distanceM / 1000).toFixed(1)} km</div>
                    <div className="mt-1 text-slate-500">Thermal {safePathMetrics.thermalExposure.toFixed(1)}</div>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-[0.6rem]">
                  <div className="rounded-xl bg-slate-50 px-3 py-2">
                    <div className="font-black uppercase tracking-[0.16em] text-slate-400">Distance</div>
                    <div className="mt-1 font-black text-slate-900">+{Math.abs(comparisonDelta?.distance_overhead_pct ?? distanceDeltaPct)}%</div>
                  </div>
                  <div className="rounded-xl bg-slate-50 px-3 py-2">
                    <div className="font-black uppercase tracking-[0.16em] text-slate-400">Thermal</div>
                    <div className="mt-1 font-black text-emerald-700">-{Math.abs(comparisonDelta?.thermal_reduction_pct ?? activeThermalReductionPct)}%</div>
                  </div>
                  <div className="rounded-xl bg-slate-50 px-3 py-2">
                    <div className="font-black uppercase tracking-[0.16em] text-slate-400">Energy</div>
                    <div className="mt-1 font-black text-slate-900">{activeEnergyDeltaPct > 0 ? "+" : ""}{activeEnergyDeltaPct.toFixed(1)}%</div>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white/80 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-[0.62rem] font-black uppercase tracking-[0.18em] text-slate-400">Risk Breakdown</span>
                  <span className="text-[0.56rem] font-bold uppercase tracking-[0.16em] text-slate-500">{activeMetrics.riskBreakdown.safeCells + activeMetrics.riskBreakdown.cautionCells + activeMetrics.riskBreakdown.dangerCells} cells</span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { key: "safeCells", label: "Safe", tone: "text-emerald-700 bg-emerald-50" },
                    { key: "cautionCells", label: "Caution", tone: "text-amber-700 bg-amber-50" },
                    { key: "dangerCells", label: "Danger", tone: "text-red-700 bg-red-50" },
                  ].map(({ key, label, tone }) => (
                    <div key={key} className={`rounded-xl px-3 py-3 ${tone}`}>
                      <div className="text-[0.56rem] font-black uppercase tracking-[0.16em]">{label}</div>
                      <div className="mt-1 text-sm font-black">{activeMetrics.riskBreakdown[key]}</div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
                    <div className="text-[0.56rem] font-black uppercase tracking-[0.16em] text-slate-400">Start Coord</div>
                    <div className="mt-1 text-[0.64rem] font-bold text-slate-900">X {formatProjectedMeters(startProjected.x)}</div>
                    <div className="text-[0.64rem] font-bold text-slate-900">Y {formatProjectedMeters(startProjected.y)}</div>
                    <div className="mt-1 text-[0.56rem] font-bold uppercase tracking-[0.14em] text-slate-400">({formatProjectedKilometers(startProjected.x)} / {formatProjectedKilometers(startProjected.y)})</div>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
                    <div className="text-[0.56rem] font-black uppercase tracking-[0.16em] text-slate-400">Goal Coord</div>
                    <div className="mt-1 text-[0.64rem] font-bold text-slate-900">X {formatProjectedMeters(goalProjected.x)}</div>
                    <div className="text-[0.64rem] font-bold text-slate-900">Y {formatProjectedMeters(goalProjected.y)}</div>
                    <div className="mt-1 text-[0.56rem] font-bold uppercase tracking-[0.14em] text-slate-400">({formatProjectedKilometers(goalProjected.x)} / {formatProjectedKilometers(goalProjected.y)})</div>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white/80 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-[0.62rem] font-black uppercase tracking-[0.18em] text-slate-400">Event Feed</span>
                  <span className="text-[0.56rem] font-bold uppercase tracking-[0.16em] text-slate-500">{eventEntries.length} events</span>
                </div>
                <div className="space-y-2.5">
                  {eventEntries.length
                    ? eventEntries.slice(-3).map((entry) => (
                        <div key={entry.id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-[0.58rem] font-black uppercase tracking-[0.16em] text-slate-400">{entry.timestamp}</span>
                            <span className={`text-[0.56rem] font-black uppercase tracking-[0.16em] ${entry.level === "warning" ? "text-amber-600" : entry.level === "success" ? "text-emerald-600" : "text-slate-500"}`}>{entry.level}</span>
                          </div>
                          <div className="mt-1 text-[0.67rem] font-bold text-slate-900">{entry.title}</div>
                          <div className="mt-1 text-[0.62rem] leading-relaxed text-slate-500">{entry.detail}</div>
                        </div>
                      ))
                    : (
                        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-[0.62rem] font-bold uppercase tracking-[0.14em] text-slate-400">
                          Replan history will appear here.
                        </div>
                      )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Bottom Metrics Bar ───────────────────────────────────────────── */}
        <div className="map-panel fixed bottom-8 left-1/2 -translate-x-1/2 w-[90%] max-w-5xl z-40">
          <div className="glass-panel px-8 py-5 rounded-3xl shadow-2xl border border-slate-200/50 flex items-center justify-between gap-6" style={PANEL_MONO_STYLE}>
            <div className="grid flex-1 grid-cols-2 gap-4 xl:grid-cols-4">
              {bottomMetricCards.map(({ label, value, unit, secondary, delta, deltaTone }) => (
                <div key={label} className="rounded-2xl border border-slate-200 bg-white/70 px-4 py-3">
                  <span className="text-[0.56rem] font-black uppercase tracking-[0.18em] text-slate-400">{label}</span>
                  <div className="mt-1 flex items-baseline gap-1">
                    <span className="text-2xl font-extrabold tabular-nums tracking-tight text-slate-900">{value}</span>
                    <span className="text-xs font-bold uppercase text-slate-400">{unit}</span>
                  </div>
                  <div className="mt-1 text-[0.58rem] font-bold uppercase tracking-[0.14em] text-slate-500">{secondary}</div>
                  <div className={`mt-2 text-[0.58rem] font-black uppercase tracking-[0.14em] ${deltaTone}`}>{delta}</div>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-3 pl-6 border-l border-slate-100 flex-shrink-0">
              <div className={`flex items-center gap-2 px-3 py-2 rounded-full border ${safePathRecommended ? "bg-emerald-50 text-emerald-600 border-emerald-100" : "bg-amber-50 text-amber-600 border-amber-100"}`}>
                <span className="material-symbols-outlined text-sm">verified</span>
                <span className="text-[0.65rem] font-bold tracking-tight uppercase whitespace-nowrap">{safePathRecommended ? "Safe Path Preferred" : "Shortest Path Viable"}</span>
              </div>
              <button
                onClick={(e) => e.stopPropagation()}
                className="bg-slate-900 text-white px-6 py-3 rounded-2xl text-[0.65rem] font-bold uppercase tracking-widest hover:bg-slate-800 transition-all shadow-lg active:scale-95 whitespace-nowrap"
              >
                Execute Route
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
