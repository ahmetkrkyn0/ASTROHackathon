import { describe, expect, it } from 'vitest'

import { planLocalDetour } from './localPlanner'

const BASE_INPUT = {
  pose: { x_m: 0, z_m: 0 },
  lookahead: { x_m: 10, z_m: 0 },
  rover_radius_m: 0.5,
  safety_margin_m: 0.5,
  max_deviation_m: 4,
} as const

describe('planLocalDetour', () => {
  it('follows the global corridor when no LiDAR observation blocks it', () => {
    const result = planLocalDetour({ ...BASE_INPUT, obstacles: [] })
    expect(result.decision).toBe('FOLLOW')
    expect(result.waypoints).toEqual([])
  })

  it('uses a bounded detour only after a confident LiDAR observation blocks the corridor', () => {
    const result = planLocalDetour({
      ...BASE_INPUT,
      obstacles: [{ x_m: 5, z_m: 0, radius_m: 0.7, confidence: 0.9, observed_at_s: 1, source: 'lidar' }],
    })
    expect(result.decision).toBe('LOCAL_DETOUR')
    expect(result.waypoints).toHaveLength(2)
    expect(Math.abs(result.waypoints[0].z_m)).toBeGreaterThanOrEqual(1.7)
  })

  it('does not react to a low-confidence single observation', () => {
    const result = planLocalDetour({
      ...BASE_INPUT,
      obstacles: [{ x_m: 5, z_m: 0, radius_m: 1, confidence: 0.4, observed_at_s: 1, source: 'lidar' }],
    })
    expect(result.decision).toBe('FOLLOW')
  })

  it('stops and requests a replan when every bounded detour is closed', () => {
    const result = planLocalDetour({
      ...BASE_INPUT,
      max_deviation_m: 0.5,
      obstacles: [{ x_m: 5, z_m: 0, radius_m: 1, confidence: 1, observed_at_s: 1, source: 'lidar' }],
    })
    expect(result.decision).toBe('STOP_AND_REPLAN')
    expect(result.waypoints).toEqual([])
  })
})
