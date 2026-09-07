import { describe, expect, it } from 'vitest'
import { readUncertaintySummary } from './useUncertainty'

describe('readUncertaintySummary', () => {
  it('returns null when the clone ensemble was never built', () => {
    // The contract is explicit: with no cache the field is absent entirely.
    // A zeroed summary would report a route as certainly traversable when
    // nothing computed it.
    expect(readUncertaintySummary({})).toBeNull()
    expect(readUncertaintySummary(null)).toBeNull()
    expect(readUncertaintySummary({ uncertainty: null })).toBeNull()
  })

  it('reads the summary that rides along with a plan', () => {
    const summary = readUncertaintySummary({
      uncertainty: {
        model: 'nasa_pgda_clones', n_clones: 100, coarsen: 4,
        p_traversable_min: 0.2, p_traversable_mean: 0.92,
        route_feasible_fraction: 0.0,
        product_url: 'https://pgda.gsfc.nasa.gov/products/78',
      },
    })!
    expect(summary.nClones).toBe(100)
    expect(summary.pTraversableMin).toBe(0.2)
    // Zero is a real answer here -- the nominal DEM allows a traverse the
    // ensemble does not -- and must survive as 0 rather than becoming null.
    expect(summary.routeFeasibleFraction).toBe(0)
  })

  it('keeps a missing field null rather than defaulting it', () => {
    const summary = readUncertaintySummary({ uncertainty: { n_clones: 100 } })!
    expect(summary.pTraversableMean).toBeNull()
    expect(summary.routeFeasibleFraction).toBeNull()
  })
})
