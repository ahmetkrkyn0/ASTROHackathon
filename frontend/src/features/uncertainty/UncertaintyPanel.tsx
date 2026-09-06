import { Icon } from '../../components/Fleet/SpecIcons'
import { describeFailure } from '../../net/errors'
import type { AnalysisJob } from '../analysis-job'
import type { UncertaintyResponse, UncertaintyBand } from '../../net/uncertainty'
import type { UncertaintySummary } from './useUncertainty'
import './uncertainty.css'

/**
 * DEM uncertainty (B3), drawn as bands rather than printed as numbers.
 *
 * The point of this feature is that a duration is not one number: priced on a
 * hundred statistical clones of the elevation model it is a spread, and the
 * spread is the finding. So each metric is a bar running p5 to p95 with p50
 * marked, and the nominal figure -- the same computation on the surface DEM --
 * marked separately on the same scale. Where the nominal sits OUTSIDE the
 * band is the interesting case and is visible at a glance; printed as two
 * columns of digits it would not be.
 *
 * The band is never collapsed to a single figure. The plan is explicit about
 * that and it is the whole reason the feature exists.
 */

/** Metrics worth a bar, in the order an operator reads them. */
const SHOWN: Array<{ key: string; label: string; digits: number; unit: string }> = [
  { key: 'drive_hours', label: 'Drive time', digits: 2, unit: ' h' },
  { key: 'gross_drive_wh', label: 'Drive energy', digits: 0, unit: ' Wh' },
  { key: 'min_battery_pct', label: 'Lowest SOC', digits: 1, unit: '%' },
  { key: 'max_continuous_shadow_h', label: 'Longest shadow', digits: 2, unit: ' h' },
]

function Band({
  band,
  nominal,
  digits,
  unit,
}: {
  band: UncertaintyBand
  nominal: number | null
  digits: number
  unit: string
}) {
  // The drawing scale spans the clones and the nominal together, so a nominal
  // that falls outside the band is visibly outside it rather than clipped to
  // the edge and made to look marginal.
  const low = Math.min(band.min, nominal ?? band.min)
  const high = Math.max(band.max, nominal ?? band.max)
  const span = high - low || 1
  const pct = (value: number) => ((value - low) / span) * 100

  return (
    <div className="lp-unc-row">
      <div className="lp-unc-track" aria-hidden="true">
        <span
          className="lp-unc-band"
          style={{ left: `${pct(band.p5)}%`, width: `${pct(band.p95) - pct(band.p5)}%` }}
        />
        <span className="lp-unc-median" style={{ left: `${pct(band.p50)}%` }} />
        {nominal !== null ? (
          <span className="lp-unc-nominal" style={{ left: `${pct(nominal)}%` }} />
        ) : null}
      </div>
      <div className="lp-unc-numbers">
        <span>{band.p5.toFixed(digits)}</span>
        <b>{band.p50.toFixed(digits)}{unit}</b>
        <span>{band.p95.toFixed(digits)}</span>
      </div>
    </div>
  )
}

function Result({ value }: { value: UncertaintyResponse }) {
  const metrics = value.metrics ?? {}
  const nominal = value.nominal ?? {}
  const shown = SHOWN.filter((metric) => metrics[metric.key])

  return (
    <div className="lp-unc-result">
      <p className="lp-unc-scale">
        <span className="lp-unc-key"><i className="lp-unc-swatch is-band" />p5–p95</span>
        <span className="lp-unc-key"><i className="lp-unc-swatch is-median" />p50</span>
        <span className="lp-unc-key"><i className="lp-unc-swatch is-nominal" />surface DEM</span>
      </p>

      {shown.map((metric) => (
        <div key={metric.key} className="lp-unc-metric">
          <span className="lp-unc-label">{metric.label}</span>
          <Band
            band={metrics[metric.key]}
            nominal={typeof nominal[metric.key] === 'number' ? nominal[metric.key] : null}
            digits={metric.digits}
            unit={metric.unit}
          />
        </div>
      ))}

      {/* How often the route stayed traversable at all. A fraction of 0 with a
          route on screen is the finding, not a bug: the nominal DEM allows a
          traverse the clone ensemble does not. */}
      {value.route_feasible ? (
        <p className="lp-unc-feasible">
          <Icon name="route" />
          Route stayed traversable in{' '}
          <b>{value.route_feasible.count}/{value.n_clones ?? '--'}</b> clones
        </p>
      ) : null}
    </div>
  )
}

export function UncertaintyPanel({
  summary,
  job,
  start,
  cancel,
  canRun,
}: {
  summary: UncertaintySummary | null
  job: AnalysisJob<UncertaintyResponse>
  start: () => void
  cancel: () => void
  canRun: boolean
}) {
  return (
    <div className="lp-unc">
      {/* The cheap half, when the ensemble exists. */}
      {summary ? (
        <dl className="lp-unc-summary">
          <div>
            <dt>P traversable</dt>
            <dd>
              {summary.pTraversableMean !== null ? summary.pTraversableMean.toFixed(2) : '--'}
              <span className="lp-unc-sub">
                min {summary.pTraversableMin !== null ? summary.pTraversableMin.toFixed(2) : '--'}
              </span>
            </dd>
          </div>
          <div>
            <dt>Clones</dt>
            <dd>{summary.nClones ?? '--'}</dd>
          </div>
        </dl>
      ) : null}

      {job.state === 'idle' || job.state === 'failure' ? (
        <button
          type="button"
          className="lp-unc-run"
          onClick={start}
          disabled={!canRun}
        >
          <Icon name="levels" />
          Price the route on the clone ensemble
        </button>
      ) : null}

      {/* Indeterminate, and nothing here pretends otherwise: the backend
          reports no progress for this job, so a percentage would be an
          animation impersonating telemetry. */}
      {job.state === 'running' ? (
        <div className="lp-unc-running">
          <span className="lp-unc-spinner" aria-hidden="true" />
          <span>Pricing on 100 clones…</span>
          <button type="button" className="lp-unc-cancel" onClick={cancel}>Cancel</button>
        </div>
      ) : null}

      {job.state === 'success' ? <Result value={job.value} /> : null}

      {/* Stale rather than gone: the operator changed something, and a result
          that described the previous route is greyed out instead of vanishing,
          which would read as data loss. */}
      {job.state === 'stale' ? (
        <>
          <p className="lp-unc-stale">
            <Icon name="clock" />
            This band is for the previous route.
          </p>
          <div className="is-stale"><Result value={job.value} /></div>
          <button type="button" className="lp-unc-run" onClick={start} disabled={!canRun}>
            <Icon name="restart" />
            Re-price for this route
          </button>
        </>
      ) : null}

      {job.state === 'failure' ? (
        <p
          className={`lp-unc-failure ${
            job.failure.kind === 'data-unavailable' ? 'is-absent' : 'is-error'
          }`}
        >
          <Icon name={job.failure.kind === 'data-unavailable' ? 'info' : 'warning'} />
          <span>{describeFailure(job.failure)}</span>
        </p>
      ) : null}
    </div>
  )
}
