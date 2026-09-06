import type { Failure } from '../net/errors'

/**
 * Whether a backend capability is here, and if not, why not.
 *
 * Section 5.1 of the integration plan. The assumption it exists to break is
 * "the backend is the new one, therefore every layer is present". It is not:
 * most of the new scientific products are read from preprocessing caches that
 * a given deployment may simply never have built, and the contract is explicit
 * that in that case the backend refuses rather than returning a grid of zeros.
 *
 * The distinction the plan insists on, and the reason this is a discriminated
 * union rather than a status string beside a nullable error, is:
 *
 *     UNAVAILABLE IS NOT AN ERROR.
 *
 * A missing thermal-envelope cache is not a fault. Nothing is broken, no one
 * needs to retry, and the honest screen says "not available on this
 * deployment" and moves on. Reporting it in red as a failure teaches the
 * operator to distrust a working system. Made structural here so the two
 * cannot be mixed up by accident: `unavailable` carries a reason and no error,
 * `error` carries a Failure and no reason, and neither field can be read
 * without narrowing first.
 *
 * Fabricating the data instead is out of the question, and is the one thing
 * this type exists to make awkward. There is no state that means "absent, but
 * here are some numbers anyway".
 */
export type Capability<T> =
  /** Nobody has asked yet. */
  | { state: 'idle' }
  /** A request is in flight. Any previously held value is kept visible. */
  | { state: 'loading'; previous?: T }
  /** The data is here and matches the current mission. */
  | { state: 'ready'; value: T }
  /**
   * The backend answered and said it cannot produce this: the cache, kernel or
   * epoch it needs does not exist. `reason` is the backend's own wording,
   * which usually names the script that would build it.
   */
  | { state: 'unavailable'; reason: string }
  /**
   * This backend does not know the feature at all -- an older deployment than
   * the frontend. Distinct from `unavailable`, where the feature exists and
   * its data does not, because the fix is different: one is a deployment
   * upgrade, the other is a preprocessing run.
   */
  | { state: 'unsupported' }
  /** Something actually went wrong. */
  | { state: 'error'; failure: Failure }
  /**
   * The value was correct for a mission that is no longer the current one.
   * Kept rather than discarded so a panel can grey out what it was showing
   * instead of flashing empty, which reads as data loss.
   */
  | { state: 'stale'; value: T }

/** True when there is a value to draw, current or not. */
export function hasValue<T>(capability: Capability<T>): capability is
  | { state: 'ready'; value: T }
  | { state: 'stale'; value: T } {
  return capability.state === 'ready' || capability.state === 'stale'
}

/**
 * True when the absence is a fact about the deployment rather than a fault.
 *
 * The call site for this is presentation: these two states get a quiet,
 * explanatory treatment, and `error` does not.
 */
export function isAbsent<T>(capability: Capability<T>): boolean {
  return capability.state === 'unavailable' || capability.state === 'unsupported'
}

/**
 * Mark a held value as no longer current.
 *
 * Only `ready` can go stale. Applying this to a capability that never had a
 * value returns it untouched, so a caller invalidating a whole set of them on
 * a mission change does not have to filter first.
 */
export function markStale<T>(capability: Capability<T>): Capability<T> {
  return capability.state === 'ready' ? { state: 'stale', value: capability.value } : capability
}

/**
 * Several endpoints report their own inability inside a 200 response, as a
 * model object whose `model` field reads `"unavailable"` and which carries a
 * `reason` beside it. That is a successful answer, so it never reaches the
 * error classifier -- it has to be read here instead.
 *
 * Returns the reason when the object says it is unavailable, and null when it
 * describes a real model, which is what lets a caller write:
 *
 *     const reason = unavailableReason(response.safe_haven_model)
 *     return reason ? { state: 'unavailable', reason } : { state: 'ready', value }
 */
export function unavailableReason(model: unknown): string | null {
  if (typeof model !== 'object' || model === null) return null
  const record = model as { model?: unknown; reason?: unknown }
  if (record.model !== 'unavailable') return null
  return typeof record.reason === 'string' && record.reason.length > 0
    ? record.reason
    : 'The backend did not say why.'
}
