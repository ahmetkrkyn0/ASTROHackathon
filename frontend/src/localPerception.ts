import type { LidarScanResult } from './lidarSimulation'
import type { LocalPoint, ObservedObstacle } from './localPlanner'

export type OccupancyCell = 'unknown' | 'free' | 'occupied'

export interface LocalOccupancyGrid {
  origin: LocalPoint
  resolution_m: number
  width: number
  height: number
  cells: OccupancyCell[]
}

interface ObstacleCluster {
  x_m: number
  z_m: number
  count: number
  max_radius_m: number
}

const MIN_RADIUS_M = 0.3
const MAX_RADIUS_M = 2.5

/**
 * Converts only LiDAR-classified first returns into obstacle hypotheses.
 * No rock ID, mesh descriptor, or world map is accepted by this function.
 */
export function observeObstaclesFromLidar(
  scan: LidarScanResult,
  observedAtS: number,
  clusterRadiusM = 1.25,
): ObservedObstacle[] {
  if (!(clusterRadiusM > 0)) throw new Error('clusterRadiusM must be positive')
  const clusters: ObstacleCluster[] = []
  for (let index = 0; index < scan.obstacleReturns.length; index += 3) {
    const x_m = scan.obstacleReturns[index]
    const z_m = scan.obstacleReturns[index + 2]
    let cluster = clusters.find((candidate) => Math.hypot(candidate.x_m - x_m, candidate.z_m - z_m) <= clusterRadiusM)
    if (!cluster) {
      cluster = { x_m, z_m, count: 0, max_radius_m: 0 }
      clusters.push(cluster)
    }
    const previousCount = cluster.count
    cluster.count += 1
    cluster.x_m = (cluster.x_m * previousCount + x_m) / cluster.count
    cluster.z_m = (cluster.z_m * previousCount + z_m) / cluster.count
    cluster.max_radius_m = Math.max(cluster.max_radius_m, Math.hypot(cluster.x_m - x_m, cluster.z_m - z_m))
  }

  return clusters.map((cluster) => ({
    x_m: cluster.x_m,
    z_m: cluster.z_m,
    // A first-return cloud observes only the facing surface, so include a
    // conservative footprint rather than reporting a false point obstacle.
    radius_m: Math.min(MAX_RADIUS_M, Math.max(MIN_RADIUS_M, cluster.max_radius_m + 0.3)),
    confidence: Math.min(1, cluster.count / 4),
    observed_at_s: observedAtS,
    source: 'lidar',
  }))
}

function cellIndex(grid: LocalOccupancyGrid, x_m: number, z_m: number): number | null {
  const col = Math.floor((x_m - grid.origin.x_m) / grid.resolution_m)
  const row = Math.floor((z_m - grid.origin.z_m) / grid.resolution_m)
  if (row < 0 || col < 0 || row >= grid.height || col >= grid.width) return null
  return row * grid.width + col
}

function markFreeRay(grid: LocalOccupancyGrid, origin: LocalPoint, obstacle: ObservedObstacle): void {
  const distance = Math.hypot(obstacle.x_m - origin.x_m, obstacle.z_m - origin.z_m)
  const steps = Math.ceil(Math.max(0, distance - obstacle.radius_m) / (grid.resolution_m * 0.5))
  for (let step = 0; step <= steps; step++) {
    const fraction = steps === 0 ? 0 : step / steps
    const x_m = origin.x_m + (obstacle.x_m - origin.x_m) * fraction
    const z_m = origin.z_m + (obstacle.z_m - origin.z_m) * fraction
    const index = cellIndex(grid, x_m, z_m)
    if (index !== null && grid.cells[index] === 'unknown') grid.cells[index] = 'free'
  }
}

/** Builds a rover-centred, three-state occupancy grid from current observations. */
export function buildLocalOccupancyGrid(
  rover: LocalPoint,
  obstacles: readonly ObservedObstacle[],
  rangeM = 20,
  resolutionM = 0.5,
): LocalOccupancyGrid {
  if (!(rangeM > 0) || !(resolutionM > 0)) throw new Error('rangeM and resolutionM must be positive')
  const width = Math.ceil((rangeM * 2) / resolutionM)
  const grid: LocalOccupancyGrid = {
    origin: { x_m: rover.x_m - rangeM, z_m: rover.z_m - rangeM },
    resolution_m: resolutionM,
    width,
    height: width,
    cells: new Array<OccupancyCell>(width * width).fill('unknown'),
  }
  for (const obstacle of obstacles) {
    markFreeRay(grid, rover, obstacle)
    const radiusCells = Math.ceil(obstacle.radius_m / resolutionM)
    const centre = cellIndex(grid, obstacle.x_m, obstacle.z_m)
    if (centre === null) continue
    const centreRow = Math.floor(centre / width)
    const centreCol = centre % width
    for (let dr = -radiusCells; dr <= radiusCells; dr++) {
      for (let dc = -radiusCells; dc <= radiusCells; dc++) {
        if (Math.hypot(dr * resolutionM, dc * resolutionM) > obstacle.radius_m) continue
        const row = centreRow + dr
        const col = centreCol + dc
        if (row >= 0 && col >= 0 && row < width && col < width) grid.cells[row * width + col] = 'occupied'
      }
    }
  }
  return grid
}
