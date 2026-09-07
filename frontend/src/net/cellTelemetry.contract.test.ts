import { describe, expect, it } from 'vitest'

import type { CellTelemetryResponse } from './types'
import { isModelUnavailable } from '../mission/capability'

import full from './__fixtures__/cell-telemetry.full.json'
import plain from './__fixtures__/cell-telemetry.available.json'

const FULL = full as unknown as CellTelemetryResponse
const PLAIN = plain as unknown as CellTelemetryResponse

/**
 * The single cell inspector, at its widest. Both optional blocks are opt-in on
 * the backend, so the two fixtures are the two states the panel renders.
 */
describe('cell telemetry, both blocks requested', () => {
  it('carries the survival block with its own model label', () => {
    expect(FULL.survival).not.toBeNull()
    expect(FULL.survival_model?.model).toBe('reach_avoid_value_iteration_v1')
    expect(FULL.survival_model?.validity).toBe('MODEL')
  })

  it('reports P(safe) zero as a value, alongside the action that explains it', () => {
    // Zero is the policy finding nothing, not missing data -- and the action
    // name says the same thing in words. The two must agree.
    const survival = FULL.survival!
    expect(survival.p_safe).toBe(0)
    expect(survival.best_action).toBe(255)
    expect(survival.best_action_name).toBe('none')
  })

  it('says which coarse block the fine cell fell in', () => {
    // The policy is solved at coarsen 4. Printing it beside a 5 m cell without
    // saying so would claim a resolution the field does not have.
    const survival = FULL.survival!
    expect(survival.coarsen).toBe(4)
    expect(survival.block).toHaveLength(2)
    expect(survival.block[0]).toBe(Math.floor(FULL.row / survival.coarsen))
    expect(survival.block[1]).toBe(Math.floor(FULL.col / survival.coarsen))
  })

  it('carries the dwell block with its uncalibrated lag', () => {
    const dwell = FULL.thermal_dwell!
    expect(dwell).not.toBeNull()
    expect(dwell.thermal_lag_validity).toBe('UNCALIBRATED')
    expect(FULL.thermal_dwell_model?.validity).toBe('MODEL')
  })

  it('distinguishes a measured dwell from one clipped to the lookahead', () => {
    const dwell = FULL.thermal_dwell!
    // This cell leaves the envelope inside the window, so the figure is real.
    expect(dwell.open_ended).toBe(false)
    expect(dwell.max_dwell_h).toBeGreaterThan(0)
    expect(dwell.max_dwell_h!).toBeLessThan(dwell.lookahead_h)
    // A limited cell names which side it hit and on which component.
    expect(dwell.side).toBeTruthy()
    expect(dwell.component).toBeTruthy()
  })

  it('states the envelope the dwell is measured against', () => {
    const dwell = FULL.thermal_dwell!
    expect(dwell.envelope.lo_c).toBeLessThan(dwell.envelope.hi_c)
    expect(dwell.initial_inner_c).toBeGreaterThanOrEqual(dwell.envelope.lo_c)
    expect(dwell.initial_outside_envelope).toBe(false)
  })

  it('carries two independent entrenchment countdowns', () => {
    // Thermal and safe-haven are different clocks and the shorter one governs.
    // Collapsing them into a single number would hide which is binding.
    const entrenched = FULL.thermal_dwell!.tolerable_entrenched
    expect(entrenched).toBeDefined()
    expect(entrenched?.thermal).toBeDefined()
    expect(entrenched?.haven).toBeDefined()
  })
})

describe('cell telemetry, neither block requested', () => {
  it('nulls both and says why, rather than omitting them silently', () => {
    expect(PLAIN.survival).toBeNull()
    expect(PLAIN.thermal_dwell).toBeNull()
    expect(isModelUnavailable(PLAIN.survival_model)).toBe(true)
    expect(isModelUnavailable(PLAIN.thermal_dwell_model)).toBe(true)
    expect(PLAIN.survival_model?.reason).toContain('not requested')
    expect(PLAIN.thermal_dwell_model?.reason).toContain('not requested')
  })

  it('keeps the always-present fields identical either way', () => {
    // The optional blocks are additive: asking for them must not change what
    // the base response says about the cell.
    expect(FULL.row).toBe(PLAIN.row)
    expect(FULL.col).toBe(PLAIN.col)
    expect(FULL.lat).toBe(PLAIN.lat)
    expect(FULL.lon).toBe(PLAIN.lon)
    expect(FULL.roughness_m).toBe(PLAIN.roughness_m)
    expect(FULL.in_psr).toBe(PLAIN.in_psr)
  })
})
