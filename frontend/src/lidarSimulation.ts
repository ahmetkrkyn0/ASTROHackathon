import * as THREE from 'three'

export const LIDAR_CONFIG = {
  maxRangeM: 60,
  minRangeM: 1.5,
  rangeNoiseSigmaM: 0.02,
  // 270, not 180: at typical dropout ~1400 returns read as sparse haze at
  // FPS range against reference point-cloud captures. This is angular
  // resolution, independent of the "16 CH" vertical channel count the UI
  // advertises, and still well inside the backend's 360-azimuth cap.
  azimuthSteps: 270,
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

/**
 * Which shape family TerrainCanvas3D should build this rock from. Chosen
 * here rather than in the renderer because the choice is not arbitrary: a
 * 10 cm clast and a 3 m block do not weather into the same silhouette, so
 * the size distribution below and the shape distribution have to be drawn
 * together.
 */
export type RockShape = 'scan' | 'cobble' | 'breccia' | 'slab'

export interface RockDescriptor {
  id: string
  x: number
  z: number
  radiusX: number
  radiusY: number
  radiusZ: number
  rotationY: number
  seed: number
  /**
   * Fraction of radiusY sunk below the surface. Rocks on the Moon sit IN
   * the regolith they have been gardened into, not balanced on top of it,
   * and the fraction is size-dependent -- a small clast is mostly buried
   * while a fresh metre-scale block is barely settled.
   */
  burial: number
  /** Shape family; see RockShape. */
  shape: RockShape
  /** Bedding tilt applied on top of the terrain normal, radians. */
  tiltX: number
  tiltZ: number
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
  /** First-return points classified as non-terrain by the local sensor pass. */
  obstacleReturns: Float32Array
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
 * Surface normal of the rendered DEM at (x, z), by central differences on
 * the same bilinear lookup everything else uses. Rocks are oriented against
 * this rather than against world up: a rock resting on a 12-degree slope
 * leans with the slope, and one that does not reads as stuck through the
 * ground on the uphill side and floating on the downhill side. Falls back
 * to straight up wherever the DEM window runs out.
 */
export function sampleTerrainNormal(field: TerrainField, x: number, z: number): THREE.Vector3 {
  const step = Math.max(field.resolutionM * 0.5, 0.5)
  const east = sampleTerrainHeight(field, x + step, z)
  const west = sampleTerrainHeight(field, x - step, z)
  const south = sampleTerrainHeight(field, x, z + step)
  const north = sampleTerrainHeight(field, x, z - step)
  if (east === null || west === null || south === null || north === null) {
    return new THREE.Vector3(0, 1, 0)
  }
  return new THREE.Vector3(west - east, 2 * step, north - south).normalize()
}

/**
 * Lunar rock-field parameters. The size distribution is Golombek & Rapp's
 * cumulative fractional-area model -- the same one used to choose Mars
 * landing sites and to predict boulder hazards from orbit:
 *
 *     F(D) = k * exp(-q(k) * D),   q(k) = 1.79 + 0.152 / k
 *
 * F is the fraction of ground covered by rocks with diameter >= D, and k is
 * the total rock abundance (CFA) of the terrain. Dividing by a rock's own
 * footprint (pi D^2 / 4) turns that area fraction into a NUMBER density,
 * which is what a point process needs. Using the real model rather than a
 * hand-tuned "0.28 + rand^2.35 * 1.9" is what makes the mix of pebbles,
 * cobbles and the occasional genuine block come out right on its own.
 */
export const ROCK_FIELD = {
  /** CFA of ordinary, gardened mare-like regolith between ejecta patches. */
  baseCfa: 0.02,
  /** CFA inside a fresh-crater ejecta patch. */
  patchCfa: 0.035,
  /** Characteristic patch size, metres -- an ejecta apron, not a continent. */
  patchScaleM: 55,
  /**
   * Smallest rock the navigation layer carries. Rocks below this are
   * decorative gravel: they are not a mobility hazard for a ~0.27 m wheel,
   * they are far too small for the backend's 5 m/px DEM to route around,
   * and at true lunar density there are tens of thousands of them inside
   * LiDAR range alone. generatePebbleField covers that range instead.
   */
  navMinDiameterM: 0.45,
  /** Largest block this field will place. */
  maxDiameterM: 4.5,
  /** Rocks nearer than this to the field origin are suppressed. */
  safetyRadiusM: 4.5,
  chunkM: 24,
  /** Guard against a pathological patch dumping a whole quarry in one cell. */
  maxPerChunk: 16,
} as const

/** Golombek's shape parameter: steeper (fewer big rocks) for sparser ground. */
function golombekQ(cfa: number): number {
  return 1.79 + 0.152 / Math.max(cfa, 1e-3)
}

/** Rocks per square metre with diameter >= dMin, for terrain of abundance k. */
function rockNumberDensity(cfa: number, dMin: number): number {
  const areaFraction = cfa * Math.exp(-golombekQ(cfa) * dMin)
  return areaFraction / ((Math.PI * dMin * dMin) / 4)
}

/**
 * Draw one diameter from the same distribution, by inverting
 * N(>=D) / N(>=dMin) = u. The ratio is monotone decreasing in D and has no
 * closed-form inverse, so this bisects -- 28 iterations is exact to well
 * under a millimetre over this range, and costs nothing at these counts.
 */
function sampleRockDiameter(cfa: number, dMin: number, dMax: number, u: number): number {
  const q = golombekQ(cfa)
  const target = Math.max(u, 1e-6)
  const ratio = (d: number) => (Math.exp(-q * (d - dMin)) * dMin * dMin) / (d * d)
  if (target <= ratio(dMax)) return dMax
  let lo = dMin
  let hi = dMax
  for (let i = 0; i < 28; i++) {
    const mid = (lo + hi) / 2
    if (ratio(mid) > target) lo = mid
    else hi = mid
  }
  return (lo + hi) / 2
}

/**
 * Observed lunar rock size-frequency curves are exponential through the
 * gardened cobble range but develop a distinctly heavier, power-law tail
 * above roughly a metre, where the population is fresh impact ejecta that
 * has not been comminuted yet. A single exponential fitted to the small end
 * predicts essentially no boulders at all -- it put the largest rock in a
 * whole 500 m field at 1.5 m, which is not what Apollo surface panoramas or
 * LROC boulder counts show. Drawing a fraction of rocks from a truncated
 * Pareto tail instead restores real blocks without inflating the overall
 * count, and ties how blocky a patch is to that patch's own abundance --
 * so ordinary ground stays cobbly and an ejecta apron reads as a boulder
 * field, which is the actual difference between the two.
 */
function sampleNavDiameter(cfa: number, random: () => number): number {
  const patchStrength = THREE.MathUtils.clamp(
    (cfa - ROCK_FIELD.baseCfa) / Math.max(ROCK_FIELD.patchCfa - ROCK_FIELD.baseCfa, 1e-6),
    0,
    1,
  )
  const tailProbability = 0.08 + 0.42 * patchStrength
  const dMin = ROCK_FIELD.navMinDiameterM
  const dMax = ROCK_FIELD.maxDiameterM
  if (random() < tailProbability) {
    const alpha = 2.2
    const cut = Math.pow(dMin / dMax, alpha)
    const d = dMin / Math.pow(1 - random() * (1 - cut), 1 / alpha)
    return Math.min(d, dMax)
  }
  return sampleRockDiameter(cfa, dMin, dMax, random())
}

/** Knuth for the small counts this field sees; normal approximation above it. */
function samplePoisson(lambda: number, random: () => number): number {
  if (lambda <= 0) return 0
  if (lambda > 30) {
    const gaussian =
      Math.sqrt(-2 * Math.log(Math.max(random(), 1e-9))) * Math.cos(2 * Math.PI * random())
    return Math.max(0, Math.round(lambda + gaussian * Math.sqrt(lambda)))
  }
  const limit = Math.exp(-lambda)
  let n = 0
  let product = 1
  do {
    n++
    product *= random()
  } while (product > limit)
  return n - 1
}

/**
 * Lattice value noise keyed on world metres. Everything about it depends on
 * (x, z) alone -- never on which window, rover position or route asked for
 * it -- which is what lets two independent callers (App.tsx's pre-planning
 * obstacle pass and TerrainCanvas3D's renderer) agree on the same field.
 */
function valueNoise2D(x: number, z: number): number {
  const xi = Math.floor(x)
  const zi = Math.floor(z)
  const xf = x - xi
  const zf = z - zi
  const u = xf * xf * (3 - 2 * xf)
  const v = zf * zf * (3 - 2 * zf)
  const n00 = hash2(xi, zi) / 4294967296
  const n10 = hash2(xi + 1, zi) / 4294967296
  const n01 = hash2(xi, zi + 1) / 4294967296
  const n11 = hash2(xi + 1, zi + 1) / 4294967296
  return (n00 * (1 - u) + n10 * u) * (1 - v) + (n01 * (1 - u) + n11 * u) * v
}

function fbm2D(x: number, z: number, octaves = 3): number {
  let amplitude = 1
  let frequency = 1
  let sum = 0
  let norm = 0
  for (let i = 0; i < octaves; i++) {
    sum += amplitude * valueNoise2D(x * frequency, z * frequency)
    norm += amplitude
    amplitude *= 0.5
    frequency *= 2.07
  }
  return sum / norm
}

/**
 * Local rock abundance. Rocks on an airless, impact-gardened surface are not
 * scattered uniformly -- they arrive in ejecta aprons around fresh craters
 * and are then slowly buried, so the ground alternates between long clean
 * stretches and distinctly blocky patches. A smoothstepped fBm reproduces
 * exactly that: mostly baseline, with localised concentrations.
 */
export function rockAbundanceAt(x: number, z: number): number {
  const patch = fbm2D(x / ROCK_FIELD.patchScaleM, z / ROCK_FIELD.patchScaleM, 3)
  const t = THREE.MathUtils.smoothstep(patch, 0.5, 0.86)
  return ROCK_FIELD.baseCfa + (ROCK_FIELD.patchCfa - ROCK_FIELD.baseCfa) * t
}

/**
 * Shape family by size. Not decoration: small clasts survive as rounded
 * cobbles because micrometeorite gardening abrades them, while a freshly
 * excavated metre block is still angular breccia or a slabby spall, and
 * the two do not read alike in silhouette.
 */
function pickShape(diameterM: number, random: () => number): RockShape {
  const u = random()
  if (diameterM < 0.22) return u < 0.85 ? 'cobble' : 'breccia'
  if (diameterM < 0.9) {
    if (u < 0.45) return 'scan'
    if (u < 0.75) return 'cobble'
    if (u < 0.93) return 'breccia'
    return 'slab'
  }
  if (u < 0.34) return 'scan'
  if (u < 0.72) return 'breccia'
  if (u < 0.92) return 'slab'
  return 'cobble'
}

/** Semi-axis ratios (b/a, c/a) per family; a is always the semi-major axis. */
const SHAPE_AXIS_RATIOS: Record<RockShape, { y: [number, number]; z: [number, number] }> = {
  cobble: { y: [0.78, 0.96], z: [0.74, 0.94] },
  scan: { y: [0.62, 0.86], z: [0.55, 0.8] },
  breccia: { y: [0.58, 0.88], z: [0.5, 0.78] },
  slab: { y: [0.22, 0.44], z: [0.66, 0.95] },
}

/**
 * Turn a drawn diameter into a full descriptor. Split out because the
 * navigation field and the gravel field below need identical rock
 * character -- only their size range and their consumers differ.
 */
function describeRock(
  id: string,
  x: number,
  z: number,
  diameterM: number,
  seed: number,
  random: () => number,
): RockDescriptor {
  const shape = pickShape(diameterM, random)
  const ratios = SHAPE_AXIS_RATIOS[shape]
  const semiMajor = diameterM / 2
  const ratioY = ratios.y[0] + random() * (ratios.y[1] - ratios.y[0])
  const ratioZ = ratios.z[0] + random() * (ratios.z[1] - ratios.z[0])
  // Small clasts have been gardened deep into the regolith; a metre block
  // has barely settled. 1/(1+D) falls off at about that rate, and a slab
  // sinks further than a compact rock of the same footprint.
  const slabFactor = shape === 'slab' ? 1.25 : 1
  const burial = THREE.MathUtils.clamp(
    0.06 + ((0.34 * random() + 0.1) / (1 + diameterM)) * slabFactor,
    0.05,
    0.46,
  )
  // A slab lies with its flat face on the ground; a compact rock can rest
  // on any facet, so it tilts further off the local surface normal.
  const tiltRange = shape === 'slab' ? 0.1 : 0.22
  return {
    id,
    x,
    z,
    radiusX: semiMajor,
    radiusY: semiMajor * ratioY,
    radiusZ: semiMajor * ratioZ,
    rotationY: random() * Math.PI * 2,
    seed: hash2(seed, 0x9e37),
    burial,
    shape,
    tiltX: (random() - 0.5) * 2 * tiltRange,
    tiltZ: (random() - 0.5) * 2 * tiltRange,
  }
}

/**
 * Stable metre-scale rocks around a rover. Rock identity is tied to absolute
 * world chunks, so moving the rover does not make obstacles slide around.
 *
 * Only rocks at or above ROCK_FIELD.navMinDiameterM appear here: these are
 * the ones that are a real mobility hazard, that LiDAR resolves as an
 * obstacle, and that the backend planner is told to route around. The
 * gravel below that size is generatePebbleField's job.
 */
export function generateRockField(
  originX: number,
  originZ: number,
  radiusM = LIDAR_CONFIG.maxRangeM + 8,
): RockDescriptor[] {
  const chunkM = ROCK_FIELD.chunkM
  // One chunk of overscan: rocks just outside the requested radius still
  // have to be generated so the overlap rejection below sees them, and are
  // only dropped afterwards. Without it, whether a rock near the edge got
  // rejected would depend on where the window happened to be cut, and the
  // field would stop being a fixed property of the world.
  const minChunkX = Math.floor((originX - radiusM) / chunkM) - 1
  const maxChunkX = Math.floor((originX + radiusM) / chunkM) + 1
  const minChunkZ = Math.floor((originZ - radiusM) / chunkM) - 1
  const maxChunkZ = Math.floor((originZ + radiusM) / chunkM) + 1

  const candidates: RockDescriptor[] = []
  for (let cz = minChunkZ; cz <= maxChunkZ; cz++) {
    for (let cx = minChunkX; cx <= maxChunkX; cx++) {
      const seed = hash2(cx, cz)
      const random = seededRandom(seed)
      const cfa = rockAbundanceAt((cx + 0.5) * chunkM, (cz + 0.5) * chunkM)
      const density = rockNumberDensity(cfa, ROCK_FIELD.navMinDiameterM)
      const count = Math.min(
        ROCK_FIELD.maxPerChunk,
        samplePoisson(density * chunkM * chunkM, random),
      )
      for (let i = 0; i < count; i++) {
        const x = (cx + random()) * chunkM
        const z = (cz + random()) * chunkM
        const diameterM = sampleNavDiameter(cfa, random)
        candidates.push(
          describeRock(`${cx}:${cz}:${i}`, x, z, diameterM, hash2(seed, i + 1), random),
        )
      }
    }
  }

  // Rocks do not interpenetrate. Resolving overlaps by "whoever was
  // generated first wins" would make the outcome depend on iteration order
  // and therefore on the window; ranking by each rock's own hash is a
  // property of the rock itself, so the same pair always resolves the same
  // way no matter who asks or from where.
  candidates.sort((a, b) => hash2(a.seed, 0x51ed) - hash2(b.seed, 0x51ed))
  const cellM = ROCK_FIELD.maxDiameterM
  const buckets = new Map<string, RockDescriptor[]>()
  const kept: RockDescriptor[] = []
  for (const rock of candidates) {
    const bx = Math.floor(rock.x / cellM)
    const bz = Math.floor(rock.z / cellM)
    let overlaps = false
    for (let dz = -1; dz <= 1 && !overlaps; dz++) {
      for (let dx = -1; dx <= 1 && !overlaps; dx++) {
        const neighbours = buckets.get(`${bx + dx}:${bz + dz}`)
        if (!neighbours) continue
        for (const other of neighbours) {
          const minGap =
            Math.max(rock.radiusX, rock.radiusZ) + Math.max(other.radiusX, other.radiusZ)
          if (Math.hypot(rock.x - other.x, rock.z - other.z) < minGap * 1.05) {
            overlaps = true
            break
          }
        }
      }
    }
    if (overlaps) continue
    const key = `${bx}:${bz}`
    const bucket = buckets.get(key)
    if (bucket) bucket.push(rock)
    else buckets.set(key, [rock])
    kept.push(rock)
  }

  const rocks: RockDescriptor[] = []
  for (const rock of kept) {
    const distance = Math.hypot(rock.x - originX, rock.z - originZ)
    if (distance > radiusM || distance < ROCK_FIELD.safetyRadiusM) continue
    rocks.push(rock)
  }
  return rocks
}

/**
 * Deliberately small, fixed boulder garden used by the interactive local
 * avoidance demo.  Unlike the broad, statistically distributed field above,
 * this is a repeatable scene feature: its anchor is chosen once by the
 * renderer and never follows a replan or the rover's moving pose.
 *
 * Six separated patches give the scene a wider obstacle field rather than
 * one artificial pile. Each patch starts with large, close but
 * non-overlapping boulders; its smaller surrounding rocks and loose outliers
 * keep it from reading as a few copied props.
 */
const FIXED_BOULDER_CLUSTER: ReadonlyArray<{
  x_m: number
  z_m: number
  diameter_m: number
  seed: number
}> = [
  { x_m: 18, z_m: 7, diameter_m: 5.4, seed: 0x4f11 },
  { x_m: 23.4, z_m: 8.2, diameter_m: 4.4, seed: 0x4f12 },
  { x_m: 20.3, z_m: 13, diameter_m: 3.8, seed: 0x4f13 },
  { x_m: 14, z_m: 12.4, diameter_m: 2.5, seed: 0x4f14 },
  { x_m: 26.2, z_m: 13.8, diameter_m: 2.2, seed: 0x4f15 },
  { x_m: 17.1, z_m: 18.1, diameter_m: 1.6, seed: 0x4f16 },
  { x_m: 23.8, z_m: 18.2, diameter_m: 1.3, seed: 0x4f17 },
  { x_m: 29.1, z_m: 9.6, diameter_m: 1.1, seed: 0x4f18 },

  // West-south patch: a second obstacle choice as the rover leaves the
  // initial garden, deliberately separated from it by open terrain.
  { x_m: -30, z_m: -12, diameter_m: 4.8, seed: 0x4f21 },
  { x_m: -24.8, z_m: -10.8, diameter_m: 3.9, seed: 0x4f22 },
  { x_m: -27.7, z_m: -5.4, diameter_m: 3.3, seed: 0x4f23 },
  { x_m: -35.1, z_m: -7.1, diameter_m: 2.2, seed: 0x4f24 },
  { x_m: -21.1, z_m: -4.1, diameter_m: 1.9, seed: 0x4f25 },
  { x_m: -32.2, z_m: -1.2, diameter_m: 1.4, seed: 0x4f26 },
  { x_m: -19.9, z_m: -14.4, diameter_m: 1.1, seed: 0x4f27 },

  // East-north patch: visible as a distinct destination-sized cluster in
  // orbit mode, with a tight three-boulder core for local LiDAR avoidance.
  { x_m: 44, z_m: 31, diameter_m: 4.7, seed: 0x4f31 },
  { x_m: 49.2, z_m: 32.5, diameter_m: 3.8, seed: 0x4f32 },
  { x_m: 46, z_m: 37, diameter_m: 3.2, seed: 0x4f33 },
  { x_m: 39.2, z_m: 36.1, diameter_m: 2.4, seed: 0x4f34 },
  { x_m: 53.2, z_m: 37.2, diameter_m: 2.0, seed: 0x4f35 },
  { x_m: 42, z_m: 42.2, diameter_m: 1.5, seed: 0x4f36 },
  { x_m: 52.3, z_m: 43.1, diameter_m: 1.2, seed: 0x4f37 },

  // South-east scatter: a large pair, an almost touching trio and several
  // small outliers make this feel like a natural ejecta apron rather than a
  // uniformly spaced obstacle course.
  { x_m: 58.4, z_m: -15.2, diameter_m: 5.7, seed: 0x4f41 },
  { x_m: 64.8, z_m: -12.7, diameter_m: 3.9, seed: 0x4f42 },
  { x_m: 60.1, z_m: -7.9, diameter_m: 3.1, seed: 0x4f43 },
  { x_m: 66.9, z_m: -6.3, diameter_m: 2.4, seed: 0x4f44 },
  { x_m: 54.2, z_m: -5.6, diameter_m: 1.8, seed: 0x4f45 },
  { x_m: 70.8, z_m: -15.8, diameter_m: 1.5, seed: 0x4f46 },
  { x_m: 61.9, z_m: -22.1, diameter_m: 1.2, seed: 0x4f47 },
  { x_m: 51.6, z_m: -19.7, diameter_m: 0.9, seed: 0x4f48 },
  { x_m: 73.5, z_m: -9.4, diameter_m: 0.7, seed: 0x4f49 },

  // North-west debris fan: visibly spread small fragments with two larger
  // anchors, so a route can encounter isolated rocks as well as a dense core.
  { x_m: -52.6, z_m: 24.1, diameter_m: 4.9, seed: 0x4f51 },
  { x_m: -47.1, z_m: 27.3, diameter_m: 3.6, seed: 0x4f52 },
  { x_m: -55.7, z_m: 31.2, diameter_m: 3.0, seed: 0x4f53 },
  { x_m: -43.2, z_m: 22.4, diameter_m: 2.2, seed: 0x4f54 },
  { x_m: -49.4, z_m: 35.4, diameter_m: 1.7, seed: 0x4f55 },
  { x_m: -60.9, z_m: 27.8, diameter_m: 1.4, seed: 0x4f56 },
  { x_m: -41.6, z_m: 33.2, diameter_m: 1.1, seed: 0x4f57 },
  { x_m: -57.6, z_m: 18.6, diameter_m: 0.8, seed: 0x4f58 },

  // North-centre loose field: unlike the tight gardens above, these clasts
  // deliberately have irregular gaps and mixed diameters.
  { x_m: -6.4, z_m: 29.2, diameter_m: 4.2, seed: 0x4f61 },
  { x_m: 0.4, z_m: 31.8, diameter_m: 2.9, seed: 0x4f62 },
  { x_m: 5.8, z_m: 26.7, diameter_m: 2.1, seed: 0x4f63 },
  { x_m: -11.5, z_m: 23.8, diameter_m: 1.9, seed: 0x4f64 },
  { x_m: 9.4, z_m: 34.7, diameter_m: 1.5, seed: 0x4f65 },
  { x_m: -2.6, z_m: 39.2, diameter_m: 1.2, seed: 0x4f66 },
  { x_m: 12.8, z_m: 21.4, diameter_m: 0.9, seed: 0x4f67 },
  { x_m: -14.1, z_m: 34.9, diameter_m: 0.7, seed: 0x4f68 },

  // South-east scatter: a looser field with a broader size mix than the
  // compact gardens, so the Apollo samples do not read as one repeated row
  // of props when orbiting or approaching in first person.
  { x_m: 38.5, z_m: -31.4, diameter_m: 4.6, seed: 0x4f71 },
  { x_m: 45.1, z_m: -27.8, diameter_m: 3.5, seed: 0x4f72 },
  { x_m: 32.8, z_m: -24.6, diameter_m: 2.8, seed: 0x4f73 },
  { x_m: 51.9, z_m: -34.2, diameter_m: 2.3, seed: 0x4f74 },
  { x_m: 40.7, z_m: -20.1, diameter_m: 1.9, seed: 0x4f75 },
  { x_m: 29.4, z_m: -37.6, diameter_m: 1.6, seed: 0x4f76 },
  { x_m: 55.6, z_m: -23.9, diameter_m: 1.4, seed: 0x4f77 },
  { x_m: 35.4, z_m: -17.8, diameter_m: 1.2, seed: 0x4f78 },
  { x_m: 47.6, z_m: -18.9, diameter_m: 1.0, seed: 0x4f79 },
  { x_m: 26.1, z_m: -30.2, diameter_m: 0.9, seed: 0x4f7a },
  { x_m: 59.4, z_m: -31.1, diameter_m: 0.8, seed: 0x4f7b },
  { x_m: 42.3, z_m: -39.7, diameter_m: 0.7, seed: 0x4f7c },
  { x_m: 31.2, z_m: -16.5, diameter_m: 0.6, seed: 0x4f7d },
]

export function generateFixedBoulderCluster(anchorX: number, anchorZ: number): RockDescriptor[] {
  return FIXED_BOULDER_CLUSTER.map((entry, index) => {
    const random = seededRandom(entry.seed)
    return describeRock(
      `boulder-garden:${index}`,
      anchorX + entry.x_m,
      anchorZ + entry.z_m,
      entry.diameter_m,
      entry.seed,
      random,
    )
  })
}

/**
 * Distance-graded gravel: the sub-navigation-size clasts that make the
 * ground read as a real regolith surface at eye height rather than a bare
 * mesh with a few boulders on it. At true lunar abundance there are tens of
 * thousands of these inside LiDAR range, so the minimum size carried rises
 * with distance -- a 10 cm clast is worth drawing two metres away and is
 * sub-pixel at fifty. Purely decorative: never raycast, never sent to the
 * planner, and rendered as instances rather than as individual meshes.
 */
export const PEBBLE_TIERS: Array<{ innerM: number; outerM: number; minDiameterM: number }> = [
  { innerM: 0, outerM: 18, minDiameterM: 0.1 },
  { innerM: 18, outerM: 40, minDiameterM: 0.13 },
  { innerM: 40, outerM: 70, minDiameterM: 0.22 },
]

export function generatePebbleField(originX: number, originZ: number): RockDescriptor[] {
  const chunkM = 6
  const outerM = PEBBLE_TIERS[PEBBLE_TIERS.length - 1].outerM
  const minChunkX = Math.floor((originX - outerM) / chunkM)
  const maxChunkX = Math.floor((originX + outerM) / chunkM)
  const minChunkZ = Math.floor((originZ - outerM) / chunkM)
  const maxChunkZ = Math.floor((originZ + outerM) / chunkM)
  const pebbles: RockDescriptor[] = []

  for (let cz = minChunkZ; cz <= maxChunkZ; cz++) {
    for (let cx = minChunkX; cx <= maxChunkX; cx++) {
      const centreX = (cx + 0.5) * chunkM
      const centreZ = (cz + 0.5) * chunkM
      const distance = Math.hypot(centreX - originX, centreZ - originZ)
      const tier = PEBBLE_TIERS.find((t) => distance >= t.innerM && distance < t.outerM)
      if (!tier) continue
      // Seeded on the chunk AND the tier: a chunk that changes tier as the
      // rover approaches re-draws at the finer size floor, which is the
      // point of the grading, and does so identically every time.
      const seed = hash2(hash2(cx, cz), Math.round(tier.minDiameterM * 1000))
      const random = seededRandom(seed)
      const cfa = rockAbundanceAt(centreX, centreZ)
      const density = rockNumberDensity(cfa, tier.minDiameterM)
      const count = Math.min(64, samplePoisson(density * chunkM * chunkM, random))
      for (let i = 0; i < count; i++) {
        const x = (cx + random()) * chunkM
        const z = (cz + random()) * chunkM
        if (Math.hypot(x - originX, z - originZ) < 2) continue
        const diameterM = sampleRockDiameter(
          cfa,
          tier.minDiameterM,
          ROCK_FIELD.navMinDiameterM,
          random(),
        )
        pebbles.push(
          describeRock(`p${cx}:${cz}:${i}`, x, z, diameterM, hash2(seed, i + 1), random),
        )
      }
    }
  }
  return pebbles
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
  const obstacleReturns: number[] = []
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
        obstacleReturns.push(point.x, point.y, point.z)
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
    obstacleReturns: new Float32Array(obstacleReturns),
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
  terrain: TerrainField,
  backendPoints: ReadonlyArray<readonly [number, number, number]>,
  rockMeshes: THREE.Mesh[],
  scanSeed = 1,
): LidarScanResult {
  const verticalScale = terrain.verticalScale
  const positions: number[] = []
  const obstacleReturns: number[] = []
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
    const pointX = origin.x + eastM * scale
    const pointZ = origin.z - northM * scale
    // The backend ray-marches its own copy of the DEM (see virtual_lidar.py)
    // to compute upM; even a tiny divergence from the frontend's own
    // heightfield -- a different resolution step, a rounding difference in
    // bilinear sampling -- reads as points floating above or sinking into
    // the rendered ground, since the two are computed by entirely separate
    // code paths in different languages. Snapping the point's height back
    // onto sampleTerrainHeight (the exact function that places every rock
    // and the terrain net, and that ultimately draws the mesh itself)
    // guarantees the point cloud can never visually diverge from the
    // ground it is supposed to be scanning. The backend's own upM survives
    // only in rawDistance/measuredDistance (used for range stats and this
    // return's azimuth-nearest comparison), never in what gets rendered.
    // sampleTerrainHeight is bilinear; the rendered mesh triangulates each
    // grid cell into two flat triangles instead, which is a slightly
    // different surface (they agree at the four cell corners, not
    // necessarily in between) -- a few cm of drift at a saddle-shaped cell,
    // worse right at a crater rim or other sharp local feature. The lift
    // below is a deliberate safety margin against that residual, not a
    // magic constant: big enough that a point on the wrong side of that
    // gap still reads as "on the surface", small enough to stay invisible
    // against a 60 m scan and metres of real relief.
    const groundY = sampleTerrainHeight(terrain, pointX, pointZ)
    const point = new THREE.Vector3(
      pointX,
      groundY !== null ? groundY + 0.15 : origin.y + upM * verticalScale * scale,
      pointZ,
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
      obstacleReturns.push(point.x, point.y, point.z)
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
    obstacleReturns: new Float32Array(obstacleReturns),
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
