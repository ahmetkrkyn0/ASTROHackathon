import { describe, expect, it } from 'vitest'
import { matchesRoute, routeIdentity, type RouteInputs } from './routeIdentity'

const base: RouteInputs = {
  roverId: 'nasa_viper',
  start: [169, 50],
  goal: [464, 193],
  weights: { w_slope: 0.35, w_energy: 0.25, w_shadow: 0.2, w_thermal: 0.2 },
}

describe('routeIdentity', () => {
  it('has no identity without both endpoints', () => {
    expect(routeIdentity({ ...base, start: null })).toBeNull()
    expect(routeIdentity({ ...base, goal: null })).toBeNull()
  })

  it('changes when anything that decides the route changes', () => {
    const id = routeIdentity(base)
    expect(routeIdentity({ ...base, roverId: 'lpr_1' })).not.toBe(id)
    expect(routeIdentity({ ...base, start: [170, 50] })).not.toBe(id)
    expect(routeIdentity({ ...base, goal: [464, 194] })).not.toBe(id)
    expect(routeIdentity({
      ...base,
      weights: { ...base.weights, w_slope: 0.36 },
    })).not.toBe(id)
    expect(routeIdentity({ ...base, constraints: { require_safe_haven: true } })).not.toBe(id)
  })

  it('changes when a constraint value changes, not just its presence', () => {
    const a = routeIdentity({ ...base, constraints: { risk_alpha: 0.9 } })
    const b = routeIdentity({ ...base, constraints: { risk_alpha: 0.95 } })
    expect(a).not.toBe(b)
  })

  it('treats no constraints and an empty constraint object as the same route', () => {
    // A constraint that is switched on but contributes no field must not
    // invalidate anything: the request is byte-for-byte the old one.
    expect(routeIdentity(base)).toBe(routeIdentity({ ...base, constraints: {} }))
  })

  it('survives float noise and key order', () => {
    const noisy = routeIdentity({
      ...base,
      weights: { w_slope: 0.1 + 0.25, w_energy: 0.25, w_shadow: 0.2, w_thermal: 0.2 },
    })
    expect(noisy).toBe(routeIdentity(base))

    const reordered = routeIdentity({
      ...base,
      constraints: { lit_rule: 'all', require_continuous_illumination: true },
    })
    const original = routeIdentity({
      ...base,
      constraints: { require_continuous_illumination: true, lit_rule: 'all' },
    })
    expect(reordered).toBe(original)
  })

  it('ignores everything that does not decide the route', () => {
    // The half the plan warns about twice: switching the visible raster must
    // not throw away a Monte Carlo run. Those inputs have no way in.
    const id = routeIdentity(base)
    expect(routeIdentity({ ...base })).toBe(id)
    expect(Object.keys(base)).toEqual(['roverId', 'start', 'goal', 'weights'])
  })
})

describe('matchesRoute', () => {
  it('never matches when either side has no route', () => {
    // Two "no route yet"s are not the same route, or an analysis from a
    // previous mission could attach itself to an empty one.
    expect(matchesRoute(null, null)).toBe(false)
    expect(matchesRoute('a', null)).toBe(false)
    expect(matchesRoute(null, 'a')).toBe(false)
  })

  it('matches identical identities', () => {
    expect(matchesRoute('a', 'a')).toBe(true)
    expect(matchesRoute('a', 'b')).toBe(false)
  })
})
