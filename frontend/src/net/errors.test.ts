import { describe, expect, it } from 'vitest'

import { ApiError } from './client'
import { classifyError, errorHeadline, isDataUnavailable, keepsExistingRoute } from './errors'

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
