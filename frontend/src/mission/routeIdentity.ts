import type { PlanWeights } from '../api'
import type { Cell } from './types'

/**
 * A stable name for "the route these inputs produce".
 *
 * Section 5.4 of the integration plan. Post-route analyses -- Monte Carlo, DEM
 * uncertainty, a risk sweep, an STL safety check -- are expensive, arrive late,
 * and are about one specific route. The failure they invite is showing the
 * previous route's stress-test result beside the new route, which is not a
 * stale number but a wrong one: it describes a traverse nobody is flying.
 *
 * Binding every analysis result to the identity of the route it was computed
 * for makes that impossible to do by accident. The result is displayed only
 * while its identity still matches.
 *
 * THE HARDER HALF IS NOT OVER-INVALIDATING. The plan is as clear that
 * switching the visible raster layer must NOT throw away a Monte Carlo run
 * that took twenty seconds. So the identity is deliberately narrow: it covers
 * exactly the inputs that change which cells the planner returns, and nothing
 * else. Camera, layer, selected cell, playback position and mission time are
 * all absent from it on purpose.
 */

/** Everything that decides the route, and nothing that does not. */
export interface RouteInputs {
  roverId: string
  start: Cell | null
  goal: Cell | null
  weights: PlanWeights
  /**
   * The advanced constraint fields as they are actually sent -- the object the
   * plan-request contributors build, already omitting everything switched off.
   *
   * Taking the sent object rather than the UI's own toggles is what keeps this
   * honest in both directions: a constraint that is enabled but contributes no
   * field cannot invalidate anything, and a field that is sent cannot fail to.
   */
  constraints?: Record<string, unknown>
}

/**
 * Weights arrive from sliders and from profile presets, so the same intended
 * value can be 0.35 and 0.35000000000000003. Six decimals is far finer than
 * any weight the UI can express and coarse enough that float noise cannot
 * invent a new identity.
 */
const WEIGHT_PRECISION = 6

function canonical(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return String(value)
    return value.toFixed(WEIGHT_PRECISION)
  }
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (typeof value === 'object') {
    // Sorted, because two objects that differ only in key order are the same
    // request, and JSON.stringify would disagree.
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => v !== undefined)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    return `{${entries.map(([k, v]) => `${k}:${canonical(v)}`).join(',')}}`
  }
  return JSON.stringify(value) ?? 'undefined'
}

/**
 * The identity, or null when there is no route to have one.
 *
 * Null rather than a placeholder string so that "no route yet" cannot
 * accidentally compare equal to another "no route yet" and let an analysis
 * from a previous mission attach itself to an empty one.
 */
export function routeIdentity(inputs: RouteInputs): string | null {
  if (!inputs.start || !inputs.goal) return null
  return canonical({
    rover: inputs.roverId,
    start: inputs.start,
    goal: inputs.goal,
    weights: inputs.weights,
    constraints: inputs.constraints ?? {},
  })
}

/**
 * Whether a result computed for `computedFor` still describes `current`.
 *
 * Two nulls are not a match. An analysis can only belong to a route, so a
 * result carrying no identity has nothing to be current for.
 */
export function matchesRoute(
  computedFor: string | null,
  current: string | null,
): boolean {
  return computedFor !== null && current !== null && computedFor === current
}
