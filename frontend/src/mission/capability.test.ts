import { describe, expect, it } from 'vitest'
import { hasValue, isAbsent, markStale, unavailableReason, type Capability } from './capability'
import type { Failure } from '../net/errors'

const failure: Failure = {
  kind: 'transport',
  status: null,
  detail: 'offline',
  keepsExistingRoute: true,
}

describe('Capability', () => {
  it('separates "not available here" from "something broke"', () => {
    const absent: Capability<number> = { state: 'unavailable', reason: 'no cache' }
    const broken: Capability<number> = { state: 'error', failure }
    expect(isAbsent(absent)).toBe(true)
    expect(isAbsent(broken)).toBe(false)
    // Structural, not conventional: neither state can carry the other's
    // payload, so the two cannot be conflated by reading the wrong field.
    expect('failure' in absent).toBe(false)
    expect('reason' in broken).toBe(false)
  })

  it('has no state that means "absent, but here are some numbers"', () => {
    const withValue: Array<Capability<number>['state']> = ['ready', 'stale']
    const absentStates: Array<Capability<number>['state']> = ['unavailable', 'unsupported']
    for (const state of absentStates) expect(withValue).not.toContain(state)
  })

  it('reports a value whether or not it is current', () => {
    expect(hasValue({ state: 'ready', value: 1 })).toBe(true)
    expect(hasValue({ state: 'stale', value: 1 })).toBe(true)
    expect(hasValue({ state: 'loading', previous: 1 })).toBe(false)
    expect(hasValue({ state: 'unavailable', reason: 'x' })).toBe(false)
  })
})

describe('markStale', () => {
  it('ages a ready value and leaves everything else alone', () => {
    expect(markStale({ state: 'ready', value: 7 })).toEqual({ state: 'stale', value: 7 })
    const absent: Capability<number> = { state: 'unavailable', reason: 'no cache' }
    expect(markStale(absent)).toBe(absent)
    const idle: Capability<number> = { state: 'idle' }
    expect(markStale(idle)).toBe(idle)
  })
})

describe('unavailableReason', () => {
  it('reads the unavailability several endpoints report inside a 200', () => {
    expect(unavailableReason({ model: 'unavailable', reason: 'no horizon cube' }))
      .toBe('no horizon cube')
  })

  it('returns null for a model that describes a real computation', () => {
    expect(unavailableReason({ model: 'spice_horizon', coarse_safe_haven_cells: 12 }))
      .toBeNull()
    expect(unavailableReason(null)).toBeNull()
    expect(unavailableReason(undefined)).toBeNull()
  })

  it('still reports unavailability when the backend gave no reason', () => {
    expect(unavailableReason({ model: 'unavailable' })).not.toBeNull()
  })
})
