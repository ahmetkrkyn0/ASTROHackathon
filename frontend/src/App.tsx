import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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

// Modular shell: App knows the slots, never the features.
import { AssistantAskProvider } from './intent/AssistantAskProvider'
import { MissionProvider } from './mission/MissionProvider'
import { MissionRuntimeProvider } from './mission/MissionRuntimeProvider'
import type { MissionActions, MissionRuntime, MissionValue } from './mission/types'
import { OverlayProvider } from './overlay/OverlayProvider'
import SystemsDrawer from './shell/SystemsDrawer'
import {
  BottomDock,
  CanvasOverlaySlot,
  GlobalOverlaySlot,
  LeftRailSlot,
  RightRailSlot,
  StatusBarSlot,
} from './shell/slots'

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
  { label: 'Safe', color: '#4fd08a' },
  { label: 'Caution', color: '#e8c85a' },
  { label: 'High', color: '#f09a4a' },
  { label: 'Critical', color: '#ee5a52' },
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

  // Workstation mode: the two working modes of the design, PLAN and ANALYZE.
  const [missionMode, setMissionMode] = useState<MissionMode>('plan')
  const [isSolving, setIsSolving] = useState(false)

  // Rail and HUD collapse states
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)
  const [hudOpen, setHudOpen] = useState(true)
  const [hudMinimized, setHudMinimized] = useState(false)
  const [systemsOpen, setSystemsOpen] = useState(false)

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
  // Yalnizca setter: bu bayragi okuyan yer kalmadi, kokpit "planlama suruyor"
  // durumunu planningEngaged ve isSolving uzerinden gosteriyor. Bayrak yine de
  // ayarlaniyor cunku istek yasam dongusunu uc yerde isaretliyor.
  const [, setPlanning] = useState(false)
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
    // Diziyi burada yakaliyoruz, temizlikte degil: .current yalnizca push ile
    // buyuyor, hicbir yerde yeniden atanmiyor, dolayisiyla bu referans bilesen
    // yasadigi surece ayni dizi. Yakalamak o degismezi acikca soyluyor ve
    // temizligin baska bir diziyi bosaltma ihtimalini ortadan kaldiriyor.
    const timers = toastTimersRef.current
    return () => {
      timers.forEach((timer) => window.clearTimeout(timer))
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
  const handlePlan = useCallback(async () => {
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
  }, [goal, isSolving, selectedRoverId, start, weights])

  // Reset full mission setup. Every call here is a state setter, so this is
  // stable for the life of the app.
  const handleReset = useCallback(() => {
    setStart(null)
    setGoal(null)
    setPlanResult(null)
    setPlanError(null)
    setClickMode('idle')
    setHoverPoint(null)
    setRoutePlaybackStep(null)
    setMissionMode('plan')
  }, [])

  const toggleHud = useCallback(() => setHudOpen((open) => !open), [])

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
  // MEMOISED. `?? []` her render'da yeni bir dizi kimligi uretiyordu ve bu
  // dizi asagidaki odak telemetrisi efektinin bagimlilik listesinde; plan
  // yokken efekt her render'da yeniden kosardi.
  const waypoints = useMemo(() => planResult?.waypoints ?? [], [planResult])
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

  // Exactly the fields MissionValue declares and no more: an extra one is a
  // compile error, which is what keeps this object honest as the contract
  // grows. Eleven fields already existed under these names; this task adds
  // the four values the mission setup feature needs from its context.
  const missionValue: MissionValue = useMemo(
    () => ({
      gridMeta: elevationLayer
        ? {
            rows: elevationLayer.shape[0],
            cols: elevationLayer.shape[1],
            resolutionM: focusTelemetry.resolutionM,
          }
        : null,
      roverId: selectedRoverId,
      rover: selectedRover,
      rovers,
      weights,
      start,
      goal,
      planResult,
      clickMode,
      isSolving,
      layerError,
      // Always null, and deliberately: this cockpit has no "select a cell"
      // control. Start and goal are placed by mode-scoped clicks and mean
      // "route from here" / "route to here". A feature that wants today's
      // analysis focus calls selectStableAnalysisCell by name.
      selectedCell: null,
      activeViewMode: viewMode,
      dimension,
      missionMode,
    }),
    [
      dimension,
      clickMode,
      elevationLayer,
      focusTelemetry.resolutionM,
      goal,
      isSolving,
      layerError,
      missionMode,
      planResult,
      selectedRover,
      selectedRoverId,
      rovers,
      start,
      viewMode,
      weights,
    ],
  )

  // Writing is a separate contract from reading, so a control panel can take
  // an action without subscribing to the mission snapshot. Every entry is
  // already memoised above; this object exists so the identity of the whole
  // does not churn either.
  const missionActions: MissionActions = useMemo(
    () => ({
      selectRover: handleRoverSelect,
      setWeights,
      setClickMode,
      planRoute: handlePlan,
      resetMission: handleReset,
      setMissionMode,
      setPlaybackStep: setRoutePlaybackStep,
      setPayloadW,
      setHeaterW,
      setViewMode,
      setDimension,
      toggleHud,
    }),
    [handlePlan, handleReset, handleRoverSelect, toggleHud],
  )

  const missionRuntimeValue: MissionRuntime = useMemo(
    () => ({ routePlaybackStep, payloadW, heaterW }),
    [heaterW, payloadW, routePlaybackStep],
  )

  return (
    <MissionProvider
      value={missionValue}
      focusTelemetry={focusTelemetry}
      actions={missionActions}
    >
      <MissionRuntimeProvider value={missionRuntimeValue}>
      <OverlayProvider>
      <AssistantAskProvider>
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
          isSolving={isSolving}
          systemsOpen={systemsOpen}
          onToggleSystems={() => setSystemsOpen((v) => !v)}
        />

        {/* The cockpit. Rover selection is a drawer off the left rail, not a
            stage of its own -- the mission shell never gets replaced. */}
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

              {leftOpen && <LeftRailSlot />}
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

              {/* Primary Map Viewport (2D or 3D). .map-canvas-shell already
                  carries position: relative (App.css:1208), which is what
                  CanvasOverlaySlot sizes itself against. */}
              <div className="map-canvas-shell">
                <CanvasOverlaySlot />
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

            </div>

            <BottomDock />
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

            <RightRailSlot />
          </aside>
        </main>

        {/* ── STATUS STRIP: what the map is showing, and how to move through it ── */}
        <footer className="lp-status-bar">
          <div className="lp-status-left">
            <div className="lp-scale">
              <span className="lp-scale-rule" aria-hidden="true" />
              <span className="lp-scale-copy">
                0 - {focusTelemetry.spanKm.toFixed(1)} km · {focusTelemetry.resolutionM.toFixed(0)} m/px
              </span>
            </div>

            <div className="lp-risk-legend">
              <span className="lp-legend-label">RISK</span>
              {LEGEND_ITEMS.map((item) => (
                <span key={item.label} className="lp-legend-item">
                  <span className="lp-legend-swatch" style={{ background: item.color }} />
                  {item.label}
                </span>
              ))}
            </div>
          </div>

          <div className="lp-status-right">
            <StatusBarSlot />
          </div>
        </footer>

        {/* Application-level floating utilities. Sits immediately before the
            toast stack and shares its parent: shell.css moves the toasts clear
            of an open assistant with a sibling combinator, which needs both. */}
        <GlobalOverlaySlot />

        {/* Systems & Evidence: the diagnostics/proof panels, pulled out of the
            rails so the default cockpit stays task + context. */}
        <SystemsDrawer open={systemsOpen} onClose={() => setSystemsOpen(false)} />

        {/* Floating System Toasts */}
        {toasts.length > 0 && (
          <aside className="toast-stack" aria-live="polite" aria-label="System notifications">
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
      </AssistantAskProvider>
      </OverlayProvider>
      </MissionRuntimeProvider>
    </MissionProvider>
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
