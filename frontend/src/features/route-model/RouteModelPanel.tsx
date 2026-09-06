import type { ReactNode } from 'react'
import type { RouteModelView } from './routeModel'
import './route-model.css'

/**
 * The rail readout for slip, risk appetite and roughness.
 *
 * Figures and their validity label, and nothing else. Each of these three
 * blocks ships a claim of eighty to a hundred and twenty words -- what the
 * slip curve is anchored to, where the risk sigma comes from, why a LOLA
 * roughness statistic is not the roughness of a cell -- and every one of those
 * sentences earns its place in the mission report. In a rail column they were
 * a wall of prose that buried the six numbers they qualify.
 *
 * The validity labels stay, because a number from this backend is never shown
 * without one. What moves is the argument behind them.
 */

function Figure({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="lp-rm-figure">
      <dt>{label}</dt>
      <dd>{value}</dd>
      {hint ? <span className="lp-rm-hint">{hint}</span> : null}
    </div>
  )
}

function Section({
  title,
  validity,
  children,
}: {
  title: string
  validity: ReactNode
  children: ReactNode
}) {
  return (
    <section className="lp-rm-section">
      <header className="lp-rm-head">
        <h4>{title}</h4>
        <span className="lp-rm-validity">{validity}</span>
      </header>
      {children}
    </section>
  )
}

const n = (value: number | null, digits = 2, unit = ''): string =>
  value === null ? '--' : `${value.toFixed(digits)}${unit}`

export function RouteModelPanel({ view }: { view: RouteModelView }) {
  return (
    <div className="lp-rm">
      {view.slip ? (
        <Section title="Mobility · slip" validity={view.slip.validity ?? 'MODEL'}>
          {view.slip.applied ? (
            <>
              <dl className="lp-rm-figures">
                <Figure label="Mean slip" value={n(view.slip.meanSlip)} />
                <Figure
                  label="Max slip"
                  value={n(view.slip.maxSlip)}
                  hint={view.slip.maxSlipSlopeDeg !== null
                    ? `at ${view.slip.maxSlipSlopeDeg.toFixed(1)}°`
                    : undefined}
                />
                <Figure label="Wheel dist." value={n(view.slip.distanceFactor, 2, '×')} />
              </dl>
              {/* The figure an operator plans against: what slip cost THIS
                  route, rather than what slip is in general. */}
              <p className="lp-rm-line">
                Added <b>{n(view.slip.extraHours, 2)} h</b> ·{' '}
                <b>{n(view.slip.extraDrawnWh, 0)} Wh</b>
              </p>
            </>
          ) : (
            <p className="lp-rm-absent">Not applied — this profile declares no slip curve.</p>
          )}
        </Section>
      ) : null}

      {view.risk ? (
        <Section title="Risk appetite" validity={view.risk.validity ?? 'MODEL'}>
          {view.risk.applied && view.risk.alpha !== null ? (
            <>
              <dl className="lp-rm-figures">
                <Figure label="Alpha" value={view.risk.alpha.toFixed(3)} />
                <Figure label="Tail mult." value={n(view.risk.multiplier, 3, '×')} />
                <Figure
                  label="Slip μ → tail"
                  value={`${n(view.risk.meanSlipMu)} → ${n(view.risk.meanSlipCvar)}`}
                />
              </dl>
              {/* Both figures, always. The planner's clock does not move with
                  alpha, so the adjusted hours alone would be a schedule nobody
                  is flying. "Ranking only" is the short form of the backend's
                  scope sentence, which the report carries in full. */}
              <p className="lp-rm-line">
                Ranking only: <b>{n(view.risk.hours, 2)} h</b> →{' '}
                <b>{n(view.risk.riskAdjustedHours, 2)} h</b>
              </p>
            </>
          ) : (
            <p className="lp-rm-absent">Nominal — no tail pricing requested.</p>
          )}
        </Section>
      ) : null}

      {view.roughness ? (
        <Section
          title="Roughness"
          validity={
            <>
              {view.roughness.validity ?? 'MEASURED'}
              {view.roughness.scaleValidity ? (
                <span className="lp-rm-validity-second"> · scale {view.roughness.scaleValidity}</span>
              ) : null}
            </>
          }
        >
          {view.roughness.applied ? (
            <>
              <dl className="lp-rm-figures">
                <Figure label="Mean" value={n(view.roughness.meanRoughnessM, 2, ' m')} />
                <Figure label="Max" value={n(view.roughness.maxRoughnessM, 2, ' m')} />
                <Figure
                  label="In PSR"
                  // Null is not zero: without the mask, nobody checked.
                  value={view.roughness.cellsInPsr === null
                    ? 'not checked'
                    : `${view.roughness.cellsInPsr}`}
                />
              </dl>
              <p className="lp-rm-line">
                {view.roughness.baselineM !== null ? `${view.roughness.baselineM} m baseline` : 'LOLA LDRM'}
                {view.roughness.weight !== null ? ` · weight ${view.roughness.weight}` : ''}
              </p>
            </>
          ) : (
            // The backend's reason names the cache file and the script that
            // builds it. That belongs in the report; the rail states the fact.
            <p className="lp-rm-absent">Not applied — no roughness layer on this deployment.</p>
          )}
        </Section>
      ) : null}

      <p className="lp-rm-foot">Claims and sources in the mission report.</p>
    </div>
  )
}
