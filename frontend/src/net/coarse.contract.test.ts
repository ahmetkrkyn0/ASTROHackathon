import { describe, expect, it } from 'vitest'

import type { SurvivalManifest, ThermalDwellManifest } from './analysis'
import { isModelUnavailable } from '../mission/capability'

import survival from './__fixtures__/survival.available.json'
import dwell from './__fixtures__/thermal-dwell.available.json'
import survivalMissingGoal from './__fixtures__/survival.422-missing-goal.json'

const SURVIVAL = survival as unknown as SurvivalManifest
const DWELL = dwell as unknown as ThermalDwellManifest

describe('GET /api/survival', () => {
  it('parses the manifest and its model block', () => {
    expect(SURVIVAL.survival_model.model).toBe('reach_avoid_value_iteration_v1')
    expect(SURVIVAL.survival_model.validity).toBe('MODEL')
    expect(isModelUnavailable(SURVIVAL.survival_model)).toBe(false)
  })

  it('is a coarse grid, four fine cells to a block', () => {
    expect(SURVIVAL.grid.coarsen).toBe(4)
    expect(SURVIVAL.grid.rows).toBe(125)
    expect(SURVIVAL.grid.resolution_m).toBe(20)
    // Drawn at the fine grid's 5 m pitch this would be wrong by a factor of
    // four in each axis.
    expect(SURVIVAL.grid.resolution_m).toBeGreaterThan(5)
  })

  it('publishes both fields with binary urls', () => {
    for (const name of ['p_safe', 'best_action'] as const) {
      expect(SURVIVAL.fields[name]?.binary_url).toContain('field=' + name)
    }
  })

  it('marks best_action as a code, not a quantity', () => {
    // `units: "code"` is the whole reason it is drawn as separate masks. A
    // rename here would silently turn it back into a ramp.
    expect(SURVIVAL.fields.best_action?.units).toBe('code')
    expect(SURVIVAL.fields.p_safe?.units).toBe('fraction')
  })

  it('reports the blocks that can reach nothing', () => {
    // Nearly a third of traversable blocks. The panel shows this as its own
    // finding rather than as one summary number among four.
    expect(SURVIVAL.summary.fraction_zero).toBeGreaterThan(0.2)
    expect(SURVIVAL.summary.fraction_zero).toBeLessThan(1)
    expect(SURVIVAL.summary.mean_p_safe).toBeLessThan(1)
  })

  it('requires a goal, and says so rather than failing obscurely', () => {
    expect(survivalMissingGoal.detail).toContain('goal_row')
  })
})

describe('GET /api/thermal-dwell', () => {
  it('parses the manifest and both model blocks', () => {
    expect(DWELL.dwell_model.model).toBe('inner_temperature_first_order_lag_v1')
    expect(DWELL.dwell_model.validity).toBe('MODEL')
    // The shadow series underneath it is a separate model with its own state.
    expect(isModelUnavailable(DWELL.shadow_model)).toBe(false)
  })

  it('is the same coarse grid as survival', () => {
    expect(DWELL.grid.coarsen).toBe(4)
    expect(DWELL.grid.rows).toBe(SURVIVAL.grid.rows)
    expect(DWELL.grid.cols).toBe(SURVIVAL.grid.cols)
  })

  it('marks side as a code and max_dwell_h as hours', () => {
    expect(DWELL.fields.side?.units).toBe('code')
    expect(DWELL.fields.max_dwell_h?.units).toBe('h')
    expect(DWELL.fields.open_ended?.units).toBe('boolean')
  })

  it('caps max_dwell_h at the lookahead, which is a floor not a value', () => {
    // A block that never leaves the envelope is clipped to the lookahead. The
    // number that comes back is "at least this", and `open_ended` is how the
    // response says so -- reading 24.0 as a measured dwell overstates it.
    expect(DWELL.fields.max_dwell_h?.max).toBe(DWELL.summary.lookahead_h)
    expect(DWELL.summary.fraction_unlimited).toBeGreaterThan(0)
  })

  it('splits the envelope three ways, and they account for everything', () => {
    const total =
      DWELL.summary.fraction_unlimited +
      DWELL.summary.fraction_cold_limited +
      DWELL.summary.fraction_hot_limited
    expect(total).toBeCloseTo(1, 2)
  })

  it('does not report a median of the clipped blocks', () => {
    // finite_median_h is over the blocks that actually left the envelope.
    // Including the clipped ones would drag it toward the lookahead.
    expect(DWELL.summary.finite_median_h).toBeLessThan(DWELL.summary.lookahead_h)
    expect(DWELL.summary.finite_p5_h).toBeLessThan(DWELL.summary.finite_median_h)
    expect(DWELL.summary.finite_p95_h).toBeGreaterThan(DWELL.summary.finite_median_h)
  })
})
