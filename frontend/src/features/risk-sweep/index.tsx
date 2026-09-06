import { Icon } from '../../components/Fleet/SpecIcons'
import { describeFailure } from '../../net/errors'
import type { RiskSweepResponse, SweepDelta } from '../../net/riskSweep'
import { useRiskSweep } from './useRiskSweep'
import './risk-sweep.css'

/**
 * Risk appetite sweep (B2), in the systems drawer.
 *
 * The same start and goal planned at several alphas at once, which turns an
 * argument into a measurement: on this site alpha 0.5 leaves the route
 * completely unchanged and 0.9 moves it to seventeen per cent of its original
 * cells. That is the honest answer to "what does risk appetite buy", and it is
 * only visible by planning more than one.
 *
 * Overlap is the headline rather than the cost deltas, because the question
 * alpha answers is which route you take, not what that route costs. The
 * backend's note -- alpha changes the ranking cost and nothing else, and every
 * summary here is mean-slip physics -- is printed verbatim underneath, since
 * it is the sentence that stops a delta being read as a saving.
 */

function Row({ delta }: { delta: SweepDelta }) {
  const moved = 1 - delta.overlap_with_nominal
  return (
    <li className="lp-rs-row">
      <span className="lp-rs-alpha">α {delta.risk_alpha}</span>
      <span className="lp-rs-track" aria-hidden="true">
        <span className="lp-rs-fill" style={{ width: `${moved * 100}%` }} />
      </span>
      <span className="lp-rs-moved">
        {moved === 0 ? 'unchanged' : `${(moved * 100).toFixed(0)}% new`}
      </span>
      <span className="lp-rs-delta">
        {delta.hours === 0 && delta.energy_wh === 0
          ? '—'
          : `${delta.hours >= 0 ? '+' : ''}${delta.hours.toFixed(2)} h · ${
              delta.energy_wh >= 0 ? '+' : ''
            }${delta.energy_wh.toFixed(0)} Wh`}
      </span>
    </li>
  )
}

function Result({ value }: { value: RiskSweepResponse }) {
  const deltas = value.comparison?.deltas ?? []
  const nominal = value.comparison?.nominal

  return (
    <div className="lp-rs-result">
      {nominal ? (
        <p className="lp-rs-nominal">
          Nominal <b>{nominal.hours?.toFixed(2)} h</b> · <b>{nominal.energy_wh?.toFixed(0)} Wh</b>
        </p>
      ) : null}

      <ul className="lp-rs-list">
        {deltas.map((delta) => (
          <Row key={delta.risk_alpha} delta={delta} />
        ))}
      </ul>

      {/* Verbatim. It is what stops a delta being read as a saving, and it
          says the thing about alpha 0.5 that everyone gets wrong. */}
      {value.note ? (
        <p className="lp-rs-note">
          <Icon name="info" />
          <span>{value.note}</span>
        </p>
      ) : null}
    </div>
  )
}

export function RiskSweep() {
  const { job, start, cancel, canRun, alphas } = useRiskSweep()

  return (
    <section className="rail-section">
      <p className="panel-kicker">Risk Appetite Sweep</p>

      <div className="lp-rs">
        {job.state === 'idle' || job.state === 'failure' ? (
          <button type="button" className="lp-rs-run" onClick={start} disabled={!canRun}>
            <Icon name="balance" />
            Plan at α {alphas.join(', ')}
          </button>
        ) : null}

        {job.state === 'running' ? (
          <div className="lp-rs-running">
            <span className="lp-rs-spinner" aria-hidden="true" />
            <span>Planning {alphas.length} more routes…</span>
            <button type="button" className="lp-rs-cancel" onClick={cancel}>Cancel</button>
          </div>
        ) : null}

        {job.state === 'success' ? <Result value={job.value} /> : null}

        {job.state === 'stale' ? (
          <>
            <p className="lp-rs-stale">
              <Icon name="clock" />
              This sweep is for the previous mission.
            </p>
            <div className="is-stale"><Result value={job.value} /></div>
          </>
        ) : null}

        {job.state === 'failure' ? (
          <p className={`lp-rs-failure ${job.failure.kind === 'data-unavailable' ? 'is-absent' : 'is-error'}`}>
            <Icon name={job.failure.kind === 'data-unavailable' ? 'info' : 'warning'} />
            <span>{describeFailure(job.failure)}</span>
          </p>
        ) : null}
      </div>
    </section>
  )
}
