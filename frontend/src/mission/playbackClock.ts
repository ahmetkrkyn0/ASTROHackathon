import type { Waypoint } from '../api'

/**
 * The mission clock: the pure part of playback, kept out of App so it can be
 * tested without a renderer.
 *
 * The whole point of this module is that ONE number -- elapsed hours on the
 * planner's own timeline -- drives the 2D map, the 3D scene and the transport
 * bar. Before it there were three independent timers (33 ms per waypoint in
 * MapCanvas, 50 ms in the transport bar, and the entire traverse compressed
 * into a fixed 10-45 second window in the 3D view), so the same route
 * finished at three different times and none of those times was the rover's
 * actual speed.
 */

/**
 * Fallback rover speed for the stationary-segment test, used before the
 * profile catalogue has loaded. LPR-1's own v_max; every profile in the
 * catalogue is within a factor of four of it and the test below is a
 * factor-of-five one, so the fallback never changes an answer.
 */
export const NOMINAL_ROVER_SPEED_MS = 0.2

/**
 * Wall-clock seconds a recharge stop is allowed to take on screen.
 *
 * The planner charges real time for recharging (backend/app/simulation.py
 * banks it into elapsed_hours), so at true real time the rover would sit
 * motionless for literal hours. Driving stays at whatever speed the operator
 * chose; only the stops are compressed, and the transport bar says so while
 * it is happening.
 */
export const RECHARGE_STOP_WALL_SECONDS = 4

/**
 * Is this segment a stop rather than a drive?
 *
 * Judged by the speed the two waypoints imply: a segment that covers 5 m in
 * three hours is not the rover crawling, it is the rover parked with its
 * panels up. `recharged_this_step` says a recharge happened somewhere in the
 * step but not how much of the step's elapsed time it took, so the implied
 * speed is the sharper test.
 */
export function isRechargeSegment(
  current: Waypoint,
  next: Waypoint,
  roverSpeedMs: number,
): boolean {
  const spanHours = next.elapsed_hours - current.elapsed_hours
  if (spanHours <= 1e-9) return false
  const spanMetres = Math.max(0, next.distance_m - current.distance_m)
  return spanMetres / (spanHours * 3600) < roverSpeedMs * 0.2
}

/** Index of the last waypoint at or before `hours`. */
function waypointIndexAt(waypoints: Waypoint[], hours: number): number {
  let index = 0
  for (let i = 0; i < waypoints.length; i++) {
    if (waypoints[i].elapsed_hours <= hours) index = i
    else break
  }
  return index
}

/**
 * How fast the mission clock should run right now, in simulated seconds per
 * wall-clock second: the operator's chosen scale on a driving segment, or
 * fast enough to clear a recharge stop in RECHARGE_STOP_WALL_SECONDS.
 */
export function playbackScaleAt(
  waypoints: Waypoint[] | null,
  hours: number,
  roverSpeedMs: number,
  timeScale: number,
): number {
  if (!waypoints || waypoints.length === 0) return timeScale
  const index = waypointIndexAt(waypoints, hours)
  const current = waypoints[index]
  const next = waypoints[index + 1]
  if (!next || !isRechargeSegment(current, next, roverSpeedMs)) return timeScale
  const spanSeconds = (next.elapsed_hours - current.elapsed_hours) * 3600
  return Math.max(timeScale, spanSeconds / RECHARGE_STOP_WALL_SECONDS)
}

/**
 * Advance the clock by one frame.
 *
 * The clamp is the load-bearing part. The scale is a property of the SEGMENT
 * the rover is on, and a recharge stop's boost runs into the thousands, so a
 * single boosted frame can be worth minutes of mission time -- more than a
 * whole 5 m drive step is. Carrying that boost across the segment boundary
 * therefore does not just overshoot slightly, it skips the entire drive that
 * follows the stop: the rover teleports out of the charge. Stopping exactly
 * on the boundary makes the next frame re-read the scale for the segment it
 * is actually on.
 */
export function advancePlaybackHours(
  waypoints: Waypoint[] | null,
  hours: number,
  deltaMs: number,
  roverSpeedMs: number,
  timeScale: number,
): number {
  const scale = playbackScaleAt(waypoints, hours, roverSpeedMs, timeScale)
  const next = hours + (deltaMs / 3_600_000) * scale
  if (!waypoints || waypoints.length === 0) return next
  const boundary = waypoints[waypointIndexAt(waypoints, hours) + 1]?.elapsed_hours
  return boundary !== undefined && next > boundary ? boundary : next
}

export interface PlaybackState {
  /** Waypoint the rover is on or has just left. */
  activeWaypoint: Waypoint | null
  /** Progress 0-1 toward the next waypoint, for smooth interpolation. */
  roverFraction: number
  /** Same waypoint as an index, for the 2D map and the scrubber. */
  stepIndex: number | null
  isRecharging: boolean
  /** Ground speed the planner's own timeline implies here, m/s. */
  groundSpeedMs: number
}

const AT_REST: PlaybackState = {
  activeWaypoint: null,
  roverFraction: 0,
  stepIndex: null,
  isRecharging: false,
  groundSpeedMs: 0,
}

/** Everything derived from the clock, in one pass over the route. */
export function resolvePlaybackState(
  waypoints: Waypoint[] | null | undefined,
  hours: number,
  roverSpeedMs: number,
): PlaybackState {
  if (!waypoints || waypoints.length === 0) return AT_REST
  const index = waypointIndexAt(waypoints, hours)
  const current = waypoints[index]
  const next = waypoints[index + 1]
  if (!next) {
    return {
      activeWaypoint: current,
      roverFraction: 0,
      stepIndex: index,
      isRecharging: false,
      groundSpeedMs: 0,
    }
  }
  const spanHours = next.elapsed_hours - current.elapsed_hours
  const spanMetres = Math.max(0, next.distance_m - current.distance_m)
  return {
    activeWaypoint: current,
    roverFraction:
      spanHours > 1e-9 ? Math.min(1, Math.max(0, (hours - current.elapsed_hours) / spanHours)) : 0,
    stepIndex: index,
    isRecharging: isRechargeSegment(current, next, roverSpeedMs),
    groundSpeedMs: spanHours > 1e-9 ? spanMetres / (spanHours * 3600) : 0,
  }
}

/** Elapsed hours of the waypoint a scrubber index refers to. */
export function hoursForStep(waypoints: Waypoint[] | null, step: number | null): number {
  if (!waypoints || waypoints.length === 0 || step === null) return 0
  const clamped = Math.min(waypoints.length - 1, Math.max(0, step))
  return waypoints[clamped].elapsed_hours
}

/** Index the clock is currently sitting on; the inverse of hoursForStep. */
export function stepForHours(waypoints: Waypoint[] | null, hours: number): number {
  if (!waypoints || waypoints.length === 0) return 0
  return waypointIndexAt(waypoints, hours)
}
