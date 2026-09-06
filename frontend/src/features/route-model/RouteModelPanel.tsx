import type { ReactNode } from 'react'
import type { RouteModelView } from './routeModel'
import './route-model.css'

/**
 * A number with its validity beside it, which is the only way a number from
 * this backend is allowed on screen.
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
                <Figure label="Wheel distance" value={n(view.slip.distanceFactor, 2, '×')} />
              </dl>
              {/* The one figure an operator plans against: what slip cost THIS
                  route, as opposed to what slip is in general. */}
              <p className="lp-rm-line">
                Slip added <b>{n(view.slip.extraHours, 2)} h</b> and{' '}
                <b>{n(view.slip.extraDrawnWh, 0)} Wh</b> to this route.
              </p>
            </>
          ) : (
            <p className="lp-rm-absent">
              Not applied{view.slip.reason ? ` — ${view.slip.reason}` : ': this profile declares no slip curve.'}
            </p>
          )}
          {view.slip.claim ? <p className="lp-rm-claim">{view.slip.claim}</p> : null}
        </Section>
      ) : null}

      {view.risk ? (
        <Section title="Risk appetite · CVaR" validity={view.risk.validity ?? 'MODEL'}>
          {view.risk.applied && view.risk.alpha !== null ? (
            <>
              <dl className="lp-rm-figures">
                <Figure label="Alpha" value={view.risk.alpha.toFixed(3)} />
                <Figure label="Tail multiplier" value={n(view.risk.multiplier, 3, '×')} />
                <Figure
                  label="Slip μ → tail"
                  value={`${n(view.risk.meanSlipMu)} → ${n(view.risk.meanSlipCvar)}`}
                />
              </dl>
              {/* Both numbers, and which is which. The risk-adjusted hours are
                  not the mission's hours -- the planner's clock does not move
                  with alpha -- so presenting only the adjusted figure would
                  report a schedule nobody is flying. */}
              <p className="lp-rm-line">
                Priced at the tail: <b>{n(view.risk.hours, 2)} h</b> →{' '}
                <b>{n(view.risk.riskAdjustedHours, 2)} h</b>,{' '}
                <b>{n(view.risk.drawnWh, 0)} Wh</b> →{' '}
                <b>{n(view.risk.riskAdjustedDrawnWh, 0)} Wh</b>.
              </p>
            </>
          ) : (
            <p className="lp-rm-absent">
              Nominal — no risk appetite was requested, so the cost grid is the
              ordinary one. α = 0.5 would not be the mean.
            </p>
          )}
          {/* Scope before claim: it is the sentence that stops the adjusted
              figures being read as the route's physics. */}
          {view.risk.scope ? <p className="lp-rm-scope">{view.risk.scope}</p> : null}
          {view.risk.claim ? <p className="lp-rm-claim">{view.risk.claim}</p> : null}
        </Section>
      ) : null}

      {view.roughness ? (
        <Section
          title="Terrain roughness"
          validity={
            <>
              {view.roughness.validity ?? 'MEASURED'}
              {view.roughness.scaleValidity ? (
                <span className="lp-rm-validity-second">
                  {' '}· scale {view.roughness.scaleValidity}
                </span>
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
                  // Null is not zero: without the PSR mask nobody checked.
                  value={view.roughness.cellsInPsr === null
                    ? 'not checked'
                    : `${view.roughness.cellsInPsr} cells`}
                />
              </dl>
              <p className="lp-rm-line">
                {view.roughness.product ?? 'LOLA LDRM'}
                {view.roughness.baselineM !== null
                  ? ` · ${view.roughness.baselineM} m baseline`
                  : ''}
                {view.roughness.weight !== null ? ` · weight ${view.roughness.weight}` : ''}
              </p>
            </>
          ) : (
            <p className="lp-rm-absent">
              Not applied{view.roughness.reason ? ` — ${view.roughness.reason}` : '.'}
            </p>
          )}
          {view.roughness.claim ? <p className="lp-rm-claim">{view.roughness.claim}</p> : null}
        </Section>
      ) : null}
    </div>
  )
}
