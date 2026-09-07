import { Icon } from '../../components/Fleet/SpecIcons'
import { Divide, Meter, Readout, type Tone } from '../../components/Instrument'
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

/**
 * A rate with its interval on the same axis.
 *
 * The interval is drawn as the bar's own extent and the point estimate as a
 * marker inside it, so how well the rate is pinned down is read at the same
 * moment as the rate. 0.30 from a thousand runs and 0.30 from ten are the same
 * number and completely different findings.
 */
function RateBar({ rate, label, headline }: { rate: Rate; label: string; headline?: boolean }) {
  const [lo, hi] = rate.ci95
  const tone: Tone = rate.rate >= 0.95 ? 'ok' : rate.rate >= 0.5 ? 'warn' : 'bad'

  if (headline) {
    return (
      <div className="lp-st-headline">
        <Readout
          label={label}
          value={(rate.rate * 100).toFixed(1)}
          unit="%"
          tone={tone}
          sub={`${rate.count} runs · 95% CI ${(lo * 100).toFixed(1)}–${(hi * 100).toFixed(1)}%`}
        />
        {/* The interval drawn WHERE IT IS, not as a width from zero: an
            interval of 99.6-100% is a mark at the right-hand end, and starting
            it at the origin made a completion of 100% look like a sliver at 0. */}
        <Meter
          from={lo}
          fraction={Math.max(hi - lo, 0.01)}
          tone={tone}
          ticks={4}
          marker={rate.rate}
          low="0%"
          high="100%"
        />
      </div>
    )
  }

  return (
    <div className="lp-st-rate">
      <div className="lp-st-rate-head">
        <span className="lp-st-rate-label">{label}</span>
        <b className="lp-st-rate-value">{(rate.rate * 100).toFixed(1)}%</b>
      </div>
      <Meter fraction={rate.rate} tone={tone} ticks={4} marker={undefined} />
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

  return (
    <div className="lp-st-result">
      {rates.completion ? (
        <RateBar rate={rates.completion} label="Reached the goal" headline />
      ) : null}
      {rates.full_success ? <RateBar rate={rates.full_success} label="Full success" /> : null}

      {/* The backend's decision sentence, verbatim. It is the one line that
          says what the rates mean for THIS route -- including, in the measured
          case, that full success is zero because no haven exists in that lunar
          day rather than because the rover failed. */}
      {value.verdict?.text ? (
        <p className="lp-st-verdict">
          <Icon name="guide" />
          <span>{value.verdict.text}</span>
        </p>
      ) : null}

      {histograms.duration_h ? (
        <>
          <Divide label="Duration" />
          <Bars histogram={histograms.duration_h} unit=" h" />
        </>
      ) : null}

      {histograms.min_battery_pct ? (
        <>
          <Divide label="Lowest battery" />
          <Bars histogram={histograms.min_battery_pct} unit="%" />
        </>
      ) : null}

      {failures.length > 0 ? (
        <>
          <Divide label="First failure cause" />
          <ul className="lp-st-failures">
            {failures.map(([cause, count]) => (
              <li key={cause}>
                <span>{FAILURE_LABEL[cause] ?? cause.replace(/_/g, ' ')}</span>
                <b>{count}</b>
              </li>
            ))}
          </ul>
        </>
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
