import React from 'react'
import { batteryToHex, riskToHex } from '../../colormap'
import type { Waypoint } from '../../api'
import { useMission, useMissionActions } from '../../mission/MissionContext'
import { useMissionRuntime } from '../../mission/MissionRuntimeContext'

const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const

/** How many of the meter's five segments each verdict fills. */
const RISK_FILL: Record<(typeof RISK_LEVELS)[number], number> = {
  LOW: 2,
  MEDIUM: 3,
  HIGH: 4,
  CRITICAL: 5,
}

/** What the verdict means, in a sentence, beside the word itself. */
const RISK_MEANING: Record<(typeof RISK_LEVELS)[number], string> = {
  LOW: 'Route is safe to drive as planned.',
  MEDIUM: 'Route is feasible with manageable risk.',
  HIGH: 'Route is drivable but carries findings to review before committing.',
  CRITICAL: 'Route is not safe as planned.',
}

/** 88.9025\u00b0 S, 73.9967\u00b0 W -- signed degrees are not how a site is read out. */
function formatLatLon(lat: number, lon: number): string {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return '--'
  const la = `${Math.abs(lat).toFixed(4)}\u00b0 ${lat < 0 ? 'S' : 'N'}`
  const lo = `${Math.abs(lon).toFixed(4)}\u00b0 ${lon < 0 ? 'W' : 'E'}`
  return `${la}, ${lo}`
}

export const RouteAnalysisInspector = () => {
  const { planResult } = useMission()
  // No playback cursor here on purpose: this panel reports the route, and
  // the cursor's own readings belong to the transport bar under the map.
  const { payloadW, heaterW } = useMissionRuntime()
  const { setPayloadW, setHeaterW } = useMissionActions()

  if (!planResult) return null

  const { summary, astar_metrics: metrics, waypoints } = planResult

  /**
   * Battery at the END of the route, which is what this panel's label says.
   *
   * It used to fall back to the playback cursor's waypoint, so during playback
   * a figure labelled "End battery" showed the battery right now -- the same
   * number the transport bar under the map was already showing, under a label
   * that meant something else. This panel reports the route; the cursor's
   * values are the transport bar's job and are two inches away.
   */
  const finalBattery = summary?.final_battery_pct ?? 100

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
  const firstWp = waypoints[0] ?? null
  const lastWp = waypoints.length > 0 ? waypoints[waypoints.length - 1] : null

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
      {/* ── The route this panel is about ──
          Start and goal used to be pills on the map HUD, over the terrain and
          duplicating the left rail. Here they are the heading of the analysis
          that describes them, with the coordinates the operator would actually
          quote -- the waypoints already carry lat/lon, so nothing is derived. */}
      <section className="lp-panel-section lp-route-id-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Route</span>
        </div>
        <p className="lp-route-id-line">
          <strong>{planResult.rover?.name ?? 'Rover'}</strong>
          <span>South Pole Traverse</span>
        </p>

        <div className="lp-route-endpoints">
          {firstWp && (
            <div className="lp-route-endpoint">
              <span className="lp-endpoint-marker is-start" aria-hidden="true" />
              <div className="lp-endpoint-body">
                <span className="lp-endpoint-title">
                  START <em>[{firstWp.row}, {firstWp.col}]</em>
                </span>
                <span className="lp-endpoint-coord">{formatLatLon(firstWp.lat, firstWp.lon)}</span>
              </div>
            </div>
          )}
          {lastWp && (
            <div className="lp-route-endpoint">
              <span className="lp-endpoint-marker is-goal" aria-hidden="true" />
              <div className="lp-endpoint-body">
                <span className="lp-endpoint-title">
                  GOAL <em>[{lastWp.row}, {lastWp.col}]</em>
                </span>
                <span className="lp-endpoint-coord">{formatLatLon(lastWp.lat, lastWp.lon)}</span>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ── TIER 1: DECISION SUMMARY ────────────────────────── */}
      <section className="lp-panel-section lp-tier-1-section">
        {/* The verdict was a bordered chip in the header row, the same size as
            the section label beside it -- the single most important output of
            the whole planner, set in 12px. It is the section now: the word at
            display size, a five-segment meter that says where it sits on the
            scale, and the sentence that says what it means. */}
        <div className="lp-verdict-block" style={{ '--verdict-color': riskToHex(overallRisk) } as React.CSSProperties}>
          <div className="lp-verdict-head">
            <div className="lp-verdict-naming">
              <span className="lp-meta-label">Overall risk</span>
              <strong className="lp-verdict-value">{overallRisk}</strong>
            </div>
            <div className="lp-verdict-meter" role="img" aria-label={`Risk ${overallRisk}, ${RISK_FILL[overallRisk]} of 5`}>
              {[0, 1, 2, 3, 4].map((i) => (
                <span
                  key={i}
                  className={`lp-verdict-seg ${i < RISK_FILL[overallRisk] ? 'is-on' : ''}`}
                  style={
                    i < RISK_FILL[overallRisk]
                      ? { background: riskToHex(i < 2 ? 'LOW' : overallRisk) }
                      : undefined
                  }
                />
              ))}
            </div>
          </div>
          <p className="lp-verdict-meaning">{RISK_MEANING[overallRisk]}</p>
        </div>

        <div className="lp-section-header-row">
          <span className="lp-meta-label">Mission decision summary</span>
        </div>

        <div className="lp-decision-kpi-grid">
          <div className="lp-decision-kpi">
            {/* "Route", because the transport bar reports distance COVERED at
                the cursor and two figures both called Distance, one reading
                0.00 km and the other 2.64, is worse than either alone. */}
            <span className="lp-kpi-label">Route distance</span>
            <strong className="lp-kpi-val">
              {summary?.total_distance_km ? `${summary.total_distance_km.toFixed(2)} km` : '--'}
            </strong>
          </div>

          <div className="lp-decision-kpi">
            <span className="lp-kpi-label">End battery</span>
            <strong
              className="lp-kpi-val"
              style={{ color: batteryToHex(finalBattery) }}
            >
              {finalBattery.toFixed(1)}%
            </strong>
          </div>

          <div className="lp-decision-kpi">
            <span className="lp-kpi-label">Route speed</span>
            <strong className="lp-kpi-val">{routeSpeedMs.toFixed(2)} m/s</strong>
          </div>

          <div className="lp-decision-kpi">
            <span className="lp-kpi-label">Estimated duration</span>
            <strong className="lp-kpi-val">
              {totalHours > 0 ? `${totalHours.toFixed(1)} h` : '--'}
            </strong>
          </div>

          <div className="lp-decision-kpi">
            <span className="lp-kpi-label">Route nodes</span>
            <strong className="lp-kpi-val">{totalWaypoints}</strong>
          </div>

          <div className="lp-decision-kpi">
            <span className="lp-kpi-label">Recharges</span>
            <strong className="lp-kpi-val">{summary?.total_recharges ?? 0} stops</strong>
          </div>
        </div>
      </section>

      {/* ── TIER 2: ENGINEERING ANALYSIS ────────────────────── */}
      <section className="lp-panel-section lp-tier-2-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Engineering analysis</span>
        </div>

        {/* Engineering Stats */}
        <div className="lp-eng-stat-grid">
          <div className="lp-eng-stat-cell">
            <span className="lp-spec-label">Steepest segment</span>
            <strong className="lp-spec-val">
              {summary?.max_slope_deg ? `${summary.max_slope_deg.toFixed(1)}°` : '--'}
            </strong>
          </div>
          <div className="lp-eng-stat-cell">
            <span className="lp-spec-label">Planner effort</span>
            <strong className="lp-spec-val">
              {metrics?.nodes_expanded ? `${metrics.nodes_expanded} nodes` : '--'}
            </strong>
          </div>
          <div className="lp-eng-stat-cell">
            <span className="lp-spec-label">Total energy</span>
            <strong className="lp-spec-val">
              {summary?.total_energy_consumed_wh
                ? `${summary.total_energy_consumed_wh.toFixed(0)} Wh`
                : '--'}
            </strong>
          </div>
          <div className="lp-eng-stat-cell">
            <span className="lp-spec-label">Compute time</span>
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
            <span className="lp-slider-label">LiDAR payload cost</span>
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
                onChange={(e) => setPayloadW(Math.max(0, parseInt(e.target.value) || 0))}
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
                onChange={(e) => setHeaterW(Math.max(0, parseInt(e.target.value) || 0))}
              />
              <span className="lp-unit-tag">W</span>
            </label>
          </div>

          <div className="lp-payload-result-row">
            <div>
              <span className="lp-mono-label">Overhead</span>
              <strong className="lp-mono-val">{payloadOverheadWh.toFixed(0)} Wh</strong>
            </div>
            <div>
              <span className="lp-mono-label">Battery cost</span>
              <strong className="lp-mono-val">{payloadOverheadPct.toFixed(1)}%</strong>
            </div>
            <div>
              <span className="lp-mono-label">Arrives with</span>
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
          <span className="lp-meta-label">Route milestones</span>
        </div>

        <div className="lp-milestones-timeline">
          {milestones.map(({ title, wp }, idx) => (
            <div key={idx} className="lp-milestone-entry">
              <div className="lp-milestone-marker">
                <span
                  className="lp-milestone-dot"
                  style={{ backgroundColor: riskToHex(wp.risk_level) }}
                />
                {idx < milestones.length - 1 && (
                  <div
                    className="lp-milestone-stem"
                    style={{ background: riskToHex(wp.risk_level) }}
                  />
                )}
              </div>
              <div className="lp-milestone-body">
                <div className="lp-milestone-title-row">
                  <strong className="lp-milestone-title">{title}</strong>
                  <span className="lp-milestone-coord">
                    [{wp.col}, {wp.row}] · {wp.distance_m.toFixed(0)} m
                  </span>
                </div>
                {/* Slope, temperature, and the verdict that follows from them.
                    Battery came out: it is the one number here already given
                    its own KPI above, and at four readings on a 400px row the
                    line wrapped and none of them could be read at a glance. */}
                <div className="lp-milestone-sub">
                  <span>Slope: {wp.slope_deg.toFixed(1)}°</span>
                  <span className="lp-milestone-sep" aria-hidden="true">|</span>
                  <span>Temp: {wp.surface_temp_c.toFixed(0)}°C</span>
                  <span
                    className="lp-milestone-risk"
                    style={{
                      color: riskToHex(wp.risk_level),
                      borderColor: riskToHex(wp.risk_level),
                    }}
                  >
                    {wp.risk_level}
                  </span>
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

