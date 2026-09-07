/**
 * What makes one planned route a different route -- spec 5.4.
 *
 * Post-analysis results (a Monte Carlo run, an uncertainty band, a safety
 * margin catalogue) belong to the route they were computed on. Show one of
 * them beside a different route and it is a fabricated number: it describes a
 * path the operator is no longer looking at, with nothing on screen to say so.
 *
 * The other half of the rule matters just as much: do not invalidate for
 * nothing. Switching the raster under the map from `slope` to `thermal`
 * changes no input to any analysis, and throwing away a completed stress test
 * because someone changed the colour of the background would train operators
 * to distrust the staleness marker.
 *
 * So identity is exactly the planner's inputs and nothing else: rover, start,
 * goal, the weights, and the forward constraints that were switched on. View
 * mode, dimension, playback position and hover cell are all absent by design.
 */

import type { PlanWeights } from '../api'
import type { Cell } from './types'

/**
 * The advanced constraints that change the route the planner returns.
 *
 * Only forward constraints belong here -- ones the planner enforces during the
 * search. A post-hoc check that reports on a route without altering it does
 * not change the route's identity, so it must not appear.
 *
 * Recorded as an object rather than a boolean list so that adding a constraint
 * is a field, and so an absent field and a `false` field hash identically:
 * a constraint nobody has implemented yet must not change the identity of
 * every route planned before it existed.
 */
export interface RouteConstraintFlags {
  requireEarthVisibility?: boolean
  requireSafeHaven?: boolean
  requireIlluminationCorridor?: boolean
  riskAlpha?: number | null
}

export interface RouteIdentityInput {
  roverId: string
  start: Cell | null
  goal: Cell | null
  weights: PlanWeights
  constraints?: RouteConstraintFlags
}

/**
 * A route identity, or null when there is no route to identify.
 *
 * Null rather than an empty string so `identityA === identityB` cannot quietly
 * report that two un-planned states are "the same route" and un-stale an
 * analysis that should have gone stale.
 */
export type RouteIdentity = string | null

/**
 * Weight keys, sorted, so that `{w_slope, w_energy}` and `{w_energy, w_slope}`
 * -- which are the same weights -- produce the same identity. Object key order
 * is insertion order in JS, and the weights object is rebuilt from a slider
 * every render, so relying on it would make identity flap for no reason.
 *
 * Values are rounded to six decimals before hashing. A slider produces floats
 * whose last bits are noise; without this, dragging a control back to where it
 * started could leave a value that differs in the fifteenth decimal and marks
 * every analysis stale.
 */
function serialiseWeights(weights: PlanWeights): string {
  const record = weights as unknown as Record<string, unknown>
  return Object.keys(record)
    .sort()
    .map((key) => {
      const value = record[key]
      return typeof value === 'number' && Number.isFinite(value)
        ? `${key}=${value.toFixed(6)}`
        : `${key}=${String(value)}`
    })
    .join(',')
}

/**
 * Only constraints that are actually on are serialised.
 *
 * This is the non-regression rule from spec section 2 applied to identity: a
 * disabled feature contributes nothing, exactly as it contributes no field to
 * the request body. A route planned with every advanced constraint off has to
 * hash identically to a route planned before those constraints existed --
 * otherwise merely shipping the feature would invalidate every stored
 * analysis.
 */
function serialiseConstraints(constraints: RouteConstraintFlags | undefined): string {
  if (!constraints) return ''
  const parts: string[] = []
  if (constraints.requireEarthVisibility) parts.push('earth')
  if (constraints.requireSafeHaven) parts.push('haven')
  if (constraints.requireIlluminationCorridor) parts.push('corridor')
  if (typeof constraints.riskAlpha === 'number' && Number.isFinite(constraints.riskAlpha)) {
    parts.push(`alpha=${constraints.riskAlpha.toFixed(4)}`)
  }
  return parts.sort().join(',')
}

/**
 * Build the identity. Null when start or goal is missing -- there is no route
 * without both, so there is nothing for an analysis to be attached to.
 *
 * The result is a readable string rather than a numeric hash: it lands in
 * React dependency arrays and in test failures, and "lpr_1|100,100|140,140|..."
 * says what changed where a 32-bit number would not. Nothing here is a
 * security boundary, so collision resistance is not a requirement.
 */
export function routeIdentityOf(input: RouteIdentityInput): RouteIdentity {
  const { roverId, start, goal, weights, constraints } = input
  if (!start || !goal) return null
  return [
    roverId,
    `${start[0]},${start[1]}`,
    `${goal[0]},${goal[1]}`,
    serialiseWeights(weights),
    serialiseConstraints(constraints),
  ].join('|')
}

/**
 * Has the route an analysis was computed against been replaced?
 *
 * `false` when either side is null: an analysis with no recorded identity is
 * not evidence of staleness, and a cockpit with no current route has nothing
 * to contradict it. Marking those stale would put a warning on screen in the
 * one case where there is nothing to warn about.
 */
export function isRouteIdentityStale(
  analysedAt: RouteIdentity,
  current: RouteIdentity,
): boolean {
  if (analysedAt === null || current === null) return false
  return analysedAt !== current
}
