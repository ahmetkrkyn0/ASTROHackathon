import { describe, expect, it } from 'vitest'

import type { Waypoint } from '../api'
import { applyLocalDetour } from './localDetourExecution'

function waypoint(step: number, row: number, col: number, elapsed_hours: number, distance_m: number): Waypoint {
  return {
    step, row, col, elapsed_hours, distance_m,
    lon: 0, lat: 0, altitude_m: 0, battery_pct: 100, recharge_count: 0, recharged_this_step: false,
    risk_level: 'LOW', slope_deg: 0, surface_temp_c: -30, shadow_ratio: 0,
    node_cost: 0, step_energy_wh: 0,
  }
}

describe('applyLocalDetour', () => {
  const route = [waypoint(0, 0, 0, 0, 0), waypoint(1, 0, 2, 2 / 3600, 10), waypoint(2, 0, 4, 4 / 3600, 20)]

  it('splices a local path and preserves the global suffix after its rejoin point', () => {
    const result = applyLocalDetour(
      route, 0, 0,
      { current: { row: 0, col: 0 }, waypoints: [{ row: 1, col: 1 }, { row: 0, col: 2 }] },
      5, 0.2,
    )
    expect(result.map((point) => [point.row, point.col])).toEqual([[0, 0], [1, 1], [0, 2], [0, 4]])
    expect(result[2].elapsed_hours).toBeGreaterThan(route[1].elapsed_hours)
    expect(result[3].elapsed_hours).toBeGreaterThan(route[2].elapsed_hours)
    expect(result.map((point) => point.step)).toEqual([0, 1, 2, 3])
  })

  it('refuses a local segment that does not rejoin the immediate global waypoint', () => {
    const result = applyLocalDetour(
      route, 0, 0,
      { current: { row: 0, col: 0 }, waypoints: [{ row: 1, col: 1 }, { row: 2, col: 2 }] },
      5, 0.2,
    )
    expect(result).toEqual(route)
  })
})
