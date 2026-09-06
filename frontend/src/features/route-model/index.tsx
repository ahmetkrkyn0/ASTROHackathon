import { useMission } from '../../mission/MissionContext'
import { RouteModelPanel } from './RouteModelPanel'
import { isEmpty, readRouteModel } from './routeModel'

/**
 * Slip, risk appetite and measured roughness (C3, B2, C4).
 *
 * All three arrive with every plan response, so there is nothing to fetch and
 * no control to press. Renders nothing when a response carries none of them.
 */
export function RouteModel() {
  const { planResult } = useMission()
  const view = readRouteModel(planResult)
  if (isEmpty(view)) return null

  return (
    <section className="rail-section">
      <p className="panel-kicker">Route Cost Model</p>
      <RouteModelPanel view={view} />
    </section>
  )
}
