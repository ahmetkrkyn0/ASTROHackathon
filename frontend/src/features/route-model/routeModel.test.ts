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

describe('survival (B1)', () => {
  it('keeps a transferred failure rate marked as an assumption', () => {
    // Hiding an assumed failure rate is one of the integration plan's named
    // acceptance failures, so the source string has to survive intact.
    const view = readRouteModel({
      survival: {
        requested: true, applied: true, beta: 0.05, validity: 'MODEL',
        failure_model: {
          rate_per_km: 0.2,
          source: 'assumption: Lamarre, Malhotra, Kelly (transferred)',
        },
        route: { execution_failure_probability: 0.0123, moves_refused: 0 },
        claim: 'reach-avoid value iteration on a discretised field',
      },
    })
    expect(view.survival!.failureSource).toContain('assumption')
    expect(view.survival!.failureRatePerKm).toBe(0.2)
    expect(view.survival!.executionFailureProbability).toBeCloseTo(0.0123, 4)
  })

  it('tells "not requested" apart from "requested and refused"', () => {
    const notAsked = readRouteModel({ survival: { requested: false, applied: false } })
    expect(notAsked.survival!.requested).toBe(false)
    const refused = readRouteModel({
      survival: { requested: true, applied: false, reason: 'no safe haven map' },
    })
    expect(refused.survival!.requested).toBe(true)
    expect(refused.survival!.reason).toBe('no safe haven map')
  })

  it('keeps zero refused moves as zero', () => {
    // Non-zero on a 200 is normal -- the search found another way -- so zero
    // is a real finding and must not become null.
    const view = readRouteModel({
      survival: { applied: true, route: { moves_refused: 0 } },
    })
    expect(view.survival!.movesRefused).toBe(0)
  })
})

describe('thermal dwell (C6)', () => {
  it('keeps the lag validity apart from the block validity', () => {
    // The thermal lag is UNCALIBRATED and the block is MODEL. One label for
    // both would promote the weaker of the two, and the plan forbids this
    // product ever reading as "thermally validated".
    const view = readRouteModel({
      thermal_dwell: {
        validity: 'MODEL', thermal_lag_validity: 'UNCALIBRATED',
        requested: false, applied: true, heater_model: 'none',
        envelope: { lo_c: 0, hi_c: 35 },
        route: {
          min_dwell_margin_h: 0.36, open_ended_states: 3, states_past_thermal_dwell: 0,
          inner: { min_c: -15.66, max_c: 17.5 },
        },
        claim: 'MODEL, uncalibrated',
      },
    })
    expect(view.thermal!.validity).toBe('MODEL')
    expect(view.thermal!.lagValidity).toBe('UNCALIBRATED')
    expect(view.thermal!.claim).toContain('uncalibrated')
  })

  it('counts open-ended states rather than inventing an infinity', () => {
    // Open-ended means no limit inside the evaluated horizon. Rendering it as
    // a very large number of hours would be a deadline nobody computed.
    const view = readRouteModel({
      thermal_dwell: { applied: true, route: { open_ended_states: 3 } },
    })
    expect(view.thermal!.openEndedStates).toBe(3)
    expect(view.thermal!.minDwellMarginH).toBeNull()
  })
})
