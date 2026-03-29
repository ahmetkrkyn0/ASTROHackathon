import React, { useCallback, useEffect, useRef, useState } from 'react'
import MapCanvas, { type ClickMode, DOWNSAMPLE, type MapCanvasHandle } from './MapCanvas'
import {
  checkHealth,
  fetchLayer,
  fetchProfiles,
  loadPreprocessed,
  planRoute,
  type LayerResponse,
  type PlanResponse,
  type PlanWeights,
  type ProfileEntry,
} from './api'
import { batteryToHex, riskToHex } from './colormap'

// ── Default AHP weights (v3.2 frozen) ─────────────────────────────────────────
const DEFAULT_WEIGHTS: PlanWeights = {
  w_slope:   0.409,
  w_energy:  0.259,
  w_shadow:  0.142,
  w_thermal: 0.190,
}

// ── App ────────────────────────────────────────────────────────────────────────

export default function App() {
  // Grid layers
  const [slopeLayer,  setSlopeLayer]  = useState<LayerResponse | null>(null)
  const [travLayer,   setTravLayer]   = useState<LayerResponse | null>(null)
  const [layerError,  setLayerError]  = useState<string | null>(null)

  // Profiles
  const [profiles, setProfiles] = useState<ProfileEntry[]>([])
  const [selectedProfile, setSelectedProfile] = useState<string>('balanced')

  // Coordinate selection
  const [clickMode, setClickMode] = useState<ClickMode>('idle')
  const [start, setStart] = useState<[number, number] | null>(null)
  const [goal,  setGoal]  = useState<[number, number] | null>(null)

  // Weights (editable via sliders)
  const [weights, setWeights] = useState<PlanWeights>(DEFAULT_WEIGHTS)

  // Plan result
  const [planResult, setPlanResult] = useState<PlanResponse | null>(null)
  const [planning,   setPlanning]   = useState(false)
  const [planError,  setPlanError]  = useState<string | null>(null)

  const mapRef = useRef<MapCanvasHandle>(null)

  // ── Load layers on mount ─────────────────────────────────────────────────

  useEffect(() => {
    async function init() {
      try {
        const health = await checkHealth()
        if (!health.dem_loaded) {
          await loadPreprocessed()
        }
        const [slope, trav, profs] = await Promise.all([
          fetchLayer('slope', DOWNSAMPLE),
          fetchLayer('traversable', DOWNSAMPLE),
          fetchProfiles(),
        ])
        setSlopeLayer(slope)
        setTravLayer(trav)
        setProfiles(profs)
      } catch (e) {
        setLayerError((e as Error).message)
      }
    }
    void init()
  }, [])

  // ── Profile selection syncs weights ─────────────────────────────────────

  const handleProfileChange = (profileId: string) => {
    setSelectedProfile(profileId)
    const p = profiles.find(pr => pr.id === profileId)
    if (p) setWeights(p.weights)
  }

  // ── Canvas click ─────────────────────────────────────────────────────────

  const handleCellClick = useCallback((row: number, col: number) => {
    if (clickMode === 'start') {
      setStart([row, col])
      setClickMode('goal')
    } else if (clickMode === 'goal') {
      setGoal([row, col])
      setClickMode('idle')
    }
  }, [clickMode])

  // ── Plan route ───────────────────────────────────────────────────────────

  const handlePlan = async () => {
    if (!start || !goal) return
    setPlanning(true)
    setPlanError(null)
    setPlanResult(null)
    try {
      const result = await planRoute(start, goal, weights)
      setPlanResult(result)
      // Auto-start animation after path loads
      setTimeout(() => mapRef.current?.startAnimation(), 100)
    } catch (e) {
      setPlanError((e as Error).message)
    } finally {
      setPlanning(false)
    }
  }

  // ── Reset ────────────────────────────────────────────────────────────────

  const handleReset = () => {
    setStart(null)
    setGoal(null)
    setPlanResult(null)
    setPlanError(null)
    setClickMode('idle')
  }

  // ── Render ───────────────────────────────────────────────────────────────

  const summary = planResult?.summary
  const metrics = planResult?.astar_metrics

  return (
    <div style={styles.root}>

      {/* Header */}
      <div style={styles.header}>
        <span style={styles.headerTitle}>LUNAPATH</span>
        <span style={styles.headerSub}>Lunar Rover Route Planner — Lunar South Pole · 500×500 · 80 m/px</span>
      </div>

      {/* Body */}
      <div style={styles.body}>

        {/* Left: map + controls */}
        <div style={styles.leftPanel}>

          {layerError && (
            <div style={styles.errorBanner}>
              Backend error: {layerError}
            </div>
          )}

          <MapCanvas
            ref={mapRef}
            slopeGrid={slopeLayer?.data ?? null}
            traversableGrid={travLayer?.data ?? null}
            waypoints={planResult?.waypoints ?? null}
            start={start}
            goal={goal}
            clickMode={clickMode}
            onCellClick={handleCellClick}
          />

          {/* Legend */}
          <div style={styles.legend}>
            {LEGEND_ITEMS.map(item => (
              <span key={item.label} style={styles.legendItem}>
                <span style={{ ...styles.legendDot, background: item.color }} />
                {item.label}
              </span>
            ))}
          </div>

          {/* Coordinate controls */}
          <div style={styles.coordRow}>
            <button
              style={{ ...styles.btn, ...(clickMode === 'start' ? styles.btnActive : {}) }}
              onClick={() => setClickMode(clickMode === 'start' ? 'idle' : 'start')}
            >
              {start ? `START (${start[0]}, ${start[1]})` : 'Set START'}
            </button>
            <button
              style={{ ...styles.btn, ...(clickMode === 'goal' ? styles.btnActiveGoal : {}) }}
              onClick={() => setClickMode(clickMode === 'goal' ? 'idle' : 'goal')}
            >
              {goal ? `GOAL (${goal[0]}, ${goal[1]})` : 'Set GOAL'}
            </button>
            <button style={styles.btnGhost} onClick={handleReset}>
              Reset
            </button>
          </div>

          {/* Profile selector */}
          <div style={styles.row}>
            <span style={styles.label}>Mission profile:</span>
            <select
              style={styles.select}
              value={selectedProfile}
              onChange={e => handleProfileChange(e.target.value)}
            >
              {profiles.length > 0
                ? profiles.map(p => (
                    <option key={p.id} value={p.id}>{p.name ?? p.id}</option>
                  ))
                : FALLBACK_PROFILES.map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
            </select>
          </div>

          {/* Weight sliders */}
          <div style={styles.sliders}>
            {(Object.keys(weights) as (keyof PlanWeights)[]).map(key => (
              <div key={key} style={styles.sliderRow}>
                <span style={styles.sliderLabel}>{key}</span>
                <input
                  type="range"
                  min={0}
                  max={2}
                  step={0.01}
                  value={weights[key]}
                  onChange={e => setWeights(w => ({ ...w, [key]: parseFloat(e.target.value) }))}
                  style={styles.sliderInput}
                />
                <span style={styles.sliderValue}>{weights[key].toFixed(3)}</span>
              </div>
            ))}
          </div>

          {/* Calculate button */}
          <button
            style={{
              ...styles.calcBtn,
              opacity: (!start || !goal || planning) ? 0.4 : 1,
              cursor: (!start || !goal || planning) ? 'not-allowed' : 'pointer',
            }}
            onClick={handlePlan}
            disabled={!start || !goal || planning}
          >
            {planning ? 'Computing A* path...' : 'Calculate Route'}
          </button>

          {planError && (
            <div style={styles.errorBanner}>{planError}</div>
          )}
        </div>

        {/* Right: metrics panel */}
        <div style={styles.rightPanel}>
          <div style={styles.panelTitle}>Mission Telemetry</div>

          {!summary && !planning && (
            <div style={styles.emptyState}>
              Select start and goal on the map, then calculate a route.
            </div>
          )}

          {planning && (
            <div style={styles.emptyState}>Running A* planner...</div>
          )}

          {summary && (
            <>
              <MetricGroup title="Path">
                <Metric label="Distance"      value={`${(summary.total_distance_km * 1000).toFixed(0)} m`} />
                <Metric label="Duration"      value={`${summary.total_elapsed_hours.toFixed(2)} h`} />
                <Metric label="Waypoints"     value={String(summary.waypoint_count)} />
                {metrics && (
                  <Metric label="Nodes expanded" value={String(metrics.nodes_expanded ?? '—')} />
                )}
                {metrics && (
                  <Metric label="Compute time"   value={`${(metrics.computation_time_ms ?? 0).toFixed(0)} ms`} />
                )}
              </MetricGroup>

              <MetricGroup title="Energy">
                <Metric
                  label="Final battery"
                  value={`${summary.final_battery_pct.toFixed(1)} %`}
                  valueStyle={{ color: batteryToHex(summary.final_battery_pct) }}
                />
                <Metric
                  label="Min battery"
                  value={`${summary.min_battery_pct.toFixed(1)} %`}
                  valueStyle={{ color: batteryToHex(summary.min_battery_pct) }}
                />
                <Metric label="Energy used"   value={`${summary.total_energy_consumed_wh.toFixed(1)} Wh`} />
              </MetricGroup>

              <MetricGroup title="Terrain">
                <Metric label="Max slope"     value={`${summary.max_slope_deg.toFixed(1)}°`} />
                <Metric label="Shadow exp."   value={`${summary.total_shadow_exposure.toFixed(3)} h`} />
              </MetricGroup>

              <MetricGroup title="Risk">
                <Metric
                  label="Critical steps"
                  value={String(summary.critical_steps_count)}
                  valueStyle={{ color: summary.critical_steps_count > 0 ? '#ff1744' : '#00e676' }}
                />
                <Metric
                  label="High+ steps"
                  value={String(summary.high_or_above_steps_count)}
                  valueStyle={{ color: summary.high_or_above_steps_count > 0 ? '#ff6d00' : '#00e676' }}
                />
              </MetricGroup>

              {/* Risk bar */}
              <RiskBar waypoints={planResult?.waypoints ?? []} totalSteps={summary.waypoint_count} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function MetricGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={styles.groupTitle}>{title}</div>
      {children}
    </div>
  )
}

function Metric({
  label,
  value,
  valueStyle,
}: {
  label: string
  value: string
  valueStyle?: React.CSSProperties
}) {
  return (
    <div style={styles.metricRow}>
      <span style={styles.metricLabel}>{label}</span>
      <span style={{ ...styles.metricValue, ...valueStyle }}>{value}</span>
    </div>
  )
}

function RiskBar({
  waypoints,
  totalSteps,
}: {
  waypoints: import('./api').Waypoint[]
  totalSteps: number
}) {
  if (waypoints.length === 0) return null
  const levels = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const
  const counts = Object.fromEntries(levels.map(l => [l, 0])) as Record<string, number>
  waypoints.forEach(w => { counts[w.risk_level] = (counts[w.risk_level] ?? 0) + 1 })

  return (
    <div style={{ marginTop: 16 }}>
      <div style={styles.groupTitle}>Risk distribution</div>
      <div style={{ display: 'flex', height: 14, borderRadius: 2, overflow: 'hidden', marginTop: 6 }}>
        {levels.map(l => {
          const pct = (counts[l] / totalSteps) * 100
          if (pct < 0.5) return null
          return (
            <div
              key={l}
              title={`${l}: ${counts[l]} steps (${pct.toFixed(1)}%)`}
              style={{ width: `${pct}%`, background: riskToHex(l) }}
            />
          )
        })}
      </div>
      <div style={{ display: 'flex', gap: 10, marginTop: 6, flexWrap: 'wrap' }}>
        {levels.map(l => (
          <span key={l} style={{ fontSize: 10, color: riskToHex(l), fontFamily: 'monospace' }}>
            {l}: {counts[l]}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Static data ────────────────────────────────────────────────────────────────

const LEGEND_ITEMS = [
  { label: 'Flat (0–5°)',     color: '#1e5546' },
  { label: 'Mild (5–10°)',    color: '#509640' },
  { label: 'Moderate (10–15°)', color: '#beb414' },
  { label: 'Steep (15–20°)', color: '#d26e00' },
  { label: 'Near-limit (20–25°)', color: '#be2800' },
  { label: 'Blocked (≥25°)', color: '#5a0505' },
]

const FALLBACK_PROFILES = [
  { id: 'balanced',        name: 'Balanced' },
  { id: 'energy_saver',    name: 'Energy Saver' },
  { id: 'fast_recon',      name: 'Fast Recon' },
  { id: 'shadow_traverse', name: 'Shadow Traverse' },
]

// ── Styles ─────────────────────────────────────────────────────────────────────

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
    border: '1px solid #2a2a5a',
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
}
