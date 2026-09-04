import * as THREE from 'three'

export const LIDAR_CONFIG = {
  maxRangeM: 60,
  minRangeM: 1.5,
  rangeNoiseSigmaM: 0.02,
  azimuthSteps: 180,
  elevationAnglesDeg: [-16, -14, -12, -10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10, 12, 14],
  scanRateHz: 5,
  terrainStepM: 0.5,
} as const

export interface TerrainField {
  rows: number
  cols: number
  resolutionM: number
  minElevationM: number
  heights: Float32Array
  verticalScale: number
}

export interface RockDescriptor {
  id: string
  x: number
  z: number
  radiusX: number
  radiusY: number
  radiusZ: number
  rotationY: number
  seed: number
}

export interface LidarScanSummary {
  beams: number
  returns: number
  rockReturns: number
  terrainReturns: number
  returnRate: number
  nearestObstacleM: number | null
  detectedRocks: number
}

export interface LidarScanResult {
  positions: Float32Array
  colors: Float32Array
  /** Nearest first-return for every azimuth; used by the animated sweep fan. */
  azimuthEndpoints: Array<THREE.Vector3 | null>
  summary: LidarScanSummary
}

function hash2(a: number, b: number): number {
  let h = Math.imul(a | 0, 0x45d9f3b) ^ Math.imul(b | 0, 0x119de1f3)
  h = Math.imul(h ^ (h >>> 16), 0x45d9f3b)
  return (h ^ (h >>> 16)) >>> 0
}

export function seededRandom(seed: number): () => number {
  let value = seed >>> 0
  return () => {
    value += 0x6d2b79f5
    let t = value
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Bilinear DEM lookup in the same world frame as TerrainCanvas3D. */
export function sampleTerrainHeight(field: TerrainField, x: number, z: number): number | null {
  const width = field.cols * field.resolutionM
  const depth = field.rows * field.resolutionM
  const stepX = width / (field.cols - 1)
  const stepZ = depth / (field.rows - 1)
  const col = (x + width / 2) / stepX
  const row = (z + depth / 2) / stepZ

  if (row < 0 || col < 0 || row > field.rows - 1 || col > field.cols - 1) return null

  const r0 = Math.floor(row)
  const c0 = Math.floor(col)
  const r1 = Math.min(field.rows - 1, r0 + 1)
  const c1 = Math.min(field.cols - 1, c0 + 1)
  const fr = row - r0
  const fc = col - c0
  const values = [
    field.heights[r0 * field.cols + c0],
    field.heights[r0 * field.cols + c1],
    field.heights[r1 * field.cols + c0],
    field.heights[r1 * field.cols + c1],
  ]
  if (values.some((value) => !Number.isFinite(value))) return null

  const north = values[0] * (1 - fc) + values[1] * fc
  const south = values[2] * (1 - fc) + values[3] * fc
  const elevationM = north * (1 - fr) + south * fr
  return (elevationM - field.minElevationM) * field.verticalScale
}

/**
 * Stable metre-scale rocks around a rover. Rock identity is tied to absolute
 * world chunks, so moving the rover does not make obstacles slide around.
 */
export function generateRockField(
  originX: number,
  originZ: number,
  radiusM = LIDAR_CONFIG.maxRangeM + 8,
): RockDescriptor[] {
  const chunkM = 18
  const minChunkX = Math.floor((originX - radiusM) / chunkM)
  const maxChunkX = Math.floor((originX + radiusM) / chunkM)
  const minChunkZ = Math.floor((originZ - radiusM) / chunkM)
  const maxChunkZ = Math.floor((originZ + radiusM) / chunkM)
  const rocks: RockDescriptor[] = []

  for (let cz = minChunkZ; cz <= maxChunkZ; cz++) {
    for (let cx = minChunkX; cx <= maxChunkX; cx++) {
      const seed = hash2(cx, cz)
      const random = seededRandom(seed)
      const count = random() < 0.36 ? 1 : 2
      for (let i = 0; i < count; i++) {
        const x = (cx + 0.12 + random() * 0.76) * chunkM
        const z = (cz + 0.12 + random() * 0.76) * chunkM
        const distance = Math.hypot(x - originX, z - originZ)
        if (distance > radiusM || distance < 4.5) continue

        // A long-tailed size distribution: mostly cobbles, with occasional
        // boulders large enough to be a genuine mobility hazard.
        const size = 0.28 + Math.pow(random(), 2.35) * 1.9
        rocks.push({
          id: `${cx}:${cz}:${i}`,
          x,
          z,
          radiusX: size * (0.72 + random() * 0.48),
          radiusY: size * (0.58 + random() * 0.58),
          radiusZ: size * (0.72 + random() * 0.48),
          rotationY: random() * Math.PI * 2,
          seed: hash2(seed, i + 1),
        })
      }
    }
  }
  return rocks
}

function firstTerrainReturn(
  origin: THREE.Vector3,
  direction: THREE.Vector3,
  field: TerrainField,
): number | null {
  let previousDistance = LIDAR_CONFIG.minRangeM
  let previousClearance: number | null = null

  for (
    let distance = LIDAR_CONFIG.minRangeM;
    distance <= LIDAR_CONFIG.maxRangeM;
    distance += LIDAR_CONFIG.terrainStepM
  ) {
    const x = origin.x + direction.x * distance
    const z = origin.z + direction.z * distance
    const groundY = sampleTerrainHeight(field, x, z)
    if (groundY === null) return null
    const beamY = origin.y + direction.y * distance
    const clearance = beamY - groundY
    if (clearance <= 0) {
      if (previousClearance !== null && previousClearance > 0) {
        const crossing = previousClearance / (previousClearance - clearance)
        return THREE.MathUtils.lerp(previousDistance, distance, crossing)
      }
      return distance
    }
    previousDistance = distance
    previousClearance = clearance
  }
  return null
}

/**
 * 360-degree multi-channel first-return scan. Rocks are intersected against
 * their real triangle meshes; the large DEM uses a 0.5 m height-field march so
 * a 500k-triangle raycast is not repeated thousands of times per revolution.
 */
export function simulateLidarScan(
  origin: THREE.Vector3,
  terrain: TerrainField,
  rockMeshes: THREE.Mesh[],
  scanSeed = 1,
): LidarScanResult {
  const positions: number[] = []
  const colors: number[] = []
  const azimuthEndpoints: Array<THREE.Vector3 | null> = []
  const raycaster = new THREE.Raycaster()
  raycaster.near = LIDAR_CONFIG.minRangeM
  raycaster.far = LIDAR_CONFIG.maxRangeM
  const random = seededRandom(scanSeed)
  const detectedRockIds = new Set<string>()
  let rockReturns = 0
  let terrainReturns = 0
  let nearestObstacleM: number | null = null

  for (let azimuthIndex = 0; azimuthIndex < LIDAR_CONFIG.azimuthSteps; azimuthIndex++) {
    const azimuth = (azimuthIndex / LIDAR_CONFIG.azimuthSteps) * Math.PI * 2
    let nearestForAzimuth: THREE.Vector3 | null = null
    let nearestForAzimuthDistance = Number.POSITIVE_INFINITY

    for (const elevationDeg of LIDAR_CONFIG.elevationAnglesDeg) {
      const elevation = THREE.MathUtils.degToRad(elevationDeg)
      const direction = new THREE.Vector3(
        Math.sin(azimuth) * Math.cos(elevation),
        Math.sin(elevation),
        -Math.cos(azimuth) * Math.cos(elevation),
      ).normalize()

      raycaster.set(origin, direction)
      const rockHit = raycaster.intersectObjects(rockMeshes, false)[0]
      const terrainDistance = firstTerrainReturn(origin, direction, terrain)
      const rockDistance = rockHit?.distance ?? Number.POSITIVE_INFINITY
      const groundDistance = terrainDistance ?? Number.POSITIVE_INFINITY
      const rawDistance = Math.min(rockDistance, groundDistance)
      if (!Number.isFinite(rawDistance)) continue

      // No atmosphere means no fog attenuation. Remaining missed returns are
      // dominated here by range, grazing incidence and dark regolith albedo.
      const dropoutProbability = 0.008 + 0.055 * Math.pow(rawDistance / LIDAR_CONFIG.maxRangeM, 2)
      if (random() < dropoutProbability) continue

      // Box-Muller range noise, sigma 2 cm, applied along the measured beam.
      const gaussian = Math.sqrt(-2 * Math.log(Math.max(random(), 1e-9))) * Math.cos(2 * Math.PI * random())
      const measuredDistance = THREE.MathUtils.clamp(
        rawDistance + gaussian * LIDAR_CONFIG.rangeNoiseSigmaM,
        LIDAR_CONFIG.minRangeM,
        LIDAR_CONFIG.maxRangeM,
      )
      const point = origin.clone().addScaledVector(direction, measuredDistance)
      positions.push(point.x, point.y, point.z)

      const rangeT = measuredDistance / LIDAR_CONFIG.maxRangeM
      if (rockDistance < groundDistance) {
        rockReturns++
        const rockId = String(rockHit.object.userData.lidarRockId ?? rockHit.object.uuid)
        detectedRockIds.add(rockId)
        nearestObstacleM = nearestObstacleM === null
          ? measuredDistance
          : Math.min(nearestObstacleM, measuredDistance)
        // Hazard returns are amber/red; terrain remains cyan-blue.
        colors.push(1, 0.34 + 0.38 * rangeT, 0.08)
      } else {
        terrainReturns++
        colors.push(0.1 + 0.18 * rangeT, 0.95 - 0.38 * rangeT, 1)
      }

      if (measuredDistance < nearestForAzimuthDistance) {
        nearestForAzimuth = point
        nearestForAzimuthDistance = measuredDistance
      }
    }
    azimuthEndpoints.push(nearestForAzimuth)
  }

  const beams = LIDAR_CONFIG.azimuthSteps * LIDAR_CONFIG.elevationAnglesDeg.length
  const returns = positions.length / 3
  return {
    positions: new Float32Array(positions),
    colors: new Float32Array(colors),
    azimuthEndpoints,
    summary: {
      beams,
      returns,
      rockReturns,
      terrainReturns,
      returnRate: beams > 0 ? returns / beams : 0,
      nearestObstacleM,
      detectedRocks: detectedRockIds.size,
    },
  }
}
