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
  fetchLayer,
  fetchProfiles,
  fetchRovers,
  loadPreprocessed,
  planRoute,
  type LayerResponse,
  type PlanResponse,
  type PlanWeights,
  type ProfileEntry,
  type RoverEntry,
  type Waypoint,
} from './api'
import { batteryToHex, pixelToApproxLonLat, riskToHex } from './colormap'

// ── App ────────────────────────────────────────────────────────────────────────

export default function App() {
  // Rover selection
  const [rovers, setRovers] = useState<Record<string, RoverEntry>>({})
  const [selectedRover, setSelectedRover] = useState<string>('lpr_1')

  // Grid layers
  const [slopeLayer,  setSlopeLayer]  = useState<LayerResponse | null>(null)
  const [travLayer,   setTravLayer]   = useState<LayerResponse | null>(null)
  const [layerError,  setLayerError]  = useState<string | null>(null)
const DEFAULT_WEIGHTS: PlanWeights = {
  w_slope: 0.409,
  w_energy: 0.259,
  w_shadow: 0.142,
  w_thermal: 0.19,
}

const FALLBACK_PROFILES: ProfileEntry[] = [
  {
    id: 'balanced',
    name: 'Balanced',
    color: '#3b82f6',
    weights: DEFAULT_WEIGHTS,
  },
  {
    id: 'energy_saver',
    name: 'Energy Saver',
    color: '#22c55e',
    weights: {
      w_slope: 0.32,
      w_energy: 0.42,
      w_shadow: 0.11,
      w_thermal: 0.15,
    },
  },
  {
    id: 'fast_recon',
    name: 'Fast Recon',
    color: '#ef4444',
    weights: {
      w_slope: 0.48,
      w_energy: 0.16,
      w_shadow: 0.12,
      w_thermal: 0.24,
    },
  },
  {
    id: 'shadow_traverse',
    name: 'Shadow Traverse',
    color: '#a855f7',
    weights: {
      w_slope: 0.34,
      w_energy: 0.2,
      w_shadow: 0.28,
      w_thermal: 0.18,
    },
  },
]

const DEFAULT_POINT: [number, number] = [250, 250]
const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const
const BATTERY_RADIUS = 58
const BATTERY_CIRCUMFERENCE = 2 * Math.PI * BATTERY_RADIUS
const LOADING_STEPS = [
  { delayMs: 160, progress: 28, message: 'Loading terrain matrices...' },
  { delayMs: 640, progress: 56, message: 'Resolving thermal field...' },
  { delayMs: 1120, progress: 82, message: 'Calibrating rover constraints...' },
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
  const [thermalLayer, setThermalLayer] = useState<LayerResponse | null>(null)
  const [traversableLayer, setTraversableLayer] = useState<LayerResponse | null>(null)
  const [layerError, setLayerError] = useState<string | null>(null)

  const [profiles, setProfiles] = useState<ProfileEntry[]>([])
  const [selectedProfile, setSelectedProfile] = useState<string>('balanced')
  const [viewMode, setViewMode] = useState<MapViewMode>('thermal')

  const [clickMode, setClickMode] = useState<ClickMode>('idle')
  const [start, setStart] = useState<[number, number] | null>(null)
  const [goal,  setGoal]  = useState<[number, number] | null>(null)

  // Weights (editable via sliders)
  const [weights, setWeights] = useState<PlanWeights>({
    w_slope: 0.409, w_energy: 0.259, w_shadow: 0.142, w_thermal: 0.190,
  })
  const [goal, setGoal] = useState<[number, number] | null>(null)
  const [weights, setWeights] = useState<PlanWeights>(DEFAULT_WEIGHTS)

  const [planResult, setPlanResult] = useState<PlanResponse | null>(null)
  const [planning, setPlanning] = useState(false)
  const [planError, setPlanError] = useState<string | null>(null)

  const mapRef = useRef<MapCanvasHandle>(null)

  // ── Load layers + rovers on mount ───────────────────────────────────────

  useEffect(() => {
    async function init() {
      setBootstrapState('loading')
      try {
        const health = await checkHealth()
        if (!health.dem_loaded) {
          await loadPreprocessed()
        }
        const [slope, trav, profs, roversResp] = await Promise.all([
          fetchLayer('slope', DOWNSAMPLE),

        const [elevation, thermal, traversable, fetchedProfiles] = await Promise.all([
          fetchLayer('elevation', DOWNSAMPLE),
          fetchLayer('thermal', DOWNSAMPLE),
          fetchLayer('traversable', DOWNSAMPLE),
          fetchProfiles(),
          fetchRovers(),
        ])
        setSlopeLayer(slope)
        setTravLayer(trav)
        setProfiles(profs)
        setRovers(roversResp.rovers)
        setSelectedRover(roversResp.default)

        // Set initial weights from default rover
        const defaultRover = roversResp.rovers[roversResp.default]
        if (defaultRover) {
          setWeights({
            w_slope: defaultRover.w_slope,
            w_energy: defaultRover.w_energy,
            w_shadow: defaultRover.w_shadow,
            w_thermal: defaultRover.w_thermal,
          })
        }
      } catch (e) {
        setLayerError((e as Error).message)

        setElevationLayer(elevation)
        setThermalLayer(thermal)
        setTraversableLayer(traversable)
        setProfiles(fetchedProfiles)
        setBootstrapState('ready')
      } catch (error) {
        setLayerError((error as Error).message)
        setBootstrapState('error')
      }
    }

    void init()
  }, [])

  // ── Rover change → reload layers + profiles ──────────────────────────────

  const handleRoverChange = async (roverId: string) => {
    setSelectedRover(roverId)
    setPlanResult(null)
    setPlanError(null)

    const rover = rovers[roverId]
    if (rover) {
      setWeights({
        w_slope: rover.w_slope,
        w_energy: rover.w_energy,
        w_shadow: rover.w_shadow,
        w_thermal: rover.w_thermal,
      })
    }

    try {
      // Load grids for the new rover
      await loadPreprocessed(roverId)
      const [slope, trav, profs] = await Promise.all([
        fetchLayer('slope', DOWNSAMPLE, roverId),
        fetchLayer('traversable', DOWNSAMPLE, roverId),
        fetchProfiles(roverId),
      ])
      setSlopeLayer(slope)
      setTravLayer(trav)
      setProfiles(profs)
    } catch (e) {
      setLayerError((e as Error).message)
    }
  }

  // ── Profile selection syncs weights ─────────────────────────────────────
  const availableProfiles = profiles.length > 0 ? profiles : FALLBACK_PROFILES

  useEffect(() => {
    if (availableProfiles.some((profile) => profile.id === selectedProfile)) {
      return
    }
    const fallbackProfile = availableProfiles[0]
    if (!fallbackProfile) {
      return
    }
    setSelectedProfile(fallbackProfile.id)
    setWeights(fallbackProfile.weights)
  }, [availableProfiles, selectedProfile])

  const activeProfile =
    availableProfiles.find((profile) => profile.id === selectedProfile) ??
    availableProfiles[0] ??
    FALLBACK_PROFILES[0]

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

  const handleProfileChange = useCallback(
    (profileId: string) => {
      setSelectedProfile(profileId)
      const profile = availableProfiles.find((candidate) => candidate.id === profileId)
      if (profile) {
        setWeights(profile.weights)
      }
      setPlanResult(null)
      setPlanError(null)
    },
    [availableProfiles],
  )

  const handleCellClick = useCallback(
    (row: number, col: number) => {
      setPlanResult(null)
      setPlanError(null)

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

    try {
      const result = await planRoute(start, goal, weights, selectedRover)
      setPlanResult(result)
      setTimeout(() => mapRef.current?.startAnimation(), 100)
    } catch (e) {
      setPlanError((e as Error).message)
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
  }

  const focusTelemetry = buildFocusTelemetry(goal ?? start ?? DEFAULT_POINT, elevationLayer, thermalLayer)
  const summary = planResult?.summary
  const metrics = planResult?.astar_metrics
  const currentRover = rovers[selectedRover]

  return (
    <div style={styles.root}>

      {/* Header */}
      <div style={styles.header}>
        <span style={styles.headerTitle}>LUNAPATH</span>
        <span style={styles.headerSub}>Lunar Rover Route Planner — Lunar South Pole · 500x500 · 80 m/px</span>
  const waypoints = planResult?.waypoints ?? []
  const riskCounts = countRiskLevels(waypoints)
  const totalRiskSamples = RISK_LEVELS.reduce((sum, level) => sum + riskCounts[level], 0)
  const waypointPreview = buildWaypointPreview(waypoints)

  const averageVelocityMs =
    summary && summary.total_elapsed_hours > 0
      ? (summary.total_distance_km * 1000) / (summary.total_elapsed_hours * 3600)
      : 0

  const batteryPct = clamp(summary?.final_battery_pct ?? 67.3, 0, 100)
  const batteryStrokeOffset = BATTERY_CIRCUMFERENCE * (1 - batteryPct / 100)

  const riskState = resolveRiskState(riskCounts)
  const mapStatus =
    clickMode === 'start'
      ? 'Select START on map'
      : clickMode === 'goal'
        ? 'Select GOAL on map'
        : planResult
          ? 'Route ready'
          : 'Standby'

  const hasData = Boolean(elevationLayer && thermalLayer && traversableLayer)
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
          <span className="status-line">MISSION_STATUS: {missionStatus}</span>
          <span className="status-line status-line-muted">
            UPLINK: {hasData ? 'ACTIVE' : 'SYNCING'}
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
                  <p className="panel-kicker">Mission Control</p>
                  <h2 className="panel-title">Sector 7-G</h2>
                </div>
              </div>
            </section>

            <section className="rail-section">
              <p className="eyebrow">Profiles</p>
              <div className="profile-list">
                {availableProfiles.map((profile) => (
                  <button
                    key={profile.id}
                    type="button"
                    className={`profile-button ${profile.id === activeProfile.id ? 'is-active' : ''}`}
                    onClick={() => handleProfileChange(profile.id)}
                    style={{ borderLeftColor: profile.color }}
                  >
                    <span className="profile-name">{profile.name}</span>
                    <span className="profile-id">{profile.id.split('_').join(' ')}</span>
                  </button>
                ))}
              </div>
            </section>

            <section className="rail-section">
              <p className="eyebrow">Route Control</p>
              <div className="coord-chip-grid">
                <button
                  type="button"
                  className={`coord-chip ${clickMode === 'start' ? 'is-start' : ''}`}
                  onClick={() => setClickMode(clickMode === 'start' ? 'idle' : 'start')}
                >
                  {start ? `START ${start[0]},${start[1]}` : 'Set START'}
                </button>
                <button
                  type="button"
                  className={`coord-chip ${clickMode === 'goal' ? 'is-goal' : ''}`}
                  onClick={() => setClickMode(clickMode === 'goal' ? 'idle' : 'goal')}
                >
                  {goal ? `GOAL ${goal[0]},${goal[1]}` : 'Set GOAL'}
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
              <p className="eyebrow">Mission Constraints</p>
              <div className="slider-stack">
                {(Object.keys(weights) as (keyof PlanWeights)[]).map((key) => (
                  <label key={key} className="slider-row">
                    <span className="slider-head">
                      <span className="slider-name">{key}</span>
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

          {/* Rover selector */}
          <div style={styles.row}>
            <span style={styles.label}>Rover:</span>
            <select
              style={styles.select}
              value={selectedRover}
              onChange={e => handleRoverChange(e.target.value)}
            >
              {Object.entries(rovers).map(([id, r]) => (
                <option key={id} value={id}>{r.name}</option>
              ))}
              {Object.keys(rovers).length === 0 && (
                <option value="lpr_1">LPR-1 (default)</option>
              )}
            </select>
          </div>

          {/* Rover specs */}
          {currentRover && (
            <div style={styles.roverSpecs}>
              <span>Mass: {currentRover.mass_kg} kg</span>
              <span>Speed: {currentRover.v_max_ms} m/s</span>
              <span>Battery: {currentRover.e_cap_wh} Wh</span>
              <span>Max slope: {currentRover.slope_max_deg}°</span>
            </div>
          )}

          {/* Coordinate controls */}
          <div style={styles.coordRow}>
            <button
              style={{ ...styles.btn, ...(clickMode === 'start' ? styles.btnActive : {}) }}
              onClick={() => setClickMode(clickMode === 'start' ? 'idle' : 'start')}
            >
              {start ? `START (${start[0]}, ${start[1]})` : 'Set START'}
          <div className="left-actions">
            <button type="button" className="ghost-btn" onClick={handleReset}>
              Reset Selection
            </button>
            <button
              type="button"
              className="primary-btn"
              onClick={handlePlan}
              disabled={!start || !goal || planning}
            >
              {planning ? 'Computing route...' : 'Calculate Route'}
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

            <div className="map-overlay map-overlay-top-center">
              <span className="map-status-tag">{mapStatus}</span>
            </div>

            <div className="map-overlay-top-right">
              <div className="map-switch">
                <button
                  type="button"
                  className={viewMode === 'surface' ? 'is-active' : ''}
                  onClick={() => setViewMode('surface')}
                >
                  Surface
                </button>
                <button
                  type="button"
                  className={viewMode === 'thermal' ? 'is-active' : ''}
                  onClick={() => setViewMode('thermal')}
                >
                  Thermal
                </button>
              </div>
              <div className="map-mode-card">
                <span className="eyebrow tight">View</span>
                <strong>{viewMode === 'surface' ? 'Regolith Hillshade' : 'Thermal Field'}</strong>
              </div>
            </div>

            <div className="map-canvas-shell">
              <MapCanvas
                ref={mapRef}
                elevationGrid={elevationLayer?.data ?? null}
                thermalGrid={thermalLayer?.data ?? null}
                traversableGrid={traversableLayer?.data ?? null}
                waypoints={planResult?.waypoints ?? null}
                start={start}
                goal={goal}
                clickMode={clickMode}
                viewMode={viewMode}
                resolutionM={focusTelemetry.resolutionM}
                onCellClick={handleCellClick}
              />
            </div>

            <div className="map-overlay map-overlay-bottom-left">
              <div className="scale-line" />
              <span className="scale-copy">
                0 - {focusTelemetry.spanKm.toFixed(1)} KM | {focusTelemetry.resolutionM.toFixed(0)} M/PIX
              </span>
            </div>

          {/* Active rover indicator */}
          {planResult?.rover_name && (
            <div style={styles.roverBadge}>
              Rover: {planResult.rover_name}
            </div>
          )}

          {!summary && !planning && (
            <div style={styles.emptyState}>
              Select start and goal on the map, then calculate a route.
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
              <p className="panel-kicker">Telemetry Stream</p>
              <h2 className="panel-title">Route Analytics</h2>
            </div>
            <span className={`signal-dot ${hasData ? 'is-live' : ''}`} />
          </div>

          <div className="telemetry-scroll">
            <section className="telemetry-grid">
              <TelemetryWell
                label="Velocity"
                value={`${averageVelocityMs.toFixed(2)} M/S`}
                accent="#a0a0ff"
              />
              <TelemetryWell
                label="Incline"
                value={summary ? `${summary.max_slope_deg.toFixed(1)} deg` : '--'}
                accent="#adc6ff"
              />
              <TelemetryWell
                label="Temp Ext"
                value={formatTemperature(focusTelemetry.thermalC)}
                accent={focusTelemetry.thermalC !== null && focusTelemetry.thermalC < -150 ? '#ff6d00' : '#00e676'}
              />
              <TelemetryWell
                label="Nodes"
                value={metrics ? String(metrics.nodes_expanded ?? '--') : '--'}
                accent="#00e676"
              />
            </section>

            <section className="battery-card">
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
                  <span>Battery</span>
                </div>
              </div>
            </section>

            <section className="risk-card">
              <div className="risk-head">
                <span className="eyebrow tight">Risk Assessment</span>
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
                <span className="eyebrow tight">Active Waypoints</span>
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

      <footer className="footer-bar">
        <div className="footer-group">
          <span className="footer-live">System Ready</span>
          <span className="footer-copy">PROFILE: {activeProfile.name}</span>
        </div>
        <div className="footer-group footer-group-right">
          <span className="footer-copy">GRID 500 x 500</span>
          <span className="footer-copy">{focusTelemetry.resolutionM.toFixed(0)} M/PIX</span>
        </div>
      </footer>
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

function buildFocusTelemetry(
  point: [number, number],
  elevationLayer: LayerResponse | null,
  thermalLayer: LayerResponse | null,
): FocusTelemetry {
  const row = point[0]
  const col = point[1]
  const metadata = (elevationLayer?.metadata ?? thermalLayer?.metadata ?? {}) as {
    origin?: { x?: number; y?: number }
    resolution_m?: number
    shape?: [number, number]
  }

  const resolutionM = metadata.resolution_m ?? 80
  const shape = Array.isArray(metadata.shape) ? metadata.shape : [500, 500]
  const originX = metadata.origin?.x ?? 176000
  const originY = metadata.origin?.y ?? 48000
  const coords = pixelToApproxLonLat(row, col, {
    originX,
    originY,
    resolutionM,
  })

  return {
    row,
    col,
    lat: coords.lat,
    lon: coords.lon,
    altitudeM: readLayerValue(elevationLayer, row, col),
    thermalC: readLayerValue(thermalLayer, row, col),
    resolutionM,
    spanKm: (shape[0] * resolutionM) / 1000,
  }
}

function readLayerValue(
  layer: LayerResponse | null,
  row: number,
  col: number,
): number | null {
  if (!layer || layer.data.length === 0 || layer.data[0].length === 0) {
    return null
  }

  const dataRow = clamp(Math.floor(row / DOWNSAMPLE), 0, layer.data.length - 1)
  const dataCol = clamp(Math.floor(col / DOWNSAMPLE), 0, layer.data[0].length - 1)
  const value = layer.data[dataRow]?.[dataCol]

  return typeof value === 'number' && Number.isFinite(value) ? value : null
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
        label: 'WP_000',
        detail: 'Await start lock',
        status: 'PEND',
        accent: '#918f9d',
      },
      {
        key: 'wp-track',
        label: 'WP_001',
        detail: 'Await route trace',
        status: 'IDLE',
        accent: '#918f9d',
      },
      {
        key: 'wp-goal',
        label: 'WP_999',
        detail: 'Await goal lock',
        status: 'PEND',
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

    return {
      key: `${waypoint.step}-${index}`,
      label: `WP_${String(waypoint.step).padStart(3, '0')}`,
      detail: `${waypoint.row},${waypoint.col} | ${formatTemperature(waypoint.surface_temp_c)}`,
      status,
      accent: riskToHex(waypoint.risk_level),
    }
  })
}

function formatLatitude(value: number): string {
  const hemisphere = value >= 0 ? 'N' : 'S'
  return `${Math.abs(value).toFixed(4)} deg ${hemisphere}`
}

const LEGEND_ITEMS = [
  { label: 'Flat (0-5°)',     color: '#1e5546' },
  { label: 'Mild (5-10°)',    color: '#509640' },
  { label: 'Moderate (10-15°)', color: '#beb414' },
  { label: 'Steep (15-20°)', color: '#d26e00' },
  { label: 'Near-limit (20-25°)', color: '#be2800' },
  { label: 'Blocked (>=25°)', color: '#5a0505' },
]
function formatLongitude(value: number): string {
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

const styles: Record<string, React.CSSProperties> = {
  root: {
    minHeight: '100vh',
    background: '#080810',
    color: '#c8c8dc',
    fontFamily: "'Courier New', monospace",
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    padding: '10px 20px',
    borderBottom: '1px solid #1a1a3a',
    display: 'flex',
    alignItems: 'baseline',
    gap: 16,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    letterSpacing: 4,
    color: '#a0a0ff',
  },
  headerSub: {
    fontSize: 11,
    color: '#505070',
  },
  body: {
    display: 'flex',
    flex: 1,
    gap: 0,
    overflow: 'hidden',
  },
  leftPanel: {
    flex: '0 0 auto',
    width: 640,
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    borderRight: '1px solid #1a1a3a',
    overflowY: 'auto',
  },
  rightPanel: {
    flex: 1,
    padding: 20,
    overflowY: 'auto',
    minWidth: 260,
  },
  panelTitle: {
    fontSize: 12,
    letterSpacing: 3,
    color: '#6060a0',
    textTransform: 'uppercase',
    marginBottom: 16,
    borderBottom: '1px solid #1a1a3a',
    paddingBottom: 8,
  },
  legend: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '4px 12px',
    fontSize: 10,
    color: '#888',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  legendDot: {
    width: 10,
    height: 10,
    display: 'inline-block',
    borderRadius: 2,
  },
  coordRow: {
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
  },
  btn: {
    background: 'transparent',
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: '#2a2a5a',
    color: '#a0a0d0',
    padding: '5px 12px',
    cursor: 'pointer',
    fontSize: 11,
    fontFamily: 'monospace',
    letterSpacing: 1,
  },
  btnActive: {
    borderColor: '#00e676',
    color: '#00e676',
  },
  btnActiveGoal: {
    borderColor: '#ff1744',
    color: '#ff1744',
  },
  btnGhost: {
    background: 'transparent',
    border: '1px solid #2a2a3a',
    color: '#505060',
    padding: '5px 12px',
    cursor: 'pointer',
    fontSize: 11,
    fontFamily: 'monospace',
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    fontSize: 12,
  },
  label: {
    color: '#606080',
    minWidth: 110,
  },
  select: {
    background: '#0e0e20',
    border: '1px solid #2a2a5a',
    color: '#c8c8dc',
    padding: '4px 8px',
    fontSize: 12,
    fontFamily: 'monospace',
    cursor: 'pointer',
  },
  roverSpecs: {
    display: 'flex',
    gap: 16,
    fontSize: 10,
    color: '#505080',
    padding: '4px 0',
    flexWrap: 'wrap',
  },
  roverBadge: {
    fontSize: 11,
    color: '#8080c0',
    padding: '4px 8px',
    border: '1px solid #2a2a5a',
    marginBottom: 12,
    display: 'inline-block',
  },
  sliders: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  sliderRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  sliderLabel: {
    fontSize: 11,
    color: '#606080',
    minWidth: 80,
  },
  sliderInput: {
    flex: 1,
    accentColor: '#6060ff',
  },
  sliderValue: {
    fontSize: 11,
    color: '#a0a0d0',
    minWidth: 44,
    textAlign: 'right',
  },
  calcBtn: {
    background: '#1a1a4a',
    border: '1px solid #4040a0',
    color: '#a0a0ff',
    padding: '10px',
    fontSize: 13,
    fontFamily: 'monospace',
    letterSpacing: 2,
    width: '100%',
    transition: 'background 0.15s',
  },
  errorBanner: {
    background: '#2a0808',
    border: '1px solid #aa2222',
    color: '#ff8888',
    padding: '6px 10px',
    fontSize: 11,
    fontFamily: 'monospace',
  },
  emptyState: {
    color: '#404060',
    fontSize: 12,
    lineHeight: 1.8,
    marginTop: 20,
  },
  groupTitle: {
    fontSize: 10,
    letterSpacing: 2,
    color: '#4040a0',
    textTransform: 'uppercase',
    marginBottom: 6,
  },
  metricRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '3px 0',
    borderBottom: '1px solid #12122a',
    fontSize: 12,
  },
  metricLabel: {
    color: '#606080',
  },
  metricValue: {
    color: '#c0c0e0',
    fontWeight: 'bold',
  },
function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

const LEGEND_ITEMS = [
  { label: 'Safe', color: '#00e676' },
  { label: 'Caution', color: '#ffea00' },
  { label: 'High', color: '#ff6d00' },
  { label: 'Critical', color: '#ff1744' },
]
