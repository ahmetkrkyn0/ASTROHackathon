import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import LandingPage from './LandingPage'
import MapCanvas, {
  type ClickMode,
  DOWNSAMPLE,
  type MapCanvasHandle,
  type MapViewMode,
} from './MapCanvas'
import {
  checkHealth,
  fetchCellTelemetry,
  fetchLayer,
  loadPreprocessed,
  planRoute,
  type FocusTelemetryResponse,
  type LayerResponse,
  type PlanResponse,
  type PlanWeights,
  type Waypoint,
} from './api'
import { batteryToHex, riskToHex } from './colormap'

const DEFAULT_WEIGHTS: PlanWeights = {
  w_slope: 0.409,
  w_energy: 0.259,
  w_shadow: 0.142,
  w_thermal: 0.19,
}

const DEFAULT_POINT: [number, number] = [250, 250]
const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const
const BATTERY_RADIUS = 58
const BATTERY_CIRCUMFERENCE = 2 * Math.PI * BATTERY_RADIUS
const LOADING_STEPS = [
  { delayMs: 160, progress: 28, message: 'Loading terrain matrices...' },
  { delayMs: 640, progress: 56, message: 'Resolving thermal field...' },
  { delayMs: 1120, progress: 82, message: 'Calibrating rover constraints...' },
] as const
const MAP_VIEW_OPTIONS: Array<{
  id: MapViewMode
  label: string
  title: string
}> = [
  { id: 'surface', label: 'Surface', title: 'Lunar Surface DEM' },
  { id: 'thermal', label: 'Thermal', title: 'Surface Temperature' },
  { id: 'cost', label: 'Cost', title: 'Weighted Cost Grid' },
  { id: 'shadow', label: 'Shadow', title: 'Shadow Ratio' },
  { id: 'traversability', label: 'Traverse', title: 'Traversability Grid' },
  { id: 'slope', label: 'Slope', title: 'Slope Grid' },
  { id: 'aspect', label: 'Aspect', title: 'Aspect Grid' },
] as const
const WEIGHT_CONTROLS: Array<{
  key: keyof PlanWeights
  label: string
}> = [
  { key: 'w_slope', label: 'Slope Safety' },
  { key: 'w_energy', label: 'Energy Use' },
  { key: 'w_shadow', label: 'Shadow Exposure' },
  { key: 'w_thermal', label: 'Thermal Risk' },
] as const

type RiskLevel = (typeof RISK_LEVELS)[number]
type BootstrapState = 'loading' | 'ready' | 'error'
type AppPhase = 'landing' | 'loading' | 'app'

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
  resolutionM: 80,
  spanKm: 40,
}

interface WaypointPreviewItem {
  key: string
  label: string
  detail: string
  status: string
  accent: string
}

export default function App() {
  const [phase, setPhase] = useState<AppPhase>('landing')
  const [bootstrapState, setBootstrapState] = useState<BootstrapState>('loading')
  const [loadingProgress, setLoadingProgress] = useState(0)
  const [loadingMessage, setLoadingMessage] = useState('Initializing navigation systems...')
  const [loadingFloorReached, setLoadingFloorReached] = useState(false)

  const [elevationLayer, setElevationLayer] = useState<LayerResponse | null>(null)
  const [slopeLayer, setSlopeLayer] = useState<LayerResponse | null>(null)
  const [aspectLayer, setAspectLayer] = useState<LayerResponse | null>(null)
  const [shadowLayer, setShadowLayer] = useState<LayerResponse | null>(null)
  const [thermalLayer, setThermalLayer] = useState<LayerResponse | null>(null)
  const [costLayer, setCostLayer] = useState<LayerResponse | null>(null)
  const [traversableLayer, setTraversableLayer] = useState<LayerResponse | null>(null)
  const [layerError, setLayerError] = useState<string | null>(null)

  const [viewMode, setViewMode] = useState<MapViewMode>('surface')

  const [clickMode, setClickMode] = useState<ClickMode>('idle')
  const [start, setStart] = useState<[number, number] | null>(null)
  const [goal, setGoal] = useState<[number, number] | null>(null)
  const [weights, setWeights] = useState<PlanWeights>(DEFAULT_WEIGHTS)

  const [planResult, setPlanResult] = useState<PlanResponse | null>(null)
  const [planning, setPlanning] = useState(false)
  const [planError, setPlanError] = useState<string | null>(null)
  const [focusTelemetry, setFocusTelemetry] = useState<FocusTelemetry>(DEFAULT_FOCUS_TELEMETRY)
  const [routePlaybackStep, setRoutePlaybackStep] = useState<number | null>(null)
  const [hoverPoint, setHoverPoint] = useState<[number, number] | null>(null)

  const mapRef = useRef<MapCanvasHandle>(null)

  useEffect(() => {
    async function init() {
      setBootstrapState('loading')
      try {
        const health = await checkHealth()
        if (!health.dem_loaded) {
          await loadPreprocessed()
        }

        const [elevation, slope, aspect, shadow, thermal, cost, traversable] = await Promise.all([
          fetchLayer('elevation', DOWNSAMPLE),
          fetchLayer('slope', DOWNSAMPLE),
          fetchLayer('aspect', DOWNSAMPLE),
          fetchLayer('shadow_ratio', DOWNSAMPLE),
          fetchLayer('thermal', DOWNSAMPLE),
          fetchLayer('cost', DOWNSAMPLE, { weights }),
          fetchLayer('traversable', DOWNSAMPLE),
        ])

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
    setPhase('loading')
  }, [])

  useEffect(() => {
    if (phase !== 'loading') {
      return
    }

    setLoadingProgress(8)
    setLoadingMessage('Initializing navigation systems...')
    setLoadingFloorReached(false)

    const timers = LOADING_STEPS.map(({ delayMs, progress, message }) =>
      window.setTimeout(() => {
        setLoadingProgress(progress)
        setLoadingMessage(message)
      }, delayMs),
    )

    const floorTimer = window.setTimeout(() => {
      setLoadingFloorReached(true)
    }, 1500)

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer))
      window.clearTimeout(floorTimer)
    }
  }, [phase])

  useEffect(() => {
    if (phase !== 'loading' || !loadingFloorReached || bootstrapState === 'loading') {
      return
    }

    setLoadingProgress(100)
    setLoadingMessage(layerError ? 'Mission control online with warnings' : 'Mission ready')

    const timer = window.setTimeout(() => {
      setPhase('app')
    }, 420)

    return () => window.clearTimeout(timer)
  }, [bootstrapState, layerError, loadingFloorReached, phase])

  useEffect(() => {
    if (bootstrapState === 'loading') {
      return
    }

    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      try {
        const nextCostLayer = await fetchLayer('cost', DOWNSAMPLE, {
          weights,
          signal: controller.signal,
        })
        setCostLayer(nextCostLayer)
        setLayerError(null)
      } catch (error) {
        if (controller.signal.aborted) {
          return
        }
        setLayerError((error as Error).message)
      }
    }, 120)

    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [bootstrapState, weights])

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

  const handlePlan = async () => {
    if (!start || !goal) {
      return
    }

    setPlanning(true)
    setPlanError(null)
    setPlanResult(null)
    setRoutePlaybackStep(null)

    try {
      const result = await planRoute(start, goal, weights)
      setPlanResult(result)
      window.setTimeout(() => mapRef.current?.startAnimation(), 100)
    } catch (error) {
      setPlanError((error as Error).message)
    } finally {
      setPlanning(false)
    }
  }

  const handleReset = () => {
    setStart(null)
    setGoal(null)
    setPlanResult(null)
    setPlanError(null)
    setClickMode('idle')
    setHoverPoint(null)
    setRoutePlaybackStep(null)
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
  const activeMapView = MAP_VIEW_OPTIONS.find((option) => option.id === viewMode) ?? MAP_VIEW_OPTIONS[0]

  useEffect(() => {
    if (hoverPoint === null && routePlaybackStep !== null) {
      return
    }

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
        if (cancelled) {
          return
        }

        setFocusTelemetry(mapFocusTelemetryResponse(telemetry))
      } catch {
        if (controller.signal.aborted) {
          return
        }
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
    if (hoverPoint !== null || routePlaybackStep === null) {
      return
    }

    const activeWaypoint = waypoints[routePlaybackStep]
    if (!activeWaypoint) {
      return
    }

    setFocusTelemetry((current) => mapWaypointToFocusTelemetry(activeWaypoint, current))
  }, [hoverPoint, routePlaybackStep, waypoints])

  const summary = planResult?.summary
  const metrics = planResult?.astar_metrics
  const riskCounts = countRiskLevels(waypoints)
  const totalRiskSamples = RISK_LEVELS.reduce((sum, level) => sum + riskCounts[level], 0)
  const waypointPreview = buildWaypointPreview(waypoints)
  const playbackWaypoint =
    routePlaybackStep !== null && routePlaybackStep >= 0 && routePlaybackStep < waypoints.length
      ? waypoints[routePlaybackStep]
      : null

  const averageVelocityMs =
    summary && summary.total_elapsed_hours > 0
      ? (summary.total_distance_km * 1000) / (summary.total_elapsed_hours * 3600)
      : 0

  const batteryPct = clamp(playbackWaypoint?.battery_pct ?? summary?.final_battery_pct ?? 100, 0, 100)
  const batteryStrokeOffset = BATTERY_CIRCUMFERENCE * (1 - batteryPct / 100)
  const batteryLabel = playbackWaypoint ? 'Live Playback' : summary ? 'Remaining' : 'Starting Reserve'
  const batteryMeta = playbackWaypoint
    ? `Waypoint ${String(playbackWaypoint.step).padStart(3, '0')}`
    : summary
      ? 'Projected after route'
      : 'Mission start default'
  const routeGuidance = !start
    ? 'Choose a start point on the map to begin.'
    : !goal
      ? 'Choose a goal point to unlock route generation.'
      : planResult
        ? 'Route is ready. Hover the map or review checkpoints.'
        : 'Tune priorities if needed, then generate the route.'

  const riskState = resolveRiskState(riskCounts)
  const mapStatus =
    hoverPoint
      ? 'Inspecting terrain'
      : clickMode === 'start'
      ? 'Pick a start point'
      : clickMode === 'goal'
        ? 'Pick a goal point'
        : planResult
          ? 'Route ready'
          : 'Ready to plan'
  const mapStatusTone =
    hoverPoint
      ? 'neutral'
      : clickMode === 'start'
        ? 'safe'
        : clickMode === 'goal'
          ? 'critical'
          : planResult
            ? 'ready'
            : 'idle'

  const missionStatus = layerError ? 'ATTN' : planning ? 'PLANNING' : planResult ? 'LOCKED' : 'NOMINAL'
  const appIsVisible = phase === 'app'

  return (
    <>
      {phase === 'landing' && <LandingPage onExplore={handleEnterMission} />}

      <div className={`loading-screen ${phase === 'loading' ? 'is-active' : ''}`}>
        <div className="loading-frame">
          <span className="loading-brand">LUNAPATH</span>
          <div className="loading-bar-track">
            <div className="loading-bar-fill" style={{ width: `${loadingProgress}%` }} />
          </div>
          <div className="loading-copy-row">
            <span className="loading-copy">{loadingMessage}</span>
            <span className="loading-percent">{Math.round(loadingProgress)}%</span>
          </div>
        </div>
      </div>

      <div className={`app-shell ${appIsVisible ? 'is-visible' : 'is-hidden'}`}>
        <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark">LUNAPATH</span>
        </div>
        <div className="topbar-status">
          <span className="status-line">Mission: {missionStatus}</span>
          <span className="status-line status-line-muted">
            Data link: {hasData ? 'Active' : 'Syncing'}
          </span>
        </div>
      </header>

      <main className="content-grid">
        <aside className="left-rail">
          <div className="rail-scroll">
            <section className="rail-section">
              <div className="rail-section-header">
                <div className="avatar-tile">MC</div>
                <div>
                  <p className="panel-kicker">Mission Workspace</p>
                  <h2 className="panel-title">South Pole Route Planner</h2>
                  <p className="panel-description">
                    Review terrain, place mission points, and generate a safer rover corridor.
                  </p>
                </div>
              </div>
            </section>

            <section className="rail-section">
              <p className="eyebrow">Route Control</p>
              <div className={`status-pill status-pill--${mapStatusTone}`}>{mapStatus}</div>
              <p className="section-note">{routeGuidance}</p>
              <div className="coord-chip-grid">
                <button
                  type="button"
                  className={`coord-chip ${clickMode === 'start' ? 'is-start' : ''}`}
                  onClick={() => setClickMode(clickMode === 'start' ? 'idle' : 'start')}
                >
                  {start ? `START ${start[0]},${start[1]}` : 'Select Start'}
                </button>
                <button
                  type="button"
                  className={`coord-chip ${clickMode === 'goal' ? 'is-goal' : ''}`}
                  onClick={() => setClickMode(clickMode === 'goal' ? 'idle' : 'goal')}
                >
                  {goal ? `GOAL ${goal[0]},${goal[1]}` : 'Select Goal'}
                </button>
              </div>
              <div className="coord-readout">
                <div className="coord-card">
                  <span className="coord-label">Lat / Lon</span>
                  <strong className="coord-value">
                    {formatLatitude(focusTelemetry.lat)} / {formatLongitude(focusTelemetry.lon)}
                  </strong>
                </div>
                <div className="coord-card">
                  <span className="coord-label">Alt / Temp</span>
                  <strong className="coord-value">
                    {formatAltitude(focusTelemetry.altitudeM)} / {formatTemperature(focusTelemetry.thermalC)}
                  </strong>
                </div>
              </div>
            </section>

            <section className="rail-section">
              <p className="eyebrow">Route Priorities</p>
              <p className="section-note">
                Increase a priority to make the planner avoid that condition more aggressively.
              </p>
              <div className="slider-stack">
                {WEIGHT_CONTROLS.map(({ key, label }) => (
                  <label key={key} className="slider-row">
                    <span className="slider-head">
                      <span className="slider-name">{label}</span>
                      <span className="slider-value">{weights[key].toFixed(3)}</span>
                    </span>
                    <input
                      type="range"
                      min={0}
                      max={2}
                      step={0.01}
                      value={weights[key]}
                      onChange={(event) => {
                        const nextValue = Number.parseFloat(event.target.value)
                        setWeights((current) => ({ ...current, [key]: nextValue }))
                        setPlanResult(null)
                        setPlanError(null)
                      }}
                    />
                  </label>
                ))}
              </div>
            </section>

            {layerError && <div className="alert-card">{layerError}</div>}
            {planError && <div className="alert-card">{planError}</div>}
          </div>

          <div className="left-actions">
            <button type="button" className="ghost-btn" onClick={handleReset}>
              Clear Points
            </button>
            <button
              type="button"
              className="primary-btn"
              onClick={handlePlan}
              disabled={!start || !goal || planning}
            >
              {planning ? 'Generating route...' : 'Generate Route'}
            </button>
          </div>
        </aside>

        <section className="center-stage">
          <div className="map-stage">
            <div className="map-overlay map-overlay-top-left">
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
            <div className="map-overlay-top-right">
              <div className="map-switch">
                {MAP_VIEW_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className={viewMode === option.id ? 'is-active' : ''}
                    onClick={() => setViewMode(option.id)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <div className="map-mode-card">
                <span className="eyebrow tight">View</span>
                <strong>{activeMapView.title}</strong>
              </div>
            </div>

            <div className="map-canvas-shell">
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
            </div>

            <div className="map-overlay map-overlay-bottom-left">
              <div className="scale-line" />
              <span className="scale-copy">
                0 - {focusTelemetry.spanKm.toFixed(1)} KM | {focusTelemetry.resolutionM.toFixed(0)} M/PIX
              </span>
            </div>

            <div className="map-overlay map-overlay-bottom-center legend-ribbon">
              {LEGEND_ITEMS.map((item) => (
                <span key={item.label} className="legend-item">
                  <span className="legend-dot" style={{ color: item.color, background: item.color }} />
                  {item.label}
                </span>
              ))}
            </div>
          </div>
        </section>

        <aside className="right-rail">
          <div className="telemetry-header">
            <div>
              <p className="panel-kicker">Mission Snapshot</p>
              <h2 className="panel-title">Route Analytics</h2>
              <p className="panel-description">
                Selected cell telemetry and route health update here as you plan.
              </p>
            </div>
            <span className={`signal-dot ${hasData ? 'is-live' : ''}`} />
          </div>

          <div className="telemetry-scroll">
            <section className="telemetry-grid">
              <TelemetryWell
                label="Route Speed"
                value={`${averageVelocityMs.toFixed(2)} M/S`}
                accent="#a0a0ff"
              />
              <TelemetryWell
                label="Steepest Segment"
                value={summary ? `${summary.max_slope_deg.toFixed(1)} deg` : '--'}
                accent="#adc6ff"
              />
              <TelemetryWell
                label="Cell Temperature"
                value={formatTemperature(focusTelemetry.thermalC)}
                accent={focusTelemetry.thermalC !== null && focusTelemetry.thermalC < -150 ? '#ff6d00' : '#00e676'}
              />
              <TelemetryWell
                label="Planner Effort"
                value={metrics ? String(metrics.nodes_expanded ?? '--') : '--'}
                accent="#00e676"
              />
            </section>

            <section className="battery-card">
              <div className="card-head">
                <span className="eyebrow tight">Battery</span>
                <span className="card-meta">{batteryMeta}</span>
              </div>
              <div className="battery-ring">
                <svg viewBox="0 0 128 128" aria-hidden="true">
                  <circle
                    cx="64"
                    cy="64"
                    r={BATTERY_RADIUS}
                    className="battery-track"
                  />
                  <circle
                    cx="64"
                    cy="64"
                    r={BATTERY_RADIUS}
                    className="battery-progress"
                    stroke={batteryToHex(batteryPct)}
                    strokeDasharray={BATTERY_CIRCUMFERENCE}
                    strokeDashoffset={batteryStrokeOffset}
                  />
                </svg>
                <div className="battery-copy">
                  <strong>{batteryPct.toFixed(1)}%</strong>
                  <span>{batteryLabel}</span>
                </div>
              </div>
            </section>

            <section className="risk-card">
              <div className="risk-head">
                <span className="eyebrow tight">Risk Mix</span>
                <span className="risk-state" style={{ color: riskState.color }}>
                  {riskState.label}
                </span>
              </div>
              <div className="risk-bar">
                {RISK_LEVELS.map((level) => {
                  const width = totalRiskSamples > 0 ? (riskCounts[level] / totalRiskSamples) * 100 : 0
                  return (
                    <div
                      key={level}
                      style={{
                        width: `${width}%`,
                        background: riskToHex(level),
                        opacity: width > 0 ? 1 : 0.18,
                      }}
                    />
                  )
                })}
              </div>
              <div className="risk-count-grid">
                {RISK_LEVELS.map((level) => (
                  <div key={level} className="risk-count-card">
                    <span>{level}</span>
                    <strong style={{ color: riskToHex(level) }}>{riskCounts[level]}</strong>
                  </div>
                ))}
              </div>
            </section>

            <section className="waypoint-card">
              <div className="risk-head">
                <span className="eyebrow tight">Route Milestones</span>
                <span className="waypoint-meta">
                  {summary ? `${summary.waypoint_count} nodes` : 'No route'}
                </span>
              </div>
              <div className="waypoint-list">
                {waypointPreview.map((item) => (
                  <div key={item.key} className="waypoint-row">
                    <div className="waypoint-main">
                      <span className="waypoint-index" style={{ color: item.accent }}>
                        {item.label}
                      </span>
                      <span className="waypoint-detail">{item.detail}</span>
                    </div>
                    <span className="waypoint-status" style={{ color: item.accent }}>
                      {item.status}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </aside>
      </main>
      </div>
    </>
  )
}

function TelemetryWell({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent: string
}) {
  return (
    <div className="telemetry-well" style={{ color: accent }}>
      <span className="telemetry-label">{label}</span>
      <strong className="telemetry-value">{value}</strong>
    </div>
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

function countRiskLevels(waypoints: Waypoint[]): Record<RiskLevel, number> {
  const counts: Record<RiskLevel, number> = {
    LOW: 0,
    MEDIUM: 0,
    HIGH: 0,
    CRITICAL: 0,
  }

  for (const waypoint of waypoints) {
    counts[waypoint.risk_level] += 1
  }

  return counts
}

function resolveRiskState(counts: Record<RiskLevel, number>) {
  if (counts.CRITICAL > 0) {
    return { label: 'CRITICAL', color: '#ff1744' }
  }
  if (counts.HIGH > 0) {
    return { label: 'HIGH', color: '#ff6d00' }
  }
  if (counts.MEDIUM > 0) {
    return { label: 'CAUTION', color: '#ffea00' }
  }
  if (counts.LOW > 0) {
    return { label: 'LOW', color: '#00e676' }
  }
  return { label: 'NO ROUTE', color: '#918f9d' }
}

function buildWaypointPreview(waypoints: Waypoint[]): WaypointPreviewItem[] {
  if (waypoints.length === 0) {
    return [
      {
        key: 'wp-start',
        label: 'START',
        detail: 'Choose a start point',
        status: 'WAIT',
        accent: '#918f9d',
      },
      {
        key: 'wp-track',
        label: 'ROUTE',
        detail: 'Generate a route preview',
        status: 'IDLE',
        accent: '#918f9d',
      },
      {
        key: 'wp-goal',
        label: 'GOAL',
        detail: 'Choose a goal point',
        status: 'WAIT',
        accent: '#918f9d',
      },
    ]
  }

  const lastIndex = waypoints.length - 1
  const indexes = Array.from(
    new Set([0, Math.floor(lastIndex * 0.33), Math.floor(lastIndex * 0.66), lastIndex]),
  )

  return indexes.map((index, position) => {
    const waypoint = waypoints[index]
    const status =
      position === 0 ? 'START' : position === indexes.length - 1 ? 'GOAL' : waypoint.risk_level
    const label =
      position === 0
        ? 'START'
        : position === indexes.length - 1
          ? 'GOAL'
          : `WP ${String(waypoint.step).padStart(3, '0')}`

    return {
      key: `${waypoint.step}-${index}`,
      label,
      detail: `${waypoint.row},${waypoint.col} | ${formatTemperature(waypoint.surface_temp_c)}`,
      status,
      accent: riskToHex(waypoint.risk_level),
    }
  })
}

function formatLatitude(value: number): string {
  if (!Number.isFinite(value)) {
    return '--'
  }
  const hemisphere = value >= 0 ? 'N' : 'S'
  return `${Math.abs(value).toFixed(4)} deg ${hemisphere}`
}

function formatLongitude(value: number): string {
  if (!Number.isFinite(value)) {
    return '--'
  }
  const hemisphere = value >= 0 ? 'E' : 'W'
  return `${Math.abs(value).toFixed(4)} deg ${hemisphere}`
}

function formatAltitude(value: number | null): string {
  if (value === null) {
    return '--'
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)} m`
}

function formatTemperature(value: number | null): string {
  if (value === null) {
    return '--'
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)} C`
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

const LEGEND_ITEMS = [
  { label: 'Safe', color: '#00e676' },
  { label: 'Caution', color: '#ffea00' },
  { label: 'High', color: '#ff6d00' },
  { label: 'Critical', color: '#ff1744' },
]
