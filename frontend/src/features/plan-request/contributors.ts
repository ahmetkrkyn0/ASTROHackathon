/**
 * How an advanced planner constraint reaches the request.
 *
 * Section 6 of the integration plan: the new planner capabilities are additive
 * fields on the existing request, not a second "advanced planner API". And
 * section 2's non-regression rule is the sharp end of it --
 *
 *     A CONSTRAINT THAT IS OFF SENDS NO FIELD AT ALL.
 *
 * -- because several of these fields have no neutral value. `risk_alpha: 0.5`
 * is not "no risk appetite": CVaR at 0.5 is mu + 0.798 sigma, and the contract
 * states that omitting the field is what makes the cost grid bit-identical to
 * today's. A disabled toggle that quietly sends a default would change every
 * route in the product and look like nothing had happened.
 *
 * So a contributor returns `null` when it is off, and the builder drops nulls.
 * There is no path from "off" to a key in the body.
 *
 * The list is append-only on purpose. Two people adding constraints to a
 * shared request builder would edit the same function every day; appending a
 * line each is a conflict that resolves by keeping both.
 */

export interface ConstraintState {
  enabled: boolean
  /** Whatever the control holds -- an alpha, a rule name, a temperature. */
  value?: unknown
}

/**
 * What the operator manipulates. Declared here rather than in the panel so
 * that adding a constraint stays a single append to this list -- the panel
 * renders whatever the registry describes and has no per-constraint code.
 */
export type ConstraintControl =
  /** On or off. Contributes a fixed field when enabled. */
  | { kind: 'toggle' }
  /** A number in a range, with the value the control starts at. */
  | { kind: 'number'; min: number; max: number; step: number; initial: number; unit?: string }
  /** One of a fixed set of backend enum values. */
  | { kind: 'choice'; options: ReadonlyArray<{ value: string; label: string }>; initial: string }

export interface PlanRequestContributor {
  /** Stable key. Also how the store addresses this constraint's state. */
  id: string
  /** Shown wherever the constraint is listed. */
  label: string
  /** One line saying what switching this on does to the route. */
  hint: string
  control: ConstraintControl
  /**
   * The fields to merge into the request body, or null to send nothing.
   * Returning `{}` is not the same as returning null and is treated as a bug:
   * an enabled constraint that contributes no field would still change the
   * route identity, invalidating analyses for a request that did not change.
   */
  fields: (state: ConstraintState) => Record<string, unknown> | null
}

/** B2: conditional value-at-risk on the ranking cost. */
const riskContributor: PlanRequestContributor = {
  id: 'risk',
  label: 'Risk appetite',
  hint: 'Ranks routes on the adverse tail of the slip and slope distributions rather than their mean. Changes which route is chosen, not what it costs to drive.',
  control: { kind: 'number', min: 0.5, max: 0.999, step: 0.001, initial: 0.9 },
  fields: (state) => {
    if (!state.enabled) return null
    const alpha = typeof state.value === 'number' ? state.value : null
    // The contract's allowed interval. Out of range is a 422, and sending one
    // would turn an operator's slider into a failed plan.
    if (alpha === null || alpha < 0.5 || alpha > 0.999) return null
    return { risk_alpha: alpha }
  },
}

export const PLAN_REQUEST_CONTRIBUTORS: readonly PlanRequestContributor[] = [
  riskContributor,
]
