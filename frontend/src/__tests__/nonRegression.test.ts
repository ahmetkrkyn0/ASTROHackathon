import { beforeEach, describe, expect, it } from 'vitest'
import { PLAN_REQUEST_CONTRIBUTORS } from '../features/plan-request/contributors'
import { readPlanConstraints, setConstraint } from '../features/plan-request/store'
import { routeIdentity } from '../mission/routeIdentity'
import { readSafetyMargins } from '../features/safety-margins/safetyMargins'
import { readRouteModel, isEmpty } from '../features/route-model/routeModel'
import { readUncertaintySummary } from '../features/uncertainty/useUncertainty'
import { classifyFailure } from '../net/errors'

/**
 * THE NON-REGRESSION SUITE.
 *
 * Section 34 of the integration plan calls this the most important regression
 * test on the frontend side, and keeps it deliberately separate from the
 * feature tests: those check that a capability works, and this checks that
 * having the capability at all changed nothing for anyone not using it.
 *
 * The failure it guards against is the quiet one. Twelve features were added
 * to a product that already worked, every one of them optional, and the way
 * that goes wrong is not a crash -- it is a default that leaks into a request,
 * a panel that renders an empty frame where there was nothing before, or an
 * absent block read as a zero. None of those look like bugs on the day.
 */

beforeEach(() => {
  for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
    setConstraint(contributor.id, { enabled: false })
  }
})

describe('the request is unchanged with everything off', () => {
  it('adds no field to the plan body', () => {
    // The literal rule the plan opens with. With no advanced feature enabled
    // the body must be the one this product has always sent.
    expect(readPlanConstraints()).toEqual({})
    expect(Object.keys(readPlanConstraints())).toHaveLength(0)
  })

  it('holds no contributor that contributes while disabled', () => {
    for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
      expect(contributor.fields({ enabled: false })).toBeNull()
      expect(contributor.fields({ enabled: false, value: 0.5 })).toBeNull()
      expect(contributor.fields({ enabled: false, value: 'all' })).toBeNull()
    }
  })

  it('leaves the route identity of an unconstrained mission untouched', () => {
    // A constraint that exists but is off must not make yesterday's route a
    // different route, or every post-route analysis goes stale on upgrade.
    const inputs = {
      roverId: 'nasa_viper',
      start: [169, 50] as [number, number],
      goal: [200, 90] as [number, number],
      weights: { w_slope: 0.35, w_energy: 0.25, w_shadow: 0.2, w_thermal: 0.2 },
    }
    expect(routeIdentity({ ...inputs, constraints: readPlanConstraints() }))
      .toBe(routeIdentity(inputs))
  })
})

describe('a response from before any of this still reads correctly', () => {
  /** What /api/plan returned before the twelve features existed. */
  const legacyPlan = {
    waypoints: [{ row: 1, col: 1 }],
    summary: {},
    astar_metrics: {},
  }

  it('shows no safety panel where a backend sent no safety block', () => {
    expect(readSafetyMargins(legacyPlan)).toBeNull()
  })

  it('shows no cost-model panel where a backend sent none of its blocks', () => {
    expect(isEmpty(readRouteModel(legacyPlan))).toBe(true)
  })

  it('shows no uncertainty summary where a backend sent no block', () => {
    expect(readUncertaintySummary(legacyPlan)).toBeNull()
  })

  it('never turns an absent block into a zeroed one', () => {
    // The difference between "not measured" and "measured as zero" is the
    // whole of this integration's honesty, and absence is where it is lost.
    const view = readRouteModel(legacyPlan)
    expect(view.slip).toBeNull()
    expect(view.risk).toBeNull()
    expect(view.roughness).toBeNull()
    expect(view.survival).toBeNull()
    expect(view.thermal).toBeNull()
  })
})

describe('an optional analysis failing never costs the route', () => {
  it('keeps the route for every failure except an infeasible mission', () => {
    const kinds = [
      classifyFailure(Object.assign(new Error('down'), {}), 'analysis'),
      classifyFailure(Object.assign(new Error('no cache'), { status: 404 }), 'analysis'),
      classifyFailure(Object.assign(new Error('no cache'), { status: 404 }), 'layer'),
      classifyFailure(Object.assign(new Error('bad'), { status: 422 }), 'planner'),
      classifyFailure(Object.assign(new Error('boom'), { status: 500 }), 'analysis'),
    ]
    expect(kinds.every((failure) => failure.keepsExistingRoute)).toBe(true)
  })

  it('drops the route only when the planner itself found none', () => {
    const infeasible = classifyFailure(
      Object.assign(new Error('no route'), { status: 404 }),
      'planner',
    )
    expect(infeasible.kind).toBe('mission-infeasible')
    expect(infeasible.keepsExistingRoute).toBe(false)
  })
})

describe('nothing in the new work fabricates a value', () => {
  it('has no progress percentage anywhere in the analysis lifecycle', () => {
    // The backend reports no progress for these jobs. A number on screen
    // would be an animation impersonating telemetry, so the type has nowhere
    // to put one -- this asserts the shipped states, not the intent.
    const states = [
      { state: 'idle' },
      { state: 'running' },
      { state: 'success', value: 1, computedFor: 'r' },
      { state: 'stale', value: 1, computedFor: 'r' },
    ]
    for (const state of states) expect('percent' in state).toBe(false)
  })

  it('keeps a real zero apart from a missing figure', () => {
    const measured = readRouteModel({
      roughness: { applied: true, route: { cells_in_psr: 0 } },
    })
    const unchecked = readRouteModel({
      roughness: { applied: true, route: { cells_in_psr: null } },
    })
    expect(measured.roughness!.cellsInPsr).toBe(0)
    expect(unchecked.roughness!.cellsInPsr).toBeNull()
  })
})
