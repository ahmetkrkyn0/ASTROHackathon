import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import './App.css'
import LandingPage from './LandingPage'
import MapCanvas, {
  type ClickMode,
  DOWNSAMPLE,
  type MapCanvasHandle,
  type MapViewMode,
} from './MapCanvas'
import { generateRockField, type RockDescriptor } from './lidarSimulation'
import SpaceBackdrop from './SpaceBackdrop'
import TerrainCanvas3D from './TerrainCanvas3D'
import {
  advancePlaybackHours,
  hoursForStep,
  NOMINAL_ROVER_SPEED_MS,
  resolvePlaybackState,
  stepForHours,
} from './mission/playbackClock'
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
  const [terrainPhotoAvailable, setTerrainPhotoAvailable] = useState(false)

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
  // Computed once per plan, BEFORE calling planRoute, and handed to both the
  // backend (as obstacle_cells, so A* actually routes around them) and
  // TerrainCanvas3D (as the exact rocks to render) -- the same list either
  // side of the request, so what got avoided and what gets drawn can never
  // drift apart the way two independent generateRockField calls could.
  const [obstacleRocks, setObstacleRocks] = useState<RockDescriptor[] | null>(null)
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

  // ONE mission clock, in the planner's own elapsed hours, shared by the 2D
  // map, the 3D scene and the transport bar.
  //
  // There used to be three, and none of them was the rover's speed:
  // MapCanvas stepped a waypoint every 33 ms, the transport bar every 50 ms,
  // and the 3D view compressed the whole traverse into a fixed 10-45 second
  // window. A 230 m route that the planner charges ~20 minutes for finished
  // in under two seconds -- somewhere north of 500x real time, with the
  // factor depending on the route, so nothing on screen could be read as a
  // duration. At timeScale 1 the rover now crosses the ground at exactly the
  // 0.2 m/s the planner charged it for, and any speed-up is a number the
  // operator chose and can see.
  const [playbackHours, setPlaybackHours] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [timeScale, setTimeScale] = useState(1)

  const totalPlaybackHours = planResult?.waypoints[planResult.waypoints.length - 1]?.elapsed_hours ?? 0

  // Read inside the animation frame without making the loop depend on them:
  // re-creating the loop on every waypoint or scale change would reset its
  // frame timing and stutter the drive.
  const waypointsRef = useRef<Waypoint[] | null>(null)
  waypointsRef.current = planResult?.waypoints ?? null
  const timeScaleRef = useRef(timeScale)
  timeScaleRef.current = timeScale
  const roverSpeedRef = useRef(NOMINAL_ROVER_SPEED_MS)

  useEffect(() => {
    if (!isPlaying || totalPlaybackHours <= 0) return

    let raf = 0
    let lastTs: number | null = null
    const tick = (ts: number) => {
      if (lastTs === null) lastTs = ts
      // Clamped: a backgrounded tab hands back one enormous delta on
      // return, which would teleport the rover to the end of the route.
      const deltaMs = Math.min(ts - lastTs, 250)
      lastTs = ts
      setPlaybackHours((previous) => {
        const next = advancePlaybackHours(
          waypointsRef.current,
          previous,
          deltaMs,
          roverSpeedRef.current,
          timeScaleRef.current,
        )
        if (next >= totalPlaybackHours) {
          setIsPlaying(false)
          return totalPlaybackHours
        }
        return next
      })
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [isPlaying, totalPlaybackHours])

  // Everything derived from the clock: which waypoint the rover is on, how
  // far between it and the next, whether this segment is a recharge stop,
  // and the ground speed the planner's own timeline implies.
  const playbackState = useMemo(
    () => resolvePlaybackState(planResult?.waypoints, playbackHours, roverSpeedRef.current),
    [planResult, playbackHours],
  )
  const activeWaypoint3D = playbackState.activeWaypoint
  const roverFraction3D = playbackState.roverFraction

  // Seeking by waypoint index (what the transport bar's scrubber offers)
  // means moving the CLOCK to that waypoint's own timestamp, so every other
  // reader of the clock follows without a second source of truth.
  const seekPlaybackStep: Dispatch<SetStateAction<number | null>> = useCallback((update) => {
    const waypoints = waypointsRef.current
    if (!waypoints || waypoints.length === 0) return
    setPlaybackHours((previousHours) => {
      const nextStep =
        typeof update === 'function' ? update(stepForHours(waypoints, previousHours)) : update
      return hoursForStep(waypoints, nextStep)
    })
  }, [])
  // The 2D map and every panel that reads "which waypoint are we on" follow
  // the same clock rather than a timer of their own.
  const routePlaybackStep = playbackState.stepIndex

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
      setIsPlaying(false)
      setPlaybackHours(0)

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
      setIsPlaying(false)
      setPlaybackHours(0)
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
    setIsPlaying(false)
    setPlaybackHours(0)

    // Seed the rock field from start/goal alone, BEFORE the route exists --
    // the only way for the backend to route around these cells is to know
    // about them before it plans, not after. World<->grid conversion here
    // is the same x = col*stepX - width/2 mapping TerrainCanvas3D uses for
    // every other row/col <-> world placement in the scene.
    let rocks: RockDescriptor[] = []
    if (elevationLayer) {
      const rows = elevationLayer.shape[0]
      const cols = elevationLayer.shape[1]
      const resolutionM = focusTelemetry.resolutionM
      const width = cols * resolutionM
      const depth = rows * resolutionM
      const stepX = width / (cols - 1)
      const stepZ = depth / (rows - 1)
      const toWorld = (row: number, col: number) => ({
        x: col * stepX - width / 2,
        z: row * stepZ - depth / 2,
      })
      const startWorld = toWorld(start[0], start[1])
      const goalWorld = toWorld(goal[0], goal[1])
      const midX = (startWorld.x + goalWorld.x) / 2
      const midZ = (startWorld.z + goalWorld.z) / 2
      const halfDiagonal = Math.hypot(goalWorld.x - startWorld.x, goalWorld.z - startWorld.z) / 2
      const radiusM = Math.min(500, halfDiagonal + 60)
      rocks = generateRockField(midX, midZ, radiusM, { rows, cols, resolutionM })
    }
    setObstacleRocks(rocks.length > 0 ? rocks : null)

    const obstacleCells = new Map<string, [number, number]>()
    for (const rock of rocks) {
      if (rock.row === undefined || rock.col === undefined) continue
      obstacleCells.set(`${rock.row}:${rock.col}`, [rock.row, rock.col])
    }

    try {
      const result = await planRoute(
        start,
        goal,
        weights,
        selectedRoverId,
        Array.from(obstacleCells.values()),
      )
      // Display the radar scanning search animation briefly for authentic mission control feedback
      window.setTimeout(() => {
        setPlanResult(result)
        setIsSolving(false)
        setPlanning(false)
        setMissionMode('analyze')
        window.setTimeout(() => {
          setPlaybackHours(0)
          setIsPlaying(true)
        }, 100)
      }, 750)
    } catch (error) {
      setIsSolving(false)
      setPlanning(false)
      setPlanError((error as Error).message)
    }
  }, [elevationLayer, focusTelemetry.resolutionM, goal, isSolving, selectedRoverId, start, weights])

  // Reset full mission setup. Every call here is a state setter, so this is
  // stable for the life of the app.
  const handleReset = useCallback(() => {
    setStart(null)
    setGoal(null)
    setPlanResult(null)
    setPlanError(null)
    setClickMode('idle')
    setHoverPoint(null)
    setIsPlaying(false)
    setPlaybackHours(0)
    setObstacleRocks(null)
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
  // The clock's recharge-stop test compares against the selected rover's own
  // top speed; a ref rather than a dependency so changing rover never
  // restarts the animation frame loop mid-drive.
  roverSpeedRef.current = selectedRover?.v_max_ms ?? NOMINAL_ROVER_SPEED_MS

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
      setPlaybackStep: seekPlaybackStep,
      setPlaying: setIsPlaying,
      setTimeScale,
      seekPlayback: setPlaybackHours,
      setPayloadW,
      setHeaterW,
      setViewMode,
      setDimension,
      toggleHud,
    }),
    [handlePlan, handleReset, handleRoverSelect, seekPlaybackStep, toggleHud],
  )

  const missionRuntimeValue: MissionRuntime = useMemo(
    () => ({
      routePlaybackStep,
      payloadW,
      heaterW,
      playbackHours,
      playbackTotalHours: totalPlaybackHours,
      isPlaying,
      timeScale,
      isRecharging: playbackState.isRecharging,
      groundSpeedMs: playbackState.groundSpeedMs,
    }),
    [
      heaterW,
      isPlaying,
      payloadW,
      playbackHours,
      playbackState.groundSpeedMs,
      playbackState.isRecharging,
      routePlaybackStep,
      timeScale,
      totalPlaybackHours,
    ],
  )

  return (
    <MissionProvider
      value={missionValue}
      focusTelemetry={focusTelemetry}
      actions={missionActions}
    >
      <MissionRuntimeProvider value={missionRuntimeValue}>
      <OverlayProvider>
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
                    playbackStep={routePlaybackStep}
                    onHoverCellChange={setHoverPoint}
                  />
                ) : (
                  <TerrainCanvas3D
                    viewMode={viewMode}
                    waypoints={planResult?.waypoints ?? null}
                    activeWaypoint={activeWaypoint3D}
                    roverFraction={roverFraction3D}
                    isPlaying={isPlaying}
                    obstacleRocks={obstacleRocks}
                    clickMode={clickMode}
                    onCellClick={handleCellClick}
                    exaggeration={null}
                    sliceIndex={sliceIndex}
                    photo={photoDrape}
                    onReady={({ slices, timeVarying, brightestSlice, photoAvailable }) => {
                      setTerrainSlices(timeVarying ? slices : 0)
                      setSliceIndex(brightestSlice)
                      setTerrainPhotoAvailable(photoAvailable)
                      // Mirror availability: the real NAC crop is strictly
                      // more detailed than the shaded/procedural fallback, so
                      // default to it whenever the current DEM window has one.
                      setPhotoDrape(photoAvailable)
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
                      disabled={!terrainPhotoAvailable}
                      onChange={(event) => setPhotoDrape(event.target.checked)}
                    />
                    <span>
                      {terrainPhotoAvailable
                        ? 'Photographic Overlay (LROC NAC, 1 m/px)'
                        : 'Photographic Overlay (not aligned with current DEM window)'}
                    </span>
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
