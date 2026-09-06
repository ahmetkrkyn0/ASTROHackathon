import { describe, expect, it } from 'vitest'
import { isEmpty, readRouteModel } from './routeModel'

describe('readRouteModel', () => {
  it('reports nothing when a response carries none of the three blocks', () => {
    expect(isEmpty(readRouteModel({}))).toBe(true)
    expect(isEmpty(readRouteModel(null))).toBe(true)
  })

  it('keeps a block that is present but not applied, with its reason', () => {
    // Absent and "present, not applied" are different answers: the second
    // says the backend considered it and explains why it did not count.
    const view = readRouteModel({
      roughness: { applied: false, reason: 'roughness layer not loaded', route: null },
    })
    expect(view.roughness).not.toBeNull()
    expect(view.roughness!.applied).toBe(false)
    expect(view.roughness!.reason).toBe('roughness layer not loaded')
    expect(view.roughness!.meanRoughnessM).toBeNull()
  })
})

describe('slip (C3)', () => {
  it('reads what slip cost this route, and its claim', () => {
    const view = readRouteModel({
      slip_model: {
        applied: true, validity: 'MODEL',
        route: {
          mean_slip: 0.326, max_slip: 0.537, max_slip_slope_deg: 16.9,
          distance_factor: 1.53, extra_hours: 0.75, extra_drawn_wh: 321,
        },
        claim: 'Literature-anchored MODEL, not a measurement',
      },
    })
    expect(view.slip!.validity).toBe('MODEL')
    expect(view.slip!.extraHours).toBe(0.75)
    expect(view.slip!.distanceFactor).toBe(1.53)
    expect(view.slip!.claim).toContain('not a measurement')
  })
})

describe('risk (B2)', () => {
  it('treats a null alpha as nominal, never as 0.5', () => {
    // CVaR at 0.5 is mu + 0.798 sigma. Defaulting a missing alpha to 0.5
    // would report a tail-priced route as the ordinary one.
    const view = readRouteModel({ risk: { alpha: null, applied: false, route: null } })
    expect(view.risk!.alpha).toBeNull()
    expect(view.risk!.applied).toBe(false)
  })

  it('keeps the nominal and the risk-adjusted figures apart', () => {
    // The planner's clock does not move with alpha. Showing only the adjusted
    // hours would report a schedule nobody is flying.
    const view = readRouteModel({
      risk: {
        alpha: 0.9, applied: true, validity: 'MODEL', multiplier: 1.755,
        scope: 'ranking cost only; travel time, battery and safety margins use the mean',
        route: {
          mean_slip_mu: 0.313, mean_slip_cvar: 0.51,
          hours: 2.23, risk_adjusted_hours: 3.4,
          drawn_wh: 970, risk_adjusted_drawn_wh: 1480,
        },
        claim: 'CVaR of MODEL-labelled distributions, not a measured risk',
      },
    })
    expect(view.risk!.hours).toBe(2.23)
    expect(view.risk!.riskAdjustedHours).toBe(3.4)
    expect(view.risk!.scope).toContain('ranking cost only')
    expect(view.risk!.claim).toContain('not a measured risk')
  })
})

describe('roughness (C4)', () => {
  it('keeps the measurement’s validity apart from the cost scale’s', () => {
    // The product is real NASA LOLA data; turning it into a cost is a model.
    // One label for both would promote or demote one of them.
    const view = readRouteModel({
      roughness: {
        applied: true, validity: 'MEASURED', scale_validity: 'MODEL',
        product: 'LDRM_80S_50MPP_ADJ_ROUGH_100M', baseline_m: 100, weight: 0.15,
        route: { mean_roughness_m: 1.04, max_roughness_m: 1.96, cells_in_psr: 0 },
        claim: 'NOT the roughness of the cell itself',
      },
    })
    expect(view.roughness!.validity).toBe('MEASURED')
    expect(view.roughness!.scaleValidity).toBe('MODEL')
    expect(view.roughness!.claim).toContain('NOT the roughness of the cell')
  })

  it('never reads an unchecked PSR count as zero', () => {
    // cells_in_psr is null when the PSR mask is not loaded. Zero would say
    // "no cells in permanent shadow" for a route nobody checked.
    const view = readRouteModel({
      roughness: { applied: true, route: { mean_roughness_m: 1.0, cells_in_psr: null } },
    })
    expect(view.roughness!.cellsInPsr).toBeNull()
    const checked = readRouteModel({
      roughness: { applied: true, route: { cells_in_psr: 0 } },
    })
    expect(checked.roughness!.cellsInPsr).toBe(0)
  })
})
