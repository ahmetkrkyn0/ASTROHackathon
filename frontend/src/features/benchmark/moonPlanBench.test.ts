import { describe, expect, it } from 'vitest'
import {
  MOONPLANBENCH_CLAIM,
  MOONPLANBENCH_VARIANTS,
} from './moonPlanBench'

describe('MoonPlanBench figures', () => {
  it('reproduces the paper’s shortest-path length exactly under its own model', () => {
    // This is the report's central claim and the strongest honest thing this
    // product can say about the benchmark: same model, same answer. If a
    // transcription ever drifts, this is where it shows.
    for (const variant of MOONPLANBENCH_VARIANTS) {
      expect(variant.benchmarkModelLength).toBe(variant.paperLength)
    }
  })

  it('records LunaPath scoring lower, and never rounds the gap away', () => {
    // The 10-degree variant is the uncomfortable one: 33.3% against 100%.
    // Softening it would be the single most misleading thing this product
    // could say about itself.
    const ten = MOONPLANBENCH_VARIANTS[0]
    expect(ten.lunapathSuccess).toBeCloseTo(0.333, 3)
    expect(ten.benchmarkModelSuccess).toBe(1)
    expect(ten.lunapathSuccess).toBeLessThan(ten.benchmarkModelSuccess)
  })

  it('explains the gap with a measured count, not an assertion', () => {
    // Where LunaPath scores lower there are maps connected only by cutting a
    // corner; where it does not, there are none. The two move together, which
    // is what makes the explanation a finding rather than an excuse.
    for (const variant of MOONPLANBENCH_VARIANTS) {
      const behind = variant.lunapathSuccess < variant.benchmarkModelSuccess
      expect(variant.cornerCutOnlyMaps > 0).toBe(behind)
    }
  })

  it('keeps a path found under the safety rule no shorter than the paper’s', () => {
    // Refusing to cut corners cannot produce a shorter route. A transcription
    // that made LunaPath look better than the reference would be wrong.
    for (const variant of MOONPLANBENCH_VARIANTS) {
      expect(variant.lunapathLength).toBeGreaterThanOrEqual(variant.paperLength)
    }
  })
})

describe('the claim boundary', () => {
  it('says what the benchmark does not measure', () => {
    for (const absent of ['shadow', 'thermal', 'slip', 'Earth-visibility']) {
      expect(MOONPLANBENCH_CLAIM).toContain(absent)
    }
  })

  it('marks the paper’s figures as quotations', () => {
    expect(MOONPLANBENCH_CLAIM).toContain('quotation')
    expect(MOONPLANBENCH_CLAIM).toContain('not our measurement')
  })

  it('never claims an unconditional hundred per cent', () => {
    expect(MOONPLANBENCH_CLAIM).not.toMatch(/\b100%\s+success/i)
  })
})
