import { describe, expect, it } from 'vitest'

import { ApiError } from '../net/client'
import { isDataUnavailable } from '../net/errors'
import {
  capabilityFromError,
  capabilityFromModel,
  capabilityMessage,
  capabilityReady,
  capabilityStale,
  capabilityUnavailable,
  capabilityValue,
} from './capability'

import uncertaintySeries from '../net/__fixtures__/uncertainty-series.unavailable.json'
import safeHaven from '../net/__fixtures__/safe-haven.available.json'
import cellTelemetry from '../net/__fixtures__/cell-telemetry.available.json'
import roughnessUnavailable from '../net/__fixtures__/layers-roughness.unavailable.json'

describe('capability', () => {
  it('carries a value only where a value exists', () => {
    expect(capabilityValue(capabilityReady(7))).toBe(7)
    // A stale value is still shown -- marked, not blanked.
    expect(capabilityValue(capabilityStale(7, 'route changed'))).toBe(7)
    expect(capabilityValue(capabilityUnavailable('no cache'))).toBeNull()
  })

  it('passes the backend sentence through instead of rewording it', () => {
    const capability = capabilityUnavailable(roughnessUnavailable.detail)
    expect(capabilityMessage(capability)).toBe(roughnessUnavailable.detail)
    expect(capability.remedy).toBe('python scripts/build_roughness_cache.py')
  })

  it('reads a 200 that says "unavailable" as unavailable', () => {
    // uncertainty-series answers 200 with an unavailable model block. Checking
    // response.ok alone would conclude there is data here.
    const capability = capabilityFromModel(uncertaintySeries, uncertaintySeries)
    expect(capability.status).toBe('unavailable')
    expect(capabilityValue(capability)).toBeNull()
    if (capability.status === 'unavailable') {
      expect(capability.reason).toBe(uncertaintySeries.reason)
      expect(capability.remedy).toBe('python scripts/build_dem_clone_cache.py')
    }
  })

  it('treats a real model block as ready', () => {
    const capability = capabilityFromModel(safeHaven.safe_haven_model, safeHaven)
    expect(capability.status).toBe('ready')
    expect(capabilityValue(capability)).toBe(safeHaven)
  })

  it('reads the nested unavailable blocks a 200 telemetry response carries', () => {
    // Same response, three sub-models: two unavailable because they were not
    // requested, one absent entirely.
    expect(capabilityFromModel(cellTelemetry.survival_model, null).status).toBe('unavailable')
    expect(capabilityFromModel(cellTelemetry.thermal_dwell_model, null).status).toBe(
      'unavailable',
    )
    expect(capabilityFromModel(null, null).status).toBe('unavailable')
  })

  it('separates a missing cache from a genuine fault', () => {
    const missing = new ApiError(404, roughnessUnavailable.detail)
    const fault = new ApiError(500, 'internal error')

    const asUnavailable = capabilityFromError(missing, {
      isDataUnavailable: isDataUnavailable(missing),
    })
    const asError = capabilityFromError(fault, { isDataUnavailable: isDataUnavailable(fault) })

    expect(asUnavailable?.status).toBe('unavailable')
    expect(asError?.status).toBe('error')
  })

  it('reports nothing for a cancelled request', () => {
    // A superseded request is not a failure. Reporting one makes every
    // fast-moving slider look broken.
    const controller = new AbortController()
    controller.abort()
    expect(
      capabilityFromError(new Error('aborted'), {
        isDataUnavailable: false,
        signal: controller.signal,
      }),
    ).toBeNull()
    expect(
      capabilityFromError(new DOMException('aborted', 'AbortError'), {
        isDataUnavailable: false,
      }),
    ).toBeNull()
  })
})
