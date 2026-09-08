import { beforeEach, describe, expect, it } from 'vitest'
import { PLAN_REQUEST_CONTRIBUTORS } from './contributors'
import { getConstraint, readConstraintKeys, readPlanConstraints, setConstraint } from './store'

/** The store is a module singleton, so each case states its own world. */
beforeEach(() => {
  for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
    setConstraint(contributor.id, { enabled: false })
  }
})

describe('the non-regression rule', () => {
  it('sends nothing at all when every constraint is off', () => {
    // The rule the integration plan opens with: with no advanced feature
    // enabled the request body must be the one this product always sent.
    expect(readPlanConstraints()).toEqual({})
  })

  it('sends nothing for a constraint that is off but still holds a value', () => {
    // A switch turned back off must not leave its last value in the body.
    setConstraint('risk', { enabled: true, value: 0.9 })
    expect(readPlanConstraints()).toEqual({ risk_alpha: 0.9 })
    setConstraint('risk', { enabled: false, value: 0.9 })
    expect(readPlanConstraints()).toEqual({})
  })

  it('never lets a disabled constraint contribute a neutral default', () => {
    // risk_alpha 0.5 is NOT neutral -- CVaR at 0.5 is mu + 0.798 sigma. A
    // default sent while the toggle reads "off" would change every route in
    // the product and look like nothing had happened.
    for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
      expect(contributor.fields({ enabled: false })).toBeNull()
      expect(contributor.fields({ enabled: false, value: 0.5 })).toBeNull()
    }
  })
})

describe('risk appetite (B2)', () => {
  it('sends the alpha the operator chose', () => {
    setConstraint('risk', { enabled: true, value: 0.99 })
    expect(readPlanConstraints()).toEqual({ risk_alpha: 0.99 })
  })

  it('refuses an alpha outside the contract’s interval', () => {
    // Out of [0.5, 0.999] is a 422. Sending one would turn a slider into a
    // failed plan; contributing nothing leaves the route nominal instead.
    for (const value of [0.4, 0.4999, 1, 1.5, -1]) {
      setConstraint('risk', { enabled: true, value })
      expect(readPlanConstraints()).toEqual({})
    }
  })

  it('refuses a non-numeric alpha rather than coercing it', () => {
    setConstraint('risk', { enabled: true, value: '0.9' })
    expect(readPlanConstraints()).toEqual({})
  })
})

describe('the registry', () => {
  it('gives every contributor a stable id, a label and a hint', () => {
    const ids = PLAN_REQUEST_CONTRIBUTORS.map((c) => c.id)
    expect(new Set(ids).size).toBe(ids.length)
    for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
      expect(contributor.label.length).toBeGreaterThan(0)
      expect(contributor.hint.length).toBeGreaterThan(0)
    }
  })

  it('never contributes an empty object, which would invalidate for nothing', () => {
    // An enabled constraint that adds no field would still move the route
    // identity and mark every post-route analysis stale for a request that
    // did not change. Contributors return null instead.
    for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
      const produced = contributor.fields({ enabled: true, value: undefined })
      if (produced !== null) expect(Object.keys(produced).length).toBeGreaterThan(0)
    }
  })

  it('starts a numeric control on its declared initial value', () => {
    // So switching a constraint on never hands the backend an undefined
    // where a number belongs.
    for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
      if (contributor.control.kind !== 'number') continue
      expect(getConstraint(contributor.id).value).toBe(contributor.control.initial)
    }
  })
})

/**
 * The by-constraintKey view the 4-D builder reads.
 *
 * The 4-D constraints used to live in a `useState` inside the time-axis hook
 * while the 2-D ones lived in this store, so `risk` was settable in one place
 * and read in the other and the alpha never crossed -- the audit's B2-1. One
 * store now serves both, addressed by `id` for the 2-D fields it builds
 * itself and by `constraintKey` for the 4-D builder that folds them.
 */
describe('the 4-D constraint view', () => {
  it('produces no key at all for a constraint that is off', () => {
    expect(readConstraintKeys()).toEqual({})
  })

  it('produces no key for a constraint switched off after holding a value', () => {
    setConstraint('risk', { enabled: true, value: 0.97 })
    expect(readConstraintKeys()).toEqual({ riskAlpha: 0.97 })
    setConstraint('risk', { enabled: false, value: 0.97 })
    // Not `riskAlpha: false`, not `riskAlpha: undefined` -- absent. The 4-D
    // builder reads a missing key as off, so anything else re-enables it.
    expect(readConstraintKeys()).toEqual({})
  })

  it('states a toggle as literally true', () => {
    // constraintStateFrom opens a toggle on `raw === true` and nothing else.
    setConstraint('thermal-dwell', { enabled: true })
    expect(readConstraintKeys()).toEqual({ requireThermalDwell: true })
  })

  it('carries a number and a string, which a boolean record could not', () => {
    setConstraint('survival-chance', { enabled: true, value: 0.05 })
    setConstraint('lit-rule', { enabled: true, value: 'majority' })
    expect(readConstraintKeys()).toMatchObject({
      maxFailureProbability: 0.05,
      litRule: 'majority',
    })
  })

  it('falls back to the control initial for a switch never dragged', () => {
    // Switching a slider on without touching it must send the number the
    // panel is displaying, not an undefined the backend would reject.
    setConstraint('survival-chance', { enabled: true })
    expect(readConstraintKeys().maxFailureProbability).toBe(0.05)
  })

  it('keys every contributor by its own constraintKey', () => {
    for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
      setConstraint(contributor.id, { enabled: true })
    }
    const keys = readConstraintKeys()
    for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
      expect(keys).toHaveProperty(contributor.constraintKey)
    }
  })
})
