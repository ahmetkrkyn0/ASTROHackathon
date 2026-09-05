import React, { useEffect, useMemo, useRef, useState } from 'react'
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
import { fmt } from './format'
import {
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
}

/** The reserve the battery chart draws as a line to read the trough against. */
const BATTERY_RESERVE_PCT = 30

const Section: React.FC<{ label: string; note?: string; children: React.ReactNode }> = ({
  label,
  note,
  children,
}) => (
  <section className="lp-report-card">
    <header className="lp-report-card-head">
      <span className="lp-meta-label">{label}</span>
      {note && <span className="lp-report-card-note">{note}</span>}
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
export const MissionReportModal: React.FC<Props> = ({ plan, payloadW, heaterW, onClose }) => {
  const closeRef = useRef<HTMLButtonElement>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)

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
    { label: 'MESAFE', value: `${fmt(summary.total_distance_km, 2)} km` },
    { label: 'SÜRE', value: `${fmt(summary.total_elapsed_hours, 1)} s` },
    {
      label: 'BİTİŞ PİLİ',
      value: `%${fmt(summary.final_battery_pct)}`,
      color: summary.final_battery_pct < BATTERY_RESERVE_PCT ? 'var(--risk-high)' : undefined,
    },
    {
      label: 'EN DÜŞÜK PİL',
      value: `%${fmt(summary.min_battery_pct)}`,
      color: summary.min_battery_pct < BATTERY_RESERVE_PCT ? 'var(--risk-high)' : undefined,
    },
    { label: 'HARCANAN ENERJİ', value: `${fmt(summary.total_energy_consumed_wh, 0)} Wh` },
    { label: 'MAKS. EĞİM', value: `${fmt(summary.max_slope_deg)}°` },
    { label: 'ŞARJ MOLASI', value: String(summary.total_recharges) },
    { label: 'ROTA DÜĞÜMÜ', value: String(summary.waypoint_count) },
  ]

  return (
    <div className="lp-report-scrim" role="presentation">
      <div
        className="lp-report-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Görev raporu"
      >
        <header className="lp-report-header">
          <div className="lp-report-title-block">
            <span className="lp-meta-label">GÖREV RAPORU</span>
            <h2 className="lp-report-title">Rota tamamlandı</h2>
            <span className="lp-report-subtitle">
              {plan.rover?.name ?? 'Rover'} · {summary.waypoint_count} düğüm ·{' '}
              {fmt(summary.total_distance_km, 2)} km
            </span>
          </div>
          <div className="lp-report-header-right">
            <span
              className="lp-report-verdict"
              style={{ borderColor: verdictColor, color: verdictColor }}
            >
              {view.verdict.verdict}
            </span>
            <button
              type="button"
              ref={closeRef}
              className="lp-report-close"
              onClick={onClose}
              aria-label="Raporu kapat ve haritaya dön"
            >
              Haritaya dön ✕
            </button>
          </div>
        </header>

        <div className="lp-report-body">
          {/* ── Karar özeti ─────────────────────────────────────────── */}
          <Section label="KARAR ÖZETİ">
            <ul className="lp-report-reasons">
              {view.verdict.reasons.map((reason) => (
                <li key={reason}>
                  <span className="lp-reason-dot" style={{ background: verdictColor }} />
                  {reason}
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

          {/* ── Pil ─────────────────────────────────────────────────── */}
          <Section
            label="PİL PROFİLİ"
            note={
              view.recharges.length > 0
                ? `${view.recharges.length} şarj molası (kesik yeşil çizgi)`
                : 'Şarj molası yok'
            }
          >
            <LineArea
              title="Mesafeye göre pil yüzdesi"
              points={view.battery}
              color="var(--mint)"
              yMin={0}
              yMax={100}
              markers={view.recharges}
              refLines={[
                { y: BATTERY_RESERVE_PCT, label: 'REZERV %30', color: 'var(--risk-high)' },
                {
                  y: summary.min_battery_pct,
                  label: `MİN %${fmt(summary.min_battery_pct)}`,
                  color: 'var(--text-dim)',
                },
              ]}
              formatY={(v) => `%${v.toFixed(0)}`}
              formatX={(v) => `${v.toFixed(1)}km`}
              height={200}
            />
          </Section>

          {/* ── Eğim + risk ─────────────────────────────────────────── */}
          <div className="lp-report-row">
            <Section label="EĞİM DAĞILIMI" note={`En dik adım ${fmt(summary.max_slope_deg)}°`}>
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

            <Section label="RİSK DAĞILIMI" note="Adım başına risk seviyesi">
              <StackedBar
                segments={RISK_LEVELS.map((level) => ({
                  label: level,
                  pct: view.shares[level],
                  color: riskToHex(level),
                }))}
              />
            </Section>
          </div>

          {/* ── Termal + gölge ──────────────────────────────────────── */}
          <div className="lp-report-row">
            <Section
              label="TERMAL ZARF"
              note={`${fmt(metrics.min_surface_temp_c, 0)}°C … ${fmt(metrics.max_surface_temp_c, 0)}°C`}
            >
              <LineArea
                title="Mesafeye göre yüzey sıcaklığı"
                points={view.thermal}
                color="var(--coral)"
                fill={false}
                refLines={[
                  {
                    y: metrics.min_surface_temp_c,
                    label: `MİN ${fmt(metrics.min_surface_temp_c, 0)}°C`,
                    color: 'var(--cyan)',
                  },
                  {
                    y: metrics.max_surface_temp_c,
                    label: `MAKS ${fmt(metrics.max_surface_temp_c, 0)}°C`,
                    color: 'var(--risk-med)',
                  },
                ]}
                formatY={(v) => `${v.toFixed(0)}°`}
                formatX={(v) => `${v.toFixed(1)}km`}
                height={168}
              />
            </Section>

            <Section label="GÖLGE MARUZİYETİ" note="Kesintisiz gölge, rover limitine karşı">
              <LimitGauge
                label="KESİNTİSİZ GÖLGE"
                value={summary.max_continuous_shadow_h}
                limit={summary.shadow_limit_h}
                unit="s"
                exceeded={summary.shadow_limit_exceeded}
              />
              <LineArea
                title="Mesafeye göre gölge oranı"
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
            label="ENERJİ KIRILIMI"
            note="Sürüş enerjisi simülasyondan; payload ve ısıtıcı operatör ayarından"
          >
            <Donut
              centerValue={`${fmt(energyTotal, 0)}`}
              centerLabel="TOPLAM Wh"
              slices={[
                { label: 'Sürüş', value: view.energy.driveWh, color: 'var(--lavender)' },
                { label: 'Payload', value: view.energy.payloadWh, color: 'var(--cyan)' },
                { label: 'Isıtıcı', value: view.energy.heaterWh, color: 'var(--coral)' },
              ]}
            />
          </Section>

          {/* ── Detaylar ────────────────────────────────────────────── */}
          <button
            type="button"
            className="lp-report-toggle"
            onClick={() => setDetailsOpen((open) => !open)}
            aria-expanded={detailsOpen}
          >
            {detailsOpen ? '▾ Teknik detayları gizle' : '▸ Teknik detaylar (arazi kesiti, planlayıcı kanıtı, kilometre taşları)'}
          </button>

          {detailsOpen && (
            <>
              <Section label="ARAZİ KESİTİ" note="Yükseklik, adım riskiyle boyanmış">
                <SegmentedProfile
                  title="Mesafeye göre yükseklik"
                  points={view.elevation}
                  colors={view.elevationColors}
                  formatY={(v) => `${v.toFixed(0)}m`}
                  formatX={(v) => `${v.toFixed(1)}km`}
                  height={200}
                />
              </Section>

              <div className="lp-report-row">
                <Section label="PLANLAYICI KANITI" note="A* gerçekten kısıt uyguladı">
                  <dl className="lp-report-dl">
                    <div>
                      <dt>Genişletilen düğüm</dt>
                      <dd>{metrics.nodes_expanded.toLocaleString('tr-TR')}</dd>
                    </div>
                    <div>
                      <dt>Çözüm süresi</dt>
                      <dd>{fmt(metrics.computation_time_ms)} ms</dd>
                    </div>
                    <div>
                      <dt>Toplam ağırlıklı maliyet</dt>
                      <dd>{fmt(metrics.total_weighted_cost, 0)}</dd>
                    </div>
                    <div>
                      <dt>Bariyer payı</dt>
                      <dd>
                        {metrics.barrier_share === null
                          ? '--'
                          : `%${fmt(metrics.barrier_share * 100)}`}
                      </dd>
                    </div>
                    {Object.entries(metrics.edges_rejected).map(([reason, count]) => (
                      <div key={reason}>
                        <dt>Reddedilen kenar · {reason}</dt>
                        <dd>{count}</dd>
                      </div>
                    ))}
                  </dl>
                </Section>

                <Section label="KİLOMETRE TAŞLARI">
                  <div className="lp-report-table-wrap">
                    <table className="lp-report-table">
                      <thead>
                        <tr>
                          <th>NOKTA</th>
                          <th>ADIM</th>
                          <th>KM</th>
                          <th>PİL</th>
                          <th>EĞİM</th>
                          <th>SICAKLIK</th>
                          <th>RİSK</th>
                        </tr>
                      </thead>
                      <tbody>
                        {view.marks.map((m) => (
                          <tr key={m.step}>
                            <td>{m.title}</td>
                            <td>{m.step}</td>
                            <td>{fmt(m.wp.distance_m / 1000, 2)}</td>
                            <td>%{fmt(m.wp.battery_pct)}</td>
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
    </div>
  )
}
