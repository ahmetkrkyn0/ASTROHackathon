import { describe, expect, it } from 'vitest'
import type { Waypoint } from '../api'
import {
  advancePlaybackHours,
  hoursForStep,
  isRechargeSegment,
  NOMINAL_ROVER_SPEED_MS,
  playbackScaleAt,
  RECHARGE_STOP_WALL_SECONDS,
  resolvePlaybackState,
  stepForHours,
} from './playbackClock'

/** A waypoint with only the fields the clock reads; the rest is filler. */
function waypoint(step: number, elapsedHours: number, distanceM: number): Waypoint {
  return {
    step,
    row: 0,
    col: step,
    lon: 0,
    lat: 0,
    altitude_m: 0,
    battery_pct: 100,
    recharge_count: 0,
    recharged_this_step: false,
    risk_level: 'LOW',
    slope_deg: 0,
    surface_temp_c: -80,
    shadow_ratio: 0,
    node_cost: 1,
    elapsed_hours: elapsedHours,
    distance_m: distanceM,
    step_energy_wh: 0,
  }
}

/**
 * A straight drive at exactly the rover's top speed: 5 m grid steps, which
 * at 0.2 m/s take 25 s each.
 */
function straightDrive(steps = 5): Waypoint[] {
  const secondsPerStep = 5 / NOMINAL_ROVER_SPEED_MS
  return Array.from({ length: steps }, (_, i) =>
    waypoint(i, (i * secondsPerStep) / 3600, i * 5),
  )
}

describe('isRechargeSegment', () => {
  it('does not mistake a normal drive step for a stop', () => {
    const [a, b] = straightDrive(2)
    expect(isRechargeSegment(a, b, NOMINAL_ROVER_SPEED_MS)).toBe(false)
  })

  it('recognises a segment that covers 5 m in three hours', () => {
    const a = waypoint(0, 0, 0)
    const b = waypoint(1, 3, 5)
    expect(isRechargeSegment(a, b, NOMINAL_ROVER_SPEED_MS)).toBe(true)
  })

  it('ignores a zero-length span rather than dividing by it', () => {
    expect(isRechargeSegment(waypoint(0, 1, 10), waypoint(1, 1, 10), NOMINAL_ROVER_SPEED_MS)).toBe(
      false,
    )
  })
})

describe('playbackScaleAt', () => {
  it('runs at exactly the chosen scale while driving', () => {
    const route = straightDrive()
    expect(playbackScaleAt(route, 0.001, NOMINAL_ROVER_SPEED_MS, 1)).toBe(1)
    expect(playbackScaleAt(route, 0.001, NOMINAL_ROVER_SPEED_MS, 60)).toBe(60)
  })

  it('clears a recharge stop in the budgeted wall-clock time', () => {
    // 5 m of ground in 3 hours: a stop, not a crawl.
    const route = [waypoint(0, 0, 0), waypoint(1, 3, 5), waypoint(2, 3.01, 10)]
    const scale = playbackScaleAt(route, 0.5, NOMINAL_ROVER_SPEED_MS, 1)
    const wallSeconds = (3 * 3600) / scale
    expect(wallSeconds).toBeCloseTo(RECHARGE_STOP_WALL_SECONDS, 6)
  })

  it('never slows a stop down below the chosen scale', () => {
    // A short stop whose natural boost is under 300x must still run at 300x.
    const route = [waypoint(0, 0, 0), waypoint(1, 0.1, 1), waypoint(2, 0.11, 6)]
    expect(playbackScaleAt(route, 0.05, NOMINAL_ROVER_SPEED_MS, 300)).toBe(300)
  })

  it('is the plain scale with no route loaded', () => {
    expect(playbackScaleAt(null, 0, NOMINAL_ROVER_SPEED_MS, 10)).toBe(10)
    expect(playbackScaleAt([], 0, NOMINAL_ROVER_SPEED_MS, 10)).toBe(10)
  })
})

describe('resolvePlaybackState', () => {
  it('reports the rover moving at the speed the planner charged for', () => {
    const route = straightDrive()
    const state = resolvePlaybackState(route, 0.001, NOMINAL_ROVER_SPEED_MS)
    expect(state.groundSpeedMs).toBeCloseTo(NOMINAL_ROVER_SPEED_MS, 6)
    expect(state.isRecharging).toBe(false)
  })

  it('interpolates between waypoints instead of snapping to them', () => {
    const route = straightDrive()
    const halfway = route[1].elapsed_hours / 2
    const state = resolvePlaybackState(route, halfway, NOMINAL_ROVER_SPEED_MS)
    expect(state.stepIndex).toBe(0)
    expect(state.roverFraction).toBeCloseTo(0.5, 6)
  })

  it('holds at the final waypoint once the route is finished', () => {
    const route = straightDrive()
    const state = resolvePlaybackState(route, 999, NOMINAL_ROVER_SPEED_MS)
    expect(state.stepIndex).toBe(route.length - 1)
    expect(state.roverFraction).toBe(0)
  })

  it('is at rest with no route', () => {
    expect(resolvePlaybackState(null, 5, NOMINAL_ROVER_SPEED_MS).activeWaypoint).toBeNull()
  })
})

describe('the clock as a whole', () => {
  /**
   * The headline claim: at 1x, the wall-clock time the drive takes on screen
   * IS the mission time the planner charged for. Stepping the same arithmetic
   * the animation frame loop runs, at a 60 Hz frame budget.
   */
  it('takes as long to play back at 1x as the traverse takes to drive', () => {
    const route = straightDrive(9) // 8 steps x 25 s = 200 s of driving
    const totalHours = route[route.length - 1].elapsed_hours
    let hours = 0
    let wallMs = 0
    const frameMs = 1000 / 60
    while (hours < totalHours && wallMs < 10 * 60 * 1000) {
      hours = advancePlaybackHours(route, hours, frameMs, NOMINAL_ROVER_SPEED_MS, 1)
      wallMs += frameMs
    }
    expect(wallMs / 1000).toBeCloseTo(totalHours * 3600, 0)
    expect(wallMs / 1000).toBeGreaterThan(199)
  })

  it('spends its wall-clock time driving, not waiting out a recharge', () => {
    // 100 s of driving with a 5-hour recharge stop in the middle of it.
    const route = [
      waypoint(0, 0, 0),
      waypoint(1, 50 / 3600, 10),
      waypoint(2, 50 / 3600 + 5, 15),
      waypoint(3, 100 / 3600 + 5, 25),
    ]
    const totalHours = route[route.length - 1].elapsed_hours
    let hours = 0
    let wallMs = 0
    const frameMs = 1000 / 60
    while (hours < totalHours && wallMs < 10 * 60 * 1000) {
      hours = advancePlaybackHours(route, hours, frameMs, NOMINAL_ROVER_SPEED_MS, 1)
      wallMs += frameMs
    }
    // 100 s of driving at real time, plus the stop's fixed budget -- not the
    // five hours the stop actually takes.
    expect(wallMs / 1000).toBeGreaterThan(100)
    expect(wallMs / 1000).toBeLessThan(100 + RECHARGE_STOP_WALL_SECONDS + 2)
  })
})

describe('scrubbing', () => {
  it('round-trips a waypoint index through the clock', () => {
    const route = straightDrive()
    for (let step = 0; step < route.length; step++) {
      expect(stepForHours(route, hoursForStep(route, step))).toBe(step)
    }
  })

  it('clamps out-of-range and null seeks instead of leaving the timeline', () => {
    const route = straightDrive()
    expect(hoursForStep(route, -5)).toBe(route[0].elapsed_hours)
    expect(hoursForStep(route, 999)).toBe(route[route.length - 1].elapsed_hours)
    expect(hoursForStep(route, null)).toBe(0)
  })
})

describe('advancePlaybackHours', () => {
  it('never carries one segments scale across into the next', () => {
    // A 5-hour stop followed by a 50 s drive. The stop's boost is worth
    // minutes of mission time per frame -- more than the whole drive -- so
    // without the clamp one frame swallows the drive and the rover teleports.
    const route = [
      waypoint(0, 0, 0),
      waypoint(1, 5, 5),
      waypoint(2, 5 + 50 / 3600, 15),
    ]
    let hours = 0.001
    // One frame from inside the stop cannot land past the stop's own end.
    hours = advancePlaybackHours(route, hours, 1000, NOMINAL_ROVER_SPEED_MS, 1)
    expect(hours).toBeLessThanOrEqual(route[1].elapsed_hours)
  })

  it('is a plain scaled advance with no route loaded', () => {
    expect(advancePlaybackHours(null, 0, 3_600_000, NOMINAL_ROVER_SPEED_MS, 1)).toBeCloseTo(1, 9)
  })
})
