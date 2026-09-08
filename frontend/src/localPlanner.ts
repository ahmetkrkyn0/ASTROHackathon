/**
 * Bounded local obstacle avoidance.
 *
 * This module intentionally knows nothing about the 3-D scene or its rock
 * meshes. Its obstacles must be observations produced by LiDAR perception;
 * keeping that boundary explicit prevents the global-map information leak
 * that the old pre-plan `obstacle_cells` path introduced.
 */

export type LocalPlanDecision = 'FOLLOW' | 'LOCAL_DETOUR' | 'STOP_AND_REPLAN'

export interface LocalPoint {
  x_m: number
  z_m: number
}

export interface ObservedObstacle extends LocalPoint {
  radius_m: number
  confidence: number
  observed_at_s: number
  source: 'lidar'
}

export interface LocalPlanInput {
  pose: LocalPoint
  /** The next reachable point on the global corridor, inside the local horizon. */
  lookahead: LocalPoint
  obstacles: readonly ObservedObstacle[]
  rover_radius_m: number
  safety_margin_m: number
  max_deviation_m: number
  minimum_confidence?: number
}

export interface LocalPlanResult {
  decision: LocalPlanDecision
  /** Empty for FOLLOW; a detour is always followed by the original lookahead. */
  waypoints: LocalPoint[]
  nearest_obstacle_m: number | null
  reason: string
}

const EPSILON = 1e-9

function distance(a: LocalPoint, b: LocalPoint): number {
  return Math.hypot(a.x_m - b.x_m, a.z_m - b.z_m)
}

function distanceToSegment(point: LocalPoint, start: LocalPoint, end: LocalPoint): number {
  const dx = end.x_m - start.x_m
  const dz = end.z_m - start.z_m
  const lengthSquared = dx * dx + dz * dz
  if (lengthSquared < EPSILON) return distance(point, start)
  const t = Math.max(0, Math.min(1, ((point.x_m - start.x_m) * dx + (point.z_m - start.z_m) * dz) / lengthSquared))
  return Math.hypot(point.x_m - (start.x_m + dx * t), point.z_m - (start.z_m + dz * t))
}

function clearSegment(
  start: LocalPoint,
  end: LocalPoint,
  obstacles: readonly ObservedObstacle[],
  clearance: number,
): boolean {
  return obstacles.every((obstacle) => distanceToSegment(obstacle, start, end) >= obstacle.radius_m + clearance)
}

/**
 * Select a short, safe detour around LiDAR-observed discs. This is the
 * initial bounded planner: it never changes the global target and returns a
 * fail-safe stop when no candidate stays inside the allowed corridor band.
 */
export function planLocalDetour(input: LocalPlanInput): LocalPlanResult {
  const minimumConfidence = input.minimum_confidence ?? 0.65
  const obstacles = input.obstacles.filter((obstacle) => obstacle.confidence >= minimumConfidence)
  const nearest = obstacles.reduce<number | null>((best, obstacle) => {
    const candidate = Math.max(0, distance(input.pose, obstacle) - obstacle.radius_m)
    return best === null ? candidate : Math.min(best, candidate)
  }, null)
  const clearance = input.rover_radius_m + input.safety_margin_m

  if (clearSegment(input.pose, input.lookahead, obstacles, clearance)) {
    return {
      decision: 'FOLLOW',
      waypoints: [],
      nearest_obstacle_m: nearest,
      reason: 'LiDAR-observed obstacle does not block the local corridor segment.',
    }
  }

  const dx = input.lookahead.x_m - input.pose.x_m
  const dz = input.lookahead.z_m - input.pose.z_m
  const length = Math.hypot(dx, dz)
  if (length < EPSILON) {
    return {
      decision: 'STOP_AND_REPLAN',
      waypoints: [],
      nearest_obstacle_m: nearest,
      reason: 'Local lookahead is degenerate while an observed obstacle blocks the rover.',
    }
  }

  const normal = { x_m: -dz / length, z_m: dx / length }
  const candidates: LocalPoint[] = []
  for (const obstacle of obstacles) {
    // A waypoint on the inflated disc's side is not enough: the two straight
    // legs would cut through that disc. The extra tangent margin makes each
    // segment clear the inflated obstacle without pretending this simple
    // first version can drive an arc.
    const detourRadius = (obstacle.radius_m + clearance) * 1.25
    for (const side of [-1, 1]) {
      const candidate = {
        x_m: obstacle.x_m + normal.x_m * detourRadius * side,
        z_m: obstacle.z_m + normal.z_m * detourRadius * side,
      }
      if (distanceToSegment(candidate, input.pose, input.lookahead) > input.max_deviation_m + EPSILON) continue
      if (clearSegment(input.pose, candidate, obstacles, clearance) && clearSegment(candidate, input.lookahead, obstacles, clearance)) {
        candidates.push(candidate)
      }
    }
  }

  if (candidates.length === 0) {
    return {
      decision: 'STOP_AND_REPLAN',
      waypoints: [],
      nearest_obstacle_m: nearest,
      reason: 'Observed obstacle blocks the local corridor and no bounded safe detour exists.',
    }
  }

  candidates.sort((a, b) =>
    distance(input.pose, a) + distance(a, input.lookahead)
    - distance(input.pose, b) - distance(b, input.lookahead),
  )
  return {
    decision: 'LOCAL_DETOUR',
    waypoints: [candidates[0], input.lookahead],
    nearest_obstacle_m: nearest,
    reason: 'Bounded detour selected from LiDAR-observed obstacles.',
  }
}
