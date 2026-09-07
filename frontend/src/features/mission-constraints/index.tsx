import { MissionConstraintsPanel } from './MissionConstraintsPanel'

/**
 * Advanced planner constraints (plan mode).
 *
 * Registered in the systems drawer rather than the primary rail: these change
 * how a route is ranked and when it is feasible, but the moment-to-moment task
 * is still picking a rover and two endpoints. An operator who never opens this
 * gets exactly the product that existed before it.
 */
export function MissionConstraints() {
  return (
    <section className="rail-section">
      <p className="panel-kicker">Advanced Constraints</p>
      <MissionConstraintsPanel />
    </section>
  )
}
