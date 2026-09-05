import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { PlanResponse } from '../../api'
import type { RouteStatistics } from '../../net/types'
import { riskToHex } from '../../colormap'
import {
  Donut,
  HBars,
  LimitGauge,
  LineArea,
  SegmentedProfile,
  StackedBar,
  type Point,
} from './charts'
import { downloadCsv } from './exportCsv'
import { fmt } from './format'
import {
  ASSISTANT_QUESTION,
  BATTERY_WATCH_PCT,
  RISK_LEVELS,
  VERDICT_COLOR,
  decideVerdict,
  energySplit,
  milestones,
  riskShares,
  slopeHistogram,
} from './report'

interface Props {
  plan: PlanResponse
  payloadW: number
  heaterW: number
  onClose: () => void
  /** Puts a question in the assistant's composer. Sends nothing. */
  onAskAssistant: (question: string) => void
}

const Section: React.FC<{
  label: string
  note?: string
  /** A control belonging to this section, right-aligned in its header. */
  action?: React.ReactNode
  children: React.ReactNode
}> = ({ label, note, action, children }) => (
  <section className="lp-report-card">
    <header className="lp-report-card-head">
      <span className="lp-meta-label">{label}</span>
      {note && <span className="lp-report-card-note">{note}</span>}
      {action && <span className="lp-report-card-action">{action}</span>}
    </header>
    {children}
  </section>
)

/**
 * The full-screen mission report.
 *
 * It replaces the map rather than floating beside it, which is the whole point:
 * once the rover has arrived, the nine rail panels are competing for attention
 * with a question that is already answered. The modal answers it in one screen
 * and hands the map back on close.
 *
 * Nothing here fetches. Every number comes from the /api/plan response already
 * in mission state, so the report cannot disagree with the route the operator
 * just watched.
 */
export const MissionReportModal: React.FC<Props> = ({
  plan,
  payloadW,
  heaterW,
  onClose,
  onAskAssistant,
}) => {
  const closeRef = useRef<HTMLButtonElement>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [printing, setPrinting] = useState(false)

  /**
   * Printing has to show the whole report, including the detail the operator
   * left collapsed.
   *
   * The technical section is conditionally rendered, so the print stylesheet
   * cannot reveal it -- there is nothing in the DOM to reveal. Opening it and
   * printing on the next frame is the difference between exporting the report
   * and exporting the half of it that happened to be on screen.
   */
  const handlePrint = () => {
    setDetailsOpen(true)
    setPrinting(true)
  }

  useEffect(() => {
    if (!printing) {
      return
    }
    // Two frames: one for React to commit the opened section, one for layout
    // and the chart width observers to settle before the page is captured.
    let inner = 0
    const outer = requestAnimationFrame(() => {
      inner = requestAnimationFrame(() => {
        window.print()
        setPrinting(false)
      })
    })
    return () => {
      cancelAnimationFrame(outer)
      cancelAnimationFrame(inner)
    }
  }, [printing])

  // Esc closes, and focus starts on the close button. Deliberately not a focus
  // trap: the modal covers the viewport and the cockpit behind it is inert to
  // the pointer, so the cost of a full trap buys very little here.
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const { summary, waypoints, astar_metrics: metrics } = plan
  const stats = (plan.route_statistics ?? null) as RouteStatistics | null

  const view = useMemo(() => {
    // x is distance in km for every series: the operator watched the rover
    // cross ground, not tick through node indices, and a step axis makes an
    // uneven route look evenly paced.
    const km = (m: number) => m / 1000

    const battery: Point[] = waypoints.map((w) => ({ x: km(w.distance_m), y: w.battery_pct }))
    const thermal: Point[] = waypoints.map((w) => ({ x: km(w.distance_m), y: w.surface_temp_c }))
    const shadow: Point[] = waypoints.map((w) => ({ x: km(w.distance_m), y: w.shadow_ratio }))
    const elevation: Point[] = waypoints
      .filter((w) => w.altitude_m !== null)
      .map((w) => ({ x: km(w.distance_m), y: w.altitude_m as number }))
    const elevationColors = waypoints
      .filter((w) => w.altitude_m !== null)
      .map((w) => riskToHex(w.risk_level))

    const recharges = waypoints
      .filter((w) => w.recharged_this_step)
      .map((w) => ({ x: km(w.distance_m) }))

    const shares = riskShares(waypoints, stats)
    const bins = slopeHistogram(waypoints, stats)
    const energy = energySplit(
      summary.total_energy_consumed_wh,
      summary.total_elapsed_hours,
      payloadW,
      heaterW,
    )

    return {
      battery,
      thermal,
      shadow,
      elevation,
      elevationColors,
      recharges,
      shares,
      bins,
      energy,
      verdict: decideVerdict(plan),
      marks: milestones(waypoints),
    }
  }, [plan, waypoints, summary, stats, payloadW, heaterW])

  const verdictColor = VERDICT_COLOR[view.verdict.verdict]
  const energyTotal = view.energy.driveWh + view.energy.payloadWh + view.energy.heaterWh

  const kpis: Array<{ label: string; value: string; color?: string }> = [
    { label: 'DISTANCE', value: `${fmt(summary.total_distance_km, 2)} km` },
    { label: 'Duration', value: `${fmt(summary.total_elapsed_hours, 1)} h` },
    {
      label: 'End battery',
      value: `${fmt(summary.final_battery_pct)}%`,
      color: summary.final_battery_pct < BATTERY_WATCH_PCT ? 'var(--risk-high)' : undefined,
    },
    {
      label: 'Lowest battery',
      value: `${fmt(summary.min_battery_pct)}%`,
      color: summary.min_battery_pct < BATTERY_WATCH_PCT ? 'var(--risk-high)' : undefined,
    },
    { label: 'Energy used', value: `${fmt(summary.total_energy_consumed_wh, 0)} Wh` },
    { label: 'Max slope', value: `${fmt(summary.max_slope_deg)}°` },
    { label: 'Recharges', value: String(summary.total_recharges) },
    { label: 'Route nodes', value: String(summary.waypoint_count) },
  ]

  /**
   * Portalled to <body>, and the print stylesheet is why.
   *
   * Printing this report means hiding everything that is not it, which
   * `report.css` does with `body > *:not(.lp-report-scrim)`. Rendered in the
   * globalOverlay slot the scrim sits inside `#root > .app-shell`, so that
   * selector matched `#root` and hid the report along with the cockpit: every
   * "Save as PDF" produced a blank A4 page.
   *
   * The portal also takes the report out from under `.app-shell`, which is
   * `height: 100vh; overflow: hidden` -- ancestors that would have cropped a
   * ten-card report to a single page. On screen nothing moves: the scrim is
   * `position: fixed; inset: 0`, which looks the same from either parent.
   */
  return createPortal(
    <div className="lp-report-scrim" role="presentation">
      <div
        className="lp-report-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Mission report"
      >
        <header className="lp-report-header">
          <div className="lp-report-title-block">
            <span className="lp-meta-label">Mission report</span>
            <h2 className="lp-report-title">Route complete</h2>
            <p className="lp-report-subtitle">
              {plan.rover?.name ?? 'Rover'} drove{' '}
              <span className="lp-report-figure">{fmt(summary.total_distance_km, 2)} km</span> over{' '}
              <span className="lp-report-figure">{summary.waypoint_count}</span> waypoints.
            </p>
          </div>
          <div className="lp-report-header-right">
            <span
              className="lp-report-verdict"
              style={{ borderColor: verdictColor, color: verdictColor }}
            >
              {view.verdict.verdict}
            </span>
            <div className="lp-report-actions">
              <button type="button" className="lp-report-action" onClick={handlePrint}>
                Save as PDF
              </button>
              <button
                type="button"
                className="lp-report-action"
                onClick={() => downloadCsv(plan)}
              >
                Download data
              </button>
            </div>
            <button
              type="button"
              ref={closeRef}
              className="lp-report-close"
              onClick={onClose}
              aria-label="Close the report and return to the map"
            >
              Back to map ✕
            </button>
          </div>
        </header>

        <div className="lp-report-body">
          {/* ── Decision summary ───────────────────────────────────── */}
          <Section
            label="Decision summary"
            action={
              <button
                type="button"
                className="lp-report-ask"
                onClick={() => onAskAssistant(ASSISTANT_QUESTION[view.verdict.verdict])}
              >
                Ask the assistant
              </button>
            }
          >
            <ul className="lp-report-reasons">
              {view.verdict.reasons.map((reason) => (
                <li key={reason.code}>
                  <span className="lp-reason-dot" style={{ background: verdictColor }} />
                  {reason.text}
                </li>
              ))}
            </ul>
            <div className="lp-report-kpis">
              {kpis.map((kpi) => (
                <div className="lp-report-kpi" key={kpi.label}>
                  <span className="lp-kpi-label">{kpi.label}</span>
                  <strong className="lp-kpi-val" style={kpi.color ? { color: kpi.color } : undefined}>
                    {kpi.value}
                  </strong>
                </div>
              ))}
            </div>
          </Section>

          {/* ── Battery ───────────────────────────────────────────── */}
          <Section
            label="Battery profile"
            note={
              view.recharges.length > 0
                ? `${view.recharges.length} recharge stops (dashed green)`
                : 'No recharge stops'
            }
          >
            <LineArea
              title="Battery percentage against distance"
              points={view.battery}
              color="var(--mint)"
              yMin={0}
              yMax={100}
              markers={view.recharges}
              refLines={[
                { y: BATTERY_WATCH_PCT, label: 'RESERVE 30%', color: 'var(--risk-high)' },
                {
                  y: summary.min_battery_pct,
                  label: `MIN ${fmt(summary.min_battery_pct)}%`,
                  color: 'var(--text-dim)',
                },
              ]}
              formatY={(v) => `${v.toFixed(0)}%`}
              formatX={(v) => `${v.toFixed(1)}km`}
              height={200}
            />
          </Section>

          {/* ── Slope + risk ───────────────────────────────────────── */}
          <div className="lp-report-row">
            <Section label="Slope distribution" note={`Steepest step ${fmt(summary.max_slope_deg)}°`}>
              <HBars
                rows={view.bins.map((bin) => ({
                  label: `${bin.bin_low_deg}–${bin.bin_high_deg}°`,
                  value: bin.count,
                  pct: bin.pct,
                  color:
                    bin.bin_low_deg >= 20
                      ? 'var(--risk-crit)'
                      : bin.bin_low_deg >= 15
                        ? 'var(--risk-high)'
                        : bin.bin_low_deg >= 10
                          ? 'var(--risk-med)'
                          : 'var(--risk-low)',
                }))}
              />
            </Section>

            <Section label="Risk distribution" note="Risk level per step">
              <StackedBar
                segments={RISK_LEVELS.map((level) => ({
                  label: level,
                  pct: view.shares[level],
                  color: riskToHex(level),
                }))}
              />
            </Section>
          </div>

          {/* ── Thermal + shadow ───────────────────────────────────── */}
          <div className="lp-report-row">
            <Section
              label="Thermal envelope"
              note={`${fmt(metrics.min_surface_temp_c, 0)}°C … ${fmt(metrics.max_surface_temp_c, 0)}°C`}
            >
              <LineArea
                title="Surface temperature against distance"
                points={view.thermal}
                color="var(--coral)"
                fill={false}
                refLines={[
                  {
                    y: metrics.min_surface_temp_c,
                    label: `MIN ${fmt(metrics.min_surface_temp_c, 0)}°C`,
                    color: 'var(--cyan)',
                  },
                  {
                    y: metrics.max_surface_temp_c,
                    label: `MAX ${fmt(metrics.max_surface_temp_c, 0)}°C`,
                    color: 'var(--risk-med)',
                  },
                ]}
                formatY={(v) => `${v.toFixed(0)}°`}
                formatX={(v) => `${v.toFixed(1)}km`}
                height={168}
              />
            </Section>

            <Section label="Shadow exposure" note="Continuous shadow against the rover limit">
              <LimitGauge
                label="Continuous shadow"
                value={summary.max_continuous_shadow_h}
                limit={summary.shadow_limit_h}
                unit="h"
                exceeded={summary.shadow_limit_exceeded}
              />
              <LineArea
                title="Shadow ratio against distance"
                points={view.shadow}
                color="var(--cyan)"
                yMin={0}
                yMax={1}
                formatY={(v) => v.toFixed(1)}
                formatX={(v) => `${v.toFixed(1)}km`}
                height={120}
              />
            </Section>
          </div>

          {/* ── Enerji ──────────────────────────────────────────────── */}
          <Section
            label="Energy breakdown"
            note="Drive energy from the simulation; payload and heater from the operator setting"
          >
            <Donut
              centerValue={`${fmt(energyTotal, 0)}`}
              centerLabel="Total Wh"
              slices={[
                { label: 'Drive', value: view.energy.driveWh, color: 'var(--lavender)' },
                { label: 'Payload', value: view.energy.payloadWh, color: 'var(--cyan)' },
                { label: 'Heater', value: view.energy.heaterWh, color: 'var(--coral)' },
              ]}
            />
          </Section>

          {/* ── Details ────────────────────────────────────────────── */}
          <button
            type="button"
            className="lp-report-toggle"
            onClick={() => setDetailsOpen((open) => !open)}
            aria-expanded={detailsOpen}
          >
            {detailsOpen
              ? '▾ Hide technical detail'
              : '▸ Technical detail (terrain cut, planner evidence, milestones)'}
          </button>

          {detailsOpen && (
            <>
              <Section label="Terrain cut" note="Elevation, painted by step risk">
                <SegmentedProfile
                  title="Elevation against distance"
                  points={view.elevation}
                  colors={view.elevationColors}
                  formatY={(v) => `${v.toFixed(0)}m`}
                  formatX={(v) => `${v.toFixed(1)}km`}
                  height={200}
                />
              </Section>

              <div className="lp-report-row">
                <Section label="Planner evidence" note="A* really did apply constraints">
                  <dl className="lp-report-dl">
                    <div>
                      <dt>Nodes expanded</dt>
                      <dd>{metrics.nodes_expanded.toLocaleString('tr-TR')}</dd>
                    </div>
                    <div>
                      <dt>Solve time</dt>
                      <dd>{fmt(metrics.computation_time_ms)} ms</dd>
                    </div>
                    <div>
                      <dt>Total weighted cost</dt>
                      <dd>{fmt(metrics.total_weighted_cost, 0)}</dd>
                    </div>
                    <div>
                      <dt>Barrier share</dt>
                      <dd>
                        {metrics.barrier_share === null
                          ? '--'
                          : `${fmt(metrics.barrier_share * 100)}%`}
                      </dd>
                    </div>
                    {Object.entries(metrics.edges_rejected).map(([reason, count]) => (
                      <div key={reason}>
                        <dt>Edges rejected · {reason}</dt>
                        <dd>{count}</dd>
                      </div>
                    ))}
                  </dl>
                </Section>

                <Section label="Milestones">
                  <div className="lp-report-table-wrap">
                    <table className="lp-report-table">
                      <thead>
                        <tr>
                          <th>Point</th>
                          <th>Step</th>
                          <th>KM</th>
                          <th>Battery</th>
                          <th>Slope</th>
                          <th>Temp</th>
                          <th>Risk</th>
                        </tr>
                      </thead>
                      <tbody>
                        {view.marks.map((m) => (
                          <tr key={m.step}>
                            <td>{m.title}</td>
                            <td>{m.step}</td>
                            <td>{fmt(m.wp.distance_m / 1000, 2)}</td>
                            <td>{fmt(m.wp.battery_pct)}%</td>
                            <td>{fmt(m.wp.slope_deg)}°</td>
                            <td>{fmt(m.wp.surface_temp_c, 0)}°C</td>
                            <td style={{ color: riskToHex(m.wp.risk_level) }}>{m.wp.risk_level}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Section>
              </div>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
