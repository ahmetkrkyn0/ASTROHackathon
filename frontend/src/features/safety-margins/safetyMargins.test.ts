import { describe, expect, it } from 'vitest'
import { formatMargin, readSafetyMargins, type RequirementView } from './safetyMargins'

/** A row shaped like the contract's own example. */
function requirement(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'LP-R01',
    name: 'shadow_endurance',
    class: 'safety',
    applicable: true,
    reason: null,
    rho: 91.45,
    unit: 'h',
    rho_normalized: 0.953,
    satisfied: true,
    boundary: false,
    open_ended: false,
    pending: false,
    fretish: 'The rover shall always satisfy shadow_continuous_h <= h_max_shadow_h',
    worst_at: { index: 40, hours: 7.36, row: 51, col: 106 },
    ...overrides,
  }
}

function response(root: Record<string, unknown> = {}): unknown {
  return {
    safety_margins: {
      monitor: {
        engine: 'rtamt',
        cross_check: { engine: 'builtin', max_abs_diff: 0.0 },
        claim: 'checked by runtime monitoring of the planned trace; not proven by model checking',
        trace: { kind: '4d', n_samples: 41, complete: true },
      },
      requirements: [requirement()],
      min_margin: { id: 'LP-R06', rho: 0.48, unit: 'deg', rho_normalized: 0.024 },
      n_applicable: 11,
      n_violated: 2,
      violated: ['LP-R04', 'LP-R05'],
      verdict: 'violated',
      ...root,
    },
  }
}

describe('readSafetyMargins', () => {
  it('returns null when the result carries no block', () => {
    // Not the same as an empty one: a compare result whose simulation was
    // dropped has no field, and an empty panel would report twelve untested
    // requirements when none were asked for.
    expect(readSafetyMargins({})).toBeNull()
    expect(readSafetyMargins(null)).toBeNull()
  })

  it('keeps the backend’s claim sentence verbatim', () => {
    const view = readSafetyMargins(response())!
    expect(view.claim).toContain('not proven by model checking')
  })

  it('reads the verdict and the violated list', () => {
    const view = readSafetyMargins(response())!
    expect(view.verdict).toBe('violated')
    expect(view.violatedIds).toEqual(['LP-R04', 'LP-R05'])
    expect(view.nViolated).toBe(2)
    expect(view.minMargin).toEqual({ id: 'LP-R06', rho: 0.48, unit: 'deg' })
  })
})

describe('requirement state', () => {
  const stateOf = (overrides: Record<string, unknown>) =>
    readSafetyMargins(response({ requirements: [requirement(overrides)] }))!.requirements[0].state

  it('never reads an untestable requirement as a pass', () => {
    // The row still carries satisfied: null, and reading that as "not
    // violated" is how an untested requirement becomes a green tick.
    expect(stateOf({ applicable: false, satisfied: null, reason: 'signal absent in 2-D trace' }))
      .toBe('not-applicable')
  })

  it('keeps pending apart from satisfied', () => {
    expect(stateOf({ pending: true, satisfied: null })).toBe('pending')
    expect(stateOf({ satisfied: null })).toBe('pending')
  })

  it('reads a zero margin as met, but at the boundary', () => {
    expect(stateOf({ rho: 0, boundary: true, satisfied: true })).toBe('boundary')
  })

  it('reads violations and passes', () => {
    expect(stateOf({ satisfied: false, rho: -46.04 })).toBe('violated')
    expect(stateOf({ satisfied: true })).toBe('satisfied')
  })

  it('prefers inapplicable over every other signal on the same row', () => {
    expect(stateOf({ applicable: false, pending: true, satisfied: false })).toBe('not-applicable')
  })
})

describe('formatMargin', () => {
  const view = (overrides: Partial<RequirementView>): RequirementView => ({
    id: 'LP-R08', name: 'earth_link', requirementClass: 'safety', state: 'satisfied',
    rho: 1, unit: 'h', rhoNormalized: null, openEnded: false, reason: null,
    fretish: null, worstAt: null, ...overrides,
  })

  it('never prints an unbounded margin as a number', () => {
    // +infinity: no Earth-set within the look-ahead. A big number here would
    // be inventing a deadline the backend explicitly did not give.
    expect(formatMargin(view({ rho: null, openEnded: true }))).toBe('No limit reached')
  })

  it('never prints an unbounded violation as a missing value', () => {
    // -infinity: a finite Earth-set with no reachable haven. Showing "--"
    // would read as "not measured" for the worst answer there is.
    expect(formatMargin(view({ rho: null, openEnded: false, state: 'violated' })))
      .toBe('Unbounded violation')
  })

  it('signs the margin and keeps the unit', () => {
    expect(formatMargin(view({ rho: 91.45, unit: 'h' }))).toBe('+91.45 h')
    expect(formatMargin(view({ rho: -46.04, unit: 'degC', state: 'violated' }))).toBe('-46.04 degC')
    expect(formatMargin(view({ rho: 0, unit: 'deg', state: 'boundary' }))).toBe('0.00 deg')
  })
})
