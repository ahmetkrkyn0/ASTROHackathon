import { describe, expect, it } from 'vitest'

import {
  PLAN_REQUEST_CONTRIBUTORS,
  applyPlanRequestContributors,
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
    // later cannot opt out of it.
    for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
      expect(contributor.enabled(NOTHING_ON)).toBe(false)
      expect(contributor.fields(NOTHING_ON)).toBeNull()
    }
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
