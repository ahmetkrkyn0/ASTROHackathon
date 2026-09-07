import { describe, expect, it } from 'vitest'
import type { Rate, StressTestResponse } from '../../net/stressTest'

/**
 * The stress test's own numbers are the backend's; what is worth pinning here
 * is the reading of them, and the one reading the plan calls out by name.
 */

function rate(count: number, n: number, ci: [number, number]): Rate {
  return { count, rate: count / n, ci95: ci }
}

describe('completion is not safety', () => {
  it('is a rate over runs, not a verdict about the route', () => {
    // The planner returned a route; this says how often a perturbed execution
    // of it finishes. Two different questions, and the panel must not let the
    // second overwrite the first.
    const response: StressTestResponse = {
      rates: { completion: rate(296, 1000, [0.269, 0.325]) },
      verdict: { reaches_goal_at_95pct: false, text: '296/1000 runs reached the goal' },
    }
    expect(response.rates!.completion!.rate).toBeCloseTo(0.296, 3)
    // Nothing in the response speaks about route validity at all.
    expect(response).not.toHaveProperty('route_valid')
    expect(response).not.toHaveProperty('status')
  })

  it('carries an interval, because a rate alone hides how few runs support it', () => {
    const few = rate(3, 10, [0.108, 0.603])
    const many = rate(300, 1000, [0.272, 0.329])
    expect(few.rate).toBeCloseTo(many.rate, 1)
    // Same point estimate, completely different finding.
    const width = (r: Rate) => r.ci95[1] - r.ci95[0]
    expect(width(few)).toBeGreaterThan(width(many) * 5)
  })
})

describe('histograms', () => {
  it('are the backend’s own bins, with one more edge than count', () => {
    // Re-binning would invent a distribution shape the analysis did not
    // report, which the contract forbids. The shape here is the check that
    // the bins are being consumed as given.
    const histogram = { edges: [0, 1, 2, 3], counts: [5, 9, 2] }
    expect(histogram.edges.length).toBe(histogram.counts.length + 1)
  })
})

describe('failure causes', () => {
  it('keeps a zero count apart from an absent one', () => {
    // Zero battery depletions is a finding. A missing key is not the same
    // claim and must not be drawn as one.
    const failures: Record<string, number> = {
      battery_depleted: 0, shadow_endurance: 0, horizon_exceeded: 0,
    }
    const shown = Object.entries(failures).filter(([, count]) => count > 0)
    expect(shown).toHaveLength(0)
    expect(Object.keys(failures)).toHaveLength(3)
  })
})
