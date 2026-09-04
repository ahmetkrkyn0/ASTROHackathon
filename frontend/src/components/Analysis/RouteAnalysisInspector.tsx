import React from 'react'
import type { PlanResponse, Waypoint } from '../../api'
import { batteryToHex, riskToHex } from '../../colormap'

interface RouteAnalysisInspectorProps {
  planResult: PlanResponse
  playbackStep: number | null
  payloadW: number
  heaterW: number
  onPayloadWChange: (val: number) => void
  onHeaterWChange: (val: number) => void
}

const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const

export const RouteAnalysisInspector: React.FC<RouteAnalysisInspectorProps> = ({
  planResult,
  playbackStep,
  payloadW,
  heaterW,
  onPayloadWChange,
  onHeaterWChange,
}) => {
  const { summary, astar_metrics: metrics, waypoints } = planResult

  // Playback waypoint
  const currentWp: Waypoint | null =
    playbackStep !== null && playbackStep >= 0 && playbackStep < waypoints.length
      ? waypoints[playbackStep]
      : null

  // Battery metrics
  const finalBattery = summary?.final_battery_pct ?? 100
  const activeBattery = currentWp ? currentWp.battery_pct : finalBattery

  // LiDAR calculations
  const totalHours = summary?.total_elapsed_hours ?? 0
  const payloadDrawW = Math.max(0, payloadW + heaterW)
  const payloadOverheadWh = totalHours * payloadDrawW
  const roverCapacityWh =
    summary?.total_energy_consumed_wh && finalBattery < 100
      ? summary.total_energy_consumed_wh / ((100 - finalBattery) / 100)
      : 5420
  const payloadOverheadPct = (payloadOverheadWh / roverCapacityWh) * 100
  const payloadAdjustedBatteryPct = Math.max(0, finalBattery - payloadOverheadPct)

  // Speed
  const totalDistM = (summary?.total_distance_km ?? 0) * 1000
  const totalSeconds = totalHours * 3600
  const routeSpeedMs = totalSeconds > 0 ? totalDistM / totalSeconds : 0.2

  // Risk counts
  const riskCounts: Record<string, number> = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 }
  waypoints.forEach((w) => {
    if (w.risk_level) riskCounts[w.risk_level] = (riskCounts[w.risk_level] || 0) + 1
  })
  const totalWaypoints = waypoints.length || 1

  // Overall risk determination
  const criticalPct = (riskCounts.CRITICAL / totalWaypoints) * 100
  const highPct = (riskCounts.HIGH / totalWaypoints) * 100
  let overallRisk: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' = 'LOW'
  if (criticalPct > 0 || (summary?.critical_steps_count ?? 0) > 0) {
    overallRisk = 'CRITICAL'
  } else if (highPct > 5) {
    overallRisk = 'HIGH'
  } else if (highPct > 0 || (riskCounts.MEDIUM / totalWaypoints) * 100 > 25) {
    overallRisk = 'MEDIUM'
  }

  // Milestones sample (Start, quarter, half, three-quarter, steepest, goal)
  const milestones: Array<{ title: string; step: number; wp: Waypoint }> = []
  if (waypoints.length > 0) {
    milestones.push({ title: 'START', step: 0, wp: waypoints[0] })
    if (waypoints.length > 10) {
      const q1 = Math.floor(waypoints.length * 0.25)
      const half = Math.floor(waypoints.length * 0.5)
      const q3 = Math.floor(waypoints.length * 0.75)
      milestones.push({ title: `WP ${String(q1).padStart(3, '0')}`, step: q1, wp: waypoints[q1] })
      milestones.push({ title: `WP ${String(half).padStart(3, '0')}`, step: half, wp: waypoints[half] })
      milestones.push({ title: `WP ${String(q3).padStart(3, '0')}`, step: q3, wp: waypoints[q3] })
    }
    const last = waypoints.length - 1
    milestones.push({ title: 'GOAL', step: last, wp: waypoints[last] })
  }

  return (
    <div className="lp-panel-content">
      {/* ── TIER 1: DECISION SUMMARY ────────────────────────── */}
      <section className="lp-panel-section lp-tier-1-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">TIER 1 · MISSION DECISION SUMMARY</span>
          <span
            className="lp-overall-risk-badge"
            style={{
              borderColor: riskToHex(overallRisk),
              color: riskToHex(overallRisk),
            }}
          >
            OVERALL RISK: {overallRisk}
          </span>
        </div>

        <div className="lp-decision-kpi-grid">
          <div className="lp-decision-kpi">
            <span className="lp-kpi-label">DISTANCE</span>
            <strong className="lp-kpi-val">
              {summary?.total_distance_km ? `${summary.total_distance_km.toFixed(2)} km` : '--'}
            </strong>
          </div>

          <div className="lp-decision-kpi">
            <span className="lp-kpi-label">END BATTERY</span>
            <strong
              className="lp-kpi-val"
              style={{ color: batteryToHex(activeBattery) }}
            >
              {activeBattery.toFixed(1)}%
            </strong>
            {currentWp && <span className="lp-kpi-sub">Step {playbackStep}</span>}
          </div>

          <div className="lp-decision-kpi">
            <span className="lp-kpi-label">ROUTE SPEED</span>
            <strong className="lp-kpi-val">{routeSpeedMs.toFixed(2)} m/s</strong>
          </div>

          <div className="lp-decision-kpi">
            <span className="lp-kpi-label">EST. DURATION</span>
            <strong className="lp-kpi-val">
              {totalHours > 0 ? `${totalHours.toFixed(1)} h` : '--'}
            </strong>
          </div>

          <div className="lp-decision-kpi">
            <span className="lp-kpi-label">ROUTE NODES</span>
            <strong className="lp-kpi-val">{totalWaypoints}</strong>
          </div>

          <div className="lp-decision-kpi">
            <span className="lp-kpi-label">RECHARGES</span>
            <strong className="lp-kpi-val">{summary?.total_recharges ?? 0} stops</strong>
          </div>
        </div>
      </section>

      {/* ── TIER 2: ENGINEERING ANALYSIS ────────────────────── */}
      <section className="lp-panel-section lp-tier-2-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">TIER 2 · ENGINEERING ANALYSIS</span>
        </div>

        {/* Engineering Stats */}
        <div className="lp-eng-stat-grid">
          <div className="lp-eng-stat-cell">
            <span className="lp-spec-label">STEEPEST SEGMENT</span>
            <strong className="lp-spec-val">
              {summary?.max_slope_deg ? `${summary.max_slope_deg.toFixed(1)}°` : '--'}
            </strong>
          </div>
          <div className="lp-eng-stat-cell">
            <span className="lp-spec-label">PLANNER EFFORT</span>
            <strong className="lp-spec-val">
              {metrics?.nodes_expanded ? `${metrics.nodes_expanded} nodes` : '--'}
            </strong>
          </div>
          <div className="lp-eng-stat-cell">
            <span className="lp-spec-label">TOTAL ENERGY</span>
            <strong className="lp-spec-val">
              {summary?.total_energy_consumed_wh
                ? `${summary.total_energy_consumed_wh.toFixed(0)} Wh`
                : '--'}
            </strong>
          </div>
          <div className="lp-eng-stat-cell">
            <span className="lp-spec-label">COMPUTE TIME</span>
            <strong className="lp-spec-val">
              {metrics?.computation_time_ms ? `${metrics.computation_time_ms.toFixed(0)} ms` : '< 50 ms'}
            </strong>
          </div>
        </div>

        {/* Risk Breakdown Bar */}
        <div className="lp-risk-bar-block">
          <div className="lp-slider-head">
            <span className="lp-slider-label">RISK DISTRIBUTION</span>
            <span className="lp-slider-number">{totalWaypoints} waypoints</span>
          </div>
          <div className="lp-risk-segmented-bar">
            {RISK_LEVELS.map((level) => {
              const count = riskCounts[level]
              const pct = (count / totalWaypoints) * 100
              if (pct === 0) return null
              return (
                <div
                  key={level}
                  className="lp-risk-segment"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: riskToHex(level),
                  }}
                  title={`${level}: ${count} (${pct.toFixed(1)}%)`}
                />
              )
            })}
          </div>
          <div className="lp-risk-legend-row">
            {RISK_LEVELS.map((level) => (
              <span key={level} className="lp-risk-legend-item">
                <span
                  className="lp-legend-swatch"
                  style={{ backgroundColor: riskToHex(level) }}
                />
                {level} {((riskCounts[level] / totalWaypoints) * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        </div>

        {/* LiDAR Payload Overhead Calculator */}
        <div className="lp-payload-calculator">
          <div className="lp-slider-head">
            <span className="lp-slider-label">LIDAR SENSOR PAYLOAD PRICING</span>
            <span className="lp-slider-number">{payloadDrawW} W Draw</span>
          </div>
          <p className="lp-section-explainer">
            Simulate optional science payloads against transit battery capacity.
          </p>

          <div className="lp-payload-input-row">
            <label className="lp-payload-field">
              <span>Instrument</span>
              <input
                type="number"
                min={0}
                max={300}
                step={5}
                value={payloadW}
                onChange={(e) => onPayloadWChange(Math.max(0, parseInt(e.target.value) || 0))}
              />
              <span className="lp-unit-tag">W</span>
            </label>

            <label className="lp-payload-field">
              <span>Survival Heater</span>
              <input
                type="number"
                min={0}
                max={150}
                step={5}
                value={heaterW}
                onChange={(e) => onHeaterWChange(Math.max(0, parseInt(e.target.value) || 0))}
              />
              <span className="lp-unit-tag">W</span>
            </label>
          </div>

          <div className="lp-payload-result-row">
            <div>
              <span className="lp-mono-label">OVERHEAD</span>
              <strong className="lp-mono-val">{payloadOverheadWh.toFixed(0)} Wh</strong>
            </div>
            <div>
              <span className="lp-mono-label">BATTERY TAX</span>
              <strong className="lp-mono-val">{payloadOverheadPct.toFixed(1)}%</strong>
            </div>
            <div>
              <span className="lp-mono-label">ARRIVES WITH</span>
              <strong
                className="lp-mono-val"
                style={{ color: batteryToHex(payloadAdjustedBatteryPct) }}
              >
                {payloadAdjustedBatteryPct.toFixed(1)}%
              </strong>
            </div>
          </div>
        </div>
      </section>

      {/* ── TIER 3: DETAILED REVIEW / MILESTONES ─────────────── */}
      <section className="lp-panel-section lp-tier-3-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">TIER 3 · ROUTE MILESTONES TIMELINE</span>
        </div>

        <div className="lp-milestones-timeline">
          {milestones.map(({ title, step, wp }, idx) => (
            <div key={idx} className="lp-milestone-entry">
              <div className="lp-milestone-marker">
                <span
                  className="lp-milestone-dot"
                  style={{ backgroundColor: riskToHex(wp.risk_level) }}
                />
                {idx < milestones.length - 1 && <div className="lp-milestone-stem" />}
              </div>
              <div className="lp-milestone-body">
                <div className="lp-milestone-title-row">
                  <strong className="lp-milestone-title">{title}</strong>
                  <span className="lp-milestone-coord">
                    [{wp.col}, {wp.row}] · {wp.distance_m.toFixed(0)} m
                  </span>
                </div>
                <div className="lp-milestone-sub">
                  <span>Bat: {wp.battery_pct.toFixed(0)}%</span>
                  <span>Slope: {wp.slope_deg.toFixed(1)}°</span>
                  <span>Temp: {wp.surface_temp_c.toFixed(0)}°C</span>
                  <span style={{ color: riskToHex(wp.risk_level) }}>{wp.risk_level}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default RouteAnalysisInspector

