import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { PlanResponse } from '../../api'
import type { RouteStatistics } from '../../net/types'
import { riskToHex } from '../../colormap'
import { CostModelEvidence, SafetyEvidence } from './EvidenceSections'
import { Icon, type IconName } from '../../components/Fleet/SpecIcons'
import {
  COPY,
  LANG_LABEL,
  REPORT_LANGS,
  VERDICT_MEANING,
  fmtPct,
  readLang,
  reasonText,
  writeLang,
  type ReportLang,
} from '../../i18n/reportCopy'
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
  type Verdict,
} from './report'

/**
 * The glyph for each verdict.
 *
 * Three shapes that escalate -- a circled tick, a triangle, a filled disc --
 * so the verdict survives a monochrome print, where colour is the first thing
 * a reader loses.
 */
const VERDICT_ICON: Record<Verdict, IconName> = {
  GO: 'check',
  'GO-WITH-RISK': 'warning',
  'NO-GO': 'error',
}

interface Props {
  plan: PlanResponse
  payloadW: number
  heaterW: number
  onClose: () => void
  /** Puts a question in the assistant's composer. Sends nothing. */
  onAskAssistant: (question: string) => void
  /**
   * The region the route was planned over: extent and resolution, both read
   * from the terrain manifest.
   *
   * Null until the manifest arrives, and the row is simply absent then. There
   * is no site NAME anywhere in the data -- the one that used to appear in the
   * cockpit was hardcoded in a panel -- and a report that is exported as a PDF
   * is the last place to invent one.
   */
  region: { widthKm: number; heightKm: number; resolutionM: number } | null
}

const Section: React.FC<{
  label: string
  /**
   * Names the QUANTITY, not the card: the battery profile takes the same
   * glyph the battery KPI does, so a reader learns one mark per reading
   * rather than one per box.
   */
  icon: IconName
  note?: string
  /** A control belonging to this section, right-aligned in its header. */
  action?: React.ReactNode
  children: React.ReactNode
}> = ({ label, icon, note, action, children }) => (
  <section className="lp-report-card">
    <header className="lp-report-card-head">
      <span className="lp-report-card-title">
        <Icon name={icon} className="lp-report-card-icon" />
        <span className="lp-meta-label">{label}</span>
      </span>
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
  region,
}) => {
  const closeRef = useRef<HTMLButtonElement>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [printing, setPrinting] = useState(false)

  /**
   * The report's language, remembered across sessions.
   *
   * Read once through the initialiser rather than in an effect, so the first
   * paint is already in the right language -- a report that flashes English
   * before turning Turkish is worse than one that was always Turkish. The
   * cockpit around it stays English and the assistant stays Turkish; only
   * this document moves.
   */
  const [lang, setLang] = useState<ReportLang>(() => readLang())
  const t = COPY[lang]

  const chooseLang = (next: ReportLang) => {
    setLang(next)
    writeLang(next)
  }

  /**
   * When this report was produced, captured once.
   *
   * `new Date()` in the render body would tick on every re-render and print a
   * different time each pass. It is the moment the report was opened, not the
   * moment the route was planned -- the plan carries no timestamp -- which is
   * why the row is labelled for the report rather than for the route.
   */
  const [openedAt] = useState(() => new Date())

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

  // 'DISTANCE' used to be the only one of the eight in capitals, which read as
  // emphasis nobody had asked for -- .lp-kpi-label sets no text-transform, so
  // it really did shout while its seven neighbours did not.
  const kpis: Array<{ label: string; value: string; icon: IconName; color?: string }> = [
    {
      label: t.kpi.distance,
      icon: 'route',
      value: `${fmt(summary.total_distance_km, 2, lang)} km`,
    },
    {
      label: t.kpi.duration,
      icon: 'clock',
      value: `${fmt(summary.total_elapsed_hours, 1, lang)} h`,
    },
    {
      label: t.kpi.endBattery,
      icon: 'battery',
      value: fmtPct(summary.final_battery_pct, 1, lang),
      color: summary.final_battery_pct < BATTERY_WATCH_PCT ? 'var(--risk-high)' : undefined,
    },
    {
      label: t.kpi.lowestBattery,
      icon: 'batterylow',
      value: fmtPct(summary.min_battery_pct, 1, lang),
      color: summary.min_battery_pct < BATTERY_WATCH_PCT ? 'var(--risk-high)' : undefined,
    },
    {
      label: t.kpi.energyUsed,
      icon: 'energy',
      value: `${fmt(summary.total_energy_consumed_wh, 0, lang)} Wh`,
    },
    {
      label: t.kpi.maxSlope,
      icon: 'slope',
      value: `${fmt(summary.max_slope_deg, 1, lang)}°`,
    },
    {
      label: t.kpi.recharges,
      icon: 'plug',
      value: fmt(summary.total_recharges, 0, lang),
    },
    {
      label: t.kpi.routeNodes,
      icon: 'nodes',
      value: fmt(summary.waypoint_count, 0, lang),
    },
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
            <span className="lp-meta-label">{t.kicker}</span>
            <h2 className="lp-report-title">{t.title}</h2>
            {/* Built as one sentence per language rather than English
                fragments wrapped around <span>s. Turkish is SOV -- the verb
                lands last -- so the node order that reads correctly in one
                language cannot be reused by the other. */}
            <p className="lp-report-subtitle">
              {t.subtitle(
                plan.rover?.name ?? t.metaRover,
                fmt(summary.total_distance_km, 2, lang),
                fmt(summary.waypoint_count, 0, lang),
              )}
            </p>
          </div>

          <div className="lp-report-header-right">
            {/* Only what the mission actually recorded. There is no mission
                identifier anywhere in this system, and a report that leaves
                the building as a PDF is the last place to invent one. */}
            <dl className="lp-report-meta">
              <div>
                <dt>{t.metaRover}</dt>
                <dd>{plan.rover?.name ?? '--'}</dd>
              </div>
              {region && (
                <div>
                  <dt>{t.metaRegion}</dt>
                  <dd>
                    {t.regionValue(region.widthKm, region.heightKm, region.resolutionM)}
                  </dd>
                </div>
              )}
              <div>
                <dt>{t.metaGenerated}</dt>
                <dd>
                  <time dateTime={openedAt.toISOString()}>
                    {openedAt.toISOString().slice(0, 16).replace('T', ' ')} UTC
                  </time>
                </dd>
              </div>
            </dl>

            <div className="lp-report-controls">
              {/* One button per language, each naming itself. A single toggle
                  labelled with the OTHER language is the classic ambiguity:
                  nobody agrees whether it shows the current state or the
                  action. */}
              <div
                className="lp-report-langs"
                role="group"
                aria-label={t.langSwitchLabel}
              >
                {REPORT_LANGS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={`lp-report-lang ${option === lang ? 'is-active' : ''}`}
                    aria-pressed={option === lang}
                    onClick={() => chooseLang(option)}
                  >
                    {option === lang && <Icon name="language" />}
                    {LANG_LABEL[option]}
                  </button>
                ))}
              </div>

              <div className="lp-report-actions">
                <button type="button" className="lp-report-action" onClick={handlePrint}>
                  <Icon name="pdf" />
                  {t.savePdf}
                </button>
                <button
                  type="button"
                  className="lp-report-action"
                  onClick={() => downloadCsv(plan)}
                >
                  <Icon name="download" />
                  {t.downloadData}
                </button>
              </div>

              <button
                type="button"
                ref={closeRef}
                className="lp-report-close"
                onClick={onClose}
                aria-label={t.backToMapAria}
              >
                <Icon name="back" />
                {t.backToMap}
              </button>
            </div>
          </div>
        </header>

        {/* The one element in the report allowed to shout.
            The token is a contract value shared with the backend and is never
            translated; the sentence under it is what the UI review asked for,
            because three letters are a label and not an explanation. */}
        <div
          className={`lp-report-verdict-panel is-${view.verdict.verdict.toLowerCase()}`}
          style={{ borderColor: verdictColor }}
        >
          <Icon
            name={VERDICT_ICON[view.verdict.verdict]}
            className="lp-report-verdict-icon"
          />
          <div className="lp-report-verdict-text">
            <strong className="lp-report-verdict" style={{ color: verdictColor }}>
              {view.verdict.verdict}
            </strong>
            <span className="lp-report-verdict-meaning">
              {VERDICT_MEANING[lang][view.verdict.verdict]}
            </span>
          </div>
        </div>

        <div className="lp-report-body">
          {/* ── Decision summary ───────────────────────────────────── */}
          <Section
            label={t.sections.decision}
            icon="evidence"
            action={
              <button
                type="button"
                className="lp-report-ask"
                onClick={() => onAskAssistant(ASSISTANT_QUESTION[view.verdict.verdict])}
                title={lang === 'en' ? t.askAssistantTurkishHint : undefined}
              >
                <Icon name="spark" />
                {t.askAssistant}
                {/* The assistant answers only in Turkish -- its grounding
                    layer matches Turkish morphology -- so an English report
                    says so before the operator presses, rather than after.
                    The same badge the chat panel already carries. */}
                {lang === 'en' && <span className="lp-report-ask-lang">TR</span>}
              </button>
            }
          >
            <ul className="lp-report-reasons">
              {view.verdict.reasons.map((reason) => (
                <li key={reason.code}>
                  <span className="lp-reason-dot" style={{ background: verdictColor }} />
                  {reasonText(reason, lang)}
                </li>
              ))}
            </ul>
            <div className="lp-report-kpis">
              {kpis.map((kpi) => (
                <div className="lp-report-kpi" key={kpi.label}>
                  <span className="lp-kpi-label">
                    <Icon name={kpi.icon} className="lp-report-kpi-icon" />
                    {kpi.label}
                  </span>
                  <strong className="lp-kpi-val" style={kpi.color ? { color: kpi.color } : undefined}>
                    {kpi.value}
                  </strong>
                </div>
              ))}
            </div>
          </Section>

          {/* ── Battery ───────────────────────────────────────────── */}
          <Section
            label={t.sections.battery}
            icon="battery"
            note={
              view.recharges.length > 0
                ? t.notes.recharges(fmt(view.recharges.length, 0, lang))
                : t.notes.noRecharges
            }
          >
            <LineArea
              title={t.charts.batteryTitle}
              emptyLabel={t.charts.notEnoughPoints}
              points={view.battery}
              color="var(--mint)"
              yMin={0}
              yMax={100}
              markers={view.recharges}
              refLines={[
                {
                  y: BATTERY_WATCH_PCT,
                  // Was the literal 'RESERVE 30%' beside a threshold that is a
                  // constant -- two places to change one number.
                  label: t.charts.batteryReserve(fmtPct(BATTERY_WATCH_PCT, 0, lang)),
                  color: 'var(--risk-high)',
                },
                {
                  y: summary.min_battery_pct,
                  label: t.charts.batteryMin(fmtPct(summary.min_battery_pct, 1, lang)),
                  color: 'var(--text-dim)',
                },
              ]}
              formatY={(v) => fmtPct(v, 0, lang)}
              formatX={(v) => `${fmt(v, 1, lang)}km`}
              height={200}
            />
          </Section>

          {/* ── Slope + risk ───────────────────────────────────────── */}
          <div className="lp-report-row">
            <Section
              label={t.sections.slope}
              icon="slope"
              note={t.notes.steepest(fmt(summary.max_slope_deg, 1, lang))}
            >
              <HBars
                lang={lang}
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

            <Section label={t.sections.risk} icon="shield" note={t.notes.riskPerStep}>
              <StackedBar
                lang={lang}
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
              label={t.sections.thermal}
              icon="thermal"
              note={t.notes.thermalRange(
                fmt(metrics.min_surface_temp_c, 0, lang),
                fmt(metrics.max_surface_temp_c, 0, lang),
              )}
            >
              <LineArea
                title={t.charts.thermalTitle}
                emptyLabel={t.charts.notEnoughPoints}
                points={view.thermal}
                color="var(--coral)"
                fill={false}
                refLines={[
                  {
                    y: metrics.min_surface_temp_c,
                    label: t.charts.thermalMin(fmt(metrics.min_surface_temp_c, 0, lang)),
                    color: 'var(--cyan)',
                  },
                  {
                    y: metrics.max_surface_temp_c,
                    label: t.charts.thermalMax(fmt(metrics.max_surface_temp_c, 0, lang)),
                    color: 'var(--risk-med)',
                  },
                ]}
                formatY={(v) => `${fmt(v, 0, lang)}°`}
                formatX={(v) => `${fmt(v, 1, lang)}km`}
                height={168}
              />
            </Section>

            <Section label={t.sections.shadow} icon="shadow" note={t.notes.shadowLimit}>
              <LimitGauge
                label={t.charts.shadowGaugeLabel}
                value={summary.max_continuous_shadow_h}
                limit={summary.shadow_limit_h}
                unit="h"
                exceeded={summary.shadow_limit_exceeded}
                lang={lang}
                noLimitLabel={t.charts.noShadowLimit}
                exceededLabel={t.charts.limitExceeded}
                usedLabel={t.charts.limitUsed}
              />
              <LineArea
                title={t.charts.shadowTitle}
                emptyLabel={t.charts.notEnoughPoints}
                points={view.shadow}
                color="var(--cyan)"
                yMin={0}
                yMax={1}
                formatY={(v) => fmt(v, 1, lang)}
                formatX={(v) => `${fmt(v, 1, lang)}km`}
                height={120}
              />
            </Section>
          </div>

          {/* ── Enerji ──────────────────────────────────────────────── */}
          <Section label={t.sections.energy} icon="energy" note={t.notes.energySource}>
            <Donut
              centerValue={fmt(energyTotal, 0, lang)}
              centerLabel={t.charts.donutTotal}
              lang={lang}
              slices={[
                { label: t.charts.drive, value: view.energy.driveWh, color: 'var(--lavender)' },
                { label: t.charts.payload, value: view.energy.payloadWh, color: 'var(--cyan)' },
                { label: t.charts.heater, value: view.energy.heaterWh, color: 'var(--coral)' },
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
            <Icon name="expand" className="lp-report-toggle-icon" />
            {detailsOpen ? t.details.hide : t.details.show}
          </button>

          {detailsOpen && (
            <>
              <Section
                label={t.sections.terrain}
                icon="terrain"
                note={t.notes.terrainPainted}
              >
                <SegmentedProfile
                  title={t.charts.elevationTitle}
                  emptyLabel={t.charts.noElevation}
                  points={view.elevation}
                  colors={view.elevationColors}
                  formatY={(v) => `${fmt(v, 0, lang)}m`}
                  formatX={(v) => `${fmt(v, 1, lang)}km`}
                  height={200}
                />
              </Section>

              <div className="lp-report-row">
                <Section
                  label={t.sections.planner}
                  icon="analytics"
                  note={t.notes.plannerEvidence}
                >
                  <dl className="lp-report-dl">
                    <div>
                      <dt>{t.planner.nodesExpanded}</dt>
                      {/* Was hardcoded to tr-TR while format.ts said en-GB, so
                          one report printed two different thousands
                          separators. Both follow the reader now. */}
                      <dd>{fmt(metrics.nodes_expanded, 0, lang)}</dd>
                    </div>
                    <div>
                      <dt>{t.planner.solveTime}</dt>
                      <dd>{fmt(metrics.computation_time_ms, 1, lang)} ms</dd>
                    </div>
                    <div>
                      <dt>{t.planner.totalCost}</dt>
                      <dd>{fmt(metrics.total_weighted_cost, 0, lang)}</dd>
                    </div>
                    <div>
                      <dt>{t.planner.barrierShare}</dt>
                      <dd>
                        {metrics.barrier_share === null
                          ? '--'
                          : fmtPct(metrics.barrier_share * 100, 1, lang)}
                      </dd>
                    </div>
                    {/* The reason is a backend key -- `step_slope`,
                        `lateral_barrier`. Passed through rather than
                        translated: inventing Turkish for a value this file has
                        never enumerated would be a guess dressed as copy. */}
                    {Object.entries(metrics.edges_rejected).map(([reason, count]) => (
                      <div key={reason}>
                        <dt>{t.planner.edgesRejected(reason)}</dt>
                        <dd>{fmt(count, 0, lang)}</dd>
                      </div>
                    ))}
                  </dl>
                </Section>

                <Section label={t.sections.milestones} icon="flag">
                  <div className="lp-report-table-wrap">
                    <table className="lp-report-table">
                      <thead>
                        <tr>
                          <th>{t.table.point}</th>
                          <th>{t.table.step}</th>
                          <th>{t.table.km}</th>
                          <th>{t.table.battery}</th>
                          <th>{t.table.slope}</th>
                          <th>{t.table.temp}</th>
                          <th>{t.table.risk}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {view.marks.map((m) => (
                          <tr key={m.step}>
                            {/* A quartile title is already a percentage and
                                needs no lookup; the four named points do. */}
                            <td>
                              {m.title in t.milestone
                                ? t.milestone[m.title as keyof typeof t.milestone]
                                : m.title}
                            </td>
                            <td>{fmt(m.step, 0, lang)}</td>
                            <td>{fmt(m.wp.distance_m / 1000, 2, lang)}</td>
                            <td>{fmtPct(m.wp.battery_pct, 1, lang)}</td>
                            <td>{fmt(m.wp.slope_deg, 1, lang)}°</td>
                            <td>{fmt(m.wp.surface_temp_c, 0, lang)}°C</td>
                            <td style={{ color: riskToHex(m.wp.risk_level) }}>{m.wp.risk_level}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Section>
              </div>

              {/* Full width, outside the two-column row: a twelve-row table of
                  FRETISH sentences and eighty-word claim paragraphs are not
                  half-column content. Putting them in that row also stretched
                  the planner evidence card to match the tallest thing beside
                  it, which is where the empty space under it came from. */}
              <Section label={t.sections.safety} icon="shield">
                <SafetyEvidence plan={plan} t={t} />
              </Section>

              <Section label={t.sections.costModel} icon="evidence">
                <CostModelEvidence plan={plan} t={t} />
              </Section>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
