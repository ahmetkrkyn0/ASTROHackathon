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

/**
 * Classic "jet" colour ramp (blue -> cyan -> green -> yellow -> red),
 * the height-encoding every point-cloud tool (CloudCompare, RViz, PDAL)
 * defaults to. Point-cloud viewers colour by elevation, not by category, so
 * an obstacle reads as a hot (red/yellow) local peak against a cool ground
 * plane the same way it would in one of those tools -- no separate hazard
 * hue needed, and no surprise when this output sits next to a real one.
 */
function jetColor(t: number): [number, number, number] {
  const x = THREE.MathUtils.clamp(t, 0, 1)
  const r = THREE.MathUtils.clamp(1.5 - Math.abs(4 * x - 3), 0, 1)
  const g = THREE.MathUtils.clamp(1.5 - Math.abs(4 * x - 2), 0, 1)
  const b = THREE.MathUtils.clamp(1.5 - Math.abs(4 * x - 1), 0, 1)
  return [r, g, b]
}

/**
 * A raw hit distance becomes what the sensor actually reports: dropped
 * entirely (no atmosphere means no fog, so misses here are range, grazing
 * incidence and dark regolith albedo instead), or jittered by 2 cm range
 * noise. Shared by both return sources below so a backend-sourced terrain
 * point and a locally-raycast rock point carry the same sensor character.
 */
function applySensorNoise(rawDistance: number, random: () => number): number | null {
  const dropoutProbability = 0.008 + 0.055 * Math.pow(rawDistance / LIDAR_CONFIG.maxRangeM, 2)
  if (random() < dropoutProbability) return null
  const gaussian = Math.sqrt(-2 * Math.log(Math.max(random(), 1e-9))) * Math.cos(2 * Math.PI * random())
  return THREE.MathUtils.clamp(
    rawDistance + gaussian * LIDAR_CONFIG.rangeNoiseSigmaM,
    LIDAR_CONFIG.minRangeM,
    LIDAR_CONFIG.maxRangeM,
  )
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
  const azimuthEndpoints: Array<THREE.Vector3 | null> = []
  const raycaster = new THREE.Raycaster()
  raycaster.near = LIDAR_CONFIG.minRangeM
  raycaster.far = LIDAR_CONFIG.maxRangeM
  const random = seededRandom(scanSeed)
  const detectedRockIds = new Set<string>()
  let rockReturns = 0
  let terrainReturns = 0
  let nearestObstacleM: number | null = null
  // Height range of this scan, tracked while walking beams so the jet ramp
  // below can be applied in a second, cheap pass once it is known -- an
  // obstacle is not "coloured red" by category, it just IS the local high
  // point, and that is what the ramp needs the true min/max to show.
  let minY = Number.POSITIVE_INFINITY
  let maxY = Number.NEGATIVE_INFINITY

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

      const measuredDistance = applySensorNoise(rawDistance, random)
      if (measuredDistance === null) continue
      const point = origin.clone().addScaledVector(direction, measuredDistance)
      positions.push(point.x, point.y, point.z)
      if (point.y < minY) minY = point.y
      if (point.y > maxY) maxY = point.y

      if (rockDistance < groundDistance) {
        rockReturns++
        const rockId = String(rockHit.object.userData.lidarRockId ?? rockHit.object.uuid)
        detectedRockIds.add(rockId)
        nearestObstacleM = nearestObstacleM === null
          ? measuredDistance
          : Math.min(nearestObstacleM, measuredDistance)
      } else {
        terrainReturns++
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
  // A flat scan (minY === maxY, e.g. a single beam or perfectly level ground)
  // divides by zero -- pin the whole cloud to the ramp's midpoint instead.
  const ySpan = maxY - minY
  const colors = new Float32Array(positions.length)
  for (let i = 0; i < returns; i++) {
    const y = positions[i * 3 + 1]
    const t = ySpan > 1e-6 ? (y - minY) / ySpan : 0.5
    const [r, g, b] = jetColor(t)
    colors[i * 3] = r
    colors[i * 3 + 1] = g
    colors[i * 3 + 2] = b
  }
  return {
    positions: new Float32Array(positions),
    colors,
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

export interface BackendLidarScanResponse {
  origin: { row: number; col: number; sensor_height_m: number }
  resolution_m: number
  max_range_m: number
  n_azimuth: number
  elevation_angles_deg: number[]
  /** (east_m, north_m, up_m) per return, relative to the sensor origin. */
  points: [number, number, number][]
}

/**
 * The real thing: backend/app/main.py's /api/lidar-scan runs
 * lunapath/src/virtual_lidar.py's ray march over the actual loaded DEM --
 * the same geometry app.horizon uses for shadow computation -- rather than
 * a second, independent reimplementation living only in the browser.
 * Passing this scene's own LIDAR_CONFIG channel spec (azimuth count,
 * elevation angles, range) keeps the beam grid identical to what
 * buildLidarScanFromBackend below expects to merge rock returns into.
 */
export async function fetchBackendLidarScan(
  row: number,
  col: number,
  sensorHeightM: number,
  signal?: AbortSignal,
): Promise<BackendLidarScanResponse> {
  const params = new URLSearchParams({
    row: String(row),
    col: String(col),
    sensor_height_m: String(sensorHeightM),
    n_azimuth: String(LIDAR_CONFIG.azimuthSteps),
    max_range_m: String(LIDAR_CONFIG.maxRangeM),
    elevation_angles_deg: LIDAR_CONFIG.elevationAnglesDeg.join(','),
  })
  const response = await fetch(`/api/lidar-scan?${params.toString()}`, { signal })
  if (!response.ok) throw new Error(`/api/lidar-scan -> ${response.status}`)
  return response.json() as Promise<BackendLidarScanResponse>
}

/**
 * Merge the backend's real terrain ray-march with a LOCAL rock-only pass.
 * The backend's 5 m/px DEM cannot resolve metre-scale rocks (stated in
 * virtual_lidar.py's own docstring) -- they exist only as this scene's
 * meshes, which the backend has no way to see -- so this is not a
 * duplicate of the backend scan, it is the other half of the same one.
 */
export function buildLidarScanFromBackend(
  origin: THREE.Vector3,
  verticalScale: number,
  backendPoints: ReadonlyArray<readonly [number, number, number]>,
  rockMeshes: THREE.Mesh[],
  scanSeed = 1,
): LidarScanResult {
  const positions: number[] = []
  const random = seededRandom(scanSeed)
  const detectedRockIds = new Set<string>()
  let rockReturns = 0
  let terrainReturns = 0
  let nearestObstacleM: number | null = null
  let minY = Number.POSITIVE_INFINITY
  let maxY = Number.NEGATIVE_INFINITY
  // Nearest return per azimuth bucket, across BOTH sources, for the
  // animated sweep fan -- a rock closer than the terrain at that azimuth
  // must win here exactly as it would in the single-pass scan above.
  const nearestByAzimuth = new Map<number, { point: THREE.Vector3; distance: number }>()

  const record = (azimuthIndex: number, point: THREE.Vector3, distance: number) => {
    positions.push(point.x, point.y, point.z)
    if (point.y < minY) minY = point.y
    if (point.y > maxY) maxY = point.y
    const current = nearestByAzimuth.get(azimuthIndex)
    if (!current || distance < current.distance) {
      nearestByAzimuth.set(azimuthIndex, { point, distance })
    }
  }

  for (const [eastM, northM, upM] of backendPoints) {
    // hypot(east, north) recovers the backend's own horizontal-range step
    // regardless of elevation angle, so atan2 reconstructs the exact
    // azimuth bucket it was cast at -- east = sin(az)*r, north = cos(az)*r.
    const rawDistance = Math.hypot(eastM, northM, upM)
    if (rawDistance < LIDAR_CONFIG.minRangeM || rawDistance > LIDAR_CONFIG.maxRangeM) continue
    const measuredDistance = applySensorNoise(rawDistance, random)
    if (measuredDistance === null) continue
    const scale = measuredDistance / rawDistance
    const point = new THREE.Vector3(
      origin.x + eastM * scale,
      origin.y + upM * verticalScale * scale,
      origin.z - northM * scale,
    )
    terrainReturns++
    const azimuth = Math.atan2(eastM, northM)
    const azimuthTurns = (azimuth < 0 ? azimuth + Math.PI * 2 : azimuth) / (Math.PI * 2)
    const azimuthIndex = Math.round(azimuthTurns * LIDAR_CONFIG.azimuthSteps) % LIDAR_CONFIG.azimuthSteps
    record(azimuthIndex, point, measuredDistance)
  }

  const raycaster = new THREE.Raycaster()
  raycaster.near = LIDAR_CONFIG.minRangeM
  raycaster.far = LIDAR_CONFIG.maxRangeM
  for (let azimuthIndex = 0; azimuthIndex < LIDAR_CONFIG.azimuthSteps; azimuthIndex++) {
    const azimuth = (azimuthIndex / LIDAR_CONFIG.azimuthSteps) * Math.PI * 2
    for (const elevationDeg of LIDAR_CONFIG.elevationAnglesDeg) {
      const elevation = THREE.MathUtils.degToRad(elevationDeg)
      const direction = new THREE.Vector3(
        Math.sin(azimuth) * Math.cos(elevation),
        Math.sin(elevation),
        -Math.cos(azimuth) * Math.cos(elevation),
      ).normalize()
      raycaster.set(origin, direction)
      const rockHit = raycaster.intersectObjects(rockMeshes, false)[0]
      if (!rockHit) continue
      const measuredDistance = applySensorNoise(rockHit.distance, random)
      if (measuredDistance === null) continue
      const point = origin.clone().addScaledVector(direction, measuredDistance)
      rockReturns++
      const rockId = String(rockHit.object.userData.lidarRockId ?? rockHit.object.uuid)
      detectedRockIds.add(rockId)
      nearestObstacleM = nearestObstacleM === null
        ? measuredDistance
        : Math.min(nearestObstacleM, measuredDistance)
      record(azimuthIndex, point, measuredDistance)
    }
  }

  const azimuthEndpoints: Array<THREE.Vector3 | null> = []
  for (let azimuthIndex = 0; azimuthIndex < LIDAR_CONFIG.azimuthSteps; azimuthIndex++) {
    azimuthEndpoints.push(nearestByAzimuth.get(azimuthIndex)?.point ?? null)
  }

  const beams = LIDAR_CONFIG.azimuthSteps * LIDAR_CONFIG.elevationAnglesDeg.length
  const returns = positions.length / 3
  const ySpan = maxY - minY
  const colors = new Float32Array(positions.length)
  for (let i = 0; i < returns; i++) {
    const y = positions[i * 3 + 1]
    const t = ySpan > 1e-6 ? (y - minY) / ySpan : 0.5
    const [r, g, b] = jetColor(t)
    colors[i * 3] = r
    colors[i * 3 + 1] = g
    colors[i * 3 + 2] = b
  }

  return {
    positions: new Float32Array(positions),
    colors,
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
