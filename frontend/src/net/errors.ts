/**
 * What a failure means, as opposed to what its status code was -- spec 5.3.
 *
 * An HTTP status is not enough to decide how the cockpit should behave, and on
 * this backend 404 is the case that proves it. The same code arrives for two
 * situations with nothing in common:
 *
 *   GET /api/layers/roughness   404  "roughness is not present in the loaded
 *                                     grids ... run scripts/build_roughness_cache.py"
 *   POST /api/plan-4d           404  "... edges would have driven the rover into
 *                                     a cell with no Earth visibility ..."
 *
 * The first is a machine that never built a cache. The second is the planner
 * working perfectly and reporting that the operator's own constraints leave no
 * route. Rendering either as "Request failed" is wrong, and rendering them the
 * same way is worse: the second is a mission finding, arguably the most
 * valuable thing the constraint feature produces.
 *
 * So classification happens here, once, and every caller asks this module
 * instead of reading `status` itself.
 *
 * TWO INPUTS DECIDE A 404, and the caller's is the stronger one. `endpoint`
 * says which family was called, which the caller always knows; the marker
 * lists below are the fallback for a caller that did not say. A planner 404
 * whose sentence is "Chance constraint: 283148 moves were refused" matches no
 * marker at all, and no list of phrases would have caught it -- but the caller
 * knew it had asked for a route.
 *
 * NOTHING HERE USES `instanceof`. This codebase defines ApiError twice, in
 * net/client.ts and api/client.ts, with no relation between them, so an
 * instanceof check passes or fails depending on which module happened to
 * throw -- and the branch it falls past reports a missing cache as a
 * transport failure. Reading `status` off the object works for both and
 * would keep working if a third appeared.
 */

/**
 * Which family of endpoint a call was made to.
 *
 * Required at the call site rather than inferred: the caller always knows, and
 * deriving it from the path would put a table of URL patterns in here that goes
 * stale the first time an endpoint is renamed.
 */
export type EndpointKind =
  /** Returns a route. A 404 here is a finding about the mission. */
  | 'planner'
  /** Returns a grid or a time series. A 404 here is missing preprocessing. */
  | 'layer'
  /** Post-route analysis. Its failure never invalidates the route. */
  | 'analysis'

export type ErrorKind =
  /** The backend could not be reached at all. */
  | 'transport'
  /** We asked for something malformed or impossible. 422. */
  | 'invalid-request'
  /** The backend is fine; the cache, kernel or epoch this needs does not exist. */
  | 'data-unavailable'
  /** The planner ran and no route satisfies the selected constraints. */
  | 'mission-infeasible'
  /** An optional analysis failed. The route it was about is still valid. */
  | 'analysis-failure'
  /** Anything else. A genuine fault. */
  | 'backend-fault'

export interface ClassifiedError {
  readonly kind: ErrorKind
  /** The backend's own sentence where there is one. Never rewritten. */
  readonly detail: string
  readonly status: number | null
  /** The script that would fix a `data-unavailable`, when the detail names one. */
  readonly remedy: string | null
  readonly cause: Error
}

/**
 * Phrases the cache-missing 404s use.
 *
 * Matching on prose is ugly, and the alternative was worse: the honest
 * alternative is a machine-readable error code the backend does not emit, and
 * the dishonest one is treating every 404 the same. These strings come from
 * the captured fixtures in `net/__fixtures__/`, so a wording change on the
 * backend shows up as a failing contract test rather than as a mislabelled
 * panel in production.
 */
const UNAVAILABLE_MARKERS = [
  'is not present in the loaded grids',
  'no thermal envelope cache',
  'no dem_clone_horizons.npy',
  'beside the processed grids',
  'run scripts/',
  'has no horizon cache',
  'cannot be computed without one',
]

/**
 * Phrases a constraint-closed-the-route 404 uses.
 *
 * Checked before the unavailable markers: an infeasibility message may well
 * name a script in its explanation, and "no route under your constraints"
 * outranks "and by the way build this cache" when both are present.
 */
const INFEASIBLE_MARKERS = [
  'no route',
  'no feasible',
  'would have driven the rover',
  'not traversable',
  'falls in coarse block',
  'unreachable',
  'no path',
]

function matches(detail: string, markers: readonly string[]): boolean {
  const lowered = detail.toLowerCase()
  return markers.some((marker) => lowered.includes(marker))
}

/** Any thrown value carrying a numeric `status`, whichever class it came from. */
function statusOf(error: unknown): number | null {
  if (typeof error !== 'object' || error === null) return null
  const status = (error as { status?: unknown }).status
  return typeof status === 'number' ? status : null
}

function remedyFrom(detail: string): string | null {
  const match = /\b(scripts\/[\w.-]+\.py)/.exec(detail)
  return match ? `python ${match[1]}` : null
}

/**
 * Classify anything a fetch can throw.
 *
 * `options.endpoint` is what the caller knows and the text does not: which
 * family it asked. It decides the 404, and only the 404 -- a 422 from a planner
 * is still a configuration problem, not an infeasible mission.
 *
 * `options.optional` marks a call whose failure must not disturb what is
 * already on screen -- a stress test, an uncertainty band. Those degrade to
 * `analysis-failure` so a caller cannot accidentally clear a valid route
 * because an optional extra did not come back. `endpoint: 'analysis'` says the
 * same thing and both are honoured.
 */
export function classifyError(
  error: unknown,
  options: { optional?: boolean; endpoint?: EndpointKind } = {},
): ClassifiedError {
  const cause = error instanceof Error ? error : new Error(String(error))
  const detail = cause.message || 'The backend did not say what went wrong.'
  const status = statusOf(error)

  // Nothing answered, so nothing ran. Reported as transport even for an
  // optional analysis: an unreachable backend is a fact about the deployment,
  // and calling it an analysis failure would hide an outage behind a panel.
  if (status === null) {
    return { kind: 'transport', detail, status: null, remedy: null, cause }
  }

  const remedy = remedyFrom(detail)
  const base = { detail, status, remedy, cause }
  const endpoint = options.endpoint

  if (status === 404) {
    if (endpoint === 'planner') {
      return { ...base, kind: 'mission-infeasible' }
    }
    if (endpoint === 'layer' || endpoint === 'analysis') {
      return { ...base, kind: 'data-unavailable' }
    }
    // No endpoint given: fall back to the backend's own wording. Checked
    // infeasible-first, because an infeasibility message may well name a script
    // in its explanation and "no route under your constraints" outranks "and by
    // the way build this cache" when both are present.
    if (matches(detail, INFEASIBLE_MARKERS)) {
      return { ...base, kind: 'mission-infeasible' }
    }
    if (matches(detail, UNAVAILABLE_MARKERS)) {
      return { ...base, kind: 'data-unavailable' }
    }
    // An unrecognised 404. Data-unavailable is the safer default here: it
    // reads as "this is not here", which a 404 always at least means, and it
    // does not accuse the operator's constraints of something they may not
    // have done.
    return { ...base, kind: 'data-unavailable' }
  }

  // The contract's "the grid is not loaded". A deployment state, not a fault:
  // every planning endpoint answers this until the pipeline has been run.
  if (status === 503) {
    return { ...base, kind: 'data-unavailable' }
  }

  if (status === 422) {
    // 422 splits too. FastAPI answers 422 for a malformed request, but these
    // endpoints also use it for "the epoch or cache this needs is missing",
    // which is a data question wearing a validation status. The endpoint hint
    // deliberately does not override this: only the sentence can tell them
    // apart, because both arrive from the same family.
    if (matches(detail, UNAVAILABLE_MARKERS)) {
      return { ...base, kind: 'data-unavailable' }
    }
    // An analysis cannot discover that the mission is infeasible: it is asked
    // ABOUT a route that already exists, so a 422 from one is a statement
    // about the request we built, not about the route.
    //
    // The two live 422s prove the split. Same three words, opposite meanings:
    //
    //   planner  "goal (300, 300) falls in coarse block (75, 75) at
    //             coarsen=4, which is not traversable"
    //             -> the operator put the goal somewhere impassable. A finding.
    //   analysis "path_states: state 14 (49, 21, 14) is not traversable"
    //             -> we posted a planned route at the wrong cell size. Ours.
    //
    // No marker list can tell those apart, and the caller never has to guess.
    if (endpoint !== 'analysis' && matches(detail, INFEASIBLE_MARKERS)) {
      return { ...base, kind: 'mission-infeasible' }
    }
    return { ...base, kind: 'invalid-request' }
  }

  if (options.optional || endpoint === 'analysis') {
    return { ...base, kind: 'analysis-failure' }
  }
  return { ...base, kind: 'backend-fault' }
}

/**
 * True when this failure means the capability layer should say `unavailable`
 * rather than `error`. The bridge `capabilityFromError` takes as its flag.
 */
export function isDataUnavailable(error: unknown): boolean {
  return classifyError(error).kind === 'data-unavailable'
}

/**
 * Operator-facing headline for a classified failure.
 *
 * `mission-infeasible` is the one branch with prose of our own, because the
 * backend's sentence there is a description of rejected edges and the operator
 * needs the conclusion first. The backend's own text is still carried in
 * `detail` and belongs directly underneath this line.
 */
export function errorHeadline(classified: ClassifiedError): string {
  switch (classified.kind) {
    case 'transport':
      return 'Backend unreachable'
    case 'invalid-request':
      return 'Request rejected'
    case 'data-unavailable':
      return 'Data not available on this deployment'
    case 'mission-infeasible':
      return 'No feasible route under the selected mission constraints'
    case 'analysis-failure':
      return 'Analysis did not complete'
    case 'backend-fault':
      return 'Backend error'
  }
}

/**
 * Whether the route already on screen survives this failure.
 *
 * Only an infeasible plan invalidates a route, and even then only because
 * there is no new route to show. An optional analysis blowing up leaves the
 * route exactly as valid as it was -- spec 5.3, last clause.
 */
export function keepsExistingRoute(classified: ClassifiedError): boolean {
  return classified.kind !== 'mission-infeasible'
}

/**
 * The same verdict, in the B track's vocabulary.
 *
 * Two names for one taxonomy, and deliberately not two taxonomies. The A track
 * asks "what kind of error is this, and does the route survive it" as two
 * calls; the B track wants one object carrying both, addressed by endpoint
 * family. Rather than pick a winner and rewrite a dozen call sites -- which is
 * how a merge loses a feature -- `classifyFailure` is a projection of
 * `classifyError`. There is one place where a 404 is decided, so the two views
 * cannot drift apart later.
 */
export type FailureKind =
  | 'transport'
  | 'invalid-request'
  | 'data-unavailable'
  | 'mission-infeasible'
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

export function classifyFailure(error: unknown, endpoint: EndpointKind): Failure {
  const classified = classifyError(error, { endpoint })
  return {
    // `backend-fault` and `unknown` are the same state under two names: a
    // status this module has no rule for. Renamed rather than re-derived.
    kind: classified.kind === 'backend-fault' ? 'unknown' : classified.kind,
    status: classified.status,
    detail: classified.detail,
    keepsExistingRoute: keepsExistingRoute(classified),
  }
}

/**
 * A sentence for the operator.
 *
 * The backend's detail is preferred wherever it is the specific thing worth
 * reading, and the lead-in exists so the category is legible before the
 * detail's own wording is parsed. The word "failed" appears in none of these:
 * four of the six describe a working system.
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
