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
import FleetSelectionView from './components/Fleet/FleetSelectionView'
import {
  type AppPhase,
  hrefForLocation,
  locationFromHref,
  phaseFromHref,
} from './shell/phaseUrl'
import { Icon } from './components/Fleet/SpecIcons'
import MapCanvas, { type ClickMode, DOWNSAMPLE, type MapViewMode } from './MapCanvas'
import { generateRockField, type RockDescriptor } from './lidarSimulation'
import { riskToDashArray, riskToHex } from './colormap'
import SpaceBackdrop from './SpaceBackdrop'
import SplashScreen, { type BootStage } from './SplashScreen'
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
import { AssistantAskProvider } from './intent/AssistantAskProvider'
import { MissionProvider } from './mission/MissionProvider'
import { MissionRuntimeProvider } from './mission/MissionRuntimeProvider'
import type { MissionActions, MissionRuntime, MissionValue } from './mission/types'
import { OverlayProvider } from './overlay/OverlayProvider'
import { FEATURES, selectFeatures } from './features/registry'
import { MISSION_EPOCH_UTC } from './mission/missionTime'
import { routeIdentity as computeRouteIdentity } from './mission/routeIdentity'
import { readPlanConstraints, usePlanConstraints } from './features/plan-request'
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
  /**
   * An optional way to carry out what the message asks for.
   *
   * The unreachable-cell warning told the operator to "select an adjacent
   * terrain cell with manageable slope" while the default Surface layer shows
   * no traversability at all -- correct advice that could not be followed on
   * the screen that gave it. `actionLabel` is the id only; App supplies the
   * handler, because the toast builder is a pure function and must stay one.
   */
  actionLabel?: string
  actionId?: 'show-traversability'
}

/**
 * The risk legend, derived rather than transcribed.
 *
 * These four hexes used to be written out here, and they had drifted: the
 * legend taught green for "Safe" while the map drew a safe segment in cyan --
 * a colour distance of 62, so the legend was describing something the map
 * never rendered. Reading riskToHex makes that class of drift impossible.
 *
 * The swatch shows the dash pattern too, because the map now carries risk in
 * the line's pattern as well as its colour, and a legend that showed only
 * colour would document half the encoding.
 */
const LEGEND_ITEMS = [
  { label: 'Safe', level: 'LOW' },
  { label: 'Caution', level: 'MEDIUM' },
  { label: 'High', level: 'HIGH' },
  { label: 'Critical', level: 'CRITICAL' },
] as const

export default function App() {
  // Phase and lifecycle. The address names the stage, so a reload comes back to
  // it instead of restarting the landing sequence.
  const [phase, setPhase] = useState<AppPhase>(() =>
    typeof window === 'undefined' ? 'landing' : phaseFromHref(window.location.href),
  )
  const [bootstrapState, setBootstrapState] = useState<BootstrapState>('loading')
  /* Which step of the bootstrap is running, for the splash to name. Separate
     from bootstrapState, which only says whether it is over. */
  const [bootStage, setBootStage] = useState<BootStage>('health')
  const [splashOpen, setSplashOpen] = useState(true)
  /* The curtain over a stage change: what it says, and what it does when it is
     opaque. Null when nothing is crossing. */
  const [crossing, setCrossing] = useState<{ caption: string; then: () => void } | null>(null)
  const [planningEngaged, setPlanningEngaged] = useState(false)

  // Workstation mode: the two working modes of the design, PLAN and ANALYZE.
  // Seeded from the address like the phase, so ?stage=analysis opens on the
  // analysis rather than opening on plan and then jumping.
  const [missionMode, setMissionMode] = useState<MissionMode>(() =>
    typeof window === 'undefined' ? 'plan' : locationFromHref(window.location.href).mode,
  )
  const [isSolving, setIsSolving] = useState(false)

  // Rail and HUD collapse states
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
      setBootStage('health')
      try {
        const health = await checkHealth()
        if (!health.dem_loaded) {
          setBootStage('dem')
          await loadPreprocessed()
        }

        setBootStage('rovers')
        const roverCatalog = await fetchRovers()
        const initialRoverId = roverCatalog.default_rover_id
        const initialRover =
          roverCatalog.rovers.find((entry) => entry.id === initialRoverId) ?? roverCatalog.rovers[0]
        const initialWeights = initialRover?.default_weights ?? DEFAULT_WEIGHTS

        setBootStage('layers')
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
        setBootStage('ready')
        setBootstrapState('ready')
      } catch (error) {
        setLayerError((error as Error).message)
        setBootstrapState('error')
      }
    }

    void init()
  }, [])

  /**
   * Keep the address and the stage in step, in both directions.
   *
   * The push is guarded by comparing the address against the phase rather than
   * by a flag: after a Back the browser has already rewritten the URL, so the
   * two agree and nothing is pushed. That is what stops the listener below and
   * this effect from feeding each other an endless history.
   */
  useEffect(() => {
    const currentHref = window.location.href
    const shown = locationFromHref(currentHref)
    if (shown.phase === phase && shown.mode === missionMode) return
    window.history.pushState(
      { phase, mode: missionMode },
      '',
      hrefForLocation({ phase, mode: missionMode }, currentHref),
    )
  }, [phase, missionMode])

  useEffect(() => {
    const onPopState = () => {
      const { phase: nextPhase, mode } = locationFromHref(window.location.href)
      setPhase(nextPhase)
      setMissionMode(mode)
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  /**
   * Analysis with nothing to analyse falls back to planning.
   *
   * ?stage=analysis is linkable and survives a reload, but the mission it
   * described does not: route state is deliberately not in the address, so a
   * fresh load of that link arrives with planResult still null. The ANALYZE
   * tab is disabled in that state for exactly this reason -- the address is
   * simply the one way in that can't be disabled.
   *
   * The mode is corrected rather than the panels being left empty, and the
   * effect above then rewrites the address to match, so what is on screen and
   * what the URL claims never disagree. Guarded on `isSolving` because a solve
   * in flight is about to produce the route this is missing; without it,
   * handlePlan's optimistic switch to analyze would be undone mid-flight.
   */
  useEffect(() => {
    if (missionMode === 'analyze' && !planResult && !isSolving) {
      setMissionMode('plan')
    }
  }, [missionMode, planResult, isSolving])

  // Landing hands over to the hangar, not to the map: a rover is chosen
  // before there is a surface to drive it on.
  /* One at a time. The landing button used to call this twice -- once on click
     and again when its own exit timer fired -- which was invisible while this
     only set a phase and would restart the curtain now. */
  const cross = useCallback((caption: string, then: () => void) => {
    setCrossing((current) => (current ? current : { caption, then }))
  }, [])

  /* The two forward stage changes go behind the curtain. "Change vehicle"
     deliberately does not: it is a correction, not a departure, and putting a
     title card in front of someone fixing their rover choice is a toll. */
  const handleEnterMission = useCallback(() => {
    cross('Opening fleet hangar', () => setPhase('fleet'))
  }, [cross])

  const handleDeployToMap = useCallback(() => {
    cross('Deploying to surface map', () => setPhase('app'))
  }, [cross])

  const handleOpenFleetSelect = useCallback(() => {
    setPhase('fleet')
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

  /**
   * Which endpoint was placed last, so it can be taken back.
   *
   * There was no undo at all: the only recovery was Clear, which wiped BOTH
   * endpoints, so one mis-click cost the operator the step they had got
   * right. A single slot is enough -- the task has exactly two placements and
   * a full history would be a stack nobody has a use for.
   */
  const lastPlacementRef = useRef<'start' | 'goal' | null>(null)

  const handleCellClick = useCallback(
    (row: number, col: number) => {
      setPlanResult(null)
      setPlanError(null)
      setIsPlaying(false)
      setPlaybackHours(0)

      if (clickMode === 'start') {
        setStart([row, col])
        setClickMode('goal')
        lastPlacementRef.current = 'start'
      } else if (clickMode === 'goal') {
        setGoal([row, col])
        setClickMode('idle')
        lastPlacementRef.current = 'goal'
      }
    },
    [clickMode],
  )

  /**
   * Typed placement. Same consequences as a click -- the drawn route no longer
   * describes these endpoints, so it goes -- but the picker is left as it was.
   */
  const handlePlaceEndpoint = useCallback(
    (which: 'start' | 'goal', cell: [number, number]) => {
      setPlanResult(null)
      setPlanError(null)
      setIsPlaying(false)
      setPlaybackHours(0)
      if (which === 'start') setStart(cell)
      else setGoal(cell)
      lastPlacementRef.current = which
    },
    [],
  )

  const handleUndoPlacement = useCallback(() => {
    const last = lastPlacementRef.current
    if (!last) {
      return
    }

    // Undoing an endpoint invalidates any route drawn from it, exactly as
    // placing one does.
    setPlanResult(null)
    setPlanError(null)
    setIsPlaying(false)
    setPlaybackHours(0)

    if (last === 'goal') {
      setGoal(null)
      setClickMode('goal')
      lastPlacementRef.current = 'start'
    } else {
      setStart(null)
      setGoal(null)
      setClickMode('start')
      lastPlacementRef.current = null
    }
  }, [])

  // Ctrl+Z / Cmd+Z, the binding every user already has for this. Ignored
  // while a text field has focus so it cannot steal undo from the assistant's
  // composer or a numeric input.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'z' || !(event.ctrlKey || event.metaKey) || event.shiftKey) {
        return
      }
      const target = event.target as HTMLElement | null
      if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) {
        return
      }
      if (!lastPlacementRef.current) {
        return
      }
      event.preventDefault()
      handleUndoPlacement()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [handleUndoPlacement])

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
        // Read at issue time rather than closed over: the operator may have
        // moved a constraint since this handler was created, and the request
        // must carry what is set now.
        readPlanConstraints(),
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
  // What each rail has to show in this mode. Asked of the registry rather
  // than hardcoded per mode, so registering a feature for a rail is the only
  // thing needed to bring its column back.
  //
  // Plan and analyze now use opposite halves of the cockpit: plan owns the
  // left rail and no right one, analyze the right and no left. Neither is
  // stated here -- both fall out of what FEATURES declares.
  const leftRailFeatures = useMemo(
    () => selectFeatures(FEATURES, 'leftRail', missionMode),
    [missionMode],
  )
  const rightRailFeatures = useMemo(
    () => selectFeatures(FEATURES, 'rightRail', missionMode),
    [missionMode],
  )

  const appIsVisible = phase === 'app'

  // The mission clock. Seeded from the canonical epoch rather than from the
  // wall clock so a run is reproducible; see mission/missionTime.ts.
  const [missionTime, setMissionTime] = useState<string>(MISSION_EPOCH_UTC)

  // Derived, never stored: an identity kept in state is one that can be left
  // behind by an input it is supposed to describe. Constraints are empty until
  // the plan-request contributors exist, and an empty object is deliberately
  // identical to no constraints at all -- a feature switched on that sends no
  // field must not invalidate an analysis.
  // Subscribed, not read: a constraint change has to move the identity, which
  // is what marks a post-route analysis stale. The store is module-level so
  // this is the only place in App that knows constraints exist.
  const planConstraints = usePlanConstraints()
  const currentRouteIdentity = useMemo(
    () => computeRouteIdentity({
      roverId: selectedRoverId,
      start,
      goal,
      weights,
      constraints: planConstraints,
    }),
    [goal, planConstraints, selectedRoverId, start, weights],
  )

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
      missionTime,
      routeIdentity: currentRouteIdentity,
    }),
    [
      currentRouteIdentity,
      dimension,
      clickMode,
      elevationLayer,
      focusTelemetry.resolutionM,
      goal,
      isSolving,
      layerError,
      missionMode,
      missionTime,
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
  const handleSplashDone = useCallback(() => setSplashOpen(false), [])

  const missionActions: MissionActions = useMemo(
    () => ({
      selectRover: handleRoverSelect,
      openFleetSelect: handleOpenFleetSelect,
      setWeights,
      setClickMode,
      placeEndpoint: handlePlaceEndpoint,
      planRoute: handlePlan,
      resetMission: handleReset,
      undoPlacement: handleUndoPlacement,
      setMissionMode,
      setMissionTime,
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
    [
      handlePlan,
      handleReset,
      handleRoverSelect,
      handleOpenFleetSelect,
      handlePlaceEndpoint,
      handleUndoPlacement,
      seekPlaybackStep,
      toggleHud,
    ],
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
      <AssistantAskProvider>
      <SpaceBackdrop
        stage={phase === 'app' ? 'deck' : 'ambient'}
        frozen={planningEngaged}
      />

      {/* Over everything, including the landing screen, until the planner has
          something to plan on. */}
      {splashOpen && (
        <SplashScreen
          mode="boot"
          stage={bootStage}
          error={bootstrapState === 'error' ? (layerError ?? 'Bootstrap failed.') : null}
          onDone={handleSplashDone}
        />
      )}

      {crossing && (
        <SplashScreen
          mode="transition"
          caption={crossing.caption}
          onMidpoint={crossing.then}
          onDone={() => setCrossing(null)}
        />
      )}

      {phase === 'landing' && <LandingPage onExplore={handleEnterMission} />}

      {/* Stage 01: the hangar. A full screen of its own between the landing
          sequence and the cockpit -- the rover is picked here, with its specs
          and the route weights in view, before any terrain is shown. */}
      {phase === 'fleet' && (
        <div className="fleet-screen">
          {rovers.length > 0 ? (
            <FleetSelectionView
              rovers={rovers}
              selectedRover={selectedRover}
              onSelectRover={handleRoverSelect}
              onDeployToMap={handleDeployToMap}
            />
          ) : (
            <div className="fleet-screen-loading">
              {bootstrapState === 'error'
                ? layerError ?? 'The rover catalogue could not be loaded.'
                : 'Loading rover catalogue…'}
            </div>
          )}
        </div>
      )}

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

        {/* The cockpit. Rover selection lives in the hangar stage; "Change
            vehicle", under the rover card that prompts the thought, returns
            there rather than opening a modal over the map. */}
        <main
            className={[
              'content-grid',
              leftRailFeatures.length === 0 ? 'no-left-rail' : '',
              rightRailFeatures.length === 0 ? 'no-right-rail' : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            {/* ── LEFT RAIL: MISSION SETUP, IN PLAN ──
                Rendered only when the registry has something for it, exactly
                like the right rail below. In analyze it has nothing, so the
                column goes with it.

                Neither rail collapses any more. They each used to carry a
                40px strip for that, which spent the top of the panel plus a
                hairline on a control for a problem nobody had -- the rails
                hold what the cockpit is driven from, and a folded rail leaves
                a map you cannot plan on. */}
            {leftRailFeatures.length > 0 && (
              <aside className="left-rail">
                <LeftRailSlot />
              </aside>
            )}

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
                        {/* A pulsing dot is a status light, and this readout
                            has no status to report -- it said "live" beside
                            four numbers that are simply where the pointer is.
                            The crosshair says what the panel is instead. */}
                        <Icon name="location" />
                        <span className="lp-hud-title">Surface telemetry</span>
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

            {/* ── STATUS STRIP: what the map is showing, and how to move through it ── */}
            <footer className={`lp-status-bar ${missionMode === 'analyze' ? 'is-analyze' : ''}`}>
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
                      <svg
                        className="lp-legend-line"
                        viewBox="0 0 22 8"
                        aria-hidden="true"
                        focusable="false"
                      >
                        <line
                          x1="1"
                          y1="4"
                          x2="21"
                          y2="4"
                          stroke={riskToHex(item.level)}
                          strokeWidth="2.4"
                          strokeDasharray={riskToDashArray(item.level)}
                        />
                      </svg>
                      {item.label}
                    </span>
                  ))}
                </div>
              </div>

              <div className="lp-status-right">
                <StatusBarSlot />
              </div>
            </footer>
          </section>

          {/* ── RIGHT RAIL: MISSION CONTEXT (PLAN) vs ROUTE ANALYSIS (ANALYZE) ── */}
          {/* The right rail exists only when something is registered for it.
              In plan nothing is: it is a column of readouts, and the map is
              what the operator is actually working in -- so plan gets the
              288px back rather than an empty bordered gutter beside the
              terrain. .content-grid names its third column, so leaving the
              <aside> in place and empty would have kept the column. */}
          {rightRailFeatures.length > 0 && (
            <aside className="right-rail">
              <RightRailSlot />
            </aside>
          )}
        </main>

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
                  {toast.actionId === 'show-traversability' && (
                    <button
                      type="button"
                      className="toast-action"
                      onClick={() => {
                        setViewMode('traversability')
                        dismissToast(toast.id)
                      }}
                    >
                      {toast.actionLabel}
                    </button>
                  )}
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
        'That cell cannot be traversed by the rover envelope. Switch to the traversability layer to see which cells are drivable, then pick one.',
      detail: normalizedDetail,
      actionLabel: 'Show traversable cells',
      actionId: 'show-traversability',
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
