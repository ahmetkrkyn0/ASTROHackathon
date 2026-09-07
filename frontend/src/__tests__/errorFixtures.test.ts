import { describe, expect, it } from 'vitest'
import { classifyFailure, describeFailure, type EndpointKind } from '../net/errors'

/**
 * Section 35's mandatory error fixtures.
 *
 * Every case the plan names, with the backend's real wording where it was
 * captured from the live API and the contract's wording where it was not.
 * The assertion is always the same and always the point: does the operator
 * see what actually happened, or does everything collapse into "request
 * failed"?
 */

function failure(status: number | null, detail: string, endpoint: EndpointKind) {
  const error = status === null ? new Error(detail) : Object.assign(new Error(detail), { status })
  return classifyFailure(error, endpoint)
}

describe('data that was never built', () => {
  // Captured live from this deployment.
  it('DEM clone ensemble absent', () => {
    const result = failure(
      404,
      'the DEM clone ensemble is not available: no dem_clones.npy beside the processed ' +
        'grids; run scripts/build_dem_clone_cache.py to fetch NASA’s DEM clones',
      'analysis',
    )
    expect(result.kind).toBe('data-unavailable')
    expect(result.keepsExistingRoute).toBe(true)
    // The script name is the actionable part and must reach the screen.
    expect(describeFailure(result)).toContain('build_dem_clone_cache.py')
  })

  it('roughness and PSR layers absent', () => {
    for (const layer of ['roughness', 'psr']) {
      const result = failure(404, `${layer} cache missing; run scripts/setup_caches.py`, 'layer')
      expect(result.kind).toBe('data-unavailable')
      expect(result.keepsExistingRoute).toBe(true)
    }
  })

  it('thermal envelope cache missing', () => {
    const result = failure(422, 'no thermal dwell cube for this rover', 'analysis')
    expect(result.kind).toBe('invalid-request')
    expect(result.keepsExistingRoute).toBe(true)
  })

  it('grid not loaded', () => {
    expect(failure(503, 'grid is not loaded', 'layer').kind).toBe('data-unavailable')
  })
})

describe('a mission the constraints closed', () => {
  it('illumination corridor leaves no route', () => {
    const result = failure(
      404,
      'no route: the corridor has 0 of 14 voxels reachable from the start',
      'planner',
    )
    expect(result.kind).toBe('mission-infeasible')
    expect(result.keepsExistingRoute).toBe(false)
    expect(describeFailure(result)).toContain('No feasible route')
    expect(describeFailure(result)).not.toMatch(/request failed/i)
  })

  it('the chance constraint refuses every path', () => {
    const result = failure(
      404,
      'Chance constraint: 283148 moves were refused because the execution failure ' +
        'probability exceeded beta',
      'planner',
    )
    expect(result.kind).toBe('mission-infeasible')
    // The count is the finding: it says how hard the constraint bound.
    expect(describeFailure(result)).toContain('283148')
  })

  it('Safe Haven reachability leaves no route', () => {
    const result = failure(404, 'no route satisfies the Safe Haven leg rule', 'planner')
    expect(result.kind).toBe('mission-infeasible')
  })
})

describe('a request the backend would not take', () => {
  it('risk alpha out of its interval', () => {
    // Captured live: the contributor refuses this before sending, but a
    // hand-built request still has to read correctly.
    const result = failure(422, 'risk_alpha: Input should be less than or equal to 0.999', 'planner')
    expect(result.kind).toBe('invalid-request')
    expect(result.keepsExistingRoute).toBe(true)
  })

  it('a path that is not traversable at the requested cell size', () => {
    // Captured live from the stress test at the default coarsen of 4.
    const result = failure(422, 'path_states: state 14 (49, 21, 14) is not traversable', 'analysis')
    expect(result.kind).toBe('invalid-request')
  })

  it('a telemetry trace that goes backwards in time', () => {
    expect(failure(422, 't_h must be increasing', 'analysis').kind).toBe('invalid-request')
  })
})

describe('the backend not being there at all', () => {
  it('reads as transport, not as a mission finding', () => {
    const result = failure(null, 'Failed to fetch', 'planner')
    expect(result.kind).toBe('transport')
    expect(result.keepsExistingRoute).toBe(true)
    expect(describeFailure(result)).toContain('Cannot reach')
  })
})

describe('the four categories never blur into one another', () => {
  it('gives the same status different meanings by endpoint', () => {
    // The whole reason classification takes the endpoint. 404 from a planner
    // is a finding about the mission; 404 from a layer is a missing cache.
    expect(failure(404, 'x', 'planner').kind).toBe('mission-infeasible')
    expect(failure(404, 'x', 'layer').kind).toBe('data-unavailable')
    expect(failure(404, 'x', 'analysis').kind).toBe('data-unavailable')
  })

  it('produces a distinct sentence for every kind', () => {
    const sentences = new Set(
      [
        failure(null, 'a', 'planner'),
        failure(404, 'b', 'planner'),
        failure(404, 'c', 'layer'),
        failure(422, 'd', 'planner'),
        failure(500, 'e', 'analysis'),
      ].map((f) => describeFailure(f)),
    )
    expect(sentences.size).toBe(5)
  })
})
