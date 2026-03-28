import layersMetadataMock from "../mocks/layers.mock";
import scenariosMock from "../mocks/scenarios.mock";
import {
  createComparisonResult,
  createGridMetadata,
  createPathResult,
  createReplanResult,
  createScenario,
  createWeights,
} from "../models/missionModels";

function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function percentDelta(current, baseline) {
  if (!baseline) return 0;
  return Number((((current - baseline) / baseline) * 100).toFixed(1));
}

function clampGrid([row, col], [rows, columns]) {
  return [
    clamp(Math.round(row), 0, rows - 1),
    clamp(Math.round(col), 0, columns - 1),
  ];
}

function interpolateSegment(start, end) {
  const steps = Math.max(Math.abs(end[0] - start[0]), Math.abs(end[1] - start[1]), 1);
  const points = [];

  for (let index = 0; index <= steps; index += 1) {
    const factor = index / steps;
    points.push([
      Math.round(start[0] + ((end[0] - start[0]) * factor)),
      Math.round(start[1] + ((end[1] - start[1]) * factor)),
    ]);
  }

  return points;
}

function dedupePath(points) {
  return points.filter((point, index) => (
    !index
      || point[0] !== points[index - 1][0]
      || point[1] !== points[index - 1][1]
  ));
}

function buildPath(waypoints, shape) {
  const segments = [];

  waypoints.forEach((point, index) => {
    const nextPoint = clampGrid(point, shape);
    if (!index) {
      segments.push(nextPoint);
      return;
    }

    segments.push(...interpolateSegment(clampGrid(waypoints[index - 1], shape), nextPoint));
  });

  return dedupePath(segments);
}

function segmentLengthMeters(pathGrid, resolutionM) {
  return pathGrid.reduce((distance, point, index) => {
    if (!index) return distance;
    return distance + (Math.hypot(
      point[0] - pathGrid[index - 1][0],
      point[1] - pathGrid[index - 1][1],
    ) * resolutionM);
  }, 0);
}

function gridToProjectedPoint([row, col], metadata) {
  return [
    metadata.origin_m.x + (col * metadata.resolution_m),
    metadata.origin_m.y + (row * metadata.resolution_m),
  ];
}

const SCENARIO_PROFILES = {
  south_pole_demo_v1: {
    terrain: {
      baseElevationM: -2860,
      elevationScaleM: 1180,
      roverEfficiency: 1.02,
      plannerComplexity: 1.04,
      slopeScale: 0.96,
      routeGeometry: {
        safeLift: 48,
        safeEntryLateral: 18,
        safeExitLateral: 34,
        slopeBias: 18,
        shortestMidBias: 6,
        replanLead: 40,
        replanTrail: 18,
        replanLateral: {
          thermal_spike: 46,
          new_obstacle: 58,
          energy_budget: 28,
        },
      },
    },
    heatCenters: [
      { row: 250, col: 250, intensity: 1.0, radius: 58 },
      { row: 312, col: 286, intensity: 0.74, radius: 44 },
    ],
    slopeCenters: [
      { row: 220, col: 160, intensity: 0.62, radius: 92 },
      { row: 334, col: 360, intensity: 0.48, radius: 80 },
    ],
    psrCenters: [
      { row: 110, col: 126, intensity: 0.22, radius: 70 },
      { row: 374, col: 408, intensity: 0.28, radius: 84 },
    ],
    roughnessCenters: [
      { row: 236, col: 214, intensity: 0.3, radius: 72 },
      { row: 322, col: 348, intensity: 0.24, radius: 68 },
    ],
    elevationCenters: [
      { row: 162, col: 148, intensity: 0.42, radius: 118 },
      { row: 286, col: 252, intensity: -0.36, radius: 92 },
      { row: 368, col: 392, intensity: 0.3, radius: 104 },
    ],
  },
  ridge_crossing_demo_v1: {
    terrain: {
      baseElevationM: -2540,
      elevationScaleM: 1440,
      roverEfficiency: 1.12,
      plannerComplexity: 1.16,
      slopeScale: 1.12,
      routeGeometry: {
        safeLift: 56,
        safeEntryLateral: 24,
        safeExitLateral: 42,
        slopeBias: 28,
        shortestMidBias: -8,
        replanLead: 44,
        replanTrail: 22,
        replanLateral: {
          thermal_spike: 44,
          new_obstacle: 64,
          energy_budget: 34,
        },
      },
    },
    heatCenters: [
      { row: 210, col: 256, intensity: 0.52, radius: 46 },
      { row: 286, col: 302, intensity: 0.44, radius: 40 },
    ],
    slopeCenters: [
      { row: 250, col: 220, intensity: 0.86, radius: 86 },
      { row: 272, col: 294, intensity: 0.72, radius: 78 },
    ],
    psrCenters: [
      { row: 154, col: 122, intensity: 0.12, radius: 60 },
    ],
    roughnessCenters: [
      { row: 244, col: 214, intensity: 0.4, radius: 82 },
      { row: 286, col: 302, intensity: 0.34, radius: 74 },
      { row: 334, col: 344, intensity: 0.22, radius: 66 },
    ],
    elevationCenters: [
      { row: 242, col: 232, intensity: 0.62, radius: 110 },
      { row: 286, col: 292, intensity: 0.58, radius: 98 },
      { row: 336, col: 338, intensity: -0.18, radius: 84 },
    ],
  },
  thermal_spike_demo_v1: {
    terrain: {
      baseElevationM: -3010,
      elevationScaleM: 1260,
      roverEfficiency: 0.98,
      plannerComplexity: 1.22,
      slopeScale: 0.94,
      routeGeometry: {
        safeLift: 52,
        safeEntryLateral: 20,
        safeExitLateral: 38,
        slopeBias: 16,
        shortestMidBias: 4,
        replanLead: 46,
        replanTrail: 26,
        replanLateral: {
          thermal_spike: 52,
          new_obstacle: 60,
          energy_budget: 30,
        },
      },
    },
    heatCenters: [
      { row: 246, col: 258, intensity: 1.12, radius: 62 },
      { row: 304, col: 320, intensity: 0.88, radius: 50 },
    ],
    slopeCenters: [
      { row: 214, col: 168, intensity: 0.48, radius: 86 },
      { row: 348, col: 374, intensity: 0.42, radius: 80 },
    ],
    psrCenters: [
      { row: 96, col: 110, intensity: 0.18, radius: 68 },
      { row: 392, col: 404, intensity: 0.2, radius: 74 },
    ],
    roughnessCenters: [
      { row: 232, col: 244, intensity: 0.26, radius: 66 },
      { row: 286, col: 304, intensity: 0.3, radius: 64 },
      { row: 338, col: 362, intensity: 0.18, radius: 60 },
    ],
    elevationCenters: [
      { row: 178, col: 146, intensity: 0.26, radius: 108 },
      { row: 248, col: 260, intensity: -0.42, radius: 76 },
      { row: 344, col: 366, intensity: 0.22, radius: 96 },
    ],
  },
};

function profileForScenario(scenarioId) {
  return SCENARIO_PROFILES[scenarioId] ?? SCENARIO_PROFILES.south_pole_demo_v1;
}

function fieldStrength(point, field) {
  const distance = Math.hypot(point[0] - field.row, point[1] - field.col);
  return field.intensity * Math.exp(-((distance * distance) / (2 * field.radius * field.radius)));
}

function psrRiskAt(point, scenarioId) {
  const profile = profileForScenario(scenarioId);
  return clamp(profile.psrCenters.reduce((sum, field) => sum + fieldStrength(point, field), 0), 0, 1);
}

function thermalRiskAt(point, scenarioId, triggerLocation, triggerType) {
  const profile = profileForScenario(scenarioId);
  const base = profile.heatCenters.reduce((sum, field) => sum + fieldStrength(point, field), 0);
  const psr = psrRiskAt(point, scenarioId);
  const triggerBoost = triggerType && triggerLocation
    ? fieldStrength(point, {
        row: triggerLocation[0],
        col: triggerLocation[1],
        intensity: triggerType === "thermal_spike" ? 1.15 : triggerType === "new_obstacle" ? 0.62 : 0.34,
        radius: triggerType === "thermal_spike" ? 34 : 28,
      })
    : 0;

  return clamp(base + psr + triggerBoost, 0, 1);
}

function slopeRiskAt(point, scenarioId) {
  const profile = profileForScenario(scenarioId);
  return clamp(profile.slopeCenters.reduce((sum, field) => sum + fieldStrength(point, field), 0), 0, 1);
}

function roughnessAt(point, scenarioId) {
  const profile = profileForScenario(scenarioId);
  return clamp((profile.roughnessCenters ?? []).reduce((sum, field) => sum + fieldStrength(point, field), 0), 0, 1);
}

function elevationAt(point, scenarioId) {
  const profile = profileForScenario(scenarioId);
  const terrain = profile.terrain ?? {};
  const baseElevationM = terrain.baseElevationM ?? -2800;
  const elevationScaleM = terrain.elevationScaleM ?? 1200;
  const relief = (profile.elevationCenters ?? []).reduce((sum, field) => sum + fieldStrength(point, field), 0);
  return baseElevationM + (relief * elevationScaleM);
}

function traversabilityAt(point, scenarioId, triggerLocation, triggerType) {
  const thermal = thermalRiskAt(point, scenarioId, triggerLocation, triggerType);
  const slope = slopeRiskAt(point, scenarioId);
  const roughness = roughnessAt(point, scenarioId);
  const psr = psrRiskAt(point, scenarioId);
  const triggerPenalty = triggerType === "new_obstacle" && triggerLocation
    ? fieldStrength(point, {
        row: triggerLocation[0],
        col: triggerLocation[1],
        intensity: 0.58,
        radius: 22,
      })
    : 0;

  return clamp(0.97 - (slope * 0.38) - (thermal * 0.16) - (roughness * 0.34) - (psr * 0.24) - triggerPenalty, 0.06, 0.98);
}

function routeKindFromWeights(weights) {
  const safetyScore = (weights.w_thermal * 1.22) + (weights.w_energy * 0.68) + (weights.w_slope * 0.42);
  return safetyScore >= (weights.w_dist + 0.78) ? "safe" : "shortest";
}

function safeWaypoints(start, goal, weights, scenarioId) {
  const routeGeometry = profileForScenario(scenarioId).terrain?.routeGeometry ?? {};
  const rowDirection = start[0] <= goal[0] ? 1 : -1;
  const colDirection = start[1] <= goal[1] ? 1 : -1;
  const midRow = Math.round((start[0] + goal[0]) / 2);
  const midCol = Math.round((start[1] + goal[1]) / 2);
  const thermalLift = Math.round((routeGeometry.safeLift ?? 40) + (weights.w_thermal * 18));
  const slopeBias = Math.round((routeGeometry.slopeBias ?? 16) + (weights.w_slope * 10));
  const safeEntryLateral = routeGeometry.safeEntryLateral ?? 18;
  const safeExitLateral = routeGeometry.safeExitLateral ?? 34;

  return [
    start,
    [midRow - (thermalLift * rowDirection), midCol - (safeEntryLateral * colDirection)],
    [midRow - (slopeBias * rowDirection), midCol + (safeExitLateral * colDirection)],
    goal,
  ];
}

function shortestWaypoints(start, goal, scenarioId) {
  const shortestMidBias = profileForScenario(scenarioId).terrain?.routeGeometry?.shortestMidBias ?? 0;
  const midRow = Math.round((start[0] + goal[0]) / 2);
  const midCol = Math.round((start[1] + goal[1]) / 2) + shortestMidBias;
  return [start, [midRow, midCol], goal];
}

function replannedWaypoints(start, goal, triggerType, scenarioId) {
  const routeGeometry = profileForScenario(scenarioId).terrain?.routeGeometry ?? {};
  const rowDirection = start[0] <= goal[0] ? 1 : -1;
  const colDirection = start[1] <= goal[1] ? 1 : -1;
  const midRow = Math.round((start[0] + goal[0]) / 2);
  const midCol = Math.round((start[1] + goal[1]) / 2);
  const lateral = routeGeometry.replanLateral?.[triggerType] ?? (triggerType === "new_obstacle" ? 54 : triggerType === "energy_budget" ? 26 : 42);
  const lead = routeGeometry.replanLead ?? 38;
  const trail = routeGeometry.replanTrail ?? 18;

  return [
    start,
    [midRow - (lead * rowDirection), midCol - (lateral * colDirection)],
    [midRow + (trail * rowDirection), midCol + (lateral * colDirection)],
    goal,
  ];
}

function summarizePath({
  pathGrid,
  metadata,
  weights,
  scenarioId,
  routeKind,
  triggerLocation,
  triggerType,
}) {
  const profile = profileForScenario(scenarioId);
  const terrain = profile.terrain ?? {};
  let safeCells = 0;
  let cautionCells = 0;
  let dangerCells = 0;
  let thermalAccum = 0;
  let maxSlope = 0;
  let traversabilityAccum = 0;
  let psrAccum = 0;
  let cumulativeClimbM = 0;
  let previousElevationM = null;

  pathGrid.forEach((point) => {
    const thermal = thermalRiskAt(point, scenarioId, triggerLocation, triggerType);
    const slope = slopeRiskAt(point, scenarioId);
    const psr = psrRiskAt(point, scenarioId);
    const traversability = traversabilityAt(point, scenarioId, triggerLocation, triggerType);
    const elevationM = elevationAt(point, scenarioId);
    const combined = clamp((thermal * 0.44) + (slope * 0.3) + ((1 - traversability) * 0.22) + (psr * 0.12), 0, 1);

    thermalAccum += thermal;
    maxSlope = Math.max(maxSlope, slope);
    traversabilityAccum += traversability;
    psrAccum += psr;

    if (previousElevationM !== null && elevationM > previousElevationM) {
      cumulativeClimbM += elevationM - previousElevationM;
    }

    previousElevationM = elevationM;

    if (combined >= 0.64) {
      dangerCells += 1;
    } else if (combined >= 0.34) {
      cautionCells += 1;
    } else {
      safeCells += 1;
    }
  });

  const totalDistanceM = Math.round(segmentLengthMeters(pathGrid, metadata.resolution_m));
  const pathLength = Math.max(pathGrid.length, 1);
  const averageThermal = thermalAccum / pathLength;
  const averageTraversability = traversabilityAccum / pathLength;
  const averagePsr = psrAccum / pathLength;
  const thermalModifier = routeKind === "shortest" ? 1.08 : routeKind === "replanned" ? 0.76 : 0.84;
  const slopeModifier = routeKind === "shortest" ? 1.06 : routeKind === "replanned" ? 0.98 : 0.94;
  const totalThermalExposure = Number((((averageThermal * 86 * thermalModifier) + (dangerCells * 0.42) + (averagePsr * 18)).toFixed(1)));
  const maxSlopeDeg = Number((5.8 + (maxSlope * 24.8 * slopeModifier * (terrain.slopeScale ?? 1)) + (weights.w_slope * 0.6)).toFixed(1));
  const terrainDistanceLoad = ((totalDistanceM / 1000) * (0.88 + (weights.w_energy * 0.34) + ((terrain.roverEfficiency ?? 1) * 0.28)));
  const mobilityPenalty = (1 / Math.max(averageTraversability, 0.18)) * 11.5;
  const climbPenalty = cumulativeClimbM / 420;
  const totalEnergyCost = Number((terrainDistanceLoad + mobilityPenalty + climbPenalty + (maxSlopeDeg * 0.46) + (totalThermalExposure * 0.09)).toFixed(1));
  const computationTimeMs = Math.round(
    118
    + (pathGrid.length * 0.68 * (terrain.plannerComplexity ?? 1))
    + (routeKind === "replanned" ? 58 : routeKind === "safe" ? 34 : 16),
  );

  return {
    total_distance_m: totalDistanceM,
    total_thermal_exposure: totalThermalExposure,
    total_energy_cost: totalEnergyCost,
    max_slope_deg: maxSlopeDeg,
    risk_breakdown: {
      safe_cells: safeCells,
      caution_cells: cautionCells,
      danger_cells: dangerCells,
    },
    computation_time_ms: computationTimeMs,
  };
}

export function buildPathResultFromGrid({
  scenarioId,
  pathGrid,
  weights = createWeights(),
  routeKind = "safe",
  triggerType = "",
  triggerLocation = null,
  start = null,
  goal = null,
}) {
  const metadata = resolveGridMetadata(scenarioId);
  const normalizedPathGrid = dedupePath((pathGrid ?? []).map((point) => clampGrid(point, metadata.shape)));
  const startGrid = clampGrid(start ?? normalizedPathGrid[0] ?? metadata.start_grid, metadata.shape);
  const goalGrid = clampGrid(goal ?? normalizedPathGrid[normalizedPathGrid.length - 1] ?? metadata.goal_grid, metadata.shape);
  const effectivePathGrid = normalizedPathGrid.length ? normalizedPathGrid : [startGrid, goalGrid];
  const summary = summarizePath({
    pathGrid: effectivePathGrid,
    metadata,
    weights,
    scenarioId,
    routeKind,
    triggerLocation,
    triggerType,
  });

  return createPathResult({
    route_id: `${routeKind}-${scenarioId}-manual`,
    route_label: routeKind === "shortest" ? "Shortest Path" : routeKind === "replanned" ? "Replanned Route" : "Mission Plan",
    route_strategy: routeKind === "shortest" ? "Distance-priority route" : routeKind === "replanned" ? "Trigger-aware route" : "Thermal-priority route",
    start_grid: startGrid,
    goal_grid: goalGrid,
    path_grid: effectivePathGrid,
    path_geo: effectivePathGrid.map((point) => gridToProjectedPoint(point, metadata)),
    ...summary,
  });
}

export function resolveScenario(scenarioId) {
  return clone(scenariosMock.find((scenario) => scenario.scenario_id === scenarioId) ?? scenariosMock[0]);
}

export function resolveGridMetadata(scenarioId) {
  const scenario = resolveScenario(scenarioId);
  return createGridMetadata({
    ...clone(layersMetadataMock),
    start_grid: scenario.start_grid,
    goal_grid: scenario.goal_grid,
  });
}

export function buildPathResult({
  scenarioId,
  start,
  goal,
  weights = createWeights(),
  routeKind = routeKindFromWeights(weights),
  triggerType = "",
  triggerLocation = null,
}) {
  const metadata = resolveGridMetadata(scenarioId);
  const safeStart = clampGrid(start ?? metadata.start_grid, metadata.shape);
  const safeGoal = clampGrid(goal ?? metadata.goal_grid, metadata.shape);
  const waypoints = routeKind === "shortest"
    ? shortestWaypoints(safeStart, safeGoal, scenarioId)
    : routeKind === "replanned"
      ? replannedWaypoints(safeStart, safeGoal, triggerType, scenarioId)
      : safeWaypoints(safeStart, safeGoal, weights, scenarioId);
  const pathGrid = buildPath(waypoints, metadata.shape);
  const summary = summarizePath({
    pathGrid,
    metadata,
    weights,
    scenarioId,
    routeKind,
    triggerLocation,
    triggerType,
  });

  return createPathResult({
    route_id: `${routeKind}-${scenarioId}`,
    route_label: routeKind === "shortest" ? "Shortest Path" : routeKind === "replanned" ? "Replanned Route" : "Mission Plan",
    route_strategy: routeKind === "shortest" ? "Distance-priority route" : routeKind === "replanned" ? "Trigger-aware route" : "Thermal-priority route",
    start_grid: safeStart,
    goal_grid: safeGoal,
    path_grid: pathGrid,
    path_geo: pathGrid.map((point) => gridToProjectedPoint(point, metadata)),
    ...summary,
  });
}

export function buildComparisonResult({
  scenarioId,
  start,
  goal,
  weights = createWeights(),
}) {
  const safePath = buildPathResult({
    scenarioId,
    start,
    goal,
    weights,
    routeKind: "safe",
  });
  const shortestPath = buildPathResult({
    scenarioId,
    start,
    goal,
    weights,
    routeKind: "shortest",
  });

  return createComparisonResult({
    comparison_id: `compare-${scenarioId}`,
    scenario_id: scenarioId,
    safe_path: safePath,
    shortest_path: shortestPath,
    delta: {
      distance_overhead_pct: percentDelta(safePath.total_distance_m, shortestPath.total_distance_m),
      thermal_reduction_pct: Number(((-percentDelta(safePath.total_thermal_exposure, shortestPath.total_thermal_exposure))).toFixed(1)),
      energy_delta_pct: percentDelta(safePath.total_energy_cost, shortestPath.total_energy_cost),
      recommendation: (
        safePath.total_thermal_exposure < shortestPath.total_thermal_exposure
        && (
          safePath.total_energy_cost <= shortestPath.total_energy_cost * 1.18
          || safePath.total_thermal_exposure <= shortestPath.total_thermal_exposure * 0.88
        )
      ) ? "safe_path_preferred" : "paths_equivalent",
    },
  });
}

export function buildReplanResult({
  scenarioId,
  start,
  goal,
  weights = createWeights(),
  currentPath = null,
  triggerType = "thermal_spike",
  triggerLocation = null,
}) {
  const activeScenario = resolveScenario(scenarioId);
  const baselinePath = Array.isArray(currentPath)
    ? buildPathResultFromGrid({
        scenarioId,
        pathGrid: currentPath,
        weights,
        routeKind: routeKindFromWeights(weights),
        start,
        goal,
      })
    : currentPath?.path_grid
      ? buildPathResultFromGrid({
          scenarioId,
          pathGrid: currentPath.path_grid,
          weights,
          routeKind: routeKindFromWeights(weights),
          start: currentPath.start_grid ?? start,
          goal: currentPath.goal_grid ?? goal,
        })
      : buildPathResult({
          scenarioId,
          start,
          goal,
          weights,
          routeKind: routeKindFromWeights(weights),
        });
  const plannedTriggerLocation = triggerLocation ?? [250, 250];
  const replannedPath = buildPathResult({
    scenarioId,
    start,
    goal,
    weights: {
      ...weights,
      w_thermal: clamp(weights.w_thermal + 0.25, 0, 2),
      w_dist: clamp(weights.w_dist - 0.1, 0, 2),
    },
    routeKind: "replanned",
    triggerType,
    triggerLocation: plannedTriggerLocation,
  });
  const affectedSegmentStart = Math.max(1, Math.floor(baselinePath.path_grid.length * 0.42));

  return createReplanResult({
    replan_needed: true,
    scenario_id: scenarioId,
    trigger_type: triggerType,
    affected_segment_start: affectedSegmentStart,
    baseline_path: baselinePath,
    replanned_path: replannedPath,
    old_segment: baselinePath.path_grid.slice(affectedSegmentStart, affectedSegmentStart + 8),
    new_segment: replannedPath.path_grid.slice(affectedSegmentStart, affectedSegmentStart + 8),
    reason: triggerType === "new_obstacle"
      ? "A new obstacle intersects the active corridor. The route shifts around the blocked cells while preserving traversability."
      : triggerType === "energy_budget"
        ? "Energy budget tightened below the caution band. The route moves toward a smoother corridor to cut energy cost."
        : "Thermal risk crossed the caution threshold near sector 4-B. The route shifts away from the hazard plume.",
    metrics_delta: {
      distance_delta_m: replannedPath.total_distance_m - baselinePath.total_distance_m,
      thermal_delta: Number((replannedPath.total_thermal_exposure - baselinePath.total_thermal_exposure).toFixed(1)),
      energy_delta: Number((replannedPath.total_energy_cost - baselinePath.total_energy_cost).toFixed(1)),
    },
    computation_time_ms: replannedPath.computation_time_ms,
    event_log: [
      {
        id: `${scenarioId}-evt-001`,
        timestamp: "T+00:00",
        level: "info",
        title: "Scenario loaded",
        detail: `${activeScenario.name} scenario initialized with south pole environmental layers.`,
      },
      {
        id: `${scenarioId}-evt-002`,
        timestamp: "T+00:14",
        level: "info",
        title: "Comparison baseline ready",
        detail: "Safe and shortest corridors are available for operator review.",
      },
      {
        id: `${scenarioId}-evt-003`,
        timestamp: "T+02:11",
        level: "warning",
        title: triggerType === "new_obstacle" ? "Obstacle injected" : triggerType === "energy_budget" ? "Energy constraint update" : "Thermal event detected",
        detail: `Trigger location [${plannedTriggerLocation[0]}, ${plannedTriggerLocation[1]}] altered the active corridor state.`,
      },
      {
        id: `${scenarioId}-evt-004`,
        timestamp: "T+02:12",
        level: "success",
        title: "Replan computed",
        detail: `Distance ${replannedPath.total_distance_m.toLocaleString()} m, thermal ${replannedPath.total_thermal_exposure.toFixed(1)}, energy ${replannedPath.total_energy_cost.toFixed(1)}, max slope ${replannedPath.max_slope_deg.toFixed(1)} deg.`,
      },
    ],
  });
}

export function buildSnapshot({
  scenarioId = scenariosMock[0].scenario_id,
  weights = resolveScenario(scenarioId).default_weights,
  start = resolveScenario(scenarioId).start_grid,
  goal = resolveScenario(scenarioId).goal_grid,
}) {
  return {
    scenario: createScenario(resolveScenario(scenarioId)),
    layers_metadata: resolveGridMetadata(scenarioId),
    path_result: buildPathResult({ scenarioId, start, goal, weights }),
    comparison_result: buildComparisonResult({ scenarioId, start, goal, weights }),
    replan_result: buildReplanResult({ scenarioId, start, goal, weights }),
  };
}

export function applyScenarioSnapshot(scenarioId) {
  const scenario = resolveScenario(scenarioId);
  return buildSnapshot({
    scenarioId: scenario.scenario_id,
    weights: scenario.default_weights,
    start: scenario.start_grid,
    goal: scenario.goal_grid,
  });
}
