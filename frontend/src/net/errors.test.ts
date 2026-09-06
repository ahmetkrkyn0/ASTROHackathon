import { describe, expect, it } from 'vitest'
import { classifyFailure, describeFailure } from './errors'

/** What net/client.ts and api/client.ts both throw: an Error carrying status. */
function apiError(status: number, detail: string): Error & { status: number } {
  return Object.assign(new Error(detail), { status })
}

describe('classifyFailure', () => {
  it('reads a planner 404 as an infeasible mission, not a failed request', () => {
    const failure = classifyFailure(
      apiError(404, 'Chance constraint: 283148 moves were refused'),
      'planner',
    )
    expect(failure.kind).toBe('mission-infeasible')
    // The one verdict that is about the route itself.
    expect(failure.keepsExistingRoute).toBe(false)
    expect(describeFailure(failure)).toContain('No feasible route')
    expect(describeFailure(failure)).not.toContain('failed')
  })

  it('reads a layer 404 as missing preprocessing, not an infeasible mission', () => {
    // The same status, the opposite meaning: the contract answers a missing
    // cache with 404 and the name of the script that would build it.
    const failure = classifyFailure(
      apiError(404, 'roughness cache missing; run scripts/setup_caches.py'),
      'layer',
    )
    expect(failure.kind).toBe('data-unavailable')
    expect(failure.keepsExistingRoute).toBe(true)
    expect(describeFailure(failure)).toContain('setup_caches.py')
  })

  it('reads 422 as configuration and 503 as a deployment state', () => {
    expect(classifyFailure(apiError(422, 'risk_alpha out of range'), 'planner').kind)
      .toBe('invalid-request')
    expect(classifyFailure(apiError(503, 'grid not loaded'), 'layer').kind)
      .toBe('data-unavailable')
  })

  it('reads a failure with no status as transport', () => {
    const failure = classifyFailure(new TypeError('Failed to fetch'), 'analysis')
    expect(failure.kind).toBe('transport')
    expect(failure.status).toBeNull()
  })

  it('never invalidates a route for anything but an infeasible mission', () => {
    const kinds = [
      classifyFailure(apiError(500, 'boom'), 'analysis'),
      classifyFailure(apiError(404, 'no cache'), 'analysis'),
      classifyFailure(apiError(422, 'bad'), 'analysis'),
      classifyFailure(new Error('offline'), 'analysis'),
    ]
    expect(kinds.every((f) => f.keepsExistingRoute)).toBe(true)
  })

  it('classifies structurally, so both ApiError classes work', () => {
    // net/client.ts and api/client.ts each define their own ApiError with no
    // relation to the other, so `instanceof` would pass for one and fail for
    // the other. Anything carrying a numeric status has to work.
    class OneApiError extends Error { status = 404 }
    class OtherApiError extends Error { status = 404 }
    expect(classifyFailure(new OneApiError('a'), 'planner').kind).toBe('mission-infeasible')
    expect(classifyFailure(new OtherApiError('b'), 'planner').kind).toBe('mission-infeasible')
  })

  it('keeps the backend’s own words, which carry the specifics', () => {
    const detail = 'corridor: start not in any lit component (0 of 14 voxels)'
    expect(classifyFailure(apiError(404, detail), 'planner').detail).toBe(detail)
  })
})
