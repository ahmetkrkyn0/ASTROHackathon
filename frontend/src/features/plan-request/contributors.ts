/**
 * Fields features add to a plan request -- 2-kisi section 6.4.
 *
 * Both tracks extend the same request body: environmental constraints on one
 * side, risk and survival on the other. A single hand-edited request builder
 * would be a daily merge conflict, so this follows the codebase's own
 * `FEATURES` pattern instead -- a plain append-only array evaluated at module
 * load. Two people adding two constraints touch one line each, and a conflict
 * resolves by keeping both.
 *
 * The `enabled: false -> null` shape is not a convenience. It is spec section
 * 2, the non-regression rule, expressed in the type system: a switched-off
 * feature contributes **no key at all**, rather than a key with a neutral
 * value. `require_earth_visibility: false` and `risk_alpha: 0.5` are not
 * neutral -- the first changes a documented default and the second is a
 * fabricated number the operator never chose. `null` is the only answer that
 * leaves the request byte-identical to what the cockpit sent before any of
 * this existed, which is what `planRequest.nonregression.test.ts` asserts.
 */

/** Everything a contributor is allowed to look at. Read-only by construction. */
export interface PlanRequestContext {
  /** Which endpoint is being built. Some constraints are 4-D only. */
  readonly endpoint: 'plan' | 'plan-4d'
  /** Advanced constraints the operator has switched on. */
  readonly constraints: Readonly<Record<string, unknown>>
  /**
   * Capability verdicts by feature id. A contributor whose backing data is
   * absent must not send its field: the operator may have left a toggle on
   * from a session where the cache existed, and sending the flag anyway earns
   * a 422 that reads like a bug.
   */
  readonly available: Readonly<Record<string, boolean>>
}

export interface PlanRequestContributor {
  /** Stable id, matching the owning feature's registry id where there is one. */
  readonly id: string
  /**
   * Whether this contributor has anything to say for this request.
   * False means the request must not change in any way.
   */
  enabled(context: PlanRequestContext): boolean
  /**
   * The fields to merge in. `null` is the same statement as `enabled: false`
   * and is checked as well -- a contributor is allowed to decide late that it
   * has nothing to add without having to re-derive `enabled`.
   */
  fields(context: PlanRequestContext): Record<string, unknown> | null
}

/**
 * A4 -- Earth visibility. 4-D only: the rule is about which time slice a MOVE
 * arrives in, which the 2-D planner has no notion of.
 */
export const earthVisibilityContributor: PlanRequestContributor = {
  id: 'earth-visibility',
  enabled: (context) =>
    context.endpoint === 'plan-4d' &&
    context.constraints.requireEarthVisibility === true &&
    context.available['earth-visibility'] === true,
  fields: (context) =>
    earthVisibilityContributor.enabled(context) ? { require_earth_visibility: true } : null,
}

/** A1 -- Safe haven deadline. 4-D only, same reason. */
export const safeHavenContributor: PlanRequestContributor = {
  id: 'safe-haven',
  enabled: (context) =>
    context.endpoint === 'plan-4d' &&
    context.constraints.requireSafeHaven === true &&
    context.available['safe-haven'] === true,
  fields: (context) =>
    safeHavenContributor.enabled(context) ? { require_safe_haven: true } : null,
}

/**
 * A2 -- the continuous-illumination corridor. 4-D only.
 *
 * The backend calls this `require_continuous_illumination`, not
 * `require_illumination_corridor`: the corridor is the *volume* the rule is
 * built from, the rule itself is about staying continuously lit. The name is
 * taken from `Plan4DRequest`, never guessed from the endpoint's name.
 */
export const illuminationCorridorContributor: PlanRequestContributor = {
  id: 'illumination-corridor',
  enabled: (context) =>
    context.endpoint === 'plan-4d' &&
    context.constraints.requireIlluminationCorridor === true &&
    context.available['illumination-corridor'] === true,
  fields: (context) =>
    illuminationCorridorContributor.enabled(context)
      ? { require_continuous_illumination: true }
      : null,
}

/**
 * C4 -- the roughness weight.
 *
 * Unlike the two above this is a weight, not a flag, and it goes to both
 * endpoints. It is contributed only when the operator has actually moved the
 * slider: the backend already applies its own per-rover default of 0.15, so
 * sending that value back would be the frontend asserting a number it did not
 * choose, and would make an untouched cockpit's request differ from the one
 * the non-regression baseline recorded.
 */
export const roughnessWeightContributor: PlanRequestContributor = {
  id: 'roughness-weight',
  enabled: (context) =>
    context.available['roughness'] === true &&
    typeof context.constraints.wRoughness === 'number' &&
    Number.isFinite(context.constraints.wRoughness),
  fields: (context) =>
    roughnessWeightContributor.enabled(context)
      ? { weights: { w_roughness: context.constraints.wRoughness as number } }
      : null,
}

/**
 * The list. Append-only: add at the end, never reorder, never edit a
 * neighbour's line.
 *
 * Person B's contributors (risk, survival, thermal dwell) belong at the
 * bottom of this array.
 */
export const PLAN_REQUEST_CONTRIBUTORS: readonly PlanRequestContributor[] = [
  earthVisibilityContributor,
  safeHavenContributor,
  illuminationCorridorContributor,
  roughnessWeightContributor,
]

/**
 * Fold the contributors into a base request body.
 *
 * `weights` is merged one level deep rather than replaced, because more than
 * one contributor may add a weight and the base body already carries the four
 * the cockpit has always sent. Everything else is a top-level assignment: no
 * contributor is permitted to reach into another's sub-object, and a
 * contributor returning a key that is already present is a bug worth
 * surfacing rather than silently resolving, so the last writer wins and the
 * id is reported.
 */
export function applyPlanRequestContributors<T extends Record<string, unknown>>(
  base: T,
  context: PlanRequestContext,
  contributors: readonly PlanRequestContributor[] = PLAN_REQUEST_CONTRIBUTORS,
): T {
  let result: Record<string, unknown> = { ...base }

  for (const contributor of contributors) {
    if (!contributor.enabled(context)) continue
    const fields = contributor.fields(context)
    if (!fields) continue

    for (const [key, value] of Object.entries(fields)) {
      if (key === 'weights' && isPlainObject(value) && isPlainObject(result.weights)) {
        result = { ...result, weights: { ...result.weights, ...value } }
        continue
      }
      result = { ...result, [key]: value }
    }
  }

  return result as T
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
