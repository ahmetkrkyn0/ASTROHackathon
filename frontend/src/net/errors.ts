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
 * So classification happens here, once, from the backend's own `detail` text,
 * and every caller asks this module instead of reading `status` itself.
 */

import { ApiError } from './client'

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

function remedyFrom(detail: string): string | null {
  const match = /\b(scripts\/[\w.-]+\.py)/.exec(detail)
  return match ? `python ${match[1]}` : null
}

/**
 * Classify anything a fetch can throw.
 *
 * `options.optional` marks a call whose failure must not disturb what is
 * already on screen -- a stress test, an uncertainty band. Those degrade to
 * `analysis-failure` so a caller cannot accidentally clear a valid route
 * because an optional extra did not come back.
 */
export function classifyError(
  error: unknown,
  options: { optional?: boolean } = {},
): ClassifiedError {
  const cause = error instanceof Error ? error : new Error(String(error))

  if (!(error instanceof ApiError)) {
    // fetch() rejects with a TypeError when the request never reached a server.
    return {
      kind: options.optional ? 'analysis-failure' : 'transport',
      detail: cause.message,
      status: null,
      remedy: null,
      cause,
    }
  }

  const detail = error.message
  const remedy = remedyFrom(detail)
  const base = { detail, status: error.status, remedy, cause }

  if (error.status === 404) {
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

  if (error.status === 422) {
    // 422 splits too. FastAPI answers 422 for a malformed request, but these
    // endpoints also use it for "the epoch or cache this needs is missing",
    // which is a data question wearing a validation status.
    if (matches(detail, UNAVAILABLE_MARKERS)) {
      return { ...base, kind: 'data-unavailable' }
    }
    if (matches(detail, INFEASIBLE_MARKERS)) {
      return { ...base, kind: 'mission-infeasible' }
    }
    return { ...base, kind: 'invalid-request' }
  }

  if (options.optional) {
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
