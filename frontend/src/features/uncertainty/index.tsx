import { UncertaintyPanel } from './UncertaintyPanel'
import { useUncertainty } from './useUncertainty'

/**
 * DEM uncertainty (B3), in the systems drawer.
 *
 * A post-route analysis that takes seconds and needs a preprocessing cache
 * many deployments will not have. It never blocks the route: the plan's
 * scheduling rule puts everything in this class behind the route being
 * shown, and an unavailable ensemble costs the operator this panel and
 * nothing else.
 */
export function Uncertainty() {
  const { summary, job, start, cancel, canRun } = useUncertainty()

  return (
    <section className="rail-section">
      <p className="panel-kicker">DEM Uncertainty</p>
      <UncertaintyPanel
        summary={summary}
        job={job}
        start={start}
        cancel={cancel}
        canRun={canRun}
      />
    </section>
  )
}
