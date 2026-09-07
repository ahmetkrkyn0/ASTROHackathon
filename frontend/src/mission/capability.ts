/**
 * Whether a backend capability is actually there -- spec section 5.1.
 *
 * The twelve backend features that arrived with `berke-3d-backendEnhance` are
 * not uniformly available: several of them read a `.npy` cache that a fresh
 * clone does not have, so the same endpoint on the same build answers with
 * data on one machine and `unavailable` on the next. The frontend is
 * forbidden from assuming "new backend therefore every layer exists"; it has
 * to discover the answer from the manifest or the response it was handed.
 *
 * The distinction this module exists to enforce is `unavailable` vs `error`.
 * They are not the same thing and must never render the same way:
 *
 *   unavailable -- the backend is healthy and told us, correctly, that the
 *                  data does not exist here. It usually names the script that
 *                  would produce it. Nothing is broken. Say so, and say what
 *                  would fix it.
 *   error       -- something went wrong. The backend is unreachable, or it
 *                  failed, or we asked for something malformed.
 *
 * Collapsing the first into the second reads as a bug report for a working
 * system. Collapsing the second into the first hides a real failure. Both are
 * lies, so the union below keeps them apart at the type level: `unavailable`
 * carries a `reason` and no `error`, `error` carries an `error` and no
 * `reason`, and neither of them can carry a `value`.
 */

/** The seven states of section 5.1, as a discriminant. */
export type CapabilityStatus =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'unavailable'
  | 'unsupported'
  | 'error'
  | 'stale'

/**
 * Nothing has asked for it yet.
 *
 * `idle` rather than the spec's `available`: "available" reads as a claim
 * about the data ("this exists"), which is exactly the claim we are not
 * entitled to make before asking. What we mean is that we have not looked.
 */
export interface CapabilityIdle {
  readonly status: 'idle'
}

export interface CapabilityLoading {
  readonly status: 'loading'
}

/** The data is here. This is the only state that carries a value. */
export interface CapabilityReady<T> {
  readonly status: 'ready'
  readonly value: T
}

/**
 * The backend answered, and the honest answer is that the data does not
 * exist on this deployment.
 *
 * `reason` is the backend's own sentence, not ours. These endpoints reply with
 * text like "run scripts/build_roughness_cache.py, then reload with POST
 * /api/load-preprocessed" -- more useful than anything the frontend could
 * invent, so it is passed through rather than reworded.
 */
export interface CapabilityUnavailable {
  readonly status: 'unavailable'
  readonly reason: string
  /** The script that would produce the missing cache, when the reason names one. */
  readonly remedy: string | null
}

/**
 * The deployment cannot do this at all -- an older backend that never had the
 * endpoint, as opposed to a current one whose cache is missing.
 *
 * Separate from `unavailable` because the remedy differs: `unavailable` is
 * fixed by running a script, `unsupported` by deploying a newer backend.
 */
export interface CapabilityUnsupported {
  readonly status: 'unsupported'
  readonly reason: string
}

/** Something failed. Transport, a malformed request, or a backend fault. */
export interface CapabilityError {
  readonly status: 'error'
  readonly error: Error
}

/**
 * We hold a value, but it describes inputs that have since changed -- section
 * 5.4. The value is kept so the panel can keep showing it, marked, rather
 * than blanking and losing the operator's place.
 */
export interface CapabilityStale<T> {
  readonly status: 'stale'
  readonly value: T
  readonly reason: string
}

export type Capability<T> =
  | CapabilityIdle
  | CapabilityLoading
  | CapabilityReady<T>
  | CapabilityUnavailable
  | CapabilityUnsupported
  | CapabilityError
  | CapabilityStale<T>

export const CAPABILITY_IDLE: CapabilityIdle = Object.freeze({ status: 'idle' })
export const CAPABILITY_LOADING: CapabilityLoading = Object.freeze({ status: 'loading' })

export function capabilityReady<T>(value: T): CapabilityReady<T> {
  return { status: 'ready', value }
}

export function capabilityUnavailable(reason: string): CapabilityUnavailable {
  return { status: 'unavailable', reason, remedy: remedyFrom(reason) }
}

export function capabilityUnsupported(reason: string): CapabilityUnsupported {
  return { status: 'unsupported', reason }
}

export function capabilityError(error: Error): CapabilityError {
  return { status: 'error', error }
}

export function capabilityStale<T>(value: T, reason: string): CapabilityStale<T> {
  return { status: 'stale', value, reason }
}

/**
 * The value, or null. The only supported way to read one.
 *
 * A caller that reached into `.value` directly would have to be typed against
 * the two states that carry one, and the compiler would stop it -- which is
 * the point. This helper exists so the common "draw it if we have it" case
 * does not need a switch, and it deliberately returns the stale value too:
 * showing a marked stale number beats showing nothing.
 */
export function capabilityValue<T>(capability: Capability<T>): T | null {
  return capability.status === 'ready' || capability.status === 'stale'
    ? capability.value
    : null
}

/** True while a request is genuinely outstanding. */
export function isCapabilityPending(capability: Capability<unknown>): boolean {
  return capability.status === 'loading'
}

/**
 * The one sentence to put in front of an operator.
 *
 * Every branch returns the backend's own words where there are any. `error` is
 * the only branch that produces frontend prose, and it is the only branch
 * where something is actually wrong.
 */
export function capabilityMessage(capability: Capability<unknown>): string | null {
  switch (capability.status) {
    case 'idle':
    case 'loading':
    case 'ready':
      return null
    case 'unavailable':
    case 'unsupported':
    case 'stale':
      return capability.reason
    case 'error':
      return capability.error.message
  }
}

/**
 * `POST /api/load-preprocessed`-style remedies, pulled out of the backend's
 * own sentence so a panel can offer the command as a command.
 *
 * Matches the two shapes these endpoints actually use -- "run
 * scripts/build_x.py" and a bare "scripts/build_x.py" -- and returns null
 * rather than guessing when neither appears. A wrong command is worse than
 * no command.
 */
function remedyFrom(reason: string): string | null {
  const match = /\b(scripts\/[\w.-]+\.py)/.exec(reason)
  return match ? `python ${match[1]}` : null
}

/**
 * Turn a thrown error into the right state.
 *
 * This is where the 404-is-not-a-failure rule is actually enforced, and it is
 * the reason `net/errors.ts` exists next door: these endpoints answer 404 for
 * two completely different situations -- "that cache was never built" and
 * "the planner ran and no route satisfies your constraints". Only the first
 * is a capability question, so this function takes the classification rather
 * than repeating it.
 *
 * `signal` is checked first: an aborted request is not a failure, it is a
 * request the caller cancelled, and reporting it as an error makes every
 * fast-moving slider look broken.
 */
export function capabilityFromError(
  error: unknown,
  options: { isDataUnavailable: boolean; signal?: AbortSignal },
): Capability<never> | null {
  if (options.signal?.aborted) return null
  if (error instanceof DOMException && error.name === 'AbortError') return null

  // Read structurally, never `instanceof`. This codebase defines ApiError twice
  // -- net/client.ts and api/client.ts, unrelated -- so an instanceof check
  // recognises one and not the other, and the branch it falls past paints a
  // missing cache as `error`. That is the single rule this module exists to
  // enforce, inverted. See net/errors.ts for the same fix on the same cause.
  const status =
    typeof error === 'object' && error !== null && typeof (error as { status?: unknown }).status === 'number'
      ? (error as { status: number }).status
      : null
  const cause = error instanceof Error ? error : new Error(String(error))

  if (status !== null) {
    if (options.isDataUnavailable) return capabilityUnavailable(cause.message)
    // 501 and 405: the deployment does not have this endpoint at all, which is
    // a different remedy from a cache it never built.
    if (status === 501 || status === 405) {
      return capabilityUnsupported(cause.message)
    }
    return capabilityError(cause)
  }
  return capabilityError(cause)
}

/**
 * The `{ model, reason }` block several of these endpoints publish inline.
 *
 * `/api/safe-haven`, `/api/cell-telemetry`, `/api/earth-series` and the
 * survival and dwell endpoints all answer 200 and then say, in the body, that
 * they could not compute anything -- `"model": "unavailable"` with a reason.
 * A 200 is not evidence the data is there, so this is checked as carefully as
 * a status code.
 */
export interface ModelBlock {
  model: string
  reason?: string | null
}

export function isModelUnavailable(block: ModelBlock | null | undefined): boolean {
  return !block || block.model === 'unavailable'
}

/**
 * Fold one of those inline model blocks into a capability.
 *
 * `static` is deliberately NOT unavailable: a static shadow model is real data
 * that simply does not vary with time. It comes back as `ready`, and the
 * feature that cares about time-variation asks about `model` itself -- the way
 * `useTimeAxis` already gates its play button on
 * `manifest.shadow_model.model !== 'static'`.
 */
export function capabilityFromModel<T>(
  block: ModelBlock | null | undefined,
  value: T,
): Capability<T> {
  if (isModelUnavailable(block)) {
    return capabilityUnavailable(
      block?.reason ?? 'The backend reported this model as unavailable and gave no reason.',
    )
  }
  return capabilityReady(value)
}
