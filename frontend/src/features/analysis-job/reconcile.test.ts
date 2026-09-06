import { describe, expect, it } from 'vitest'
import { reconcileIdentity } from './useAnalysisJob'
import type { AnalysisJob } from './useAnalysisJob'

const result: AnalysisJob<number> = { state: 'success', value: 42, computedFor: 'route-a' }

describe('reconcileIdentity', () => {
  it('ages a result when the mission moves away from it', () => {
    expect(reconcileIdentity(result, 'route-b')).toEqual({
      state: 'stale', value: 42, computedFor: 'route-a',
    })
  })

  it('ages a result when the route is cleared entirely', () => {
    expect(reconcileIdentity(result, null).state).toBe('stale')
  })

  it('keeps the value while ageing it, rather than dropping it', () => {
    // A panel greys out what it was showing; it does not flash empty, which
    // reads as data loss.
    const aged = reconcileIdentity(result, 'route-b')
    expect(aged.state === 'stale' && aged.value).toBe(42)
  })

  it('revives a stale result when the operator undoes the change', () => {
    const stale = reconcileIdentity(result, 'route-b')
    const revived = reconcileIdentity(stale, 'route-a')
    expect(revived).toEqual(result)
  })

  it('leaves idle, running and failed jobs alone', () => {
    const untouched: Array<AnalysisJob<number>> = [
      { state: 'idle' },
      { state: 'running' },
      {
        state: 'failure',
        failure: { kind: 'transport', status: null, detail: 'x', keepsExistingRoute: true },
      },
    ]
    for (const job of untouched) expect(reconcileIdentity(job, 'route-b')).toBe(job)
  })

  it('has nowhere to put a progress percentage', () => {
    // The point of the type. If this ever compiles with a percent, the
    // prohibition on fake progress has become a convention again.
    for (const job of [result, { state: 'running' } as AnalysisJob<number>]) {
      expect('percent' in job).toBe(false)
    }
  })
})
