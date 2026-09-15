import { describe, expect, it } from 'vitest'

import {
  FOUR_D_CONTRIBUTORS,
  PLAN_REQUEST_CONTRIBUTORS,
  STORE_CONTRIBUTORS,
  applyPlanRequestContributors,
  mergeContributedFields,
  type PlanRequestContext,
} from '../features/plan-request/contributors'

/**
 * The most important test in this track.
 *
 * Spec section 2: a feature that is switched off leaves the request exactly as
 * it was. Not "sends a false", not "sends a neutral default" -- omits the
 * field entirely. Every advanced constraint this integration adds is a way for
 * the cockpit to quietly start sending something it never sent, and the
 * failure mode is silent: the route still comes back, it is simply a different
 * route than the one the operator asked for.
 *
 * So the byte-for-byte body the cockpit sent before any of this existed is
 * pinned here, and asserted against the contributor pipeline with everything
 * off. `api.ts:385` builds it; these two constants are that shape.
 */

/** Exactly what `planRoute()` posts to /api/plan today. */
const BASELINE_PLAN_BODY = {
  start: { row: 100, col: 100 },
  goal: { row: 140, col: 140 },
  rover_id: 'lpr_1',
  weights: {
    w_slope: 0.409,
    w_energy: 0.259,
    w_shadow: 0.142,
    w_thermal: 0.19,
  },
  include_simulation: true,
} as const

/** What `useTimeAxis.runPlan4D` posts. `slice_hours` is deliberately absent. */
const BASELINE_PLAN_4D_BODY = {
  start: { row: 100, col: 100 },
  goal: { row: 140, col: 140 },
  rover_id: 'lpr_1',
  weights: {
    w_slope: 0.409,
    w_energy: 0.259,
    w_shadow: 0.142,
    w_thermal: 0.19,
  },
  n_slices: 256,
  coarsen: 4,
  start_utc: '2026-09-07T00:00:00.000Z',
} as const

/** Nothing switched on, nothing available. The state of a fresh cockpit. */
const NOTHING_ON: PlanRequestContext = {
  endpoint: 'plan',
  constraints: {},
  available: {},
}

describe('plan request non-regression', () => {
  it('leaves the 2-D body byte-identical with every constraint off', () => {
    const built = applyPlanRequestContributors(BASELINE_PLAN_BODY, NOTHING_ON)
    expect(JSON.stringify(built)).toBe(JSON.stringify(BASELINE_PLAN_BODY))
  })

  it('leaves the 4-D body byte-identical with every constraint off', () => {
    const built = applyPlanRequestContributors(BASELINE_PLAN_4D_BODY, {
      ...NOTHING_ON,
      endpoint: 'plan-4d',
    })
    expect(JSON.stringify(built)).toBe(JSON.stringify(BASELINE_PLAN_4D_BODY))
  })

  it('adds no key when a toggle is on but the data is not there', () => {
    // The operator may leave a toggle on from a session where the cache
    // existed. Sending the flag anyway earns a 422 that reads like a bug.
    const built = applyPlanRequestContributors(BASELINE_PLAN_4D_BODY, {
      endpoint: 'plan-4d',
      constraints: { requireEarthVisibility: true, requireSafeHaven: true },
      available: {},
    })
    expect(JSON.stringify(built)).toBe(JSON.stringify(BASELINE_PLAN_4D_BODY))
  })

  it('adds no key when the data is there but the toggle is off', () => {
    const built = applyPlanRequestContributors(BASELINE_PLAN_4D_BODY, {
      endpoint: 'plan-4d',
      constraints: {},
      available: { 'earth-visibility': true, 'safe-haven': true, roughness: true },
    })
    expect(JSON.stringify(built)).toBe(JSON.stringify(BASELINE_PLAN_4D_BODY))
  })

  it('never sends an explicit false for a constraint the operator turned off', () => {
    const built = applyPlanRequestContributors(BASELINE_PLAN_4D_BODY, {
      endpoint: 'plan-4d',
      constraints: { requireEarthVisibility: false, requireSafeHaven: false },
      available: { 'earth-visibility': true, 'safe-haven': true },
    })
    expect(built).not.toHaveProperty('require_earth_visibility')
    expect(built).not.toHaveProperty('require_safe_haven')
  })

  it('keeps the four legacy weights untouched when no weight is contributed', () => {
    // The backend applies its own w_roughness default of 0.15. Echoing that
    // back would be the frontend asserting a number it did not choose.
    const built = applyPlanRequestContributors(BASELINE_PLAN_BODY, {
      endpoint: 'plan',
      constraints: {},
      available: { roughness: true },
    })
    expect(Object.keys(built.weights)).toEqual([
      'w_slope',
      'w_energy',
      'w_shadow',
      'w_thermal',
    ])
  })

  it('does not let a 4-D-only constraint leak into a 2-D request', () => {
    const built = applyPlanRequestContributors(BASELINE_PLAN_BODY, {
      endpoint: 'plan',
      constraints: { requireEarthVisibility: true, requireSafeHaven: true },
      available: { 'earth-visibility': true, 'safe-haven': true },
    })
    expect(JSON.stringify(built)).toBe(JSON.stringify(BASELINE_PLAN_BODY))
  })

  it('every contributor returns null while disabled', () => {
    // The rule stated once over the whole list, so a contributor appended
    // later cannot opt out of it. Both arities are checked: the 4-D builder
    // hands a state and a context, the store hands a state alone.
    for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
      const off = { enabled: false }
      expect(contributor.enabled(off, NOTHING_ON)).toBe(false)
      expect(contributor.fields(off, NOTHING_ON)).toBeNull()
      expect(contributor.fields(off)).toBeNull()
    }
  })

  it('sends no 4-D constraint through the store, which builds the 2-D body', () => {
    // The guard the merge turns on: POST /api/plan accepts every one of these
    // flags with a 200 and then ignores it. A contributor with no context is a
    // contributor on the 2-D path, and must contribute nothing there.
    for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
      if (contributor.id === 'risk') continue
      expect(contributor.fields({ enabled: true, value: 0.9 })).toBeNull()
    }
  })

  it('merges a weight into the four rather than replacing them', () => {
    // The hazard a flat Object.assign would create: `weights` arrives as a
    // one-key object and would take the place of all four.
    const merged = mergeContributedFields(
      { weights: { w_slope: 0.409, w_energy: 0.259, w_shadow: 0.142, w_thermal: 0.19 } },
      { weights: { w_roughness: 0.4 } },
    )
    expect(merged.weights).toEqual({
      w_slope: 0.409,
      w_energy: 0.259,
      w_shadow: 0.142,
      w_thermal: 0.19,
      w_roughness: 0.4,
    })
  })
})

describe('plan request contributions', () => {
  it('adds the flags once both the toggle and the data are there', () => {
    const built = applyPlanRequestContributors(BASELINE_PLAN_4D_BODY, {
      endpoint: 'plan-4d',
      constraints: { requireEarthVisibility: true, requireSafeHaven: true },
      available: { 'earth-visibility': true, 'safe-haven': true },
    })
    expect(built).toMatchObject({
      require_earth_visibility: true,
      require_safe_haven: true,
    })
  })

  it('merges a contributed weight instead of replacing the weights object', () => {
    const built = applyPlanRequestContributors(BASELINE_PLAN_BODY, {
      endpoint: 'plan',
      constraints: { wRoughness: 0.4 },
      available: { roughness: true },
    })
    expect(built.weights).toEqual({
      w_slope: 0.409,
      w_energy: 0.259,
      w_shadow: 0.142,
      w_thermal: 0.19,
      w_roughness: 0.4,
    })
  })

  it('does not mutate the body it was given', () => {
    const before = JSON.stringify(BASELINE_PLAN_BODY)
    applyPlanRequestContributors(BASELINE_PLAN_BODY, {
      endpoint: 'plan',
      constraints: { wRoughness: 0.4 },
      available: { roughness: true },
    })
    expect(JSON.stringify(BASELINE_PLAN_BODY)).toBe(before)
  })
})

/**
 * The five constraints added to close the integration audit's blocking
 * findings, and the two seams that made them unreachable in the first place.
 *
 * Both seams were silent. A boolean-only constraint record could not carry an
 * alpha, and `constraintStateFrom` had no branch for a `choice` control at
 * all, so a contributor could be written correctly, rendered correctly, and
 * contribute nothing. Neither would fail a type check; only a test that
 * asserts the field ARRIVES catches them.
 */
describe('4-D constraint surface', () => {
  const AVAILABLE = {
    'earth-visibility': true,
    'safe-haven': true,
    'illumination-corridor': true,
    roughness: true,
    survival: true,
    'thermal-dwell': true,
  }

  const build = (constraints: Record<string, unknown>) =>
    applyPlanRequestContributors(BASELINE_PLAN_4D_BODY, {
      endpoint: 'plan-4d',
      constraints,
      available: AVAILABLE,
    })

  it('partitions the registry between the two panels, with nothing left out', () => {
    // The 4-D strip renders FOUR_D_CONTRIBUTORS and the drawer renders
    // STORE_CONTRIBUTORS. A contributor in neither is one nothing can switch
    // on -- which is precisely how B1, C6 and the lit rule were unreachable.
    const both = [...STORE_CONTRIBUTORS, ...FOUR_D_CONTRIBUTORS]
    expect(both).toHaveLength(PLAN_REQUEST_CONTRIBUTORS.length)
    expect(new Set(both.map((c) => c.id)).size).toBe(PLAN_REQUEST_CONTRIBUTORS.length)
    for (const contributor of PLAN_REQUEST_CONTRIBUTORS) expect(both).toContain(contributor)
  })

  it('carries a number through the 4-D path -- audit B2-1 and B2-2', () => {
    // The record these arrive in used to be typed `boolean`, so neither of
    // these keys could hold its value and both fields were silently dropped.
    expect(build({ riskAlpha: 0.97 })).toMatchObject({ risk_alpha: 0.97 })
    expect(build({ wRoughness: 0.4 }).weights).toMatchObject({ w_roughness: 0.4 })
  })

  it('carries a choice through the 4-D path -- audit A2-1', () => {
    const built = build({ requireIlluminationCorridor: true, litRule: 'majority' })
    expect(built).toMatchObject({ require_continuous_illumination: true, lit_rule: 'majority' })
  })

  it('sends the survival fields once asked -- audit B1-1', () => {
    expect(build({ reportSurvival: true })).toMatchObject({ report_survival: true })
    expect(build({ maxFailureProbability: 0.05 })).toMatchObject({
      max_failure_probability: 0.05,
    })
  })

  it('sends the thermal fields once asked -- audit C6-1', () => {
    const built = build({ requireThermalDwell: true, heaterModel: 'thermostat_assumed' })
    expect(built).toMatchObject({
      require_thermal_dwell: true,
      heater_model: 'thermostat_assumed',
    })
  })

  it('omits an enum still sitting on the backend default', () => {
    // `lit_rule: 'all'` and `heater_model: 'none'` ARE the backend defaults.
    // Sending them asserts a value nobody chose, and -- because the route
    // identity is derived from the request body -- marks every post-route
    // analysis stale for a request that did not change the route.
    const lit = build({ requireIlluminationCorridor: true, litRule: 'all' })
    expect(lit).not.toHaveProperty('lit_rule')
    const heater = build({ requireThermalDwell: true, heaterModel: 'none' })
    expect(heater).not.toHaveProperty('heater_model')
  })

  it('omits an enum whose own constraint is off', () => {
    // A lit rule means nothing when the corridor is not being enforced.
    expect(build({ litRule: 'majority' })).not.toHaveProperty('lit_rule')
    expect(build({ heaterModel: 'thermostat_assumed' })).not.toHaveProperty('heater_model')
  })

  it('rejects a value outside the contributor own options', () => {
    // Not merely "is a string": every choice maps to a backend Literal, and
    // a value outside it is a 422 rather than a different plan.
    const built = build({ requireIlluminationCorridor: true, litRule: 'sometimes' })
    expect(built).not.toHaveProperty('lit_rule')
  })

  it('adds nothing at all when the capability is absent', () => {
    const built = applyPlanRequestContributors(BASELINE_PLAN_4D_BODY, {
      endpoint: 'plan-4d',
      constraints: {
        reportSurvival: true,
        maxFailureProbability: 0.05,
        requireThermalDwell: true,
        requireIlluminationCorridor: true,
        litRule: 'majority',
      },
      available: {},
    })
    expect(JSON.stringify(built)).toBe(JSON.stringify(BASELINE_PLAN_4D_BODY))
  })

  it('refuses a failure limit outside the contract interval', () => {
    // Plan4DRequest is gt=0.0, lt=1.0. Sending 0 or 1 is a 422, which would
    // turn a slider into a failed plan rather than a nominal route.
    expect(build({ maxFailureProbability: 0 })).not.toHaveProperty('max_failure_probability')
    expect(build({ maxFailureProbability: 1 })).not.toHaveProperty('max_failure_probability')
  })

  it('leaves the fault-model assumptions to the backend', () => {
    // Spec 6.5: default assumption values are not hard-coded by the UI. The
    // backend applies Lamarre's published figures and reports them with
    // their source; echoing our own numbers back would assert values the
    // operator never chose.
    const built = build({ reportSurvival: true, maxFailureProbability: 0.05 })
    for (const field of [
      'failure_rate_per_km',
      'recovery_hours',
      'survival_soc_bins',
      'survival_safe_set',
      'survival_horizon_hours',
      'initial_inner_c',
    ]) {
      expect(built).not.toHaveProperty(field)
    }
  })

  it('adds only its own field, one constraint at a time', () => {
    const cases: Array<[Record<string, unknown>, string]> = [
      [{ reportSurvival: true }, 'report_survival'],
      [{ maxFailureProbability: 0.05 }, 'max_failure_probability'],
      [{ requireThermalDwell: true }, 'require_thermal_dwell'],
      [{ riskAlpha: 0.9 }, 'risk_alpha'],
    ]
    for (const [constraints, field] of cases) {
      const built = build(constraints) as Record<string, unknown>
      const added = Object.keys(built).filter(
        (key) => !(key in BASELINE_PLAN_4D_BODY),
      )
      expect(added).toEqual([field])
    }
  })
})
