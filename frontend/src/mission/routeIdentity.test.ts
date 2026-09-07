import { describe, expect, it } from 'vitest'

import type { PlanWeights } from '../api'
import { isRouteIdentityStale, routeIdentityOf } from './routeIdentity'

const WEIGHTS: PlanWeights = {
  w_slope: 0.409,
  w_energy: 0.259,
  w_shadow: 0.142,
  w_thermal: 0.19,
}

const BASE = {
  roverId: 'lpr_1',
  start: [100, 100] as [number, number],
  goal: [140, 140] as [number, number],
  weights: WEIGHTS,
}

describe('routeIdentityOf', () => {
  it('changes when a planner input changes', () => {
    const base = routeIdentityOf(BASE)
    expect(routeIdentityOf({ ...BASE, roverId: 'nasa_viper' })).not.toBe(base)
    expect(routeIdentityOf({ ...BASE, start: [101, 100] })).not.toBe(base)
    expect(routeIdentityOf({ ...BASE, goal: [140, 141] })).not.toBe(base)
    expect(
      routeIdentityOf({ ...BASE, weights: { ...WEIGHTS, w_slope: 0.5 } }),
    ).not.toBe(base)
  })

  it('does not change when the weights object is merely rebuilt', () => {
    // A slider rebuilds this object every render; key order is insertion order
    // in JS, so an identity that depended on it would flap for no reason.
    const reordered = {
      w_thermal: 0.19,
      w_shadow: 0.142,
      w_energy: 0.259,
      w_slope: 0.409,
    } as PlanWeights
    expect(routeIdentityOf({ ...BASE, weights: reordered })).toBe(routeIdentityOf(BASE))
  })

  it('ignores float noise below the sixth decimal', () => {
    const noisy = { ...WEIGHTS, w_slope: 0.409 + 1e-12 }
    expect(routeIdentityOf({ ...BASE, weights: noisy })).toBe(routeIdentityOf(BASE))
  })

  it('hashes identically whether a constraint is absent or off', () => {
    // The non-regression rule as identity: shipping a constraint feature must
    // not invalidate every analysis stored before it existed.
    const withoutBlock = routeIdentityOf(BASE)
    const allOff = routeIdentityOf({
      ...BASE,
      constraints: {
        requireEarthVisibility: false,
        requireSafeHaven: false,
        requireIlluminationCorridor: false,
        riskAlpha: null,
      },
    })
    expect(allOff).toBe(withoutBlock)
  })

  it('changes when a forward constraint is switched on', () => {
    const off = routeIdentityOf(BASE)
    expect(
      routeIdentityOf({ ...BASE, constraints: { requireEarthVisibility: true } }),
    ).not.toBe(off)
    expect(routeIdentityOf({ ...BASE, constraints: { requireSafeHaven: true } })).not.toBe(off)
    expect(routeIdentityOf({ ...BASE, constraints: { riskAlpha: 0.9 } })).not.toBe(off)
  })

  it('does not depend on the order constraints were switched on', () => {
    const a = routeIdentityOf({
      ...BASE,
      constraints: { requireEarthVisibility: true, requireSafeHaven: true },
    })
    const b = routeIdentityOf({
      ...BASE,
      constraints: { requireSafeHaven: true, requireEarthVisibility: true },
    })
    expect(a).toBe(b)
  })

  it('is null without both endpoints', () => {
    expect(routeIdentityOf({ ...BASE, start: null })).toBeNull()
    expect(routeIdentityOf({ ...BASE, goal: null })).toBeNull()
  })
})

describe('isRouteIdentityStale', () => {
  it('marks an analysis stale once the route it described is replaced', () => {
    const analysed = routeIdentityOf(BASE)
    const current = routeIdentityOf({ ...BASE, goal: [200, 200] })
    expect(isRouteIdentityStale(analysed, current)).toBe(true)
    expect(isRouteIdentityStale(analysed, analysed)).toBe(false)
  })

  it('does not warn when there is nothing to warn about', () => {
    // No recorded identity is not evidence of staleness, and no current route
    // has nothing to contradict.
    expect(isRouteIdentityStale(null, routeIdentityOf(BASE))).toBe(false)
    expect(isRouteIdentityStale(routeIdentityOf(BASE), null)).toBe(false)
  })
})
