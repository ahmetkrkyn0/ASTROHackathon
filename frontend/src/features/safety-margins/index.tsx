import { useMission } from '../../mission/MissionContext'
import { SafetyMarginsPanel } from './SafetyMarginsPanel'
import { readSafetyMargins } from './safetyMargins'

/**
 * Formal safety margins (D3).
 *
 * Reads the block off the route already in mission state -- it arrives with
 * every plan response, so there is nothing to fetch, no button to press and no
 * loading state to hold. The plan is explicit that this analysis must not sit
 * behind a control: if the result is there, it is shown.
 */
export function SafetyMargins() {
  const { planResult } = useMission()
  const view = readSafetyMargins(planResult)

  // A route with no safety block is a route the backend did not monitor --
  // an older deployment, or a compare result whose simulation was dropped.
  // Nothing is drawn rather than an empty frame implying twelve untested
  // requirements.
  if (!view) return null

  return (
    <section className="rail-section">
      <p className="panel-kicker">Formal Safety Margins</p>
      <SafetyMarginsPanel view={view} />
    </section>
  )
}
