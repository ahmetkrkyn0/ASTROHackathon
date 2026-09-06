/**
 * What a failed backend call MEANS, as opposed to what its status code was.
 *
 * Section 5.3 of the integration plan: HTTP status alone must not decide UI
 * behaviour. The case it exists for is the planner returning 404 because no
 * route satisfies the constraints the operator switched on. That is not a
 * failed request -- the planner ran, correctly, and answered. Showing
 * "Request failed" there tells the operator their software is broken when what
 * actually happened is that their mission is infeasible, which is a finding.
 *
 * THE 404 IS OVERLOADED, and this is the whole reason a classifier is needed
 * rather than a switch on `status`. Read against the data contract, 404 means
 * two unrelated things:
 *
 *   - from a planner endpoint: no feasible route. The contract's own 404 texts
 *     say which constraint closed the route -- the corridor's voxel counts, the
 *     chance constraint's count of refused moves, the battery envelope.
 *   - from a layer or series endpoint: the preprocessing cache does not exist.
 *     The contract is explicit that a grid full of zeros is never returned in
 *     this case, and that the 404 names the script to run.
 *
 * The same split decides whether the current route survives. A layer that is
 * missing costs the operator a layer; an infeasible mission costs them the
 * route they were about to fly. Neither may be reported as the other, and
 * neither may delete a route that a separate, optional analysis failed on.
 *
 * WHAT IS NOT HERE. Unavailability that arrives with HTTP 200 -- the
 * `"model": "unavailable"` + `reason` object several endpoints return in place
 * of computed fields -- is not a failure and is not classified here. That is a
 * successful answer whose content is "I cannot compute this", and it belongs
 * to the capability model. This module only sees calls that threw.
 */

/**
 * The kind of endpoint a call was made to.
 *
 * Required, not inferred: the caller always knows, and guessing it from the
 * path would put a table of URL patterns here that goes stale the first time
 * an endpoint is renamed.
 */
export type EndpointKind =
  /** Returns a route. A 404 here is a finding about the mission. */
  | 'planner'
  /** Returns a grid or a time series. A 404 here is missing preprocessing. */
  | 'layer'
  /** Post-route analysis. Its failure never invalidates the route. */
  | 'analysis'

export type FailureKind =
  /** The backend was not reachable at all. Nothing ran. */
  | 'transport'
  /** The request was refused as malformed or out of range. Ours to fix. */
  | 'invalid-request'
  /** The data needed does not exist on this deployment. Not an error. */
  | 'data-unavailable'
  /** The planner ran and found no route under the active constraints. */
  | 'mission-infeasible'
  /** An optional analysis failed. The route it was about is still valid. */
  | 'analysis-failure'
  /** Unrecognised. Reported as itself rather than forced into a category. */
  | 'unknown'

export interface Failure {
  kind: FailureKind
  /** HTTP status, or null when nothing answered. */
  status: number | null
  /**
   * The backend's own words. Shown when it is the most useful thing available
   * -- an infeasible mission's 404 names the constraint that closed the route,
   * and an unavailable layer's names the script that builds it. Never
   * paraphrased away.
   */
  detail: string
  /**
   * Whether a route already on screen must be kept. Only a mission-infeasible
   * verdict is about the route itself; everything else leaves it standing.
   */
  keepsExistingRoute: boolean
}

/** Anything with a numeric `status` -- see `classifyFailure`. */
function statusOf(error: unknown): number | null {
  if (typeof error !== 'object' || error === null) return null
  const status = (error as { status?: unknown }).status
  return typeof status === 'number' ? status : null
}

function detailOf(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  if (typeof error === 'string') return error
  return 'The backend did not say what went wrong.'
}

/**
 * Classify a thrown error.
 *
 * Deliberately structural rather than `instanceof ApiError`. There are two
 * ApiError classes in this codebase -- one in net/client.ts, one in
 * api/client.ts -- with the same name and no relation to each other, so an
 * `instanceof` check passes or fails depending on which module threw. Reading
 * `status` off the object works for both, and would keep working if a third
 * appeared. Unifying them is a refactor, and this plan is not a refactor.
 */
export function classifyFailure(error: unknown, endpoint: EndpointKind): Failure {
  const status = statusOf(error)
  const detail = detailOf(error)

  // Nothing answered: no status was ever set. An aborted request reaches here
  // too, and callers are expected to drop those before classifying rather than
  // showing the operator a connectivity warning they caused by navigating.
  if (status === null) {
    return { kind: 'transport', status: null, detail, keepsExistingRoute: true }
  }

  if (status === 404) {
    if (endpoint === 'planner') {
      return { kind: 'mission-infeasible', status, detail, keepsExistingRoute: false }
    }
    // Layer and analysis 404s are the contract's "the cache for this does not
    // exist" -- it answers with the name of the script that would build it.
    return { kind: 'data-unavailable', status, detail, keepsExistingRoute: true }
  }

  // 503 is the contract's "the grid is not loaded", which is a deployment
  // state rather than a bad request.
  if (status === 503) {
    return { kind: 'data-unavailable', status, detail, keepsExistingRoute: true }
  }

  if (status === 422) {
    // Configuration, not connectivity: a weight outside its range, a missing
    // start_utc, a rule asked for against a shadow model that cannot support
    // it, a slice budget over the cap.
    return { kind: 'invalid-request', status, detail, keepsExistingRoute: true }
  }

  if (endpoint === 'analysis') {
    return { kind: 'analysis-failure', status, detail, keepsExistingRoute: true }
  }

  return { kind: 'unknown', status, detail, keepsExistingRoute: true }
}

/**
 * A sentence for the operator.
 *
 * The backend's detail is preferred wherever it is the specific thing worth
 * reading, and the lead-in exists so the category is legible before the
 * detail's own wording is parsed.
 */
export function describeFailure(failure: Failure): string {
  switch (failure.kind) {
    case 'transport':
      return 'Cannot reach the mission backend. Check that the API is running.'
    case 'mission-infeasible':
      return `No feasible route under the selected mission constraints. ${failure.detail}`
    case 'data-unavailable':
      return `This data is not available on this deployment. ${failure.detail}`
    case 'invalid-request':
      return `The backend refused the request as invalid. ${failure.detail}`
    case 'analysis-failure':
      return `This analysis could not be completed; the route is unaffected. ${failure.detail}`
    case 'unknown':
      return failure.detail
  }
}
