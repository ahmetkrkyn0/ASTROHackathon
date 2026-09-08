import type { Waypoint } from '../api'

export interface GridPoint {
  row: number
  col: number
}

/** A locally observed-and-approved path segment that rejoins the global route. */
export interface LocalDetourCommand {
  current: GridPoint
  /** Includes the final global-route rejoin point. */
  waypoints: GridPoint[]
}

function gridDistanceM(a: GridPoint, b: GridPoint, resolutionM: number): number {
  return Math.hypot(a.row - b.row, a.col - b.col) * resolutionM
}

function sameCell(a: GridPoint, b: GridPoint): boolean {
  return a.row === b.row && a.col === b.col
}

/**
 * Replaces the remaining part of the active global segment with a short
 * LiDAR-local detour. The backend plan remains untouched; this array is an
 * execution trace only, so downstream UI can follow what the rover actually
 * drove without claiming its energy/risk totals were re-simulated.
 */
export function applyLocalDetour(
  route: readonly Waypoint[],
  activeIndex: number,
  currentHours: number,
  command: LocalDetourCommand,
  resolutionM: number,
  speedMs: number,
): Waypoint[] {
  if (
    route.length < 2 || activeIndex < 0 || activeIndex >= route.length - 1
    || !(resolutionM > 0) || !(speedMs > 0) || command.waypoints.length < 2
  ) return [...route]

  const resume = route[activeIndex + 1]
  const requestedResume = command.waypoints[command.waypoints.length - 1]
  // The local planner must explicitly return to the next global waypoint.
  // Do not splice an unbounded local path into an unrelated global suffix.
  if (!sameCell(resume, requestedResume)) return [...route]

  const active = route[activeIndex]
  const clampedHours = Math.max(active.elapsed_hours, Math.min(currentHours, resume.elapsed_hours))
  const baseSpan = Math.max(1e-9, resume.elapsed_hours - active.elapsed_hours)
  const progress = (clampedHours - active.elapsed_hours) / baseSpan
  const currentDistance = active.distance_m + (resume.distance_m - active.distance_m) * progress
  const prefix = route.slice(0, activeIndex)
  const execution: Waypoint[] = [
    {
      ...active,
      row: command.current.row,
      col: command.current.col,
      elapsed_hours: clampedHours,
      distance_m: currentDistance,
      step_energy_wh: 0,
    },
  ]

  let previous: GridPoint = command.current
  let elapsed = clampedHours
  let distance = currentDistance
  for (const point of command.waypoints) {
    if (sameCell(previous, point)) continue
    const segmentM = gridDistanceM(previous, point, resolutionM)
    elapsed += segmentM / speedMs / 3600
    distance += segmentM
    const template = sameCell(point, resume) ? resume : active
    execution.push({
      ...template,
      row: point.row,
      col: point.col,
      elapsed_hours: elapsed,
      distance_m: distance,
      step_energy_wh: 0,
    })
    previous = point
  }
  if (!sameCell(previous, resume)) return [...route]

  const elapsedShift = elapsed - resume.elapsed_hours
  const distanceShift = distance - resume.distance_m
  const suffix = route.slice(activeIndex + 2).map((waypoint) => ({
    ...waypoint,
    elapsed_hours: waypoint.elapsed_hours + elapsedShift,
    distance_m: waypoint.distance_m + distanceShift,
  }))
  return [...prefix, ...execution, ...suffix].map((waypoint, step) => ({ ...waypoint, step }))
}
