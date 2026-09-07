import { Icon } from '../../components/Fleet/SpecIcons'
import { JobState, type AnalysisJob } from '../analysis-job'
import type { Histogram, Rate, StressTestResponse } from '../../net/stressTest'
import './stress-test.css'

/**
 * SHERPA Monte Carlo (B5).
 *
 * COMPLETION IS NOT SAFETY, and the panel is built so the two cannot be
 * confused. The headline is a rate with its Wilson interval drawn on the same
 * bar, because a completion of 0.30 from a thousand runs and 0.30 from ten are
 * different findings and the number alone hides which one you have. The
 * backend's own verdict sentence sits under it, and the route's own status is
 * never touched by anything here: the planner returned a route, and how often
 * a perturbed execution of it finishes is a separate question.
 *
 * Histograms are drawn from the bins the backend prepared. Re-binning them
 * here would be inventing a distribution shape the analysis did not report,
 * and the contract forbids it in as many words.
 */

const FAILURE_LABEL: Record<string, string> = {
  battery_depleted: 'Battery depleted',
  shadow_endurance: 'Shadow endurance',
  horizon_exceeded: 'Horizon exceeded',
}

function RateBar({ rate, label }: { rate: Rate; label: string }) {
  const [lo, hi] = rate.ci95
  return (
    <div className="lp-st-rate">
      <div className="lp-st-rate-head">
        <span className="lp-st-rate-label">{label}</span>
        <b className="lp-st-rate-value">{(rate.rate * 100).toFixed(1)}%</b>
      </div>
      <div className="lp-st-rate-track" aria-hidden="true">
        {/* The interval is drawn behind the point estimate, so how well the
            rate is pinned down is read at the same time as the rate. */}
        <span
          className="lp-st-rate-ci"
          style={{ left: `${lo * 100}%`, width: `${Math.max(hi - lo, 0.004) * 100}%` }}
        />
        <span className="lp-st-rate-fill" style={{ width: `${rate.rate * 100}%` }} />
      </div>
      <p className="lp-st-rate-foot">
        {rate.count} runs · 95% CI {(lo * 100).toFixed(1)}–{(hi * 100).toFixed(1)}%
      </p>
    </div>
  )
}

function Bars({ histogram, unit }: { histogram: Histogram; unit: string }) {
  const peak = Math.max(...histogram.counts, 1)
  const lo = histogram.edges[0]
  const hi = histogram.edges[histogram.edges.length - 1]
  return (
    <div className="lp-st-hist">
      <div className="lp-st-hist-bars" aria-hidden="true">
        {histogram.counts.map((count, index) => (
          <span
            key={index}
            className="lp-st-hist-bar"
            style={{ height: `${(count / peak) * 100}%` }}
          />
        ))}
      </div>
      <div className="lp-st-hist-axis">
        <span>{lo.toFixed(1)}{unit}</span>
        <span>{hi.toFixed(1)}{unit}</span>
      </div>
    </div>
  )
}

function Result({ value }: { value: StressTestResponse }) {
  const rates = value.rates ?? {}
  const failures = Object.entries(value.failures ?? {}).filter(([, count]) => count > 0)
  const histograms = value.histograms ?? {}
  const duration = histograms.duration_h
  const battery = histograms.min_battery_pct

  return (
    <div className="lp-st-result">
      {rates.completion ? <RateBar rate={rates.completion} label="Reached the goal" /> : null}
      {rates.full_success ? <RateBar rate={rates.full_success} label="Full success" /> : null}

      {/* The backend's decision sentence, verbatim. It is the one line that
          says what the rates mean for this particular route -- including, in
          the measured case, that full success is zero because no haven exists
          in that lunar day rather than because the rover failed. */}
      {value.verdict?.text ? (
        <p className="lp-st-verdict">
          <Icon name="guide" />
          <span>{value.verdict.text}</span>
        </p>
      ) : null}

      {duration ? (
        <div className="lp-st-block">
          <span className="lp-st-block-label">Duration</span>
          <Bars histogram={duration} unit=" h" />
        </div>
      ) : null}

      {battery ? (
        <div className="lp-st-block">
          <span className="lp-st-block-label">Lowest battery</span>
          <Bars histogram={battery} unit="%" />
        </div>
      ) : null}

      {failures.length > 0 ? (
        <div className="lp-st-block">
          <span className="lp-st-block-label">First failure cause</span>
          <ul className="lp-st-failures">
            {failures.map(([cause, count]) => (
              <li key={cause}>
                <span>{FAILURE_LABEL[cause] ?? cause.replace(/_/g, ' ')}</span>
                <b>{count}</b>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="lp-st-note">
        <Icon name="info" />
        <span>
          A completion rate is not a safety verdict. The planner returned this
          route; this is how often a perturbed execution of it finishes.
        </span>
      </p>
    </div>
  )
}

export function StressTestPanel({
  job,
  start,
  cancel,
  canRun,
  runs,
}: {
  job: AnalysisJob<StressTestResponse>
  start: () => void
  cancel: () => void
  canRun: boolean
  runs: number
}) {
  return (
    <JobState
      job={job}
      start={start}
      cancel={cancel}
      canRun={canRun}
      runIcon="spark"
      runLabel={`Run ${runs.toLocaleString('en-GB')} executions`}
      busyLabel="Executing…"
      staleLabel="This test is for the previous route."
    >
      {(value) => <Result value={value} />}
    </JobState>
  )
}
