import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import LandingPage from './LandingPage'
import MapCanvas, {
  type ClickMode,
  DOWNSAMPLE,
  type MapCanvasHandle,
  type MapViewMode,
} from './MapCanvas'
import SpaceBackdrop from './SpaceBackdrop'
import TerrainCanvas3D from './TerrainCanvas3D'
import {
  checkHealth,
  fetchCellTelemetry,
  fetchLayer,
  fetchRovers,
  loadPreprocessed,
  planRoute,
  type FocusTelemetryResponse,
  type LayerResponse,
  type PlanResponse,
  type PlanWeights,
  type RoverEntry,
  type Waypoint,
} from './api'

// New Mission Control Workstation Components
import TopBar, { type MissionMode } from './components/TopBar/TopBar'
import LayerDropdown from './components/Map/LayerDropdown'
import RouteSolvingOverlay from './components/Map/RouteSolvingOverlay'
import MissionSetupPanel from './components/Planning/MissionSetupPanel'
import MissionContextPanel from './components/Planning/MissionContextPanel'
import MissionSnapshotPanel from './components/Analysis/MissionSnapshotPanel'
import RouteAnalysisInspector from './components/Analysis/RouteAnalysisInspector'
import PlaybackBar from './components/Analysis/PlaybackBar'
import MissionAssistant from './components/Assistant/MissionAssistant'
import FleetSelectionView from './components/Fleet/FleetSelectionView'

const DEFAULT_WEIGHTS: PlanWeights = {
  w_slope: 0.409,
  w_energy: 0.259,
  w_shadow: 0.142,
  w_thermal: 0.19,
}

const DEFAULT_POINT: [number, number] = [250, 250]
const TOAST_DURATION_MS = 5200
type BootstrapState = 'loading' | 'ready' | 'error'
type AppPhase = 'landing' | 'app'

interface FocusTelemetry {
  row: number
  col: number
  lat: number
  lon: number
  altitudeM: number | null
  thermalC: number | null
  resolutionM: number
  spanKm: number
}

const DEFAULT_FOCUS_TELEMETRY: FocusTelemetry = {
  row: DEFAULT_POINT[0],
  col: DEFAULT_POINT[1],
  lat: Number.NaN,
  lon: Number.NaN,
  altitudeM: null,
  thermalC: null,
  resolutionM: 5,
  spanKm: 2.5,
}

interface ToastItem {
  id: number
  title: string
  message: string
  detail?: string
  tone: 'warning' | 'error'
}

const LEGEND_ITEMS = [
  { label: 'Safe', color: '#22c55e' },
  { label: 'Caution', color: '#eab308' },
  { label: 'High', color: '#f97316' },
  { label: 'Critical', color: '#ef4444' },
]

export default function App() {
  // Phase and lifecycle: defaults to landing or direct to app if specified in URL
  const [phase, setPhase] = useState<AppPhase>(() => {
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href)
      if (url.searchParams.has('app') || url.hash.includes('planner')) {
        return 'app'
      }
    }
    return 'landing'
  })
  const [bootstrapState, setBootstrapState] = useState<BootstrapState>('loading')
  const [planningEngaged, setPlanningEngaged] = useState(false)

  // Workstation mode: 'fleet', 'plan', or 'analyze'
  const [missionMode, setMissionMode] = useState<MissionMode>('fleet')
  const [isSolving, setIsSolving] = useState(false)

  // Rail and HUD collapse states
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)
  const [hudOpen, setHudOpen] = useState(true)
  const [hudMinimized, setHudMinimized] = useState(false)

  // Raster layers
  const [elevationLayer, setElevationLayer] = useState<LayerResponse | null>(null)
  const [slopeLayer, setSlopeLayer] = useState<LayerResponse | null>(null)
  const [aspectLayer, setAspectLayer] = useState<LayerResponse | null>(null)
  const [shadowLayer, setShadowLayer] = useState<LayerResponse | null>(null)
  const [thermalLayer, setThermalLayer] = useState<LayerResponse | null>(null)
  const [costLayer, setCostLayer] = useState<LayerResponse | null>(null)
  const [traversableLayer, setTraversableLayer] = useState<LayerResponse | null>(null)
  const [layerError, setLayerError] = useState<string | null>(null)

  // Map & 3D controls
  const [viewMode, setViewMode] = useState<MapViewMode>('surface')
  const [dimension, setDimension] = useState<'2d' | '3d'>('2d')
  const [sliceIndex, setSliceIndex] = useState(0)
  const [terrainSlices, setTerrainSlices] = useState(0)
  const [photoDrape, setPhotoDrape] = useState(false)

  // Payload simulator specs
  const [payloadW, setPayloadW] = useState(35)
  const [heaterW, setHeaterW] = useState(10)

  // Mission setup & targets
  const [clickMode, setClickMode] = useState<ClickMode>('idle')
  const [start, setStart] = useState<[number, number] | null>(null)
  const [goal, setGoal] = useState<[number, number] | null>(null)
  const [weights, setWeights] = useState<PlanWeights>(DEFAULT_WEIGHTS)
  const [rovers, setRovers] = useState<RoverEntry[]>([])
  const [selectedRoverId, setSelectedRoverId] = useState('lpr_1')

  // Computed route
  const [planResult, setPlanResult] = useState<PlanResponse | null>(null)
  const [planning, setPlanning] = useState(false)
  const [planError, setPlanError] = useState<string | null>(null)
  const [focusTelemetry, setFocusTelemetry] = useState<FocusTelemetry>(DEFAULT_FOCUS_TELEMETRY)
  const [routePlaybackStep, setRoutePlaybackStep] = useState<number | null>(null)
  const [hoverPoint, setHoverPoint] = useState<[number, number] | null>(null)
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const mapRef = useRef<MapCanvasHandle>(null)
  const toastIdRef = useRef(0)
  const toastTimersRef = useRef<number[]>([])

  const dismissToast = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const pushToast = useCallback(
    (toast: Omit<ToastItem, 'id'>) => {
      const id = toastIdRef.current + 1
      toastIdRef.current = id
      setToasts((current) => [...current, { ...toast, id }])
      const timer = window.setTimeout(() => dismissToast(id), TOAST_DURATION_MS)
      toastTimersRef.current.push(timer)
    },
    [dismissToast],
  )

  useEffect(() => {
    return () => {
      toastTimersRef.current.forEach((timer) => window.clearTimeout(timer))
    }
  }, [])

  useEffect(() => {
    if (!layerError) return
    pushToast(buildToastNotice('layer', layerError))
  }, [layerError, pushToast])

  useEffect(() => {
    if (!planError) return
    pushToast(buildToastNotice('plan', planError))
  }, [planError, pushToast])

  // Bootstrap data loading
  useEffect(() => {
    async function init() {
      setBootstrapState('loading')
      try {
        const health = await checkHealth()
        if (!health.dem_loaded) {
          await loadPreprocessed()
        }

        const roverCatalog = await fetchRovers()
        const initialRoverId = roverCatalog.default_rover_id
        const initialRover =
          roverCatalog.rovers.find((entry) => entry.id === initialRoverId) ?? roverCatalog.rovers[0]
        const initialWeights = initialRover?.default_weights ?? DEFAULT_WEIGHTS

        const [elevation, slope, aspect, shadow, thermal, cost, traversable] = await Promise.all([
          fetchLayer('elevation', DOWNSAMPLE, { roverId: initialRoverId }),
          fetchLayer('slope', DOWNSAMPLE, { roverId: initialRoverId }),
          fetchLayer('aspect', DOWNSAMPLE, { roverId: initialRoverId }),
          fetchLayer('shadow_ratio', DOWNSAMPLE, { roverId: initialRoverId }),
          fetchLayer('thermal', DOWNSAMPLE, { roverId: initialRoverId }),
          fetchLayer('cost', DOWNSAMPLE, { weights: initialWeights, roverId: initialRoverId }),
          fetchLayer('traversable', DOWNSAMPLE, { roverId: initialRoverId }),
        ])

        setRovers(roverCatalog.rovers)
        setSelectedRoverId(initialRoverId)
        setWeights(initialWeights)
        setElevationLayer(elevation)
        setSlopeLayer(slope)
        setAspectLayer(aspect)
        setShadowLayer(shadow)
        setThermalLayer(thermal)
        setCostLayer(cost)
        setTraversableLayer(traversable)
        setBootstrapState('ready')
      } catch (error) {
        setLayerError((error as Error).message)
        setBootstrapState('error')
      }
    }

    void init()
  }, [])

  const handleEnterMission = useCallback(() => {
    setPhase('app')
  }, [])

  useEffect(() => {
    if (clickMode !== 'idle') {
      setPlanningEngaged(true)
    }
  }, [clickMode])

  // Sync traversability when rover changes
  useEffect(() => {
    if (bootstrapState === 'loading') return
    const controller = new AbortController()

    async function syncTraversability() {
      try {
        const nextTraversableLayer = await fetchLayer('traversable', DOWNSAMPLE, {
          roverId: selectedRoverId,
          signal: controller.signal,
        })
        setTraversableLayer(nextTraversableLayer)
        setLayerError(null)
      } catch (error) {
        if (controller.signal.aborted) return
        setLayerError((error as Error).message)
      }
    }

    void syncTraversability()
    return () => controller.abort()
  }, [bootstrapState, selectedRoverId])

  // Sync cost map when weights change
  useEffect(() => {
    if (bootstrapState === 'loading') return
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      try {
        const nextCostLayer = await fetchLayer('cost', DOWNSAMPLE, {
          weights,
          roverId: selectedRoverId,
          signal: controller.signal,
        })
        setCostLayer(nextCostLayer)
        setLayerError(null)
      } catch (error) {
        if (controller.signal.aborted) return
        setLayerError((error as Error).message)
      }
    }, 120)

    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [bootstrapState, selectedRoverId, weights])

  const handleCellClick = useCallback(
    (row: number, col: number) => {
      setPlanResult(null)
      setPlanError(null)
      setRoutePlaybackStep(null)

      if (clickMode === 'start') {
        setStart([row, col])
        setClickMode('goal')
      } else if (clickMode === 'goal') {
        setGoal([row, col])
        setClickMode('idle')
      }
    },
    [clickMode],
  )

  const handleRoverSelect = useCallback(
    (rover: RoverEntry) => {
      if (rover.id === selectedRoverId) return
      setSelectedRoverId(rover.id)
      setWeights(rover.default_weights)
      setPlanResult(null)
      setPlanError(null)
      setRoutePlaybackStep(null)
      setMissionMode('plan')
    },
    [selectedRoverId],
  )

  // Route calculation with authentic solving feedback
  const handlePlan = async () => {
    if (!start || !goal || isSolving) return

    setIsSolving(true)
    setPlanning(true)
    setPlanError(null)
    setPlanResult(null)
    setRoutePlaybackStep(null)

    try {
      const result = await planRoute(start, goal, weights, selectedRoverId)
      // Display the radar scanning search animation briefly for authentic mission control feedback
      window.setTimeout(() => {
        setPlanResult(result)
        setIsSolving(false)
        setPlanning(false)
        setMissionMode('analyze')
        window.setTimeout(() => mapRef.current?.startAnimation(), 100)
      }, 750)
    } catch (error) {
      setIsSolving(false)
      setPlanning(false)
      setPlanError((error as Error).message)
    }
  }

  // Edit & Replan: preserves endpoints and smoothly transitions back to Plan mode
  const handleEditReplan = () => {
    setMissionMode('plan')
  }

  // Reset full mission setup
  const handleReset = () => {
    setStart(null)
    setGoal(null)
    setPlanResult(null)
    setPlanError(null)
    setClickMode('idle')
    setHoverPoint(null)
    setRoutePlaybackStep(null)
    setMissionMode('plan')
  }

  const hasData = Boolean(
    elevationLayer &&
    slopeLayer &&
    aspectLayer &&
    shadowLayer &&
    thermalLayer &&
    costLayer &&
    traversableLayer,
  )
  const focusPoint = goal ?? start ?? DEFAULT_POINT
  const telemetryPoint = hoverPoint ?? focusPoint
  const waypoints = planResult?.waypoints ?? []
  const selectedRover = rovers.find((entry) => entry.id === selectedRoverId) ?? null

  // Telemetry sync
  useEffect(() => {
    if (hoverPoint === null && routePlaybackStep !== null) return
    if (!hasData) {
      setFocusTelemetry(DEFAULT_FOCUS_TELEMETRY)
      return
    }

    const controller = new AbortController()
    let cancelled = false
    const delayMs = hoverPoint ? 90 : 0

    async function syncFocusTelemetry(point: [number, number]) {
      try {
        const telemetry = await fetchCellTelemetry(point[0], point[1], controller.signal)
        if (cancelled) return
        setFocusTelemetry(mapFocusTelemetryResponse(telemetry))
      } catch {
        if (controller.signal.aborted) return
        if (!cancelled) {
          setFocusTelemetry((current) => ({
            ...current,
            row: point[0],
            col: point[1],
          }))
        }
      }
    }

    const timer = window.setTimeout(() => {
      void syncFocusTelemetry(telemetryPoint)
    }, delayMs)

    return () => {
      cancelled = true
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [hasData, hoverPoint, routePlaybackStep, telemetryPoint])

  useEffect(() => {
    if (hoverPoint !== null || routePlaybackStep === null) return
    const activeWaypoint = waypoints[routePlaybackStep]
    if (!activeWaypoint) return
    setFocusTelemetry((current) => mapWaypointToFocusTelemetry(activeWaypoint, current))
  }, [hoverPoint, routePlaybackStep, waypoints])

  const missionStatus = layerError ? 'ATTN' : isSolving ? 'SOLVING' : planResult ? 'LOCKED' : 'NOMINAL'
  const appIsVisible = phase === 'app'

  return (
    <>
      <SpaceBackdrop
        stage={phase === 'landing' ? 'ambient' : 'deck'}
        frozen={planningEngaged}
      />

      {phase === 'landing' && <LandingPage onExplore={handleEnterMission} />}

      <div className={`app-shell ${appIsVisible ? 'is-visible' : 'is-hidden'}`}>
        {/* Modern Mission Control TopBar with PLAN / ANALYZE Switcher */}
        <TopBar
          mode={missionMode}
          onModeChange={setMissionMode}
          hasRoute={Boolean(planResult)}
          missionStatus={missionStatus}
          dataLinkActive={hasData}
          resolutionM={focusTelemetry.resolutionM}
          gridDimensions={[500, 500]}
          isSolving={isSolving}
          leftOpen={leftOpen}
          onToggleLeft={() => setLeftOpen((v) => !v)}
          rightOpen={rightOpen}
          onToggleRight={() => setRightOpen((v) => !v)}
          hudOpen={hudOpen}
          onToggleHud={() => setHudOpen((v) => !v)}
        />

        {/* Main Workstation View: Stage 1 Fleet Selection vs Stage 2/3 Surface Map & Analysis */}
        {missionMode === 'fleet' ? (
          <FleetSelectionView
            rovers={rovers}
            selectedRover={selectedRover}
            onSelectRover={handleRoverSelect}
            weights={weights}
            onWeightsChange={setWeights}
            onDeployToMap={() => setMissionMode('plan')}
          />
        ) : (
          <main
            className={`content-grid ${!leftOpen ? 'left-collapsed' : ''} ${!rightOpen ? 'right-collapsed' : ''}`}
          >
            {/* ── LEFT RAIL: MISSION SETUP (PLAN) vs MISSION SNAPSHOT (ANALYZE) ── */}
            <aside className={`left-rail ${!leftOpen ? 'is-collapsed' : ''}`}>
              <button
                type="button"
                className="rail-toggle rail-toggle--left"
                onClick={() => setLeftOpen((v) => !v)}
                aria-label={leftOpen ? 'Collapse left panel' : 'Expand left panel'}
              >
                {leftOpen ? '\u2039' : '\u203A'}
              </button>

              {leftOpen && (
                <>
                  {missionMode === 'plan' ? (
                    <MissionSetupPanel
                      selectedRover={selectedRover}
                      rovers={rovers}
                      onSelectRover={handleRoverSelect}
                      weights={weights}
                      onWeightsChange={setWeights}
                      start={start}
                      goal={goal}
                      hasRoute={Boolean(planResult)}
                      clickMode={clickMode}
                      onSetClickMode={setClickMode}
                      onPlanRoute={handlePlan}
                      onReset={handleReset}
                      isSolving={isSolving}
                      onOpenFleetHangar={() => setMissionMode('fleet')}
                    />
                ) : (
                  <MissionSnapshotPanel
                    rover={selectedRover}
                    start={start}
                    goal={goal}
                    weights={weights}
                    onEditReplan={handleEditReplan}
                  />
                )}
              </>
            )}
          </aside>

          {/* ── CENTER STAGE: 2D/3D TERRAIN WORKBENCH ───────────────────────── */}
          <section className="center-stage">
            <div className="map-stage">
              {/* Top-Left: Collapsible & Minimizable Surface Telemetry HUD */}
              {hudOpen && (
                hudMinimized ? (
                  <div
                    className="map-overlay map-overlay-top-left lp-hud-minimized"
                    onClick={() => setHudMinimized(false)}
                    title="Click to expand Surface Telemetry HUD"
                  >
                    <span className="lp-hud-min-dot">📍</span>
                    <span className="lp-hud-min-coords">
                      {formatLatitude(focusTelemetry.lat)}, {formatLongitude(focusTelemetry.lon)}
                    </span>
                    <span className="lp-hud-min-sep">·</span>
                    <span className="lp-hud-min-alt">{formatAltitude(focusTelemetry.altitudeM)}</span>
                    <span className="lp-hud-min-expand-icon">▾</span>
                  </div>
                ) : (
                  <div className="map-overlay map-overlay-top-left lp-hud-card">
                    <div className="lp-hud-header">
                      <div className="lp-hud-title-group">
                        <span className="lp-pulse-dot" />
                        <span className="lp-hud-title">SURFACE TELEMETRY</span>
                      </div>
                      <div className="lp-hud-actions">
                        <button
                          type="button"
                          className="lp-hud-btn"
                          onClick={() => setHudMinimized(true)}
                          title="Minimize HUD to compact chip"
                          aria-label="Minimize HUD"
                        >
                          –
                        </button>
                        <button
                          type="button"
                          className="lp-hud-btn"
                          onClick={() => setHudOpen(false)}
                          title="Hide HUD overlay (reopen via top-bar or toolbar)"
                          aria-label="Close HUD"
                        >
                          ✕
                        </button>
                      </div>
                    </div>

                    <div className="map-data-grid">
                      <span className="map-data-label">LAT</span>
                      <span className="map-data-value">{formatLatitude(focusTelemetry.lat)}</span>
                      <span className="map-data-label">LON</span>
                      <span className="map-data-value">{formatLongitude(focusTelemetry.lon)}</span>
                      <span className="map-data-label">ALT</span>
                      <span className="map-data-value">{formatAltitude(focusTelemetry.altitudeM)}</span>
                      <span className="map-data-label">TMP</span>
                      <span className="map-data-value">{formatTemperature(focusTelemetry.thermalC)}</span>
                    </div>

                    {(start || goal) && (
                      <div className="lp-hud-status-strip">
                        {start && (
                          <span className="lp-hud-pill is-start">
                            START [{start[0]}, {start[1]}]
                          </span>
                        )}
                        {goal && (
                          <span className="lp-hud-pill is-goal">
                            GOAL [{goal[0]}, {goal[1]}]
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )
              )}

              {/* Top-Right: Grouped Compact Layer Dropdown, 2D/3D Toggle & HUD Toggle */}
              <div className="map-overlay-top-right">
                <LayerDropdown
                  viewMode={viewMode}
                  onViewModeChange={setViewMode}
                  dimension={dimension}
                  onDimensionChange={setDimension}
                  hudOpen={hudOpen}
                  onToggleHud={() => setHudOpen((v) => !v)}
                />
              </div>

              {/* Route Solving Engineering Animation Overlay */}
              <RouteSolvingOverlay
                isSolving={isSolving}
                start={start}
                goal={goal}
                roverName={selectedRover?.name}
              />

              {/* Primary Map Viewport (2D or 3D) */}
              <div className="map-canvas-shell">
                {dimension === '2d' ? (
                  <MapCanvas
                    ref={mapRef}
                    elevationGrid={elevationLayer?.data ?? null}
                    slopeGrid={slopeLayer?.data ?? null}
                    aspectGrid={aspectLayer?.data ?? null}
                    shadowGrid={shadowLayer?.data ?? null}
                    thermalGrid={thermalLayer?.data ?? null}
                    costGrid={costLayer?.data ?? null}
                    traversableGrid={traversableLayer?.data ?? null}
                    waypoints={planResult?.waypoints ?? null}
                    start={start}
                    goal={goal}
                    clickMode={clickMode}
                    viewMode={viewMode}
                    resolutionM={focusTelemetry.resolutionM}
                    onCellClick={handleCellClick}
                    onAnimationStepChange={setRoutePlaybackStep}
                    onHoverCellChange={setHoverPoint}
                  />
                ) : (
                  <TerrainCanvas3D
                    viewMode={viewMode}
                    waypoints={planResult?.waypoints ?? null}
                    exaggeration={null}
                    sliceIndex={sliceIndex}
                    photo={photoDrape}
                    onReady={({ slices, timeVarying, brightestSlice }) => {
                      setTerrainSlices(timeVarying ? slices : 0)
                      setSliceIndex(brightestSlice)
                    }}
                    onError={(message) =>
                      pushToast({ tone: 'warning', title: '3D Terrain', message })
                    }
                  />
                )}
              </div>

              {/* 3D Sun Position & LROC NAC Photo Drape Controls */}
              {dimension === '3d' && (
                <div className="map-overlay map-overlay-bottom-right terrain3d-time">
                  <label className="terrain3d-photo">
                    <input
                      type="checkbox"
                      checked={photoDrape}
                      onChange={(event) => setPhotoDrape(event.target.checked)}
                    />
                    <span>Photographic Overlay (LROC NAC, 1 m/px)</span>
                  </label>
                  {photoDrape ? (
                    <span className="terrain3d-note">
                      2010 solstice acquisition. Native shadows are fixed to acquisition epoch.
                    </span>
                  ) : (
                    terrainSlices > 1 && (
                      <>
                        <span className="eyebrow tight">
                          Solar Ephemeris · Day {(sliceIndex / 2).toFixed(1)}
                        </span>
                        <input
                          type="range"
                          min={0}
                          max={terrainSlices - 1}
                          step={1}
                          value={sliceIndex}
                          onChange={(event) => setSliceIndex(Number(event.target.value))}
                        />
                      </>
                    )
                  )}
                </div>
              )}

              {/* Playback Scrubber (Analysis Mode Only) */}
              {missionMode === 'analyze' && planResult && (
                <PlaybackBar
                  waypoints={waypoints}
                  currentStep={routePlaybackStep}
                  onStepChange={setRoutePlaybackStep}
                />
              )}

              {/* Bottom-Left Scale Bar */}
              <div className="map-overlay map-overlay-bottom-left">
                <div className="scale-line" />
                <span className="scale-copy">
                  0 - {focusTelemetry.spanKm.toFixed(1)} KM | {focusTelemetry.resolutionM.toFixed(0)} M/PIX
                </span>
              </div>

              {/* Bottom-Center Calibrated Risk Legend Ribbon */}
              <div className="map-overlay map-overlay-bottom-center legend-ribbon">
                {LEGEND_ITEMS.map((item) => (
                  <span key={item.label} className="legend-item">
                    <span
                      className="legend-dot"
                      style={{ color: item.color, background: item.color }}
                    />
                    {item.label}
                  </span>
                ))}
              </div>
            </div>
          </section>

          {/* ── RIGHT RAIL: MISSION CONTEXT (PLAN) vs ROUTE ANALYSIS (ANALYZE) ── */}
          <aside className={`right-rail ${!rightOpen ? 'is-collapsed' : ''}`}>
            <button
              type="button"
              className="rail-toggle rail-toggle--right"
              onClick={() => setRightOpen((v) => !v)}
              aria-label={rightOpen ? 'Collapse right panel' : 'Expand right panel'}
            >
              {rightOpen ? '\u203A' : '\u2039'}
            </button>

            {rightOpen && (
              <>
                {missionMode === 'plan' ? (
                  <MissionContextPanel
                    dataLinkActive={hasData}
                    missionStatus={missionStatus}
                    activeLayer={viewMode}
                    telemetry={focusTelemetry}
                    start={start}
                    goal={goal}
                  />
                ) : planResult ? (
                  <RouteAnalysisInspector
                    planResult={planResult}
                    playbackStep={routePlaybackStep}
                    payloadW={payloadW}
                    heaterW={heaterW}
                    onPayloadWChange={setPayloadW}
                    onHeaterWChange={setHeaterW}
                  />
                ) : (
                  <MissionContextPanel
                    dataLinkActive={hasData}
                    missionStatus={missionStatus}
                    activeLayer={viewMode}
                    telemetry={focusTelemetry}
                    start={start}
                    goal={goal}
                  />
                )}
              </>
            )}
          </aside>
        </main>
      )}

        {/* Global Mission Decision Assistant Instrument */}
        <MissionAssistant
          mode={missionMode}
          selectedRover={selectedRover}
          weights={weights}
          start={start}
          goal={goal}
          planResult={planResult}
        />

        {/* Floating System Toasts */}
        {toasts.length > 0 && (
          <aside className="toast-rack" aria-live="polite" aria-label="System notifications">
            {toasts.map((toast) => (
              <div key={toast.id} className={`toast-card toast-card--${toast.tone}`} role="status">
                <div className="toast-body">
                  <strong className="toast-title">{toast.title}</strong>
                  <p className="toast-message">{toast.message}</p>
                  {toast.detail && <p className="toast-detail">{toast.detail}</p>}
                </div>
                <button
                  type="button"
                  className="toast-dismiss"
                  onClick={() => dismissToast(toast.id)}
                  aria-label="Dismiss notification"
                >
                  ✕
                </button>
              </div>
            ))}
          </aside>
        )}
      </div>
    </>
  )
}

function mapFocusTelemetryResponse(response: FocusTelemetryResponse): FocusTelemetry {
  return {
    row: response.row,
    col: response.col,
    lat: response.lat,
    lon: response.lon,
    altitudeM: response.altitude_m,
    thermalC: response.thermal_c,
    resolutionM: response.resolution_m,
    spanKm: response.span_km,
  }
}

function mapWaypointToFocusTelemetry(waypoint: Waypoint, current: FocusTelemetry): FocusTelemetry {
  return {
    row: waypoint.row,
    col: waypoint.col,
    lat: waypoint.lat,
    lon: waypoint.lon,
    altitudeM: waypoint.altitude_m,
    thermalC: waypoint.surface_temp_c,
    resolutionM: current.resolutionM,
    spanKm: current.spanKm,
  }
}

function formatLatitude(value: number): string {
  if (!Number.isFinite(value)) return '--'
  const hemisphere = value >= 0 ? 'N' : 'S'
  return `${Math.abs(value).toFixed(4)}° ${hemisphere}`
}

function formatLongitude(value: number): string {
  if (!Number.isFinite(value)) return '--'
  const hemisphere = value >= 0 ? 'E' : 'W'
  return `${Math.abs(value).toFixed(4)}° ${hemisphere}`
}

function formatAltitude(value: number | null): string {
  if (value === null) return '--'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)} m`
}

function formatTemperature(value: number | null): string {
  if (value === null) return '--'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)} °C`
}

function buildToastNotice(source: 'layer' | 'plan', detail: string): Omit<ToastItem, 'id'> {
  const normalizedDetail = detail.trim()
  const lowerDetail = normalizedDetail.toLowerCase()

  if (lowerDetail.includes('not traversable')) {
    return {
      tone: 'warning',
      title: 'Selected point is unavailable',
      message:
        'That cell cannot be traversed by the rover envelope. Select an adjacent terrain cell with manageable slope.',
      detail: normalizedDetail,
    }
  }

  if (source === 'plan') {
    return {
      tone: 'warning',
      title: 'Route could not be generated',
      message:
        'The planner could not resolve a continuous safe corridor. Tweak start/goal or relax route priority weights.',
      detail: normalizedDetail,
    }
  }

  return {
    tone: 'error',
    title: 'Terrain data warning',
    message: 'Some terrain data could not be synchronized from the backend raster server.',
    detail: normalizedDetail,
  }
}
