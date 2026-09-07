import { describe, expect, it } from 'vitest'

import { ApiError } from './client'
import {
  classifyError,
  classifyFailure,
  describeFailure,
  errorHeadline,
  isDataUnavailable,
  keepsExistingRoute,
} from './errors'

import roughnessUnavailable from './__fixtures__/layers-roughness.unavailable.json'
import psrUnavailable from './__fixtures__/layers-psr.unavailable.json'
import psrValidationUnavailable from './__fixtures__/psr-validation.unavailable.json'
import thermalEnvelope422 from './__fixtures__/thermal-envelope.422.json'
import survivalMissingGoal from './__fixtures__/survival.422-missing-goal.json'
import survivalUntraversable from './__fixtures__/survival.422-untraversable-goal.json'

/**
 * Every `detail` string here comes from a captured response, so a backend
 * wording change breaks these tests rather than silently relabelling a panel.
 */
describe('classifyError', () => {
  it('reads a missing cache as data-unavailable, not a failure', () => {
    for (const fixture of [roughnessUnavailable, psrUnavailable, psrValidationUnavailable]) {
      const classified = classifyError(new ApiError(404, fixture.detail))
      expect(classified.kind).toBe('data-unavailable')
      expect(classified.detail).toBe(fixture.detail)
    }
  })

  it('extracts the script that would fix a missing cache', () => {
    const classified = classifyError(new ApiError(404, roughnessUnavailable.detail))
    expect(classified.remedy).toBe('python scripts/build_roughness_cache.py')
  })

  it('reads a missing cache behind a 422 as data-unavailable too', () => {
    // The status says validation; the sentence says the cache is absent.
    const classified = classifyError(new ApiError(422, thermalEnvelope422.detail))
    expect(classified.kind).toBe('data-unavailable')
    expect(classified.remedy).toBe('python scripts/build_thermal_envelope_cache.py')
  })

  it('reads a constraint-closed route as mission-infeasible, not a request failure', () => {
    const classified = classifyError(
      new ApiError(
        404,
        'No route: 412 edges would have driven the rover into a cell with no Earth visibility.',
      ),
    )
    expect(classified.kind).toBe('mission-infeasible')
    expect(errorHeadline(classified)).toBe(
      'No feasible route under the selected mission constraints',
    )
  })

  it('separates a missing parameter from an infeasible one on the same status', () => {
    expect(classifyError(new ApiError(422, survivalMissingGoal.detail)).kind).toBe(
      'invalid-request',
    )
    expect(classifyError(new ApiError(422, survivalUntraversable.detail)).kind).toBe(
      'mission-infeasible',
    )
  })

  it('calls an unreachable backend transport, with no status', () => {
    const classified = classifyError(new TypeError('Failed to fetch'))
    expect(classified.kind).toBe('transport')
    expect(classified.status).toBeNull()
  })

  it('degrades an optional analysis rather than reporting a fault', () => {
    expect(classifyError(new ApiError(500, 'boom'), { optional: true }).kind).toBe(
      'analysis-failure',
    )
    expect(classifyError(new ApiError(500, 'boom')).kind).toBe('backend-fault')
  })

  it('keeps the route on screen for everything except an infeasible plan', () => {
    const infeasible = classifyError(new ApiError(404, 'No route under these constraints'))
    const analysis = classifyError(new ApiError(500, 'boom'), { optional: true })
    expect(keepsExistingRoute(infeasible)).toBe(false)
    expect(keepsExistingRoute(analysis)).toBe(true)
  })

  it('exposes the unavailable verdict the capability layer asks for', () => {
    expect(isDataUnavailable(new ApiError(404, roughnessUnavailable.detail))).toBe(true)
    expect(isDataUnavailable(new ApiError(422, survivalMissingGoal.detail))).toBe(false)
  })
})

/**
 * The two vocabularies are one taxonomy, and this is what keeps them one.
 *
 * `classifyFailure` is a projection of `classifyError`; if someone later gives
 * it a rule of its own, these break rather than the two views quietly
 * disagreeing about whether a route survives.
 */
describe('the two views agree', () => {
  it('reports the same verdict through either name', () => {
    const error = Object.assign(new Error(roughnessUnavailable.detail), { status: 404 })
    const classified = classifyError(error, { endpoint: 'layer' })
    const failure = classifyFailure(error, 'layer')
    expect(failure.kind).toBe(classified.kind)
    expect(failure.status).toBe(classified.status)
    expect(failure.detail).toBe(classified.detail)
    expect(failure.keepsExistingRoute).toBe(keepsExistingRoute(classified))
  })

  it('treats an optional call and an analysis endpoint as the same statement', () => {
    const error = Object.assign(new Error('boom'), { status: 500 })
    expect(classifyError(error, { optional: true }).kind).toBe('analysis-failure')
    expect(classifyError(error, { endpoint: 'analysis' }).kind).toBe('analysis-failure')
  })

  it('classifies structurally, so both ApiError classes work', () => {
    // net/client.ts and api/client.ts each define their own ApiError with no
    // relation to the other, so `instanceof` would pass for one and fail for
    // the other -- and the branch it fell past reported a missing cache as a
    // transport failure. Anything carrying a numeric status has to work.
    class OtherApiError extends Error {
      status = 404
    }
    expect(classifyError(new OtherApiError(roughnessUnavailable.detail)).kind).toBe(
      'data-unavailable',
    )
  })
})

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

describe('the same words, two meanings, split by who was asked', () => {
  it('reads "not traversable" from a planner as a finding about the mission', () => {
    // The operator put the goal somewhere the rover cannot stand.
    const detail = 'goal (300, 300) falls in coarse block (75, 75) at coarsen=4, which is not traversable.'
    expect(classifyError(Object.assign(new Error(detail), { status: 422 })).kind).toBe(
      'mission-infeasible',
    )
  })

  it('reads "not traversable" from an analysis as our own malformed request', () => {
    // We posted an existing route at the wrong cell size. An analysis is asked
    // ABOUT a route that already exists, so it cannot find the mission
    // infeasible -- and no marker list could have told these two apart.
    const detail = 'path_states: state 14 (49, 21, 14) is not traversable'
    expect(classifyFailure(Object.assign(new Error(detail), { status: 422 }), 'analysis').kind).toBe(
      'invalid-request',
    )
  })
})
