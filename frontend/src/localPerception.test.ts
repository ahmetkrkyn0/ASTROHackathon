import { describe, expect, it } from 'vitest'

import { buildLocalOccupancyGrid, observeObstaclesFromLidar } from './localPerception'
import type { LidarScanResult } from './lidarSimulation'

function scan(points: number[]): LidarScanResult {
  return {
    positions: new Float32Array(),
    colors: new Float32Array(),
    obstacleReturns: new Float32Array(points),
    azimuthEndpoints: [],
    summary: { beams: 0, returns: 0, rockReturns: points.length / 3, terrainReturns: 0, returnRate: 0, nearestObstacleM: null, detectedRocks: 0 },
  }
}

describe('local LiDAR perception', () => {
  it('clusters first returns without consuming a rock ID or scene descriptor', () => {
    const observed = observeObstaclesFromLidar(scan([5, 1, 0, 5.2, 1.1, 0.2, 4.9, 1.1, -0.1, 5.1, 1, 0]), 12)
    expect(observed).toHaveLength(1)
    expect(observed[0].source).toBe('lidar')
    expect(observed[0].confidence).toBe(1)
    expect(observed[0].x_m).toBeCloseTo(5.05, 1)
  })

  it('marks measured free space and the observed footprint in a local occupancy grid', () => {
    const [obstacle] = observeObstaclesFromLidar(scan([4, 1, 0, 4.1, 1, 0.1, 3.9, 1, 0]), 2)
    const grid = buildLocalOccupancyGrid({ x_m: 0, z_m: 0 }, [obstacle], 6, 0.5)
    expect(grid.cells.filter((cell) => cell === 'occupied').length).toBeGreaterThan(0)
    expect(grid.cells.filter((cell) => cell === 'free').length).toBeGreaterThan(0)
  })
})
