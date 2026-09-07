/**
 * How an advanced planner constraint reaches the request -- spec 6.4.
 *
 * Both tracks extend the same request body: environmental constraints on one
 * side, risk on the other. A single hand-edited request builder would be a
 * daily merge conflict, so this follows the codebase's own `FEATURES` pattern
 * instead -- a plain append-only array evaluated at module load. Two people
 * adding two constraints touch one line each, and a conflict resolves by
 * keeping both.
 *
 * THE RULE THIS FILE EXISTS FOR:
 *
 *     A CONSTRAINT THAT IS OFF SENDS NO FIELD AT ALL.
 *
 * Not `false`, not a neutral default -- no key. Several of these have no
 * neutral value: `risk_alpha: 0.5` is not "no risk appetite" (CVaR at 0.5 is
 * mu + 0.798 sigma), and `require_earth_visibility: false` overrides a
 * documented backend default. A disabled toggle that quietly sent one would
 * change every route in the product and look like nothing had happened. So a
 * contributor returns `null` when it is off, and both builders drop nulls.
 * `planRequest.test.ts` and `net/planRequest.nonregression.test.ts` pin it.
 *
 * TWO BUILDERS, TWO ENDPOINTS, ONE LIST. This is the shape the merge settled
 * on, and it is not an accident:
 *
 *   store.ts -> readPlanConstraints()  ->  POST /api/plan     (2-D)
 *   applyPlanRequestContributors()     ->  POST /api/plan-4d  (4-D)
 *
 * The 2-D builder calls `fields(state)` with NO context, and every contributor
 * that needs one returns null there. That is the whole guard. Measured against
 * the live backend: `POST /api/plan` accepts `require_safe_haven`,
 * `require_earth_visibility`, `require_continuous_illumination`,
 * `require_thermal_dwell` and `max_failure_probability` with a 200, then
 * SILENTLY IGNORES every one of them -- the route comes back byte-identical to
 * the unconstrained one and no field in the response says a constraint was
 * dropped. They are constraints on the time-expanded planner, and this cockpit
 * plans in 2-D on that path. A toggle that does nothing and reports nothing is
 * worse than no toggle, so they are reachable only from the 4-D builder, whose
 * switches sit beside the "Plan through time" button that issues it.
 */

/** Whatever one control holds. `value` is read only by the contributor that owns it. */
export interface ConstraintState {
  enabled: boolean
  /** An alpha, a rule name, a temperature, a weight. */
  value?: unknown
}

/**
 * What the operator manipulates. Declared beside the contributor rather than in
 * a panel so that adding a constraint stays a single append to this list -- the
 * panel renders whatever the registry describes and has no per-constraint code.
 */
export type ConstraintControl =
  /** On or off. Contributes a fixed field when enabled. */
  | { kind: 'toggle' }
  /** A number in a range, with the value the control starts at. */
  | { kind: 'number'; min: number; max: number; step: number; initial: number; unit?: string }
  /** One of a fixed set of backend enum values. */
  | { kind: 'choice'; options: ReadonlyArray<{ value: string; label: string }>; initial: string }

/** Everything a contributor is allowed to look at. Read-only by construction. */
export interface PlanRequestContext {
  /** Which endpoint is being built. Some constraints are 4-D only. */
  readonly endpoint: 'plan' | 'plan-4d'
  /** Advanced constraints the operator has switched on, by UI key. */
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
  /** Shown wherever the constraint is listed. */
  readonly label: string
  /** One line saying what switching this on does to the route. */
  readonly hint: string
  readonly control: ConstraintControl
  /**
   * The key this contributor reads out of a `PlanRequestContext.constraints`.
   * Only the 4-D builder uses it; the store addresses contributors by `id`.
   */
  readonly constraintKey: string
  /**
   * Whether this has anything to say for this request. False means the request
   * must not change in any way.
   */
  enabled(state: ConstraintState, context?: PlanRequestContext): boolean
  /**
   * The fields to merge in. `null` is the same statement as `enabled: false`
   * and is checked as well -- a contributor is allowed to decide late that it
   * has nothing to add. Returning `{}` is a bug, not a synonym for null: an
   * enabled constraint contributing no field would still move the route
   * identity and mark every post-route analysis stale for a request that did
   * not change.
   */
  fields(state: ConstraintState, context?: PlanRequestContext): Record<string, unknown> | null
}

/**
 * A 4-D-only environmental flag: on when the operator asked for it AND the data
 * behind it is actually on this deployment AND the request being built is the
 * time-expanded one.
 */
function environmentalConstraint(spec: {
  id: string
  label: string
  hint: string
  constraintKey: string
  /** Capability id in `context.available`. */
  dataId: string
  /** The backend's own field name. Read from Plan4DRequest, never guessed. */
  field: string
}): PlanRequestContributor {
  const enabled = (state: ConstraintState, context?: PlanRequestContext): boolean => {
    // No context means the 2-D builder, where this field is accepted and then
    // ignored. Off structurally, rather than by a check someone can forget.
    if (!context || context.endpoint !== 'plan-4d') return false
    const asked = state.enabled || context.constraints[spec.constraintKey] === true
    return asked && context.available[spec.dataId] === true
  }
  return {
    id: spec.id,
    label: spec.label,
    hint: spec.hint,
    control: { kind: 'toggle' },
    constraintKey: spec.constraintKey,
    enabled,
    fields: (state, context) => (enabled(state, context) ? { [spec.field]: true } : null),
  }
}

/** A4 -- Earth visibility. */
export const earthVisibilityContributor = environmentalConstraint({
  id: 'earth-visibility',
  label: 'Require Earth visibility',
  hint: 'Refuses any move that would arrive in a cell with no direct line to Earth in that time slice.',
  constraintKey: 'requireEarthVisibility',
  dataId: 'earth-visibility',
  field: 'require_earth_visibility',
})

/** A1 -- Safe haven reachability. */
export const safeHavenContributor = environmentalConstraint({
  id: 'safe-haven',
  label: 'Require Safe Haven reachability',
  hint: 'Refuses any state from which no Safe Haven can still be reached before the Earth sets.',
  constraintKey: 'requireSafeHaven',
  dataId: 'safe-haven',
  field: 'require_safe_haven',
})

/**
 * A2 -- the continuous-illumination corridor.
 *
 * The backend calls this `require_continuous_illumination`, not
 * `require_illumination_corridor`: the corridor is the *volume* the rule is
 * built from, the rule itself is about staying continuously lit. The name is
 * taken from `Plan4DRequest`, never guessed from the endpoint's name.
 */
export const illuminationCorridorContributor = environmentalConstraint({
  id: 'illumination-corridor',
  label: 'Require continuous illumination',
  hint: 'Keeps the route inside the lit, traversable and connected corridor for every slice it occupies.',
  constraintKey: 'requireIlluminationCorridor',
  dataId: 'illumination-corridor',
  field: 'require_continuous_illumination',
})

/**
 * C4 -- the roughness weight.
 *
 * Unlike the three above this is a weight, not a flag, so it nests under
 * `weights` rather than sitting at the top level. It is contributed only when
 * the operator has actually moved the slider: the backend already applies its
 * own per-rover default of 0.15, so sending that value back would be the
 * frontend asserting a number it did not choose, and would make an untouched
 * cockpit's request differ from the one the non-regression baseline recorded.
 *
 * 4-D builder only, like the rest. On the 2-D path the fifth weight is edited
 * where the other four are, in RoutePriorities, and travels inside `weights` --
 * it never passes through the store, whose flat merge would replace the whole
 * weights object with a one-key one.
 */
export const roughnessWeightContributor: PlanRequestContributor = {
  id: 'roughness-weight',
  label: 'Surface roughness',
  hint: 'Prices NASA LOLA roughness as a fifth cost criterion. Only sent once the slider has been moved.',
  control: { kind: 'number', min: 0, max: 2, step: 0.01, initial: 0.15 },
  constraintKey: 'wRoughness',
  enabled: (state, context) => {
    if (!context) return false
    if (context.available['roughness'] !== true) return false
    const value = context.constraints[roughnessWeightContributor.constraintKey] ?? state.value
    return typeof value === 'number' && Number.isFinite(value)
  },
  fields: (state, context) => {
    if (!roughnessWeightContributor.enabled(state, context)) return null
    const value = (context!.constraints[roughnessWeightContributor.constraintKey] ??
      state.value) as number
    return { weights: { w_roughness: value } }
  },
}

/**
 * B2 -- conditional value-at-risk on the ranking cost.
 *
 * The one advanced field `POST /api/plan` actually honours, so it is the one
 * that works from the store with no context.
 */
export const riskContributor: PlanRequestContributor = {
  id: 'risk',
  label: 'Risk appetite',
  hint: 'Ranks routes on the adverse tail of the slip and slope distributions rather than their mean. Changes which route is chosen, not what it costs to drive.',
  control: { kind: 'number', min: 0.5, max: 0.999, step: 0.001, initial: 0.9 },
  constraintKey: 'riskAlpha',
  enabled: (state, context) => {
    const fromContext = context?.constraints[riskContributor.constraintKey]
    if (!state.enabled && fromContext === undefined) return false
    const value = fromContext ?? state.value
    // The contract's allowed interval. Out of range is a 422, and sending one
    // would turn an operator's slider into a failed plan; contributing nothing
    // leaves the route nominal instead.
    return typeof value === 'number' && value >= 0.5 && value <= 0.999
  },
  fields: (state, context) => {
    if (!riskContributor.enabled(state, context)) return null
    const value = (context?.constraints[riskContributor.constraintKey] ?? state.value) as number
    return { risk_alpha: value }
  },
}

/**
 * The list. Append-only: add at the end, never reorder, never edit a
 * neighbour's line.
 */
export const PLAN_REQUEST_CONTRIBUTORS: readonly PlanRequestContributor[] = [
  earthVisibilityContributor,
  safeHavenContributor,
  illuminationCorridorContributor,
  roughnessWeightContributor,
  riskContributor,
]

/**
 * The contributors the 2-D request builder can actually honour.
 *
 * Derived by asking each one, not by a second hand-maintained list: a
 * contributor that returns null when switched on with no context is one whose
 * field `POST /api/plan` would accept and ignore, and a contributor appended
 * later is classified without anyone remembering to.
 *
 * This is what the constraints panel renders. Showing the 4-D-only switches
 * there would put controls in front of an operator that change nothing when
 * the button beside them is pressed -- the exact failure the measurement at
 * the top of this file was made to prevent. They belong beside the "Plan
 * through time" button, which issues the request that honours them.
 */
export const STORE_CONTRIBUTORS: readonly PlanRequestContributor[] =
  PLAN_REQUEST_CONTRIBUTORS.filter((contributor) => {
    const probe: ConstraintState = {
      enabled: true,
      value:
        contributor.control.kind === 'number' || contributor.control.kind === 'choice'
          ? contributor.control.initial
          : true,
    }
    return contributor.fields(probe) !== null
  })

/**
 * The state a contributor sees when the request is described by a context
 * rather than by the store -- the 4-D builder's path.
 *
 * A toggle is on when its key is literally `true`; a numeric control is on when
 * its key holds a finite number. Neither treats a missing key as anything but
 * absent, which is the non-regression rule restated one level down.
 */
function constraintStateFrom(
  contributor: PlanRequestContributor,
  context: PlanRequestContext,
): ConstraintState {
  const raw = context.constraints[contributor.constraintKey]
  if (contributor.control.kind === 'number') {
    return { enabled: typeof raw === 'number' && Number.isFinite(raw), value: raw }
  }
  return { enabled: raw === true, value: raw }
}

/**
 * Merge one contributor's fields into a body.
 *
 * `weights` is merged one level deep rather than replaced, because more than
 * one contributor may add a weight and the base body already carries the four
 * the cockpit has always sent. A flat assign here would swap the four for a
 * one-key object and quietly re-plan the route on a single criterion.
 * Everything else is a top-level assignment.
 *
 * Shared with the store so the two builders cannot disagree about it.
 */
export function mergeContributedFields(
  target: Record<string, unknown>,
  fields: Record<string, unknown>,
): Record<string, unknown> {
  let result = target
  for (const [key, value] of Object.entries(fields)) {
    if (key === 'weights' && isPlainObject(value) && isPlainObject(result.weights)) {
      result = { ...result, weights: { ...result.weights, ...value } }
      continue
    }
    result = { ...result, [key]: value }
  }
  return result
}

/**
 * Fold the contributors into a base request body -- the 4-D builder.
 *
 * No contributor is permitted to reach into another's sub-object, and the body
 * handed in is never mutated.
 */
export function applyPlanRequestContributors<T extends Record<string, unknown>>(
  base: T,
  context: PlanRequestContext,
  contributors: readonly PlanRequestContributor[] = PLAN_REQUEST_CONTRIBUTORS,
): T {
  let result: Record<string, unknown> = { ...base }

  for (const contributor of contributors) {
    const state = constraintStateFrom(contributor, context)
    if (!contributor.enabled(state, context)) continue
    const fields = contributor.fields(state, context)
    if (!fields) continue
    result = mergeContributedFields(result, fields)
  }

  return result as T
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
