import type { ReactNode } from 'react'
import { Icon, type IconName } from '../../components/Fleet/SpecIcons'
import { describeFailure } from '../../net/errors'
import type { AnalysisJob } from './useAnalysisJob'
import './analysis-job.css'

/**
 * The shell every post-route analysis wears.
 *
 * Written once because there are four of them -- DEM uncertainty, the Monte
 * Carlo stress test, the risk sweep, and whatever lands next -- and they had
 * each grown their own run button, their own spinner and their own way of
 * saying "this is for the previous route". Three near-identical controls in
 * three accent colours is not four features looking related; it is one
 * feature drawn three times, badly.
 *
 * The action takes the cockpit's established analysis colour, which is the
 * cyan the profile comparison already uses for exactly this: a control that
 * spends seconds of backend time and returns a finding.
 */

export function JobState<T>({
  job,
  start,
  cancel,
  canRun,
  runLabel,
  runIcon = 'spark',
  busyLabel,
  staleLabel,
  children,
}: {
  job: AnalysisJob<T>
  start: () => void
  cancel: () => void
  canRun: boolean
  runLabel: ReactNode
  runIcon?: IconName
  busyLabel: string
  /** What "this result is not about the current route" says here. */
  staleLabel: string
  /** Renders a finished result. Called for both fresh and stale values. */
  children: (value: T) => ReactNode
}) {
  return (
    <div className="lp-job">
      {job.state === 'idle' || job.state === 'failure' ? (
        <button type="button" className="lp-job-run" onClick={start} disabled={!canRun}>
          <Icon name={runIcon} />
          {runLabel}
        </button>
      ) : null}

      {/* Indeterminate on purpose. The backend reports no progress for any of
          these, so a percentage or a filling bar would be an animation
          impersonating telemetry. */}
      {job.state === 'running' ? (
        <p className="lp-job-running">
          <span className="lp-job-spinner" aria-hidden="true" />
          <span>{busyLabel}</span>
          <button type="button" className="lp-job-cancel" onClick={cancel}>Cancel</button>
        </p>
      ) : null}

      {job.state === 'success' ? children(job.value) : null}

      {/* Greyed, not gone: a result that vanishes when the mission moves reads
          as data loss, and re-running costs seconds the operator may not want
          to spend to see what they were just looking at. */}
      {job.state === 'stale' ? (
        <>
          <p className="lp-job-stale">
            <Icon name="clock" />
            <span>{staleLabel}</span>
          </p>
          <div className="lp-job-aged">{children(job.value)}</div>
          <button type="button" className="lp-job-run" onClick={start} disabled={!canRun}>
            <Icon name="restart" />
            Re-run for this route
          </button>
        </>
      ) : null}

      {/* Unavailable is not an error and is not drawn like one: a cache that
          was never built is a fact about the deployment, and the backend's own
          sentence names the script that builds it. */}
      {job.state === 'failure' ? (
        <p
          className={`lp-job-message ${
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
