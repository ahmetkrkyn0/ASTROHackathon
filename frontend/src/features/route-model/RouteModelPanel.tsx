import type { ReactNode } from 'react'
import { Icon, type IconName } from '../../components/Fleet/SpecIcons'
import type { RouteModelView } from './routeModel'
import './route-model.css'

/**
 * Slip, risk appetite and roughness: what the planner charged this route.
 *
 * Figures and their validity, and nothing else -- each of these blocks ships
 * eighty to a hundred and twenty words of claim, and all of it is in the
 * mission report where the measure is wide enough to read it.
 *
 * VALIDITY IS DRAWN, NOT JUST WRITTEN. The chip's border says how the number
 * was arrived at: solid for MEASURED, dashed for MODEL. A dashed edge is what
 * "not measured" looks like, so the distinction survives a glance rather than
 * needing the word to be read -- and it costs no colour, which matters because
 * this console spends risk colour only on safety semantics, and how confident
 * a number is is not a safety verdict.
 */

/** Solid border for a measurement, dashed for a model. */
function Validity({ level }: { level: string }) {
  const upper = level.toUpperCase()
  // Three levels, weakest last. UNCALIBRATED is not a kind of MODEL: a model
  // with no calibration behind it is a further step from a measurement, and
  // the thermal block ships both labels precisely so they can be told apart.
  const tone = upper.includes('UNCALIBRATED')
    ? 'is-uncalibrated'
    : upper.startsWith('MEASURED')
      ? 'is-measured'
      : 'is-model'
  return <span className={`lp-rm-chip ${tone}`}>{level}</span>
}

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
  icon,
  validity,
  children,
}: {
  title: string
  icon: IconName
  validity: ReactNode
  children: ReactNode
}) {
  return (
    <section className="lp-rm-section">
      <header className="lp-rm-head">
        <Icon name={icon} className="lp-rm-head-icon" />
        <h4>{title}</h4>
        <span className="lp-rm-validity">{validity}</span>
      </header>
      {children}
    </section>
  )
}

/** A block the backend considered and did not apply. A slot, visibly empty. */
function Absent({ children }: { children: ReactNode }) {
  return (
    <p className="lp-rm-absent">
      <Icon name="info" />
      <span>{children}</span>
    </p>
  )
}

const n = (value: number | null, digits = 2, unit = ''): string =>
  value === null ? '--' : `${value.toFixed(digits)}${unit}`

export function RouteModelPanel({ view }: { view: RouteModelView }) {
  return (
    <div className="lp-rm">
      {view.slip ? (
        <Section
          title="Mobility · slip"
          icon="climb"
          validity={<Validity level={view.slip.validity ?? 'MODEL'} />}
        >
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
              {/* What slip cost THIS route, which is the figure an operator
                  plans against rather than what slip is in general. */}
              <p className="lp-rm-cost">
                <Icon name="clock" />
                <b>{n(view.slip.extraHours, 2)} h</b>
                <Icon name="energy" />
                <b>{n(view.slip.extraDrawnWh, 0)} Wh</b>
                <span>added by slip</span>
              </p>
            </>
          ) : (
            <Absent>Not applied — this profile declares no slip curve.</Absent>
          )}
        </Section>
      ) : null}

      {view.risk ? (
        <Section
          title="Risk appetite"
          icon="levels"
          validity={<Validity level={view.risk.validity ?? 'MODEL'} />}
        >
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
                  is flying. */}
              <p className="lp-rm-cost is-ranking">
                <span className="lp-rm-scope-tag">ranking only</span>
                <b>{n(view.risk.hours, 2)} h</b>
                <Icon name="back" className="lp-rm-arrow" />
                <b>{n(view.risk.riskAdjustedHours, 2)} h</b>
              </p>
            </>
          ) : (
            <Absent>Nominal — no tail pricing requested.</Absent>
          )}
        </Section>
      ) : null}

      {view.roughness ? (
        <Section
          title="Roughness"
          icon="terrain"
          validity={
            <>
              <Validity level={view.roughness.validity ?? 'MEASURED'} />
              {view.roughness.scaleValidity ? (
                <Validity level={`scale ${view.roughness.scaleValidity}`} />
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
              <p className="lp-rm-cost">
                <Icon name="layers" />
                <span>
                  {view.roughness.baselineM !== null
                    ? `${view.roughness.baselineM} m baseline`
                    : 'LOLA LDRM'}
                  {view.roughness.weight !== null ? ` · weight ${view.roughness.weight}` : ''}
                </span>
              </p>
            </>
          ) : (
            // The backend's reason names the cache file and the script that
            // builds it. That belongs in the report; the rail states the fact.
            <Absent>Not applied — no roughness layer on this deployment.</Absent>
          )}
        </Section>
      ) : null}

      {view.survival ? (
        <Section
          title="Execution survival"
          icon="shield"
          validity={<Validity level={view.survival.validity ?? 'MODEL'} />}
        >
          {view.survival.applied ? (
            <>
              <dl className="lp-rm-figures">
                <Figure
                  label="Failure prob."
                  value={view.survival.executionFailureProbability !== null
                    ? `${(view.survival.executionFailureProbability * 100).toFixed(2)}%`
                    : '--'}
                />
                <Figure label="β" value={n(view.survival.beta, 3)} />
                <Figure
                  label="Moves refused"
                  value={view.survival.movesRefused !== null
                    ? `${view.survival.movesRefused}`
                    : '--'}
                />
              </dl>
              {/* A transferred failure rate is an assumption, and the contract
                  prefixes it as one. Hiding that is a named acceptance failure
                  in the integration plan. */}
              {view.survival.failureSource?.startsWith('assumption') ? (
                <p className="lp-rm-cost">
                  <Icon name="info" />
                  <span>
                    Failure rate {view.survival.failureRatePerKm ?? '--'}/km is an assumption
                  </span>
                </p>
              ) : null}
            </>
          ) : (
            <Absent>
              {view.survival.requested
                ? `Requested but not applied${view.survival.reason ? ` — ${view.survival.reason}` : '.'}`
                : 'Not requested — no chance constraint on this plan.'}
            </Absent>
          )}
        </Section>
      ) : null}

      {view.thermal ? (
        <Section
          title="Thermal dwell"
          icon="thermal"
          validity={
            <>
              <Validity level={view.thermal.validity ?? 'MODEL'} />
              {view.thermal.lagValidity ? <Validity level={view.thermal.lagValidity} /> : null}
            </>
          }
        >
          {view.thermal.applied ? (
            <>
              <dl className="lp-rm-figures">
                <Figure label="Min margin" value={n(view.thermal.minDwellMarginH, 2, ' h')} />
                <Figure
                  label="Inner temp"
                  value={`${n(view.thermal.innerMinC, 1)} … ${n(view.thermal.innerMaxC, 1)}°C`}
                  hint={view.thermal.envelopeLoC !== null
                    ? `envelope ${view.thermal.envelopeLoC}–${view.thermal.envelopeHiC}°C`
                    : undefined}
                />
                <Figure
                  label="Open-ended"
                  // Not the same as a large finite dwell, and never rendered
                  // as infinity: the contract is explicit that these are
                  // states with no limit inside the evaluated horizon.
                  value={view.thermal.openEndedStates !== null
                    ? `${view.thermal.openEndedStates} states`
                    : '--'}
                />
              </dl>
              <p className="lp-rm-cost">
                <Icon name="info" />
                <span>
                  Heater model {view.thermal.heaterModel ?? 'none'} · dwell limits are
                  uncalibrated
                </span>
              </p>
            </>
          ) : (
            <Absent>
              {view.thermal.requested
                ? 'Requested but not applied on this plan.'
                : 'Not requested — no dwell constraint on this plan.'}
            </Absent>
          )}
        </Section>
      ) : null}

      <p className="lp-rm-foot">
        <Icon name="report" />
        Claims and sources in the mission report.
      </p>
    </div>
  )
}
