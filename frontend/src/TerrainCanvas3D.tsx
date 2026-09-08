/**
 * 3-D terrain view, fed by the binary side of the API.
 *
 * MapCanvas draws the same grid in 2-D from the JSON layer endpoint, which is
 * capped at MAX_LAYER_CELLS and therefore always downsampled. This view takes
 * the f32 path instead: the whole 500x500 field at native resolution, in the
 * exact memory layout a Float32Array wants, about 1 MB per layer.
 *
 * Two things here are deliberate and worth not "fixing" later:
 *
 * 1. Ambient light is essentially zero. The Moon has no atmosphere, so nothing
 *    fills a shadow -- a shadowed slope is black, not dark grey. Earth-daylight
 *    lighting (ambient + hemisphere + fill) is what makes rendered lunar
 *    terrain read as grey clay.
 *
 * 2. Cast shadows come from the API's horizon cube, not from a three.js shadow
 *    map. At this site the Sun sits ~1.2 deg above the horizon, so shadows run
 *    for kilometres; a shadow map covering that at any useful resolution is not
 *    practical. The backend already ray-marches the real horizon per azimuth,
 *    so the honest shadow is a texture lookup, and it animates the site's real
 *    ~12-day lit / ~14-day dark cycle.
 */

import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { createSky } from './sky'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import type { ClickMode, MapViewMode } from './MapCanvas'
import type { Waypoint } from './api'
import { Icon } from './components/Fleet/SpecIcons'
import {
  buildLidarScanFromBackend,
  fetchBackendLidarScan,
  generateFixedBoulderCluster,
  generatePebbleField,
  LIDAR_CONFIG,
  ROCK_FIELD,
  sampleTerrainHeight,
  sampleTerrainNormal,
  seededRandom,
  simulateLidarScan,
} from './lidarSimulation'
import {
  buildLocalOccupancyGrid,
  localNavigationSnapshotKey,
  observeObstaclesFromLidar,
} from './localPerception'
import { planLocalDetour, type LocalPlanDecision } from './localPlanner'
import type {
  LidarScanResult,
  LidarScanSummary,
  RockShape,
  TerrainField,
} from './lidarSimulation'

/** Which binary layer paints the surface, per 2-D view mode. */
const LAYER_FOR_VIEW: Record<MapViewMode, string> = {
  surface: 'elevation',
  thermal: 'thermal',
  cost: 'cost',
  shadow: 'shadow_ratio',
  traversability: 'traversable',
  slope: 'slope',
  aspect: 'aspect',
}

/**
 * Regolith albedo for the 'surface' view.
 *
 * The Moon is grey. It is also, at this scale, very nearly UNIFORM grey: what
 * a photograph of lunar terrain shows is shading, not albedo variation, and
 * the mare/highland contrast that makes the full disc interesting is a
 * continent-scale effect that has no analogue inside one 2.5 km window. So
 * 'surface' paints a flat regolith tone and lets the lighting and the normals
 * carry the topography, rather than false-colouring height -- which is what
 * made this view read as an orange relief map instead of ground.
 *
 * The tone is the midpoint of the 2-D view's REGOLITH_STOPS, so both views
 * agree on what the ground is made of. It is barely warm (R > G > B by a few
 * percent), which is real: regolith is very slightly reddish, not the amber
 * an elevation ramp under a warm light produces.
 */
const SURFACE_ALBEDO = new THREE.Color(0x7a746c)

/**
 * Ramps for the DATA views. These are deliberately false colour -- slope,
 * cost and thermal are quantities, not appearances -- and only 'surface'
 * claims to look like the Moon.
 */
const RAMP: Record<string, [THREE.Color, THREE.Color]> = {
  slope: [new THREE.Color(0x1d3a1f), new THREE.Color(0xd94f3d)],
  thermal: [new THREE.Color(0x2b4a99), new THREE.Color(0xd94f3d)],
  shadow_ratio: [new THREE.Color(0xe8e4dc), new THREE.Color(0x0a0a0c)],
  cost: [new THREE.Color(0x243b6b), new THREE.Color(0xe8d54a)],
  traversable: [new THREE.Color(0x8a2c22), new THREE.Color(0x2f7d46)],
  aspect: [new THREE.Color(0x3b2f6b), new THREE.Color(0xe0c060)],
}

const FALLBACK_RAMP: [THREE.Color, THREE.Color] = [
  new THREE.Color(0x2c2a26),
  new THREE.Color(0xe8e4dc),
]

interface TerrainManifest {
  grid: { rows: number; cols: number; resolution_m: number }
  georeference: { origin: { x: number; y: number } }
  elevation: { min_m: number; max_m: number; vertical_exaggeration_suggested: number }
  layers: Record<string, { min: number | null; max: number | null; binary_url: string }>
}

interface SunSample {
  index: number
  utc: string
  azimuth_grid_deg: number
  elevation_deg: number
}

interface SeriesManifest {
  slices: number
  shadow_model: { model: string; time_varying: boolean }
  sun: SunSample[]
  fields: Record<string, { binary_url: string }>
  binary_format: { shape: [number, number, number] }
}

/** Six days from 2026-09-07 walks this site from fully dark to ~95% lit. */
const SERIES_QUERY =
  'start_utc=2026-09-07T00:00:00&n_slices=12&slice_hours=12&downsample=2'

/**
 * Real LROC NAC imagery of exactly this window, 1 m/px, same projection, cut
 * to the grid pixel for pixel -- so PlaneGeometry's default UVs land on it
 * without any reprojection. See NAC_SITE11_PROVENANCE.md beside the file.
 *
 * It is served as a photograph, not as a physical albedo: the mosaic was shot
 * at the 2010 southern solstice and carries that epoch's shadows baked in, and
 * those shadows were measured NOT to agree with the epoch this app simulates
 * (IoU about 51%). So the photographic mode drapes this and switches the
 * shadow mask OFF -- multiplying the two would count shadow twice and be
 * wrong about both. The simulated modes keep the flat albedo and the real
 * time-varying mask. Two separate claims, never mixed.
 */
const PHOTO_TEXTURE_URL = '/textures/nac-site11-2048.jpg'

/**
 * The same NAC imagery reduced to what does NOT depend on when it was shot,
 * so the 'surface' view can carry real crater detail and still answer to the
 * simulated Sun.
 *
 * Built as the NAC frame divided by its own 125 m local mean: the division
 * removes the large-scale illumination gradient the photograph is made of and
 * leaves the small-scale variation, then that ratio modulates the flat regolith
 * albedo. Its channel means (120, 114, 106) sit within two counts of the flat
 * tone (122, 116, 108), so it adds texture without shifting what the ground is.
 *
 * Where the source was too dark to divide (DN <= 25, about 47% of the frame at
 * this latitude) the ratio is pinned to 1 and the surface falls back to plain
 * albedo -- no detail invented where the photograph had no signal.
 *
 * The honest limit: what is left after the division is a mixture of true albedo
 * variation and the 2010 shading of features too small for the LOLA DEM to
 * hold. A small crater's own light-and-dark pair is therefore baked in and does
 * not swing round as the simulated Sun moves. It is a detail texture, not a
 * recovered albedo, and it is applied only to 'surface' -- the data views stay
 * unmodulated, because a slope or cost ramp must not be textured by a
 * photograph.
 */
const DETAIL_TEXTURE_URL = '/textures/nac-site11-detail-2048.jpg'

const NAC_TEXTURE_WINDOW = {
  originX: -32_500,
  originY: 11_000,
  rows: 500,
  cols: 500,
  resolutionM: 5,
}

function hasAlignedNacTexture(manifest: TerrainManifest): boolean {
  const { grid, georeference } = manifest
  return (
    grid.rows === NAC_TEXTURE_WINDOW.rows &&
    grid.cols === NAC_TEXTURE_WINDOW.cols &&
    Math.abs(grid.resolution_m - NAC_TEXTURE_WINDOW.resolutionM) < 1e-6 &&
    Math.abs(georeference.origin.x - NAC_TEXTURE_WINDOW.originX) < 1e-6 &&
    Math.abs(georeference.origin.y - NAC_TEXTURE_WINDOW.originY) < 1e-6
  )
}

/**
 * A lightweight, unlit cursor placed on the DEM while an endpoint picker is
 * armed. It is deliberately a scene object rather than a DOM overlay: the
 * operator can read the exact grid cell on sloped ground before committing a
 * Start or Goal click.
 */
function createTerrainSelectionCursor(resolutionM: number): {
  group: THREE.Group
  setMode: (mode: Exclude<ClickMode, 'idle'>) => void
  dispose: () => void
} {
  const group = new THREE.Group()
  group.name = 'terrain-endpoint-selection-cursor'
  group.visible = false
  group.renderOrder = 20

  const radius = Math.max(resolutionM * 0.72, 2.8)
  const ringMaterial = new THREE.MeshBasicMaterial({
    color: 0x35e7c1,
    transparent: true,
    opacity: 0.92,
    depthTest: false,
    depthWrite: false,
    side: THREE.DoubleSide,
  })
  const lineMaterial = new THREE.LineBasicMaterial({
    color: 0x35e7c1,
    transparent: true,
    opacity: 1,
    depthTest: false,
    depthWrite: false,
  })
  const ring = new THREE.Mesh(new THREE.RingGeometry(radius * 0.72, radius, 40), ringMaterial)
  ring.rotation.x = -Math.PI / 2
  ring.position.y = 0.08

  const crossGeometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-radius * 1.24, 0.1, 0), new THREE.Vector3(-radius * 0.42, 0.1, 0),
    new THREE.Vector3(radius * 0.42, 0.1, 0), new THREE.Vector3(radius * 1.24, 0.1, 0),
    new THREE.Vector3(0, 0.1, -radius * 1.24), new THREE.Vector3(0, 0.1, -radius * 0.42),
    new THREE.Vector3(0, 0.1, radius * 0.42), new THREE.Vector3(0, 0.1, radius * 1.24),
    new THREE.Vector3(0, 0.12, 0), new THREE.Vector3(0, radius * 0.9, 0),
  ])
  const cross = new THREE.LineSegments(crossGeometry, lineMaterial)
  const tip = new THREE.Mesh(
    new THREE.ConeGeometry(radius * 0.16, radius * 0.42, 16),
    ringMaterial,
  )
  tip.position.y = radius * 1.08
  group.add(ring, cross, tip)

  const setMode = (mode: Exclude<ClickMode, 'idle'>) => {
    const color = mode === 'start' ? 0x35e7c1 : 0xffa550
    ringMaterial.color.setHex(color)
    lineMaterial.color.setHex(color)
  }

  return {
    group,
    setMode,
    dispose: () => {
      ring.geometry.dispose()
      ringMaterial.dispose()
      crossGeometry.dispose()
      lineMaterial.dispose()
      tip.geometry.dispose()
    },
  }
}

/**
 * Intersect a camera ray with the DEM height field directly. This is both
 * materially cheaper than raycasting the 500 x 500 render mesh on each mouse
 * move and, unlike a flat y=0 proxy, remains accurate on a sloping ridge.
 */
function intersectTerrainHeightfield(
  ray: THREE.Ray,
  terrain: TerrainField,
  result: THREE.Vector3,
): boolean {
  const width = terrain.cols * terrain.resolutionM
  const depth = terrain.rows * terrain.resolutionM
  const minX = -width / 2
  const maxX = width / 2
  const minZ = -depth / 2
  const maxZ = depth / 2
  let enterT = 0
  let exitT = Number.POSITIVE_INFINITY

  const clipAxis = (origin: number, direction: number, low: number, high: number): boolean => {
    if (Math.abs(direction) < 1e-9) return origin >= low && origin <= high
    const a = (low - origin) / direction
    const b = (high - origin) / direction
    enterT = Math.max(enterT, Math.min(a, b))
    exitT = Math.min(exitT, Math.max(a, b))
    return enterT <= exitT
  }

  if (!clipAxis(ray.origin.x, ray.direction.x, minX, maxX)) return false
  if (!clipAxis(ray.origin.z, ray.direction.z, minZ, maxZ)) return false
  // A terrain click must be looking down onto the map. The base plane gives a
  // finite end point even for a perfectly vertical camera ray.
  if (ray.direction.y >= -1e-9) return false
  const basePlaneT = -ray.origin.y / ray.direction.y
  if (basePlaneT < 0) return false
  exitT = Math.min(exitT, basePlaneT)
  if (enterT > exitT) return false

  const signedHeight = (distance: number): number | null => {
    const point = ray.at(distance, result)
    const terrainY = sampleTerrainHeight(terrain, point.x, point.z)
    return terrainY === null ? null : point.y - terrainY
  }

  const horizontalDistance = Math.hypot(ray.direction.x, ray.direction.z) * (exitT - enterT)
  // Sample at <= half a DEM cell. This catches steep local relief while doing
  // only scalar height lookups rather than hundreds of thousands of triangle
  // intersection tests.
  const steps = THREE.MathUtils.clamp(
    Math.ceil(horizontalDistance / Math.max(terrain.resolutionM * 0.5, 0.25)),
    1,
    4096,
  )
  let previousT = enterT
  let previousHeight = signedHeight(previousT)
  if (previousHeight === null) return false

  for (let i = 1; i <= steps; i++) {
    const currentT = enterT + (exitT - enterT) * (i / steps)
    const currentHeight = signedHeight(currentT)
    if (currentHeight === null) return false
    if (previousHeight === 0 || currentHeight === 0 || previousHeight * currentHeight < 0) {
      let lowT = previousT
      let highT = currentT
      let lowHeight = previousHeight
      for (let iteration = 0; iteration < 14; iteration++) {
        const midT = (lowT + highT) / 2
        const midHeight = signedHeight(midT)
        if (midHeight === null) return false
        if (Math.abs(midHeight) < 0.002) {
          lowT = highT = midT
          break
        }
        if (lowHeight * midHeight > 0) {
          lowT = midT
          lowHeight = midHeight
        } else {
          highT = midT
        }
      }
      ray.at((lowT + highT) / 2, result)
      return true
    }
    previousT = currentT
    previousHeight = currentHeight
  }
  return false
}

async function fetchF32(url: string): Promise<Float32Array> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`${url} -> ${response.status}`)
  return new Float32Array(await response.arrayBuffer())
}

// ── 3D Deep Space Environment Generators ──────────────────────────────────────

function createEarth(span: number): { group: THREE.Group; sprite: THREE.Sprite } {
  const group = new THREE.Group()

  // The asset is a PHOTOGRAPH of the Earth as a disc on a black starfield, and
  // it is 1024 square -- not the 2:1 an equirectangular sphere map has to be.
  // Wrapped onto a SphereGeometry, its black corners land across whole regions
  // of the globe: that is what read as "one side of the Earth is dark". Not a
  // lighting problem at all, and no amount of emissive fixed it, because the
  // darkness was the texture's own background being painted onto the sphere.
  //
  // So it does not go on a sphere. A photo of a lit disc, atmospheric limb
  // already baked in, IS the image of a distant planet -- it only needs to be
  // held up facing the viewer, which is exactly what a Sprite does, and what
  // the sun flare beside it already does. The sphere's slow spin goes with it:
  // the Earth hangs all but motionless over the lunar south pole, so nobody
  // could have seen it turn even if the texture had been right.
  const canvas = document.createElement('canvas')
  canvas.width = 1024
  canvas.height = 1024
  const ctx = canvas.getContext('2d')!
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace

  new THREE.TextureLoader().load('/textures/earth_disc.jpg', (loaded) => {
    ctx.drawImage(loaded.image as CanvasImageSource, 0, 0, 1024, 1024)
    // Cut the square photo down to its own disc. A JPEG carries no alpha, so
    // without this the sprite is a black tile with a planet in the middle of
    // it. The fade band sits just outside the limb, where the frame has
    // already fallen off to space, so the corners and the photo's own stars
    // go (the scene draws its own) without biting into the atmosphere glow.
    const alpha = ctx.createRadialGradient(512, 512, 462, 512, 512, 500)
    alpha.addColorStop(0, 'rgba(0, 0, 0, 1)')
    alpha.addColorStop(1, 'rgba(0, 0, 0, 0)')
    ctx.globalCompositeOperation = 'destination-in'
    ctx.fillStyle = alpha
    ctx.fillRect(0, 0, 1024, 1024)
    ctx.globalCompositeOperation = 'source-over'
    loaded.dispose()
    texture.needsUpdate = true
  })

  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false }),
  )
  // Measured off the file: the planet's limb sits at r=428 of 512, so it
  // fills 84% of the frame it was photographed in and the sprite has to be
  // scaled up by that much to leave the Earth the size in the sky the old
  // sphere (radius span * 0.18) drew it. The alpha cut above is placed off
  // the same measurement -- brightness is 10/255 at r=462 and 3/255 by 500,
  // so the band it fades across is already space.
  const diameter = (span * 0.36) / 0.836
  sprite.scale.set(diameter, diameter, 1)
  group.add(sprite)

  // High in the upper-right sky, above the lunar horizon.
  group.position.set(span * 1.5, span * 1.05, -span * 2.4)

  return { group, sprite }
}

function createSunFlareSprite(): THREE.Sprite {
  const canvas = document.createElement('canvas')
  canvas.width = 128
  canvas.height = 128
  const ctx = canvas.getContext('2d')!

  const grad = ctx.createRadialGradient(64, 64, 0, 64, 64, 64)
  grad.addColorStop(0, 'rgba(255, 255, 255, 1.0)')
  grad.addColorStop(0.12, 'rgba(254, 240, 138, 0.95)')
  grad.addColorStop(0.35, 'rgba(251, 146, 60, 0.4)')
  grad.addColorStop(0.65, 'rgba(244, 63, 94, 0.1)')
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)')

  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 128, 128)

  const texture = new THREE.CanvasTexture(canvas)
  const material = new THREE.SpriteMaterial({
    map: texture,
    blending: THREE.AdditiveBlending,
    transparent: true,
  })

  const sprite = new THREE.Sprite(material)
  sprite.scale.set(6500, 6500, 1)
  return sprite
}

function createRockTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = 128
  canvas.height = 128
  const context = canvas.getContext('2d')!
  const image = context.createImageData(canvas.width, canvas.height)
  const random = seededRandom(0x4c554e41)

  for (let y = 0; y < canvas.height; y++) {
    for (let x = 0; x < canvas.width; x++) {
      const index = (y * canvas.width + x) * 4
      const broad = 16 * Math.sin(x * 0.17) * Math.cos(y * 0.11)
      const grain = (random() - 0.5) * 46
      // Centred near white, not near mid-grey. This texture MULTIPLIES the
      // material's base colour, so a mean of ~104/255 was quietly costing
      // rocks 60% of their albedo on top of it and rendering them near
      // black against the regolith. Rock on the Moon is the brighter of the
      // two -- fresh basalt and breccia sit around 0.10-0.30 reflectance
      // where mature soil is 0.08-0.12 -- so the base colour below carries
      // the albedo and this carries only the grain around it.
      const value = THREE.MathUtils.clamp(205 + broad + grain, 150, 255)
      image.data[index] = value
      image.data[index + 1] = value * 0.965
      image.data[index + 2] = value * 0.92
      image.data[index + 3] = 255
    }
  }
  context.putImageData(image, 0, 0)

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(2.5, 2.5)
  // Rocks are seen at a steep grazing angle from FPS eye height; without
  // anisotropic filtering the mips blur into the streaky, muddy look a flat
  // ground texture gets when viewed edge-on.
  texture.anisotropy = 16
  return texture
}

/** Direction-neutral micro-albedo for DEM windows without an aligned NAC crop. */
function createRegolithTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 256
  const context = canvas.getContext('2d')!
  const image = context.createImageData(canvas.width, canvas.height)
  const random = seededRandom(0x5245474f)

  for (let y = 0; y < canvas.height; y++) {
    for (let x = 0; x < canvas.width; x++) {
      const index = (y * canvas.width + x) * 4
      const broad = 7 * Math.sin(x * 0.08) * Math.cos(y * 0.06)
      const grain = (random() - 0.5) * 22
      const value = THREE.MathUtils.clamp(122 + broad + grain, 88, 154)
      image.data[index] = value
      image.data[index + 1] = value * 0.965
      image.data[index + 2] = value * 0.92
      image.data[index + 3] = 255
    }
  }
  context.putImageData(image, 0, 0)

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(18, 18)
  texture.anisotropy = 16
  return texture
}

/** Point-cloud dot: a solid disc with only a 1-2 px antialiased rim, not a
 * soft glow. A LiDAR return is a discrete measurement -- CloudCompare, RViz
 * and PDAL all draw it as a crisp, fully-opaque dot. */
function createSolidDotTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = 32
  canvas.height = 32
  const ctx = canvas.getContext('2d')!
  const grad = ctx.createRadialGradient(16, 16, 0, 16, 16, 16)
  grad.addColorStop(0, 'rgba(255, 255, 255, 1.0)')
  grad.addColorStop(0.82, 'rgba(255, 255, 255, 1.0)')
  grad.addColorStop(1, 'rgba(255, 255, 255, 0)')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 32, 32)
  return new THREE.CanvasTexture(canvas)
}

interface RockTemplatePayload {
  vertexCount: number
  /** Non-indexed Float32Array, base64: x,y,z per vertex. */
  position: string
  /** Non-indexed Float32Array, base64: nx,ny,nz per vertex. */
  normal: string
}

/** A web-ready Apollo sample mesh and its baked PBR material. */
interface ScannedRockVisualTemplate {
  geometry: THREE.BufferGeometry
  material: THREE.MeshStandardMaterial
}

function base64ToFloat32Array(base64: string): Float32Array {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return new Float32Array(bytes.buffer)
}

/**
 * A real Apollo lunar sample's scanned shape, not a synthetic polyhedron --
 * see frontend/simplify_rock.mjs for how the ~100k-vertex NASA Astromaterials
 * 3D source (https://ares.jsc.nasa.gov/astromaterials3d/) was decimated to
 * this. Centred at its own origin and normalised to a unit bounding sphere,
 * the same convention IcosahedronGeometry(1, ...) already used, so the rock
 * field's existing per-instance radiusX/Y/Z scaling applies unchanged.
 */
async function fetchRockGeometryTemplate(url: string): Promise<THREE.BufferGeometry | null> {
  try {
    const response = await fetch(url)
    if (!response.ok) return null
    const payload: RockTemplatePayload = await response.json()
    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(base64ToFloat32Array(payload.position), 3))
    geometry.setAttribute('normal', new THREE.BufferAttribute(base64ToFloat32Array(payload.normal), 3))
    // Welded on arrival: the payload is non-indexed, and three.js gives any
    // non-indexed geometry flat per-face normals when they are recomputed --
    // which every rock needs after the field stretches it to its own
    // semi-axes. Welding once here is what lets a scanned rock come out
    // smooth instead of faceted, and costs one pass per template rather
    // than one per rock.
    return mergeVertices(geometry, 1e-5)
  } catch {
    return null
  }
}

const NASA_ROCK_TEMPLATE_URLS = [
  '/models/nasa_rocks/rock-15016.json',
  '/models/nasa_rocks/rock-15556.json',
]

// Pre-simplified versions of the supplied GLBs. Optimising these files before
// they reach the browser avoids blocking the loading screen while the JS
// thread tries to decimate hundreds of thousands of vertices at runtime.
const NASA_ROCK_GLB_URLS = [
  '/models/nasa_rocks_optimized/apollo_lunar_sample_1201311.glb',
  '/models/nasa_rocks_optimized/apollo_lunar_sample_143211404.glb',
  '/models/nasa_rocks_optimized/apollo_lunar_sample_701750.glb',
  '/models/nasa_rocks_optimized/apollo_lunar_sample_702950.glb',
]

function normaliseRockVisualGeometry(geometry: THREE.BufferGeometry, transform: THREE.Matrix4): THREE.BufferGeometry | null {
  const normalised = geometry.clone()
  normalised.applyMatrix4(transform)
  normalised.computeBoundingBox()
  const bounds = normalised.boundingBox
  if (!bounds) {
    normalised.dispose()
    return null
  }
  const size = bounds.getSize(new THREE.Vector3())
  const largestAxis = Math.max(size.x, size.y, size.z)
  if (!(largestAxis > 1e-6)) {
    normalised.dispose()
    return null
  }
  const centre = bounds.getCenter(new THREE.Vector3())
  normalised.translate(-centre.x, -centre.y, -centre.z)
  // A normalised maximum diameter of 2 means the descriptor's radiusX/Y/Z
  // continues to be metres, exactly like the previous procedural geometry.
  const scale = 2 / largestAxis
  normalised.scale(scale, scale, scale)
  normalised.computeBoundingSphere()
  return normalised
}

async function loadScannedRockVisualTemplate(url: string): Promise<ScannedRockVisualTemplate | null> {
  try {
    const gltf = await new GLTFLoader().loadAsync(url)
    gltf.scene.updateMatrixWorld(true)
    const candidates: THREE.Mesh[] = []
    gltf.scene.traverse((object) => {
      if (object instanceof THREE.Mesh && object.geometry.getAttribute('position')) candidates.push(object)
    })
    // Apollo sample exports normally contain one surface mesh. Selecting the
    // largest surface also ignores any helper/ground mesh an exporter added.
    candidates.sort(
      (a, b) => (b.geometry.getAttribute('position')?.count ?? 0) - (a.geometry.getAttribute('position')?.count ?? 0),
    )
    const source = candidates[0]
    if (!source) return null
    const material = Array.isArray(source.material) ? source.material[0] : source.material
    if (!(material instanceof THREE.MeshStandardMaterial)) return null
    const geometry = normaliseRockVisualGeometry(source.geometry, source.matrixWorld)
    if (!geometry) return null
    const visualMaterial = material.clone()
    visualMaterial.side = THREE.DoubleSide
    visualMaterial.roughness = Math.max(visualMaterial.roughness, 0.72)
    visualMaterial.metalness = 0
    return { geometry, material: visualMaterial }
  } catch {
    return null
  }
}

/**
 * Make a MeshStandardMaterial sample its map by world-space triplanar
 * projection instead of by UV.
 *
 * This is not a stylistic choice. The NASA scan templates ship POSITION and
 * NORMAL only -- no `uv` attribute at all -- so a plain `map` on them
 * silently degraded to sampling a single texel: every real-shaped rock in
 * the field rendered as a flat, untextured colour, and only the procedural
 * fallback ever looked like stone. Projecting from world position removes
 * the requirement entirely, and it also fixes two problems a UV unwrap
 * would still have had: no seam down a blobby closed surface, and constant
 * texel density whether the rock is 10 cm or 4 m, because the projection is
 * measured in metres rather than in each rock's own normalised space.
 */
function applyTriplanarMapping(material: THREE.MeshStandardMaterial, texturesPerMetre: number) {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uTriplanarScale = { value: texturesPerMetre }
    shader.vertexShader = shader.vertexShader
      .replace(
        '#include <common>',
        `#include <common>
        varying vec3 vTriplanarPos;
        varying vec3 vTriplanarNormal;`,
      )
      .replace(
        '#include <worldpos_vertex>',
        `#include <worldpos_vertex>
        vec4 triplanarLocal = vec4( transformed, 1.0 );
        vec3 triplanarNormal = objectNormal;
        #ifdef USE_INSTANCING
          triplanarLocal = instanceMatrix * triplanarLocal;
          triplanarNormal = mat3( instanceMatrix ) * triplanarNormal;
        #endif
        vTriplanarPos = ( modelMatrix * triplanarLocal ).xyz;
        vTriplanarNormal = mat3( modelMatrix ) * triplanarNormal;`,
      )
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        `#include <common>
        uniform float uTriplanarScale;
        varying vec3 vTriplanarPos;
        varying vec3 vTriplanarNormal;`,
      )
      .replace(
        '#include <map_fragment>',
        `#ifdef USE_MAP
          vec3 triBlend = abs( normalize( vTriplanarNormal ) );
          triBlend = pow( triBlend, vec3( 3.0 ) );
          triBlend /= max( triBlend.x + triBlend.y + triBlend.z, 1e-4 );
          vec4 triSample =
            texture2D( map, vTriplanarPos.zy * uTriplanarScale ) * triBlend.x +
            texture2D( map, vTriplanarPos.xz * uTriplanarScale ) * triBlend.y +
            texture2D( map, vTriplanarPos.xy * uTriplanarScale ) * triBlend.z;
          diffuseColor *= triSample;
        #endif`,
      )
  }
  // Two materials whose onBeforeCompile differ must not share a compiled
  // program; three.js keys its program cache on this alongside the source.
  material.customProgramCacheKey = () => `triplanar-${texturesPerMetre}`
}

/**
 * Deterministic 3D value noise, used to weather a sphere into a rock. Same
 * lattice-hash construction as the rock field's own 2D patch noise, so a
 * given seed always carves the identical shape, on every reload.
 */
function rockNoise3D(x: number, y: number, z: number, seed: number): number {
  const hash = (a: number, b: number, c: number) => {
    let h =
      Math.imul(a | 0, 0x8da6b343) ^ Math.imul(b | 0, 0xd8163841) ^ Math.imul(c | 0, 0xcb1ab31f)
    h = Math.imul(h ^ seed, 0x45d9f3b)
    h = Math.imul(h ^ (h >>> 16), 0x45d9f3b)
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296
  }
  const xi = Math.floor(x)
  const yi = Math.floor(y)
  const zi = Math.floor(z)
  const xf = x - xi
  const yf = y - yi
  const zf = z - zi
  const u = xf * xf * (3 - 2 * xf)
  const v = yf * yf * (3 - 2 * yf)
  const w = zf * zf * (3 - 2 * zf)
  const lerp = (a: number, b: number, t: number) => a + (b - a) * t
  const c00 = lerp(hash(xi, yi, zi), hash(xi + 1, yi, zi), u)
  const c10 = lerp(hash(xi, yi + 1, zi), hash(xi + 1, yi + 1, zi), u)
  const c01 = lerp(hash(xi, yi, zi + 1), hash(xi + 1, yi, zi + 1), u)
  const c11 = lerp(hash(xi, yi + 1, zi + 1), hash(xi + 1, yi + 1, zi + 1), u)
  return lerp(lerp(c00, c10, v), lerp(c01, c11, v), w)
}

function rockFbm3D(x: number, y: number, z: number, seed: number, octaves: number): number {
  let amplitude = 1
  let frequency = 1
  let sum = 0
  let norm = 0
  for (let i = 0; i < octaves; i++) {
    sum += amplitude * rockNoise3D(x * frequency, y * frequency, z * frequency, seed + i * 7919)
    norm += amplitude
    amplitude *= 0.5
    frequency *= 2.13
  }
  return sum / norm
}

/**
 * Welded unit icospheres, one per subdivision level, built once and cloned
 * per rock. Welding matters for more than memory: three.js computes FLAT
 * normals for any non-indexed geometry, so the smooth families below only
 * actually come out smooth if their base shares vertices between faces.
 * (IcosahedronGeometry ships non-indexed, which is why every rock in this
 * scene read as faceted before regardless of the material's flatShading.)
 */
const icosphereBaseCache = new Map<number, THREE.BufferGeometry>()
function icosphereBase(detail: number): THREE.BufferGeometry {
  const cached = icosphereBaseCache.get(detail)
  if (cached) return cached
  const welded = mergeVertices(new THREE.IcosahedronGeometry(1, detail), 1e-5)
  icosphereBaseCache.set(detail, welded)
  return welded
}

/**
 * Build one rock's geometry, already scaled to its own semi-axes.
 *
 * The four families exist because lunar rocks of different sizes and ages
 * genuinely do not share a silhouette, and a field built from one shape
 * (or, as this one was, from two scans plus a single polyhedron) reads as a
 * repeated prop no matter how well the placement is randomised:
 *
 *  - `scan`    a real decimated Apollo sample, when one is loaded
 *  - `cobble`  gardened and abraded: rounded, low-amplitude relief
 *  - `breccia` freshly excavated: angular, cut by flat conchoidal facets
 *  - `slab`    a tabular spall: flat top and bottom, ragged rim
 */
function buildRockGeometry(
  shape: RockShape,
  seed: number,
  radiusX: number,
  radiusY: number,
  radiusZ: number,
  templates: THREE.BufferGeometry[],
  detail: number,
): THREE.BufferGeometry {
  const random = seededRandom(seed)
  const faceted = shape === 'breccia' || shape === 'slab'
  let geometry: THREE.BufferGeometry =
    shape === 'scan' && templates.length > 0
      ? templates[Math.abs(seed) % templates.length].clone()
      : icosphereBase(detail).clone()

  // Fracture planes for the angular families. A plane is a unit normal plus
  // an offset; every vertex past it is projected back onto it, which is what
  // turns a sphere into something with real flat faces and sharp edges
  // rather than a dented ball.
  const cuts: Array<{ n: THREE.Vector3; d: number }> = []
  if (shape === 'breccia') {
    const cutCount = 3 + Math.floor(random() * 4)
    for (let i = 0; i < cutCount; i++) {
      const theta = random() * Math.PI * 2
      const phi = Math.acos(2 * random() - 1)
      cuts.push({
        n: new THREE.Vector3(
          Math.sin(phi) * Math.cos(theta),
          Math.cos(phi),
          Math.sin(phi) * Math.sin(theta),
        ),
        d: 0.62 + random() * 0.3,
      })
    }
  } else if (shape === 'slab') {
    // Two near-parallel bedding planes give the flat top and bottom; a few
    // steep ones chip the rim so it is not a perfect disc.
    const tilt = (random() - 0.5) * 0.25
    cuts.push({ n: new THREE.Vector3(tilt, 1, tilt * 0.6).normalize(), d: 0.5 + random() * 0.16 })
    cuts.push({
      n: new THREE.Vector3(-tilt, -1, -tilt * 0.6).normalize(),
      d: 0.5 + random() * 0.16,
    })
    const rimCount = 2 + Math.floor(random() * 3)
    for (let i = 0; i < rimCount; i++) {
      const theta = random() * Math.PI * 2
      cuts.push({
        n: new THREE.Vector3(Math.cos(theta), (random() - 0.5) * 0.3, Math.sin(theta)).normalize(),
        d: 0.74 + random() * 0.24,
      })
    }
  }

  const relief = shape === 'cobble' ? 0.15 : shape === 'scan' ? 0.06 : 0.1
  const octaves = shape === 'cobble' ? 3 : 2
  const noiseSeed = seed >>> 0
  const positions = geometry.getAttribute('position') as THREE.BufferAttribute
  const vertex = new THREE.Vector3()
  const direction = new THREE.Vector3()

  for (let i = 0; i < positions.count; i++) {
    vertex.fromBufferAttribute(positions, i)
    direction.copy(vertex).normalize()
    // A RADIAL displacement -- one factor along the vertex's own direction.
    // Three independent per-axis factors shear neighbouring facets against
    // each other and fold them back through the surface, which is the torn
    // -hole artefact DoubleSide was previously papering over.
    const noise = rockFbm3D(
      direction.x * 2.6,
      direction.y * 2.6,
      direction.z * 2.6,
      noiseSeed,
      octaves,
    )
    vertex.multiplyScalar(1 + (noise - 0.5) * 2 * relief)
    for (const cut of cuts) {
      const distance = vertex.dot(cut.n)
      if (distance > cut.d) vertex.addScaledVector(cut.n, cut.d - distance)
    }
    positions.setXYZ(i, vertex.x * radiusX, vertex.y * radiusY, vertex.z * radiusZ)
  }
  positions.needsUpdate = true

  // Angular families keep their facets. Averaging normals across a
  // conchoidal fracture is exactly what would make a sharply cut block read
  // as another rounded blob, whatever its silhouette says.
  if (faceted && geometry.index) {
    const nonIndexed = geometry.toNonIndexed()
    geometry.dispose()
    geometry = nonIndexed
  }
  geometry.computeVertexNormals()
  geometry.computeBoundingSphere()
  return geometry
}

/**
 * Gravel is drawn as instances, so it needs a small fixed set of unit-sized
 * shapes rather than one bespoke geometry per clast. Eight is enough that
 * the repetition is invisible at the sizes and distances involved -- each
 * instance still gets its own semi-axis scaling, yaw and terrain-normal
 * tilt, so two instances of the same variant do not present the same
 * silhouette -- and few enough that the whole ground cover costs eight draw
 * calls instead of the three and a half thousand it would as loose meshes.
 */
const PEBBLE_VARIANT_SHAPES: RockShape[] = [
  'cobble',
  'cobble',
  'cobble',
  'breccia',
  'breccia',
  'slab',
  'cobble',
  'breccia',
]
/** Per-variant instance capacity; overflow is simply not drawn. */
const PEBBLE_VARIANT_CAPACITY = 1024

function buildPebbleVariants(templates: THREE.BufferGeometry[]): THREE.BufferGeometry[] {
  return PEBBLE_VARIANT_SHAPES.map((shape, index) =>
    // Detail 1: a clast this size never covers more than a few pixels, and
    // the shape families read from their silhouette and facets rather than
    // from smoothness at that scale.
    buildRockGeometry(shape, 0x9e3779b1 + index * 0x85ebca6b, 1, 1, 1, templates, 1),
  )
}

const TERRAIN_NET_RINGS = 9
const TERRAIN_NET_AZIMUTH_STEPS = 48

/**
 * A polar wireframe draped over the terrain around the sensor, out to LiDAR
 * range -- the "net" reference point-cloud HUDs overlay on raw returns so
 * the ground reads as a continuous scanned surface instead of loose dots.
 * Vertices reuse sampleTerrainHeight, the same DEM lookup rock placement
 * already relies on, so the net follows the identical surface the rover and
 * rocks sit on. Returns null (skip) for any grid vertex off the loaded DEM
 * window instead of drawing a false point at sea level.
 */
function buildTerrainNetPositions(
  terrain: TerrainField,
  originX: number,
  originZ: number,
  maxRangeM: number,
): Float32Array {
  const ringRadii: number[] = []
  for (let i = 1; i <= TERRAIN_NET_RINGS; i++) {
    ringRadii.push((i / TERRAIN_NET_RINGS) * maxRangeM)
  }
  const grid: Array<Array<THREE.Vector3 | null>> = ringRadii.map((radius) => {
    const row: Array<THREE.Vector3 | null> = []
    for (let j = 0; j < TERRAIN_NET_AZIMUTH_STEPS; j++) {
      const angle = (j / TERRAIN_NET_AZIMUTH_STEPS) * Math.PI * 2
      const x = originX + Math.sin(angle) * radius
      const z = originZ - Math.cos(angle) * radius
      const y = sampleTerrainHeight(terrain, x, z)
      row.push(y === null ? null : new THREE.Vector3(x, y + 0.15, z))
    }
    return row
  })

  const verts: number[] = []
  const pushSegment = (a: THREE.Vector3 | null, b: THREE.Vector3 | null) => {
    if (!a || !b) return
    verts.push(a.x, a.y, a.z, b.x, b.y, b.z)
  }
  for (let i = 0; i < grid.length; i++) {
    for (let j = 0; j < TERRAIN_NET_AZIMUTH_STEPS; j++) {
      pushSegment(grid[i][j], grid[i][(j + 1) % TERRAIN_NET_AZIMUTH_STEPS])
      if (i + 1 < grid.length) pushSegment(grid[i][j], grid[i + 1][j])
    }
  }
  return new Float32Array(verts)
}

// The app's own risk legend (App.tsx LEGEND_ITEMS: Safe/Caution/High/
// Critical), reused here so a close rock reads with the same urgency the
// rest of the UI already assigns to "close/risky" -- one colour language,
// not a second one invented just for this overlay.
const ROCK_DISTANCE_STOPS: Array<[number, number, number]> = [
  [0xee, 0x5a, 0x52], // Critical -- nearest
  [0xf0, 0x9a, 0x4a], // High
  [0xe8, 0xc8, 0x5a], // Caution
  [0x4f, 0xd0, 0x8a], // Safe -- farthest
]

function rockDistanceColor(distance: number, maxRangeM: number): string {
  const t = THREE.MathUtils.clamp(distance / maxRangeM, 0, 1) * (ROCK_DISTANCE_STOPS.length - 1)
  const i0 = Math.floor(t)
  const i1 = Math.min(ROCK_DISTANCE_STOPS.length - 1, i0 + 1)
  const f = t - i0
  const a = ROCK_DISTANCE_STOPS[i0]
  const b = ROCK_DISTANCE_STOPS[i1]
  const r = Math.round(a[0] + (b[0] - a[0]) * f)
  const g = Math.round(a[1] + (b[1] - a[1]) * f)
  const bch = Math.round(a[2] + (b[2] - a[2]) * f)
  return `rgb(${r}, ${g}, ${bch})`
}

const WHEEL_AXIS_VECTORS: Record<'x' | 'y' | 'z', THREE.Vector3> = {
  x: new THREE.Vector3(1, 0, 0),
  y: new THREE.Vector3(0, 1, 0),
  z: new THREE.Vector3(0, 0, 1),
}
function wheelAxisVector(axis: 'x' | 'y' | 'z'): THREE.Vector3 {
  return WHEEL_AXIS_VECTORS[axis]
}

interface RoverWheel {
  /** The wheel node itself; accumulates rolling rotation from identity. */
  spin: THREE.Object3D
  /** Pivot parent holding the wheel's rest transform and its steer angle. */
  steer: THREE.Group
  /** Rolling axis in the wheel's own frame, signed so +angle rolls forward. */
  axis: THREE.Vector3
  /** Rolling radius in METRES, not in the GLB's native units. */
  radiusM: number
  /** Position along the rover's forward axis, metres; sets front vs rear. */
  forwardOffsetM: number
  isFront?: boolean
}

/**
 * How sharply the rover is allowed to change heading, in radians per metre
 * driven. Turning is bound to DISTANCE rather than to elapsed time on
 * purpose: a vehicle's turn radius is a property of the vehicle, so the
 * same corner has to look the same whether the simulation is running at
 * real time or fast-forwarded. 1.2 rad/m is roughly a 0.85 m turn radius --
 * tight, as a four-wheel skid-steer rover is, but not a pivot in place.
 */
const MAX_YAW_RATE_RAD_PER_M = 1.2
/** Steering lock. Beyond this a real linkage binds; visually it just reads
 *  as a wheel snapped sideways. */
const MAX_STEER_RAD = THREE.MathUtils.degToRad(34)

/**
 * How far the planned route floats above the ground it is drawn on. Small
 * enough to read as painted onto the regolith; large enough that the ribbon
 * never z-fights the mesh triangle underneath it.
 */
const ROUTE_RIBBON_LIFT_M = 0.12
/** Half-width of the drawn corridor. ~1.8 m overall: a lane the rover fits. */
const ROUTE_RIBBON_HALF_WIDTH_M = 0.9
/**
 * Route segments are re-sampled to at most this spacing before being drawn.
 * Planned waypoints can sit several metres apart, and a ribbon built only
 * from those chords cuts straight through every rise between them -- it
 * sinks into the hillside going up and lifts off it coming down. Sampling
 * the terrain along the way makes the path hug ground it never had vertices
 * for.
 */
const ROUTE_RESAMPLE_STEP_M = 2

/** Orbit-mode locator exaggeration, and the camera distance below which the
 *  rover is drawn at its true size instead. */
const ROVER_ORBIT_SCALE = 10
const ROVER_TRUE_SCALE_DISTANCE_M = 45

// Scratch objects for the per-update rover pose; allocating a quaternion
// per playback tick is pure garbage at 60 Hz.
const ROVER_UP = new THREE.Vector3(0, 1, 0)
const roverTiltQuaternion = new THREE.Quaternion()
const roverYawQuaternion = new THREE.Quaternion()

/**
 * A minimal image-based lighting probe for an airless surface: black sky
 * above the horizon, regolith bounce below it, nothing else.
 *
 * A glTF metallic-roughness material reflects its environment and almost
 * nothing else -- with no environment bound, `metalness: 1` renders BLACK
 * except for one specular highlight. That is why the rover's metal read as
 * a dark silhouette no matter how bright the sun light was, and why its
 * texture looked like it was not loading. This gives those surfaces
 * something physically defensible to reflect.
 *
 * Deliberately NOT assigned to scene.environment: every MeshStandardMaterial
 * in the scene would then pick it up, and lifting the terrain's shadowed
 * side off zero is exactly what this view's lighting is built to avoid --
 * a lunar shadow gets no fill. It is bound per-material, on the rover only.
 */
function createLunarEnvironment(renderer: THREE.WebGLRenderer): THREE.Texture {
  const width = 64
  const height = 32
  const data = new Float32Array(width * height * 4)
  for (let y = 0; y < height; y++) {
    // +1 straight up, -1 straight down.
    const elevation = Math.cos(((y + 0.5) / height) * Math.PI)
    // Sunlit regolith at ~0.11 reflectance fills the lower hemisphere; the
    // upper hemisphere is vacuum, left barely above zero so a mirror-metal
    // face is not a literal void.
    const bounce = THREE.MathUtils.smoothstep(-elevation, -0.08, 0.5)
    const value = 0.012 + bounce * 0.17
    for (let x = 0; x < width; x++) {
      const index = (y * width + x) * 4
      data[index] = value
      data[index + 1] = value * 0.975
      data[index + 2] = value * 0.94
      data[index + 3] = 1
    }
  }
  const equirect = new THREE.DataTexture(data, width, height, THREE.RGBAFormat, THREE.FloatType)
  equirect.mapping = THREE.EquirectangularReflectionMapping
  equirect.needsUpdate = true
  const pmrem = new THREE.PMREMGenerator(renderer)
  const target = pmrem.fromEquirectangular(equirect)
  equirect.dispose()
  pmrem.dispose()
  return target.texture
}

function createRoverModel(): {
  group: THREE.Group
  lidarHead: THREE.Group
  mast: THREE.Mesh
  chassis: THREE.Mesh
  wheels: THREE.Mesh[]
} {
  const group = new THREE.Group()
  const chassisMaterial = new THREE.MeshStandardMaterial({
    color: 0xd5d9dc,
    roughness: 0.7,
    metalness: 0.22,
  })
  const metalMaterial = new THREE.MeshStandardMaterial({
    color: 0xa7b0b8,
    roughness: 0.38,
    metalness: 0.75,
  })
  const tireMaterial = new THREE.MeshStandardMaterial({
    color: 0x171717,
    roughness: 0.96,
    metalness: 0.05,
  })

  const chassis = new THREE.Mesh(new THREE.BoxGeometry(1.45, 0.42, 1.85), chassisMaterial)
  chassis.position.y = 0.6
  group.add(chassis)

  const wheels: THREE.Mesh[] = []
  for (const x of [-0.88, 0.88]) {
    for (const z of [-0.62, 0.62]) {
      const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.24, 16), tireMaterial)
      wheel.rotation.z = Math.PI / 2
      wheel.position.set(x, 0.34, z)
      group.add(wheel)
      wheels.push(wheel)
    }
  }

  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.065, 0.82, 12), metalMaterial)
  mast.position.y = 1.16
  group.add(mast)

  const lidarHead = new THREE.Group()
  lidarHead.position.y = 1.6
  const lower = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.14, 24), metalMaterial)
  const apertureMaterial = new THREE.MeshBasicMaterial({ color: 0x44ddff })
  const aperture = new THREE.Mesh(new THREE.CylinderGeometry(0.195, 0.195, 0.055, 24, 1, true), apertureMaterial)
  aperture.position.y = 0.01
  lidarHead.add(lower, aperture)
  group.add(lidarHead)

  return { group, lidarHead, mast, chassis, wheels }
}

function disposeObjectTree(root: THREE.Object3D): void {
  const materials = new Set<THREE.Material>()
  root.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return
    object.geometry.dispose()
    const objectMaterials = Array.isArray(object.material) ? object.material : [object.material]
    objectMaterials.forEach((material) => materials.add(material))
  })
  materials.forEach((material) => material.dispose())
}

export interface LocalNavigationRequest {
  current: { row: number; col: number }
  decision: LocalPlanDecision
  /** Bounded local path; present for LOCAL_DETOUR and ends at global rejoin. */
  local_waypoints: Array<{ row: number; col: number }>
  observed_obstacles: Array<{
    row: number
    col: number
    radius_m: number
    confidence: number
    observed_at_s: number
    source: 'lidar'
  }>
}

interface Props {
  viewMode: MapViewMode
  waypoints: Waypoint[] | null
  /** Playback pose; the rover and its local LiDAR follow this waypoint. */
  activeWaypoint: Waypoint | null
  /**
   * Progress (0-1) from activeWaypoint toward the next waypoint in the
   * array, driven by the backend's own real elapsed_hours timeline so the
   * rover eases smoothly between the (often several-metre-apart) planned
   * nodes instead of visibly snapping from one to the next.
   */
  roverFraction?: number
  /**
   * True while the App-level playback clock is actively advancing the
   * rover. The backend's /api/lidar-scan does a real ray-march per call and
   * measures ~4.7 s end to end -- far slower than any waypoint-to-waypoint
   * interval during compressed playback, so every fetch fired while moving
   * gets superseded and aborted before it resolves, and the point cloud
   * never visibly updates until the drive stops. While isPlaying is true,
   * the local raycast fallback (already used when the backend errors) is
   * used deliberately instead, purely for its speed, so LiDAR stays visibly
   * live during the drive; the slower, terrain-accurate backend scan takes
   * back over the moment the rover settles.
   */
  isPlaying?: boolean
  exaggeration: number | null
  sliceIndex: number
  /** Drape the real NAC photograph instead of shading a flat albedo. */
  photo: boolean
  /** Mirrors MapCanvas's own start/goal picker so both views share one flow. */
  clickMode?: ClickMode
  onCellClick?: (row: number, col: number) => void
  /** Invoked once for a bounded local detour or a safe-stop replan. */
  onLocalNavigation?: (request: LocalNavigationRequest) => void
  /**
   * Fullscreen is owned by App.tsx because the element that goes fullscreen
   * is .map-stage -- this canvas's parent, and the shared parent of the
   * telemetry HUD and photo-drape controls. This view only renders the
   * button, since the 3-D scene is where a bigger viewport actually buys
   * something.
   */
  fullscreen?: boolean
  /** False where the Fullscreen API is missing or blocked; hides the button. */
  canFullscreen?: boolean
  onToggleFullscreen?: () => void
  onReady?: (info: {
    slices: number
    timeVarying: boolean
    sun: SunSample[]
    photoAvailable: boolean
    /** Slice with the most ground lit -- where the view should open. */
    brightestSlice: number
  }) => void
  onError?: (message: string) => void
}

export default function TerrainCanvas3D({
  viewMode,
  waypoints,
  activeWaypoint,
  roverFraction = 0,
  isPlaying = false,
  exaggeration,
  sliceIndex,
  photo,
  clickMode,
  onCellClick,
  onLocalNavigation,
  fullscreen = false,
  canFullscreen = false,
  onToggleFullscreen,
  onReady,
  onError,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  // Preserve the original berke-3d presentation: enter at rover height with
  // the route stretching across the terrain. The live-gradient camera setup
  // below keeps that view safe when the DEM window changes.
  const [cameraMode, setCameraMode] = useState<'fps' | 'orbit'>('fps')
  const [lidarEnabled, setLidarEnabled] = useState(true)
  const [lidarTelemetry, setLidarTelemetry] = useState<LidarScanSummary | null>(null)
  const [localNavigation, setLocalNavigation] = useState<{
    observedObstacles: number
    occupiedCells: number
    decision: LocalPlanDecision
  } | null>(null)
  // Real NASA Astromaterials 3D lunar sample scans (decimated offline --
  // see frontend/simplify_rock.mjs -- from ~100k verts down to a few
  // hundred), used as the rock field's shape templates once they arrive.
  // A ref, not state holding the geometries themselves: they are mutated
  // in place by nothing, read by the rock-generation effect on demand, and
  // do not need to trigger a re-render on their own -- rockTemplatesReady
  // is the flag that does that, exactly once, when loading finishes.
  const rockTemplatesRef = useRef<THREE.BufferGeometry[]>([])
  const [rockTemplatesReady, setRockTemplatesReady] = useState(false)
  /** Textured Apollo sample meshes for rendering; LiDAR keeps its low-poly proxies. */
  const rockVisualTemplatesRef = useRef<ScannedRockVisualTemplate[]>([])
  const [rockVisualTemplatesReady, setRockVisualTemplatesReady] = useState(false)
  // Populated once the rover GLB loads (viper_rover.glb ships wheel_1/
  // wheel_2/wheek_3/wheel_4 as separate child nodes of rover_body, unlike
  // the earlier single fused-mesh export). Each wheel's own spin axis and
  // radius are measured from its geometry rather than assumed, since
  // nothing about an AI-generated asset guarantees a particular convention.
  const wheelsRef = useRef<RoverWheel[]>([])
  /** Front-to-rear axle separation in metres, measured off whichever model
   *  actually loaded; feeds the Ackermann steering angle. */
  const wheelbaseRef = useRef(0.8)
  /** Smoothed heading and steer angle, so the rover arcs into a turn the way
   *  a vehicle does instead of teleporting its yaw at every A* node. */
  const roverHeadingRef = useRef<number | null>(null)
  const roverSteerRef = useRef(0)
  /** The render loop needs the current camera mode, and it is set up once in
   *  an effect that must not re-run every time the mode changes. */
  const cameraModeRef = useRef(cameraMode)
  cameraModeRef.current = cameraMode
  const lastRoverGroundPosRef = useRef<{ x: number; z: number } | null>(null)
  // A new route jumps the rover from wherever it was idling straight to the
  // route's start node -- a real position change, but not one any wheel
  // ever rolled through. Tracking which waypoints array the last position
  // update saw lets that one jump be recognised and excluded from the
  // distance fed into the wheel-spin calculation below, instead of reading
  // as the rover having already driven however many hundred metres separate
  // the two points before the drive even starts.
  const lastRoverRouteRef = useRef<Waypoint[] | null | undefined>(undefined)
  // Throttle (not debounce) state for the rock/LiDAR effect below: during
  // active route playback activeWaypoint changes every ~50 ms, far faster
  // than a 300 ms silence-based debounce ever goes quiet, so a pure debounce
  // never fires until the rover stops -- the scan reads as frozen/fake while
  // driving. Tracking the last actual run lets it fire on a fixed cadence
  // instead, so LiDAR keeps refreshing throughout the drive.
  const lastLidarRunRef = useRef(0)
  // A stopped rover keeps scanning. Deduplicate the same obstacle snapshot so
  // a 5 Hz LiDAR cannot issue a replan storm while the request is in flight.
  const lastLocalStopKeyRef = useRef<string | null>(null)
  // The boulder garden belongs to one world-space patch. Its anchor is set
  // once from the initial scene pose and deliberately survives route changes,
  // replans and rover playback; rocks are terrain, not a route effect.
  const fixedRockAnchorRef = useRef<{ x: number; z: number } | null>(null)
  /** The mesh.scale.z the fixed cluster was last seated against. */
  const lastRockFieldScaleRef = useRef<number | null>(null)
  /**
   * How many scanned Apollo visuals existed when the cluster was last built.
   *
   * The GLBs download on a 1.2 s delay -- deliberately, so they do not
   * compete with the terrain for the first frame -- which is always AFTER
   * the boulders are first placed. Without this the cluster stayed built
   * against zero templates and every boulder kept its low-poly collision
   * proxy as its visible mesh: the scans loaded, reported no error, and
   * never reached the screen. The effect did re-run when they arrived; its
   * body simply had no reason to rebuild.
   */
  const lastRockFieldVisualCountRef = useRef(0)
  /**
   * The live route ribbon's shader and its arc-length table. The render loop
   * animates uTime/uProgress through this rather than through React state --
   * a uniform write per frame must not cost a re-render.
   */
  const routeRibbonRef = useRef<{
    material: THREE.ShaderMaterial
    distances: number[]
    totalLength: number
  } | null>(null)
  /**
   * Metres of route already driven, or -1 before a drive starts. Feeds the
   * ribbon's uProgress so the trail behind the rover dims. A ref, not state:
   * the render loop reads it every frame.
   */
  const routeProgressRef = useRef(-1)
  // Where the gravel layer was last built. Unlike the navigation rocks --
  // anchored to the route so they stay put while the rover drives past --
  // gravel is a distance-graded LOD around the sensor and has to follow it,
  // so it is rebuilt on real movement rather than on every throttle tick.
  const lastPebbleOriginRef = useRef<{ x: number; z: number } | null>(null)
  /** Last cell shown by the live endpoint cursor. Pointer-up reuses it so
   * the visible marker and the committed Start/Goal cannot disagree. */
  const selectionPreviewRef = useRef<{
    row: number
    col: number
    clientX: number
    clientY: number
  } | null>(null)

  // The raw NAC crop still carries its own 2010 grazing-light shadow
  // micro-texture (see PHOTO_TEXTURE_URL's own comment on why it is drawn
  // unlit). That reads as fine crater texture from an orbit-scale view, but
  // magnified to FPS eye height the same texels become visible streaks -- the
  // photo just is not shot at a resolution meant to be stood on. The DETAIL
  // texture divides that illumination back out and is re-lit dynamically, so
  // FPS always uses it regardless of the toggle; the checkbox only controls
  // what orbit view drapes.
  const effectivePhoto = photo && cameraMode === 'orbit'

  const sceneRef = useRef<{
    mesh: THREE.Mesh
    material: THREE.MeshStandardMaterial
    sun: THREE.DirectionalLight
    manifest: TerrainManifest
    series: SeriesManifest | null
    shadowCube: Float32Array | null
    baseColors: Float32Array
    lightMask: Float32Array | null
    photoTexture: THREE.Texture | null
    detailTexture: THREE.Texture | null
    regolithTexture: THREE.CanvasTexture
    photoAvailable: boolean
    routeGroup: THREE.Group
    selectionCursor: ReturnType<typeof createTerrainSelectionCursor>
    endpointMarkers: Record<Exclude<ClickMode, 'idle'>, ReturnType<typeof createTerrainSelectionCursor>>
    rockGroup: THREE.Group
    /** Low-poly collision meshes only; never render the same GLB geometry in a LiDAR scan. */
    lidarRockMeshes: THREE.Mesh[]
    /** One InstancedMesh per gravel variant; see buildPebbleVariants. */
    pebbleMeshes: THREE.InstancedMesh[]
    rockMaterial: THREE.MeshStandardMaterial
    /** Draw-invisible but raycastable material used by GLB collision proxies. */
    lidarProxyMaterial: THREE.MeshBasicMaterial
    rockTexture: THREE.Texture
    roverGroup: THREE.Group
    lidarHead: THREE.Group
    lidarPoints: THREE.Points
    lidarSweep: THREE.LineSegments
    lidarScan: LidarScanResult | null
    lidarOrigin: THREE.Vector3
    lidarRevolutionStartedAt: number
    terrainNet: THREE.LineSegments
    rockBoxContainer: HTMLDivElement
    rockBoxPool: HTMLDivElement[]
    sunSprite?: THREE.Sprite
    camera?: THREE.PerspectiveCamera
    controls?: OrbitControls
    heights?: Float32Array
    dispose: () => void
  } | null>(null)

  // ── Scene construction. Runs once; layer/slice changes are handled below. ──
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    let disposed = false
    let visualRockLoadTimer: number | null = null
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x020308)

    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100000)
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

    // The real sky, built after the renderer because star sizes are in pixels
    // and it owns the device pixel ratio. The catalogue loads in the
    // background; the scene does not wait on it.
    const skyAbort = new AbortController()
    const sky = createSky(renderer.getPixelRatio(), skyAbort.signal)
    scene.add(sky.group)
    sky.ready.catch((error: unknown) => {
      if (skyAbort.signal.aborted) return
      // A sky that fails to load costs the scene its backdrop and nothing
      // else, so it is reported rather than thrown -- the terrain, the route
      // and the rover are all still there to fly.
      console.error('[sky] star catalogue unavailable', error)
    })
    renderer.outputColorSpace = THREE.SRGBColorSpace
    // No tone mapping: the point of this scene is a hard terminator between
    // lit and unlit ground, and a filmic curve lifts the black side off zero.
    renderer.toneMapping = THREE.NoToneMapping
    container.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.08

    // Airless body: a shadow gets no fill. The small non-zero term is earthshine
    // and scattered light off nearby slopes, kept just high enough that a fully
    // shadowed cell reads as "dark surface" rather than "hole in the render".
    scene.add(new THREE.AmbientLight(0xc8cede, 0.1))

    // Near-white, not the warm 0xfff4e0 a terrestrial scene wants: the Sun's
    // colour on an airless body is not filtered through an atmosphere, and a
    // warm key over a warm ramp is what turned this view orange. Lunar imagery
    // is grey because the light is white and the ground is grey.
    //
    // The intensity is high for a physical reason, not to "brighten it up".
    // Lambert diffuse is a poor model for regolith: the real surface is
    // strongly backscattering (Lommel-Seeliger plus an opposition surge), so
    // at the grazing incidence of a polar site Lambert predicts a surface
    // several times darker than photographs show. Rather than compile a custom
    // BRDF, the intensity compensates for that known underestimate.
    const sun = new THREE.DirectionalLight(0xfff6ee, 3.6)
    scene.add(sun)

    const routeGroup = new THREE.Group()
    scene.add(routeGroup)

    // Local, metre-scale geometry fills the sensing gap left by the orbital
    // DEM. These objects are rebuilt around the rover from stable world-chunk
    // seeds, so they remain fixed when the rover advances along a route.
    const rockTexture = createRockTexture()
    const rockMaterial = new THREE.MeshStandardMaterial({
      // Slightly brighter than SURFACE_ALBEDO: an exposed rock face has not
      // been space-weathered and darkened the way the surrounding soil has.
      color: 0x9a938a,
      map: rockTexture,
      roughness: 1,
      metalness: 0,
      // Smooth (not flat) shading: the NASA scan templates and the
      // icosahedron fallback both carry proper computeVertexNormals()
      // output, and interpolating between them is what keeps a few hundred
      // triangles reading as a rounded rock instead of a faceted gemstone.
      flatShading: false,
      // Defensive, not decorative: vertex displacement can fold a facet back
      // on itself, flipping its winding relative to the camera. FrontSide
      // culls that facet outright, which reads as a torn hole with the void
      // showing through. DoubleSide costs nothing visible on a convex rock
      // and guarantees no gaps.
      side: THREE.DoubleSide,
    })
    // ~1.6 texture repeats per metre of world, so a 40 cm cobble and a 4 m
    // block carry grain at the same physical scale instead of one looking
    // like sandpaper and the other like a smooth boulder.
    applyTriplanarMapping(rockMaterial, 1.6)
    // Object3D.visible=false removes a mesh from Three.js raycasts too. The
    // proxy therefore stays object-visible and only its material is hidden,
    // so LiDAR can still intersect it when a scanned visual replaces it.
    const lidarProxyMaterial = new THREE.MeshBasicMaterial({
      visible: false,
      side: THREE.DoubleSide,
    })
    const rockGroup = new THREE.Group()
    scene.add(rockGroup)

    // Sub-navigation-size gravel. Allocated empty (count 0) and filled as
    // the rover moves; the geometries are swapped in once the scan
    // templates resolve, since the variants that use them cannot be built
    // before then.
    const pebbleMeshes: THREE.InstancedMesh[] = buildPebbleVariants([]).map((geometry) => {
      const mesh = new THREE.InstancedMesh(geometry, rockMaterial, PEBBLE_VARIANT_CAPACITY)
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
      mesh.count = 0
      // Instances sit at real world positions, so the mesh itself never
      // moves and its own bounds would be computed from the base geometry
      // at the origin. Frustum culling on that would blink the whole gravel
      // layer out whenever the origin left the view.
      mesh.frustumCulled = false
      scene.add(mesh)
      return mesh
    })

    const solidDotTexture = createSolidDotTexture()

    const regolithTexture = createRegolithTexture()

    const roverEnvironment = createLunarEnvironment(renderer)
    const rover = createRoverModel()
    scene.add(rover.group)
    // The physical sensor mast/dome is not shown -- it stays in the scene
    // graph (its rotation still drives the animated sweep fan below) but
    // never renders. Nothing else reads its visibility, so setting it once
    // here is enough regardless of the lidarEnabled toggle or camera mode.
    rover.mast.visible = false
    rover.lidarHead.visible = false

    // NASA VIPER's published footprint -- about the size of a golf cart,
    // 1.5 x 1.5 x 2.5 m (L x W x H). The GLB is an AI-generated asset at an
    // arbitrary native scale, not metres, so it is uniformly rescaled here
    // so its longest horizontal dimension becomes this rover's real length.
    // "True to scale" means it reads correctly next to the 0.3-2 m rocks
    // and the physically-scaled terrain, not a claim that every proportion
    // is a laser-measured replica of the real rover.
    const ROVER_MODEL_LENGTH_M = 1.5

    const findFirstMesh = (object: THREE.Object3D): THREE.Mesh | null => {
      if (object instanceof THREE.Mesh) return object
      for (const child of object.children) {
        const found = findFirstMesh(child)
        if (found) return found
      }
      return null
    }

    const configureRoverModel = (model: THREE.Group) => {
      const box = new THREE.Box3().setFromObject(model)
      const size = box.getSize(new THREE.Vector3())
      const center = box.getCenter(new THREE.Vector3())
      // Recentre horizontally and drop the model so its own lowest point
      // sits at local y=0 -- the ground-contact point every other rover
      // placement in this file already assumes.
      model.position.x -= center.x
      model.position.z -= center.z
      model.position.y -= box.min.y
      const longestHorizontal = Math.max(size.x, size.z)
      const scale = longestHorizontal > 1e-6 ? ROVER_MODEL_LENGTH_M / longestHorizontal : 1
      model.scale.setScalar(scale)
      // This file's heading math (see the rover-position effect) drives the
      // rover group's orientation assuming the model's own forward axis is
      // local +Z -- an assumption the GLB has no reason to satisfy, since it
      // is an arbitrary generated asset. Measuring which horizontal axis it
      // is actually longest along and rotating the MODEL (not the group,
      // which the per-frame heading logic owns) to put that axis on +Z
      // corrects it once, at load time.
      if (size.x > size.z) {
        model.rotation.y = Math.PI / 2
      }
      const scaledHeight = size.y * scale
      model.traverse((child) => {
        if (!(child instanceof THREE.Mesh)) return
        const materials = Array.isArray(child.material) ? child.material : [child.material]
        for (const material of materials) {
          if (!(material instanceof THREE.MeshStandardMaterial)) continue
          material.envMap = roverEnvironment
          material.needsUpdate = true
        }
      })
      rover.group.add(model)
      rover.group.updateMatrixWorld(true)

      // ── Wheels ──────────────────────────────────────────────────────────
      // Three things have to be true before a wheel can be made to turn the
      // way a vehicle's does, and none of them were:
      //
      //  1. The node has to pivot on its own axle. The source asset gives
      //     every wheel node an identity transform while its geometry sits
      //     out at a corner, so rotating the node swung the wheel in a wide
      //     arc around the middle of the rover instead of spinning it. The
      //     split asset fixes this at build time (frontend/scripts/
      //     split_rover_glb.mjs); recentring here as well means the legacy
      //     fallback asset behaves too, and neither depends on the other.
      //  2. The rolling radius has to be in METRES. It was read straight off
      //     the geometry's own bounding box, in the GLB's arbitrary native
      //     units, and then divided into a distance in metres -- so the
      //     wheels turned at 1/scale of the right rate (about 19% slow).
      //  3. Spin and steer cannot share one transform. Roll accumulates and
      //     steer is absolute; composing both on the same node makes each
      //     one corrupt the other. Every wheel gets a steering pivot parent.
      const wheels: RoverWheel[] = []
      const wheelCentre = new THREE.Vector3()
      const groupRight = new THREE.Vector3()
      model.traverse((child) => {
        // The legacy GLB misspells one of the four as "wheek_3" -- matching
        // just the "whee" stem catches that typo along with every correctly
        // spelled wheel node.
        if (!/whee[lk]/i.test(child.name)) return
        const mesh = findFirstMesh(child)
        if (!mesh) return
        mesh.geometry.computeBoundingBox()
        const bb = mesh.geometry.boundingBox
        if (!bb) return

        // (1) Move the geometry onto its own centre and push the offset up
        // into the node, so the node pivots on the axle.
        bb.getCenter(wheelCentre)
        if (wheelCentre.lengthSq() > 1e-10) {
          mesh.geometry.translate(-wheelCentre.x, -wheelCentre.y, -wheelCentre.z)
          mesh.position.add(wheelCentre)
          mesh.geometry.computeBoundingBox()
        }

        // A wheel is a thin disc, so whichever of its own local extents is
        // smallest is the axle direction; the two larger ones give the
        // rolling diameter.
        const extents = {
          x: bb.max.x - bb.min.x,
          y: bb.max.y - bb.min.y,
          z: bb.max.z - bb.min.z,
        }
        const axisName = (Object.keys(extents) as Array<'x' | 'y' | 'z'>).reduce((a, b) =>
          extents[a] < extents[b] ? a : b,
        )
        const diameters = (Object.keys(extents) as Array<'x' | 'y' | 'z'>)
          .filter((key) => key !== axisName)
          .map((key) => extents[key])
        // (2) Native units -> metres. The model scale is uniform, so one
        // factor converts the whole thing.
        const radiusM = ((diameters[0] + diameters[1]) / 4) * scale

        // (3) A steering pivot between the wheel and its parent, taking over
        // the wheel's rest transform so the wheel node itself is free to
        // accumulate roll from identity.
        const steer = new THREE.Group()
        steer.name = `${child.name}_steer`
        steer.position.copy(child.position)
        steer.quaternion.copy(child.quaternion)
        steer.scale.copy(child.scale)
        const parent = child.parent ?? model
        parent.add(steer)
        child.position.set(0, 0, 0)
        child.quaternion.identity()
        child.scale.set(1, 1, 1)
        steer.add(child)
        steer.updateMatrixWorld(true)

        // Which way is "roll forward"? A wheel whose axle points along the
        // rover's right rolls forward under a POSITIVE rotation about that
        // axle (right-hand rule with +Y up, +Z forward). Measuring the
        // axle's actual world direction against the rover's right, rather
        // than assuming it, means an asset exported with either handedness
        // rolls the correct way instead of visibly spinning backwards.
        const axis = wheelAxisVector(axisName).clone()
        const worldAxis = axis.clone().transformDirection(child.matrixWorld)
        groupRight.set(1, 0, 0).transformDirection(rover.group.matrixWorld).normalize()
        if (worldAxis.dot(groupRight) < 0) axis.negate()

        const localPosition = steer.getWorldPosition(new THREE.Vector3())
        rover.group.worldToLocal(localPosition)
        wheels.push({
          spin: child,
          steer,
          axis,
          radiusM: radiusM > 1e-3 ? radiusM : 0.13,
          forwardOffsetM: localPosition.z,
        })
      })
      // Front wheels are the ones ahead of the wheel group's own centre, so
      // "front" comes from the geometry rather than from node names the
      // legacy asset does not provide.
      const forwardMid =
        wheels.reduce((sum, wheel) => sum + wheel.forwardOffsetM, 0) / Math.max(wheels.length, 1)
      for (const wheel of wheels) wheel.isFront = wheel.forwardOffsetM >= forwardMid
      // Wheelbase drives the Ackermann steering angle below; measured, not
      // assumed, so it is right for whichever asset actually loaded.
      const frontOffsets = wheels.filter((w) => w.isFront).map((w) => w.forwardOffsetM)
      const rearOffsets = wheels.filter((w) => !w.isFront).map((w) => w.forwardOffsetM)
      wheelbaseRef.current =
        frontOffsets.length > 0 && rearOffsets.length > 0
          ? Math.abs(
              frontOffsets.reduce((a, b) => a + b, 0) / frontOffsets.length -
                rearOffsets.reduce((a, b) => a + b, 0) / rearOffsets.length,
            )
          : ROVER_MODEL_LENGTH_M * 0.55
      wheelsRef.current = wheels

      // The procedural chassis/wheels are hidden, not removed: the mast and
      // LiDAR head stay the exact objects the sweep animation and the
      // orbit-mode scale toggle already reference, just resized and
      // repositioned onto the new body's roofline instead of the
      // placeholder box's.
      rover.chassis.visible = false
      rover.wheels.forEach((wheel) => {
        wheel.visible = false
      })
      const mastMaterial = rover.mast.material
      if (mastMaterial instanceof THREE.MeshStandardMaterial) {
        mastMaterial.envMap = roverEnvironment
        mastMaterial.needsUpdate = true
      }
      const sensorScale = 0.55
      rover.mast.scale.setScalar(sensorScale)
      rover.lidarHead.scale.setScalar(sensorScale)
      const mastHeight = 0.82 * sensorScale
      rover.mast.position.y = scaledHeight + mastHeight / 2
      rover.lidarHead.position.y = scaledHeight + mastHeight + 0.03 * sensorScale
    }

    // The textured, wheel-split asset first; the original untextured split
    // asset is kept as a fallback so a failed or missing build artefact
    // degrades to a rover that still drives rather than to no rover at all.
    const loadRover = (urls: string[]) => {
      const [url, ...rest] = urls
      if (!url) {
        console.warn('No rover GLB loaded, keeping the procedural placeholder')
        return
      }
      new GLTFLoader().load(
        url,
        (gltf) => {
          if (disposed) return
          configureRoverModel(gltf.scene)
        },
        undefined,
        () => {
          if (disposed) return
          console.warn(`Rover GLB ${url} failed to load, trying the next candidate`)
          loadRover(rest)
        },
      )
    }
    loadRover(['/models/viper-rover-textured.glb', '/models/viper-rover.glb'])

    // Real rock shapes, loaded once. Failure (or simply not being loaded
    // yet the first time the rock field below builds) leaves
    // rockTemplatesRef empty, and that effect falls back to the procedural
    // icosahedron -- never a blocking dependency.
    Promise.all(NASA_ROCK_TEMPLATE_URLS.map(fetchRockGeometryTemplate)).then((results) => {
      if (disposed) return
      const templates = results.filter((geometry): geometry is THREE.BufferGeometry => geometry !== null)
      if (templates.length === 0) {
        console.warn('No NASA rock templates loaded; using procedural rocks throughout')
        return
      }
      rockTemplatesRef.current = templates
      // The gravel variants were built before the templates existed, so the
      // 'scan'-family slots fell back to procedural shapes. Rebuild them now
      // that real ones are available; the instance matrices are untouched.
      const upgraded = buildPebbleVariants(templates)
      pebbleMeshes.forEach((mesh, index) => {
        mesh.geometry.dispose()
        mesh.geometry = upgraded[index]
      })
      setRockTemplatesReady(true)
    })

    const lidarPointGeometry = new THREE.BufferGeometry()
    const lidarPointMaterial = new THREE.PointsMaterial({
      map: solidDotTexture,
      size: 5.5,
      // Screen-space dots stay legible in orbit view; their world positions
      // and occlusion are still fully metric.
      sizeAttenuation: false,
      vertexColors: true,
      transparent: true,
      opacity: 0.92,
      depthWrite: false,
      // NOT additive: the jet ramp below encodes real elevation, and additive
      // blending washes overlapping points toward white, destroying exactly
      // the colour a height ramp exists to show. Normal blending keeps each
      // point's true colour, the way CloudCompare/RViz/PDAL render one.
    })
    const lidarPoints = new THREE.Points(lidarPointGeometry, lidarPointMaterial)
    lidarPoints.renderOrder = 4
    scene.add(lidarPoints)

    // A faint polar grid draped over the terrain within scan range -- the
    // "net" every reference point-cloud viewer overlays on top of raw
    // returns so the surface reads as a continuous mesh, not just scattered
    // dots. Built alongside the point cloud in the debounced rock/lidar
    // effect below; empty until the first scan lands.
    const terrainNetMaterial = new THREE.LineBasicMaterial({
      color: 0x8fd8ff,
      transparent: true,
      opacity: 0.35,
      depthWrite: false,
    })
    const terrainNet = new THREE.LineSegments(new THREE.BufferGeometry(), terrainNetMaterial)
    terrainNet.renderOrder = 3
    terrainNet.visible = false
    scene.add(terrainNet)

    // Screen-space "ROCK 7.4 m" perception boxes: a plain HTML overlay
    // (not CSS2DObject) because each box's on-screen SIZE, not just its
    // position, has to track the rock's projected silhouette every frame --
    // an object-detection look, not a fixed-size label pinned to a point.
    // Pooled and reused rather than recreated per frame.
    const rockBoxContainer = document.createElement('div')
    rockBoxContainer.className = 'terrain3d-rockbox-layer'
    container.appendChild(rockBoxContainer)
    const rockBoxPool: HTMLDivElement[] = []

    const sweepGeometry = new THREE.BufferGeometry()
    sweepGeometry.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(LIDAR_CONFIG.elevationAnglesDeg.length * 2 * 3), 3),
    )
    const lidarSweep = new THREE.LineSegments(
      sweepGeometry,
      new THREE.LineBasicMaterial({
        color: 0x5ff4ff,
        transparent: true,
        opacity: 0.34,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    )
    lidarSweep.renderOrder = 3
    scene.add(lidarSweep)

    let frame = 0
    const onResize = () => {
      const { clientWidth: w, clientHeight: h } = container
      if (!w || !h) return
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h, false)
    }
    const observer = new ResizeObserver(onResize)
    observer.observe(container)

    const build = async () => {
      const manifest: TerrainManifest = await (await fetch('/api/terrain')).json()
      if (disposed) return
      // A NAC crop is only valid on the exact georeferenced window it was cut
      // from. Other DEM windows receive the neutral procedural regolith map.
      const photoAvailable = hasAlignedNacTexture(manifest)
      const { rows, cols, resolution_m: res } = manifest.grid
      const { min_m: minM } = manifest.elevation

      const heights = await fetchF32(manifest.layers.elevation.binary_url)
      if (disposed) return

      // PlaneGeometry's vertex order is row-major from the top-left, which is
      // exactly the binary layout -- index i in the payload is vertex i here.
      const geometry = new THREE.PlaneGeometry(cols * res, rows * res, cols - 1, rows - 1)
      const position = geometry.attributes.position
      for (let i = 0; i < heights.length; i++) {
        const h = heights[i]
        // A single NaN vertex drops the whole mesh from the render. Pin to base.
        position.setZ(i, (Number.isNaN(h) ? minM : h) - minM)
      }
      position.needsUpdate = true
      geometry.computeVertexNormals()
      geometry.setAttribute(
        'color',
        new THREE.BufferAttribute(new Float32Array(rows * cols * 3), 3),
      )

      const material = new THREE.MeshStandardMaterial({
        vertexColors: true,
        roughness: 0.97,
        metalness: 0.0,
      })

      const mesh = new THREE.Mesh(geometry, material)
      mesh.rotation.x = -Math.PI / 2 // +Z becomes height; row 0 falls to -Z (north)
      scene.add(mesh)

      const selectionCursor = createTerrainSelectionCursor(res)
      scene.add(selectionCursor.group)
      const endpointMarkers = {
        start: createTerrainSelectionCursor(res),
        goal: createTerrainSelectionCursor(res),
      }
      endpointMarkers.start.group.name = 'terrain-start-selection-marker'
      endpointMarkers.goal.group.name = 'terrain-goal-selection-marker'
      endpointMarkers.start.setMode('start')
      endpointMarkers.goal.setMode('goal')
      scene.add(endpointMarkers.start.group, endpointMarkers.goal.group)

      // The illumination series is optional: without NAIF kernels or the
      // horizon cube the backend says so rather than faking it, and the scene
      // still renders under a fixed light.
      let series: SeriesManifest | null = null
      let shadowCube: Float32Array | null = null
      try {
        series = await (await fetch(`/api/illumination-series?${SERIES_QUERY}`)).json()
        if (series && series.shadow_model.time_varying) {
          shadowCube = await fetchF32(series.fields.shadow.binary_url)
        }
      } catch {
        series = null
      }
      const span = Math.max(rows, cols) * res

      // The Earth in deep space hovering above the lunar horizon
      const earth = createEarth(span)
      scene.add(earth.group)

      // Blazing distant solar flare sprite
      const sunFlare = createSunFlareSprite()
      scene.add(sunFlare)
      sunFlare.position.copy(sun.position).normalize().multiplyScalar(55000)

      // Frame from the live relief so changing DEM windows cannot place the
      // overview camera inside a ridge or point it below the terrain.
      const relief = manifest.elevation.max_m - manifest.elevation.min_m
      const targetY = relief * 0.35
      camera.position.set(
        span * 0.72,
        Math.max(targetY + span * 0.75, relief + span * 0.45),
        span * 0.75,
      )
      controls.target.set(0, targetY, 0)
      controls.minDistance = 12
    // Zoom toward whatever is under the pointer, not toward the middle of
    // the map. Dollying at a fixed scene-centre target meant that trying to
    // get a closer look at the rover -- which is almost never at the centre
    // -- flew the camera past it and under the terrain instead.
    controls.zoomToCursor = true
      controls.maxDistance = span * 4.0
      controls.update()

      sceneRef.current = {
        mesh,
        material,
        sun,
        manifest,
        series,
        shadowCube,
        baseColors: new Float32Array(rows * cols * 3),
        lightMask: null,
        photoTexture: null,
        detailTexture: null,
        regolithTexture,
        photoAvailable,
        routeGroup,
        selectionCursor,
        endpointMarkers,
      rockGroup,
      lidarRockMeshes: [],
        pebbleMeshes,
        rockMaterial,
        lidarProxyMaterial,
        rockTexture,
        roverGroup: rover.group,
        lidarHead: rover.lidarHead,
        lidarPoints,
        lidarSweep,
        lidarScan: null,
        lidarOrigin: new THREE.Vector3(),
        lidarRevolutionStartedAt: performance.now(),
        terrainNet,
        rockBoxContainer,
        rockBoxPool,
        sunSprite: sunFlare,
        camera,
        controls,
        heights,
        dispose: () => {
          geometry.dispose()
          material.dispose()
          selectionCursor.dispose()
          endpointMarkers.start.dispose()
          endpointMarkers.goal.dispose()
          skyAbort.abort()
          sky.dispose()
          earth.sprite.material.map?.dispose()
          earth.sprite.material.dispose()
          rockGroup.children.forEach((rock) => {
            if (rock instanceof THREE.Mesh && !rock.userData.scannedApolloRock) rock.geometry.dispose()
          })
          pebbleMeshes.forEach((mesh) => {
            mesh.geometry.dispose()
            mesh.dispose()
          })
          roverEnvironment.dispose()
          rockMaterial.dispose()
          lidarProxyMaterial.dispose()
          rockTexture.dispose()
          regolithTexture.dispose()
          solidDotTexture.dispose()
          rockTemplatesRef.current.forEach((geometry) => geometry.dispose())
          rockTemplatesRef.current = []
          rockVisualTemplatesRef.current.forEach((template) => {
            template.geometry.dispose()
            template.material.dispose()
          })
          rockVisualTemplatesRef.current = []
          disposeObjectTree(rover.group)
          lidarPointGeometry.dispose()
          lidarPointMaterial.dispose()
          sweepGeometry.dispose()
          ;(lidarSweep.material as THREE.Material).dispose()
          terrainNet.geometry.dispose()
          terrainNetMaterial.dispose()
          rockBoxContainer.remove()
          sceneRef.current?.photoTexture?.dispose()
          sceneRef.current?.detailTexture?.dispose()
        },
      }

      // Which slice shows the most ground? At a polar site the answer is not
      // "the first one": this window opens 2026-09-07 fully shadowed and only
      // crosses the terminator days later, so defaulting the slider to 0 hands
      // the user a black scene and no clue that the terrain is behind a slider.
      let brightestSlice = 0
      if (shadowCube && series) {
        const [T, sr, sc] = series.binary_format.shape
        let best = -1
        for (let t = 0; t < T; t++) {
          let lit = 0
          const base = t * sr * sc
          for (let i = 0; i < sr * sc; i++) if (shadowCube[base + i] < 0.5) lit++
          if (lit > best) {
            best = lit
            brightestSlice = t
          }
        }
      }

      onResize()
      setStatus('ready')
      onReady?.({
        slices: series?.slices ?? 0,
        timeVarying: Boolean(series?.shadow_model.time_varying),
        sun: series?.sun ?? [],
        photoAvailable,
        brightestSlice,
      })

      // The terrain must become interactive before optional presentation
      // assets start downloading or parsing. Loading one scan at a time also
      // avoids a burst of GLB decoding and texture uploads competing with the
      // terrain, sky and rover on the first frame.
      visualRockLoadTimer = window.setTimeout(() => {
        void (async () => {
          const templates: ScannedRockVisualTemplate[] = []
          for (const url of NASA_ROCK_GLB_URLS) {
            if (disposed) return
            const template = await loadScannedRockVisualTemplate(url)
            if (template) templates.push(template)
            // Yield between models so a slow device can keep painting.
            await new Promise<void>((resolve) => window.setTimeout(resolve, 0))
          }
          if (disposed) return
          if (templates.length === 0) {
            console.warn('No textured Apollo rock GLBs loaded; keeping the low-poly NASA rock proxies visible')
            return
          }
          rockVisualTemplatesRef.current = templates
          setRockVisualTemplatesReady(true)
        })()
      }, 1200)
    }

    build().catch((error: unknown) => {
      if (disposed) return
      setStatus('error')
      onError?.(error instanceof Error ? error.message : String(error))
    })

    // Perception-style "ROCK 7.4 m" boxes, screen-projected fresh every
    // frame so their on-screen size and position track the live camera --
    // unlike the corner telemetry panel, a fixed-rate update would visibly
    // lag behind orbit drags and FPS look-ahead. Scratch objects are
    // module-scope-per-mount to avoid per-frame allocation.
    // Every boulder inside LiDAR range that is actually on screen gets a
    // box. The old cap of 6 left most of a 61-rock cluster unmarked while
    // the perception panel beside it reported dozens tracked -- a detector
    // that visibly misses what it is looking straight at reads as broken.
    //
    // The cap that remains is a rendering budget, not a perception limit:
    // these are DOM nodes repositioned every frame, and past a few dozen the
    // cost shows. Sorted nearest-first, so if the budget ever binds it drops
    // the far rocks, which are the ones a driver cares least about.
    const MAX_ROCK_BOXES = 48
    // Below this on-screen height a box is smaller than its own label, so
    // the text is dropped and the marker stays a plain bracket. Keeps a
    // dense field readable instead of a wall of overlapping tags.
    const ROCK_LABEL_MIN_PX = 26
    const rockBoxTempBox = new THREE.Box3()
    const rockBoxWorldPos = new THREE.Vector3()
    const rockBoxNdc = new THREE.Vector3()
    const rockBoxCorners = Array.from({ length: 8 }, () => new THREE.Vector3())
    const updateRockBoxes = (state: NonNullable<typeof sceneRef.current>) => {
      const box3dLayer = state.rockBoxContainer
      if (!state.lidarPoints.visible) {
        for (const el of state.rockBoxPool) el.style.display = 'none'
        return
      }
      const width = box3dLayer.clientWidth
      const height = box3dLayer.clientHeight
      if (width === 0 || height === 0) return

      const candidates: Array<{ left: number; top: number; w: number; h: number; distance: number }> = []
      for (const child of state.rockGroup.children) {
        if (!(child instanceof THREE.Mesh) || !child.visible) continue
        // A boulder is TWO meshes: the scanned Apollo visual and the low-poly
        // LiDAR collision proxy sitting inside it. The proxy stays visible as
        // an object -- only its material is invisible -- so `child.visible`
        // does not separate them, and boxing both drew a second bracket
        // around every rock, slightly offset because the two hulls differ.
        // Box what the driver can actually see.
        const childMaterial = Array.isArray(child.material) ? child.material[0] : child.material
        if (childMaterial && childMaterial.visible === false) continue
        child.getWorldPosition(rockBoxWorldPos)
        const distance = rockBoxWorldPos.distanceTo(state.lidarOrigin)
        if (distance > LIDAR_CONFIG.maxRangeM) continue

        rockBoxTempBox.setFromObject(child)
        const { min, max } = rockBoxTempBox
        rockBoxCorners[0].set(min.x, min.y, min.z)
        rockBoxCorners[1].set(min.x, min.y, max.z)
        rockBoxCorners[2].set(min.x, max.y, min.z)
        rockBoxCorners[3].set(min.x, max.y, max.z)
        rockBoxCorners[4].set(max.x, min.y, min.z)
        rockBoxCorners[5].set(max.x, min.y, max.z)
        rockBoxCorners[6].set(max.x, max.y, min.z)
        rockBoxCorners[7].set(max.x, max.y, max.z)

        let minX = Infinity
        let minY = Infinity
        let maxX = -Infinity
        let maxY = -Infinity
        let behind = false
        for (const corner of rockBoxCorners) {
          rockBoxNdc.copy(corner).project(camera)
          if (rockBoxNdc.z > 1) {
            behind = true
            break
          }
          const px = (rockBoxNdc.x + 1) * 0.5 * width
          const py = (1 - rockBoxNdc.y) * 0.5 * height
          if (px < minX) minX = px
          if (px > maxX) maxX = px
          if (py < minY) minY = py
          if (py > maxY) maxY = py
        }
        if (behind || maxX < 0 || minX > width || maxY < 0 || minY > height) continue
        // Skip only what is too small to draw a bracket around at all. This
        // used to be 4px on BOTH axes, which quietly dropped anything seen
        // edge-on or far enough away to be a couple of pixels wide -- rocks
        // plainly visible on the ground, sitting inside the scan rings, with
        // no marker on them.
        if (maxX - minX < 3 && maxY - minY < 3) continue

        candidates.push({ left: minX, top: minY, w: maxX - minX, h: maxY - minY, distance })
      }

      candidates.sort((a, b) => a.distance - b.distance)
      const shown = candidates.slice(0, MAX_ROCK_BOXES)

      while (state.rockBoxPool.length < shown.length) {
        const el = document.createElement('div')
        el.className = 'terrain3d-rockbox'
        const label = document.createElement('span')
        label.className = 'terrain3d-rockbox-label'
        el.appendChild(label)
        box3dLayer.appendChild(el)
        state.rockBoxPool.push(el)
      }

      state.rockBoxPool.forEach((el, i) => {
        const item = shown[i]
        if (!item) {
          el.style.display = 'none'
          return
        }
        el.style.display = 'block'
        el.style.left = `${item.left}px`
        el.style.top = `${item.top}px`
        el.style.width = `${item.w}px`
        el.style.height = `${item.h}px`
        const color = rockDistanceColor(item.distance, LIDAR_CONFIG.maxRangeM)
        el.style.borderColor = color
        el.style.boxShadow = `0 0 0 1px rgba(0, 0, 0, 0.4), 0 0 8px ${color}`
        const label = el.firstElementChild as HTMLSpanElement
        if (item.h >= ROCK_LABEL_MIN_PX) {
          label.style.display = ''
          label.textContent = `ROCK ${item.distance.toFixed(1)} m`
          label.style.background = color
        } else {
          label.style.display = 'none'
        }
      })
    }

    const animate = () => {
      frame = requestAnimationFrame(animate)
      // OrbitControls.update() re-aims the camera at controls.target every
      // call, independent of `enabled` -- calling it unconditionally here
      // fought FPS mode's own camera.lookAt() every frame and snapped the
      // "surface" view back to staring down at the orbit target.
      if (controls.enabled) controls.update()
      const state = sceneRef.current
      // Orbit mode draws the rover oversized so a 1.5 m vehicle is findable
      // across a 2.5 km overview. Held at a fixed 10x that also meant the
      // rover was a 15 m monster the moment anyone zoomed in to look at it
      // -- and the wheels and body are only worth animating if they can be
      // looked at. The exaggeration now fades out as the camera closes in,
      // so it is a locator at range and a real 1.5 m rover up close.
      if (state && cameraModeRef.current === 'orbit') {
        const cameraDistance = camera.position.distanceTo(state.roverGroup.position)
        state.roverGroup.scale.setScalar(
          THREE.MathUtils.clamp(cameraDistance / ROVER_TRUE_SCALE_DISTANCE_M, 1, ROVER_ORBIT_SCALE),
        )
      }
      if (state?.lidarScan && state.lidarSweep.visible) {
        const revolutionMs = 1000 / LIDAR_CONFIG.scanRateHz
        const phase = ((performance.now() - state.lidarRevolutionStartedAt) % revolutionMs) / revolutionMs
        const azimuthIndex = Math.min(
          LIDAR_CONFIG.azimuthSteps - 1,
          Math.floor(phase * LIDAR_CONFIG.azimuthSteps),
        )
        const azimuth = (azimuthIndex / LIDAR_CONFIG.azimuthSteps) * Math.PI * 2
        state.lidarHead.rotation.y = -azimuth

        const endpoint = state.lidarScan.azimuthEndpoints[azimuthIndex]
          ?? state.lidarOrigin.clone().add(
            new THREE.Vector3(Math.sin(azimuth), -0.08, -Math.cos(azimuth))
              .normalize()
              .multiplyScalar(LIDAR_CONFIG.maxRangeM),
          )
        const sweepPositions = state.lidarSweep.geometry.getAttribute('position') as THREE.BufferAttribute
        sweepPositions.setXYZ(0, state.lidarOrigin.x, state.lidarOrigin.y, state.lidarOrigin.z)
        sweepPositions.setXYZ(1, endpoint.x, endpoint.y, endpoint.z)
        sweepPositions.needsUpdate = true
        state.lidarSweep.geometry.setDrawRange(0, 2)
      }
      // Route ribbon animation. Uniforms only -- no geometry is touched, so
      // this is a couple of float writes per frame.
      const ribbon = routeRibbonRef.current
      if (ribbon) {
        ribbon.material.uniforms.uTime.value = performance.now() / 1000
        ribbon.material.uniforms.uProgress.value = routeProgressRef.current
      }
      renderer.render(scene, camera)
      // After render, not before: world matrices (rocks, camera) are only
      // guaranteed current once the renderer's own traversal has updated
      // them this frame, and box3-from-object / camera.project() both need
      // that here.
      if (state) updateRockBoxes(state)
    }
    animate()

    return () => {
      disposed = true
      if (visualRockLoadTimer !== null) window.clearTimeout(visualRockLoadTimer)
      cancelAnimationFrame(frame)
      observer.disconnect()
      controls.dispose()
      sceneRef.current?.dispose()
      sceneRef.current = null
      renderer.dispose()
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement)
      }
    }
    // Built once. Layer, slice and exaggeration changes are separate effects.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /** Write baseColors * lightMask into the geometry's colour attribute. */
  const applyColors = () => {
    const state = sceneRef.current
    if (!state) return
    const attr = state.mesh.geometry.getAttribute('color') as THREE.BufferAttribute
    const out = attr.array as Float32Array
    const { baseColors, lightMask } = state
    if (!lightMask) {
      out.set(baseColors)
    } else {
      for (let i = 0, n = lightMask.length; i < n; i++) {
        const k = lightMask[i]
        out[i * 3] = baseColors[i * 3] * k
        out[i * 3 + 1] = baseColors[i * 3 + 1] * k
        out[i * 3 + 2] = baseColors[i * 3 + 2] * k
      }
    }
    attr.needsUpdate = true
  }

  // ── Photographic drape: real NAC imagery instead of a shaded albedo. ───────
  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready') return
    let cancelled = false

    if (!effectivePhoto) {
      // Back to a lit surface. Clearing the emissive term is the part that
      // matters here; the colouring effect below runs on the same flip
      // (effectivePhoto is in its deps) and puts back either the detail
      // texture or the data ramp, whichever the current view mode wants.
      state.material.map = null
      state.material.emissiveMap = null
      state.material.emissive.set(0x000000)
      state.material.color.set(0xffffff)
      state.material.needsUpdate = true
      return
    }

    if (!state.photoAvailable) {
      // Never stretch a georeferenced photograph over a different DEM
      // footprint. App disables the toggle from the same manifest signal.
      state.material.map = state.regolithTexture
      state.material.emissiveMap = null
      state.material.emissive.set(0x000000)
      state.material.color.set(0xffffff)
      state.material.needsUpdate = true
      return
    }

    const apply = (texture: THREE.Texture) => {
      if (cancelled || !sceneRef.current) return
      texture.colorSpace = THREE.SRGBColorSpace
      // FPS eye height views this drape at a steep grazing angle; without
      // anisotropic filtering the mip chain blurs it into streaks.
      texture.anisotropy = 16
      // PlaneGeometry's v runs 1 -> 0 from the +Y (north) edge, and three's
      // default flipY puts image row 0 at v = 1. The crop's row 0 is the
      // window's north edge, so the two already agree -- no flip needed.
      state.photoTexture = texture

      // The photograph is shown UNLIT, and that is the whole point rather than
      // a shortcut. A NAC image already contains the Sun: its brightness IS
      // the surface's response to the illumination at capture time. Feeding it
      // in as a diffuse map makes three multiply it by a second lighting term,
      // and the result is not a darker photograph but a wrong one -- measured
      // here, the mean fell from 0.226 to about 0.016, which is why ticking
      // the box appeared to do nothing. Exactly the error the shadow mask is
      // switched off to avoid, one step further along the same pipeline.
      //
      // Driving it through emissive rather than swapping in a MeshBasicMaterial
      // keeps one material object alive, so the geometry, the route overlay and
      // the disposal path do not have to change with the mode. emissiveMap
      // reads UV channel 0, the same channel PlaneGeometry fills, so this needs
      // no second UV set.
      state.material.map = texture
      state.material.color.set(0x000000)
      state.material.emissiveMap = texture
      state.material.emissive.set(0xffffff)
      state.material.emissiveIntensity = 1
      state.material.needsUpdate = true

      // Vertex colours carry the shadow mask and the data ramps; neither
      // belongs on top of a photograph.
      const attr = state.mesh.geometry.getAttribute('color') as THREE.BufferAttribute
      ;(attr.array as Float32Array).fill(1)
      attr.needsUpdate = true
    }

    if (state.photoTexture) {
      apply(state.photoTexture)
    } else {
      new THREE.TextureLoader().load(
        PHOTO_TEXTURE_URL,
        apply,
        undefined,
        () => onError?.('NAC texture failed to load'),
      )
    }

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectivePhoto, status])

  // ── Surface colouring follows the 2-D view mode. ───────────────────────────
  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready' || effectivePhoto) return
    let cancelled = false

    const layerName = LAYER_FOR_VIEW[viewMode] ?? 'elevation'
    const entry = state.manifest.layers[layerName]
    if (!entry) return

    // 'surface' is the realistic view. Its albedo comes from the NAC detail
    // texture rather than the vertex colours, so it keeps the full 1 m/px
    // variation instead of being flattened to one value per 5 m vertex. The
    // vertex colours then carry only the shadow mask, and three multiplies the
    // two: detail albedo x shadow. It still fetches the layer, because a NaN
    // cell must read as no-data rather than as ground that happens to be there.
    const flat = viewMode === 'surface'

    if (flat) {
      const applyDetail = (texture: THREE.Texture) => {
        if (cancelled || !sceneRef.current) return
        texture.colorSpace = THREE.SRGBColorSpace
        texture.anisotropy = 16
        state.detailTexture = texture
        state.material.map = texture
        state.material.color.set(0xffffff)
        state.material.needsUpdate = true
      }
      if (!state.photoAvailable) {
        applyDetail(state.regolithTexture)
      } else if (state.detailTexture) applyDetail(state.detailTexture)
      else
        new THREE.TextureLoader().load(DETAIL_TEXTURE_URL, applyDetail, undefined, () => {
          // No texture: put the albedo back on the material so the ground is
          // still the right tone, just without the crater detail.
          if (cancelled || !sceneRef.current) return
          sceneRef.current.material.map = null
          sceneRef.current.material.color.copy(SURFACE_ALBEDO)
          sceneRef.current.material.needsUpdate = true
        })
    } else {
      state.material.map = null
      state.material.color.set(0xffffff)
      state.material.needsUpdate = true
    }

    fetchF32(entry.binary_url)
      .then((values) => {
        if (cancelled || !sceneRef.current) return
        const base = state.baseColors
        const [lo, hi] = RAMP[layerName] ?? FALLBACK_RAMP
        const min = entry.min ?? 0
        const max = entry.max ?? 1
        const span = max - min || 1
        const mixed = new THREE.Color()
        for (let i = 0; i < values.length; i++) {
          const v = values[i]
          if (Number.isNaN(v)) {
            // No-data: a flat neutral, so it reads as "unknown", not as a value.
            base[i * 3] = 0.16
            base[i * 3 + 1] = 0.15
            base[i * 3 + 2] = 0.17
            continue
          }
          if (flat) {
            // White: the albedo lives in the detail texture (or, if that
            // failed to load, in material.color). The vertex colour's job in
            // this mode is only to carry the shadow mask.
            base[i * 3] = 1
            base[i * 3 + 1] = 1
            base[i * 3 + 2] = 1
            continue
          }
          const t = Math.min(1, Math.max(0, (v - min) / span))
          mixed.copy(lo).lerp(hi, t)
          base[i * 3] = mixed.r
          base[i * 3 + 1] = mixed.g
          base[i * 3 + 2] = mixed.b
        }
        applyColors()
      })
      .catch(() => {
        if (cancelled || !sceneRef.current) return
        // baseColors starts as zeros, so a failed fetch would render the mesh
        // pure black and look like a broken scene rather than a failed layer.
        // Fall back to plain ground; the shadow mask still applies.
        const base = state.baseColors
        for (let i = 0; i < base.length; i += 3) {
          base[i] = SURFACE_ALBEDO.r
          base[i + 1] = SURFACE_ALBEDO.g
          base[i + 2] = SURFACE_ALBEDO.b
        }
        applyColors()
        onError?.(`${layerName} layer failed to load`)
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode, status, effectivePhoto])

  // ── Sun position and cast shadows follow the time slice. ───────────────────
  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready') return
    const { series, shadowCube, manifest } = state
    const span = Math.max(manifest.grid.rows, manifest.grid.cols) * manifest.grid.resolution_m

    if (!series || !series.sun.length) {
      // No ephemeris: keep the azimuth fixed but use the same 20-degree
      // shading floor as the SPICE path. The previous ~5-degree fallback made
      // one half of the high-relief DEM effectively black and looked like a
      // torn texture, even though it was simply the Lambert term collapsing.
      state.sun.position.set(0.6, 0.36, -0.8).normalize().multiplyScalar(span * 4)
      if (state.sunSprite) {
        state.sunSprite.position.copy(state.sun.position).normalize().multiplyScalar(55000)
      }
      return
    }

    const slice = Math.min(Math.max(sliceIndex, 0), series.sun.length - 1)
    const { azimuth_grid_deg: az, elevation_deg: el } = series.sun[slice]
    const a = THREE.MathUtils.degToRad(az)
    // AZIMUTH is the true measured value -- it decides which way the relief is
    // lit and which way shadows point, so it must not be invented.
    //
    // ELEVATION is lifted to a floor for shading only. The real Sun here sits
    // at ~1.2 deg, where the Lambert term (sin 1.2 = 0.02) collapses the whole
    // surface to black and no topography is legible. Who is actually in shadow
    // is NOT decided here -- that comes from the horizon cube below, which
    // carries the true 1.2 deg geometry ray-marched per azimuth. This light
    // only shapes the lit ground, so raising it trades nothing physical away.
    const SHADING_ELEVATION_FLOOR_DEG = 20
    const e = THREE.MathUtils.degToRad(Math.max(el, SHADING_ELEVATION_FLOOR_DEG))
    // Grid azimuth is clockwise from north. After the -90 deg tilt, north is
    // -Z and east is +X.
    state.sun.position
      .set(Math.sin(a) * Math.cos(e), Math.sin(e), -Math.cos(a) * Math.cos(e))
      .multiplyScalar(span * 4)

    if (state.sunSprite) {
      state.sunSprite.position.copy(state.sun.position).normalize().multiplyScalar(55000)
    }

    // In photographic mode the drape already carries the 2010 acquisition's
    // own shadows. Applying the simulated mask on top would darken the same
    // ground twice, from two epochs that were measured not to agree.
    if (!shadowCube || effectivePhoto) return
    const [, sr, sc] = series.binary_format.shape
    const slab = shadowCube.subarray(slice * sr * sc, (slice + 1) * sr * sc)
    const { rows, cols } = manifest.grid

    // The series is served downsampled (the cube is 250x250 against a 500x500
    // mesh), so each mesh vertex samples the shadow cell it falls inside.
    const rowScale = sr / rows
    const colScale = sc / cols
    const mask = state.lightMask ?? new Float32Array(rows * cols)
    // 1 = shadowed in the payload, so a lit cell keeps its full albedo and a
    // shadowed one drops to the floor below. Not zero: LROC images of polar
    // shadowed ground are dark but not empty -- nearby sunlit slopes scatter
    // enough light to keep the terrain readable, and a hard zero would erase
    // exactly the crater interiors this view exists to show.
    const SHADOW_FLOOR = 0.13
    for (let r = 0; r < rows; r++) {
      const sRow = Math.min(sr - 1, (r * rowScale) | 0)
      for (let c = 0; c < cols; c++) {
        const sCol = Math.min(sc - 1, (c * colScale) | 0)
        const v = slab[sRow * sc + sCol]
        const shadowed = Number.isNaN(v) ? 0 : Math.min(1, Math.max(0, v))
        mask[r * cols + c] = SHADOW_FLOOR + (1 - SHADOW_FLOOR) * (1 - shadowed)
      }
    }
    state.lightMask = mask
    applyColors()
  }, [sliceIndex, status, effectivePhoto])

  // ── Vertical exaggeration (flat 1.0 in FPS mode for natural level ground) ──
  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready') return
    state.mesh.scale.z =
      cameraMode === 'fps'
        ? 1.0
        : (exaggeration ?? state.manifest.elevation.vertical_exaggeration_suggested)
  }, [exaggeration, cameraMode, status])

  // Rover position + heading, decoupled from rock/LiDAR regeneration below.
  // Route playback (PlaybackBar) advances activeWaypoint every ~50 ms; the
  // heavy effect debounces so it does not rebuild rock meshes and re-fetch
  // a LiDAR scan 20 times a second, but the rover itself must not wait for
  // that debounce -- an update this cheap has no reason to lag, and a
  // rover that only "catches up" once every 300 ms reads as "not moving".
  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready' || !state.heights) return
    const heights = state.heights
    if (lastRoverRouteRef.current !== (waypoints ?? null)) {
      lastRoverRouteRef.current = waypoints ?? null
      lastRoverGroundPosRef.current = null
      // A new route starts from a standstill: carrying the old heading over
      // would make the rover spend its first metres swinging round from
      // wherever the previous drive left it pointing.
      roverHeadingRef.current = null
      roverSteerRef.current = 0
    }
    const { rows, cols, resolution_m: resolutionM } = state.manifest.grid
    const source = activeWaypoint ?? waypoints?.[0] ?? null
    const row = THREE.MathUtils.clamp(source?.row ?? Math.floor(rows / 2), 0, rows - 1)
    const col = THREE.MathUtils.clamp(source?.col ?? Math.floor(cols / 2), 0, cols - 1)
    const width = cols * resolutionM
    const depth = rows * resolutionM
    const stepX = width / (cols - 1)
    const stepZ = depth / (rows - 1)
    const baseX = col * stepX - width / 2
    const baseZ = row * stepZ - depth / 2
    const terrain: TerrainField = {
      rows,
      cols,
      resolutionM,
      minElevationM: state.manifest.elevation.min_m,
      heights,
      verticalScale: state.mesh.scale.z,
    }

    const waypointIndex = source
      ? waypoints?.findIndex((waypoint) => waypoint.step === source.step) ?? -1
      : -1
    const nextWaypoint = waypointIndex >= 0 ? waypoints?.[waypointIndex + 1] : null

    // roverFraction (0-1) is this waypoint's progress toward the next one,
    // driven by the App-level playback clock against the backend's own
    // elapsed_hours timeline -- interpolating here is what turns "snap to
    // the next 5 m grid node" into a smooth, speed-accurate drive between
    // planned nodes, matching how far the rover would really have gotten.
    let roverX = baseX
    let roverZ = baseZ
    if (nextWaypoint) {
      const nextX = nextWaypoint.col * stepX - width / 2
      const nextZ = nextWaypoint.row * stepZ - depth / 2
      const t = THREE.MathUtils.clamp(roverFraction, 0, 1)
      roverX = THREE.MathUtils.lerp(baseX, nextX, t)
      roverZ = THREE.MathUtils.lerp(baseZ, nextZ, t)
    }
    const roverGroundY = sampleTerrainHeight(terrain, roverX, roverZ) ?? 0

    // Ground actually covered since the last update. Everything below --
    // heading rate, steering angle, wheel roll -- is derived from this
    // rather than from elapsed time, so the vehicle behaves identically
    // whether the playback clock is running at real time or fast-forwarded:
    // a rover that drives one metre turns its wheels the same amount and
    // arcs into a corner by the same angle either way.
    const lastPos = lastRoverGroundPosRef.current
    const deltaX = lastPos ? roverX - lastPos.x : 0
    const deltaZ = lastPos ? roverZ - lastPos.z : 0
    const distance = Math.hypot(deltaX, deltaZ)
    lastRoverGroundPosRef.current = { x: roverX, z: roverZ }

    // Heading. The A* path turns in 45-degree steps at 5 m nodes, so taking
    // the next node's bearing directly made the rover's yaw jump the moment
    // it arrived -- a vehicle pivoting on the spot between every cell. The
    // heading now chases that bearing at a bounded rate per metre driven,
    // which is what a turn radius is, so the rover leans into a corner over
    // roughly its own length instead of snapping through it.
    let heading = roverHeadingRef.current
    let yawStep = 0
    if (distance > 1e-4) {
      const targetHeading = Math.atan2(deltaX, deltaZ)
      if (heading === null) {
        heading = targetHeading
      } else {
        // Shortest way round: without this a heading crossing +/-pi takes
        // the long way and the rover spins a full turn on the spot.
        let error = targetHeading - heading
        error = Math.atan2(Math.sin(error), Math.cos(error))
        const limit = distance * MAX_YAW_RATE_RAD_PER_M
        yawStep = THREE.MathUtils.clamp(error, -limit, limit)
        heading += yawStep
      }
      roverHeadingRef.current = heading
    } else if (heading === null && nextWaypoint) {
      // Standing still at the start of a route: face the way it is about to
      // go rather than an arbitrary default.
      heading = Math.atan2(
        nextWaypoint.col * stepX - width / 2 - baseX,
        nextWaypoint.row * stepZ - depth / 2 - baseZ,
      )
      roverHeadingRef.current = heading
    }

    // Steering angle from the curvature actually being driven, via the
    // bicycle model: tan(delta) = wheelbase * dyaw/ds. It is eased rather
    // than applied outright because a linkage takes time to swing, and an
    // instantly-snapping front wheel reads as broken even when the body
    // path is right.
    const curvature = distance > 1e-4 ? yawStep / distance : 0
    const targetSteer = THREE.MathUtils.clamp(
      Math.atan(wheelbaseRef.current * curvature),
      -MAX_STEER_RAD,
      MAX_STEER_RAD,
    )
    roverSteerRef.current += (targetSteer - roverSteerRef.current) * 0.25

    // How far along the drawn corridor the rover has reached, in the same
    // metres the ribbon's `along` attribute uses. The ribbon resamples the
    // route, so its arc-length table is indexed by resampled point, not by
    // waypoint -- interpolating between the two node distances that bracket
    // the current pose is what keeps the wake edge under the wheels rather
    // than snapping a whole waypoint at a time.
    const ribbon = routeRibbonRef.current
    if (ribbon && waypointIndex >= 0 && waypoints) {
      const perWaypoint = ribbon.distances.length - 1
      const span = Math.max(waypoints.length - 1, 1)
      const at = ((waypointIndex + THREE.MathUtils.clamp(roverFraction, 0, 1)) / span) * perWaypoint
      const i0 = Math.min(ribbon.distances.length - 1, Math.max(0, Math.floor(at)))
      const i1 = Math.min(ribbon.distances.length - 1, i0 + 1)
      routeProgressRef.current = THREE.MathUtils.lerp(
        ribbon.distances[i0],
        ribbon.distances[i1],
        at - i0,
      )
    } else {
      routeProgressRef.current = -1
    }

    state.roverGroup.position.set(roverX, roverGroundY, roverZ)
    // Sitting ON the slope, not floating level above it: the body's up axis
    // follows the terrain normal and the heading is applied within that
    // frame. A rover driving a 15-degree crater wall while staying perfectly
    // level is the single clearest tell that a vehicle is pasted onto a
    // terrain rather than driving on it.
    const surfaceNormal = sampleTerrainNormal(terrain, roverX, roverZ)
    roverTiltQuaternion.setFromUnitVectors(ROVER_UP, surfaceNormal)
    roverYawQuaternion.setFromAxisAngle(ROVER_UP, heading ?? 0)
    state.roverGroup.quaternion.copy(roverTiltQuaternion).multiply(roverYawQuaternion)
    // Orbit mode's exaggeration is the render loop's job (it depends on
    // camera distance, which changes without any of this effect's inputs
    // changing); this only has to make sure surface mode is life-size.
    if (cameraMode !== 'orbit') state.roverGroup.scale.setScalar(1)
    state.roverGroup.updateMatrixWorld(true)
    state.lidarOrigin.set(roverX, roverGroundY + 1.6, roverZ)

    // Wheels. Roll is the angle a wheel of this radius has to turn through
    // to cover the ground actually covered -- signed along the rover's own
    // forward axis, so reversing rolls the wheels backwards rather than
    // forwards. Steering is absolute and lives on a separate pivot node, so
    // the two never corrupt each other.
    const forwardDot = heading === null ? 1 : deltaX * Math.sin(heading) + deltaZ * Math.cos(heading)
    const signedDistance = distance > 1e-4 ? Math.sign(forwardDot || 1) * distance : 0
    for (const wheel of wheelsRef.current) {
      wheel.steer.rotation.y = wheel.isFront ? roverSteerRef.current : 0
      if (signedDistance === 0) continue
      // rotateOnAxis composes the turn as a quaternion multiply in the
      // wheel's OWN current local frame -- incrementing a raw Euler
      // component instead only spins cleanly when the other two angles are
      // exactly zero, which is not something an arbitrary asset guarantees.
      wheel.spin.rotateOnAxis(wheel.axis, signedDistance / wheel.radiusM)
    }
  }, [activeWaypoint, roverFraction, cameraMode, exaggeration, status, waypoints])

  // Local rock field + real first-return scan. Throttled to a fixed ~500 ms
  // cadence (not debounced to silence) so it does not rebuild every rock
  // mesh and re-fetch a backend LiDAR scan on each of the playback timer's
  // ~50 ms ticks -- but a pure silence-based debounce never actually fires
  // while activeWaypoint keeps changing every tick during active route
  // playback, which read as the scan being frozen/fake while the rover
  // drove. Tracking the last real run and scheduling only the REMAINING
  // time until the next one is due keeps it refreshing throughout the
  // drive, not just once movement stops. The rover's own position above is
  // not gated on this and keeps up regardless.
  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready' || !state.heights) return
    const heights = state.heights

    const controller = new AbortController()
    let cancelled = false

    // The local raycast used while isPlaying has no network round trip to
    // wait out, so it can refresh far more often than the backend-fetch
    // path below without any risk of piling up superseded requests.
    const LIDAR_REFRESH_MS = isPlaying ? 150 : 500
    const sinceLastRun = performance.now() - lastLidarRunRef.current
    const delay = Math.max(0, LIDAR_REFRESH_MS - sinceLastRun)

    const timer = window.setTimeout(async () => {
      lastLidarRunRef.current = performance.now()
      const { rows, cols, resolution_m: resolutionM } = state.manifest.grid
      const source = activeWaypoint ?? waypoints?.[0] ?? null
      const row = THREE.MathUtils.clamp(source?.row ?? Math.floor(rows / 2), 0, rows - 1)
      const col = THREE.MathUtils.clamp(source?.col ?? Math.floor(cols / 2), 0, cols - 1)
      const width = cols * resolutionM
      const depth = rows * resolutionM
      const stepX = width / (cols - 1)
      const stepZ = depth / (rows - 1)
      const roverX = col * stepX - width / 2
      const roverZ = row * stepZ - depth / 2
      const terrain: TerrainField = {
        rows,
        cols,
        resolutionM,
        minElevationM: state.manifest.elevation.min_m,
        heights,
        verticalScale: state.mesh.scale.z,
      }
      // Rocks are placed at sampleTerrainHeight(), which already multiplies by
      // the field's verticalScale. Re-seat the fixed cluster only when this
      // scale changes, so its ground contact and slope orientation stay true
      // in both FPS and orbit view without letting replans move it.
      const verticalScale = terrain.verticalScale
      const shouldRebuildRocks =
        fixedRockAnchorRef.current === null ||
        lastRockFieldScaleRef.current !== verticalScale ||
        // The scans finished downloading after the cluster was built:
        // rebuild once so the boulders actually take their scanned geometry
        // instead of keeping the placeholder proxies for the session.
        lastRockFieldVisualCountRef.current !== rockVisualTemplatesRef.current.length

      if (shouldRebuildRocks) {
        lastRockFieldScaleRef.current = verticalScale
        lastRockFieldVisualCountRef.current = rockVisualTemplatesRef.current.length
        if (!fixedRockAnchorRef.current) {
          // Starts ahead and to one side of the initial rover pose, outside
          // its safety footprint but within LiDAR range. It never moves after
          // this one placement decision.
          fixedRockAnchorRef.current = { x: roverX, z: roverZ }
        }
        for (const child of [...state.rockGroup.children]) {
          state.rockGroup.remove(child)
          // Scanned visuals share their template geometry. The template owns
          // it and releases it during scene cleanup; disposing it here would
          // break the next rebuild after a vertical-exaggeration change.
          if (child instanceof THREE.Mesh && !child.userData.scannedApolloRock) child.geometry.dispose()
        }
        state.lidarRockMeshes.length = 0

        const rockTemplates = rockTemplatesRef.current
        const visualTemplates = rockVisualTemplatesRef.current
        // Rocks are scene truth for the LiDAR simulation only. The fixed
        // cluster is never sent to the global planner; it reaches avoidance
        // exclusively through local LiDAR returns.
        const rockDescriptors = generateFixedBoulderCluster(
          fixedRockAnchorRef.current.x,
          fixedRockAnchorRef.current.z,
        )
        const rockUp = new THREE.Vector3(0, 1, 0)
        for (const [rockIndex, descriptor] of rockDescriptors.entries()) {
          const groundY = sampleTerrainHeight(terrain, descriptor.x, descriptor.z)
          if (groundY === null) continue
          // The collision proxy stays compact enough for the 4,320-beam
          // LiDAR pass. It is hidden whenever a textured Apollo visual is
          // available at the same pose, but it remains the exact object the
          // range sensor intersects.
          const proxyGeometry = buildRockGeometry(
            descriptor.shape,
            descriptor.seed,
            descriptor.radiusX,
            descriptor.radiusY,
            descriptor.radiusZ,
            rockTemplates,
            2,
          )
          const proxy = new THREE.Mesh<THREE.BufferGeometry, THREE.Material>(proxyGeometry, state.rockMaterial)
          // Sunk by its own burial fraction rather than a flat 12%: a rock
          // sits IN the regolith it has been gardened into, and how deep
          // depends on how long it has been there, which is what the field
          // encodes as size-dependent burial.
          proxy.position.set(descriptor.x, groundY - descriptor.radiusY * descriptor.burial, descriptor.z)
          // Oriented against the local surface, not against world up. On a
          // slope a world-up rock cuts into the hill on its uphill side and
          // hangs off it on the downhill side; matching the terrain normal
          // first, then applying the rock's own yaw and bedding tilt in
          // that frame, is what makes it read as resting on the ground.
          proxy.quaternion.setFromUnitVectors(rockUp, sampleTerrainNormal(terrain, descriptor.x, descriptor.z))
          proxy.rotateY(descriptor.rotationY)
          proxy.rotateX(descriptor.tiltX)
          proxy.rotateZ(descriptor.tiltZ)
          proxy.userData.lidarRockId = descriptor.id
          // Every visible boulder uses a scanned Apollo asset. The low-poly
          // mesh remains only as the invisible LiDAR collision proxy.
          const visualTemplate = visualTemplates[rockIndex % visualTemplates.length]
          if (visualTemplate) {
            proxy.material = state.lidarProxyMaterial
            const visual = new THREE.Mesh(visualTemplate.geometry, visualTemplate.material)
            visual.position.copy(proxy.position)
            visual.quaternion.copy(proxy.quaternion)
            visual.scale.set(descriptor.radiusX, descriptor.radiusY, descriptor.radiusZ)
            visual.userData.lidarRockId = descriptor.id
            visual.userData.scannedApolloRock = true
            visual.userData.rockBaseScale = visual.scale.clone()
            state.rockGroup.add(visual)
          }
          state.rockGroup.add(proxy)
          state.lidarRockMeshes.push(proxy)
        }

        // Position, heading, orbit-mode scale and lidarOrigin are the other
        // effect's job now (it is not debounced) -- rockGroup still needs
        // its own matrix refreshed here since it was just rebuilt above.
        state.rockGroup.updateMatrixWorld(true)
      }

      // Gravel: rebuilt only after the rover has actually covered ground,
      // and skipped entirely in orbit mode where a 10 cm clast is far below
      // one pixel across a 2.5 km overview.
      const showPebbles = cameraMode !== 'orbit'
      state.pebbleMeshes.forEach((mesh) => {
        mesh.visible = showPebbles
      })
      const lastPebbleOrigin = lastPebbleOriginRef.current
      const pebblesMoved =
        !lastPebbleOrigin || Math.hypot(roverX - lastPebbleOrigin.x, roverZ - lastPebbleOrigin.z) > 4
      if (showPebbles && pebblesMoved) {
        lastPebbleOriginRef.current = { x: roverX, z: roverZ }
        const counts = new Array<number>(state.pebbleMeshes.length).fill(0)
        const pebbleMatrix = new THREE.Matrix4()
        const pebblePosition = new THREE.Vector3()
        const pebbleQuaternion = new THREE.Quaternion()
        const pebbleTilt = new THREE.Quaternion()
        const pebbleScale = new THREE.Vector3()
        // YXZ so the composition matches the navigation rocks' rotateY ->
        // rotateX -> rotateZ exactly; a different order would tilt gravel
        // and boulders differently on the same slope.
        const pebbleEuler = new THREE.Euler(0, 0, 0, 'YXZ')
        const pebbleUp = new THREE.Vector3(0, 1, 0)
        for (const pebble of generatePebbleField(roverX, roverZ)) {
          const variant = Math.abs(pebble.seed) % state.pebbleMeshes.length
          const index = counts[variant]
          if (index >= PEBBLE_VARIANT_CAPACITY) continue
          const groundY = sampleTerrainHeight(terrain, pebble.x, pebble.z)
          if (groundY === null) continue
          pebblePosition.set(pebble.x, groundY - pebble.radiusY * pebble.burial, pebble.z)
          pebbleQuaternion.setFromUnitVectors(
            pebbleUp,
            sampleTerrainNormal(terrain, pebble.x, pebble.z),
          )
          pebbleEuler.set(pebble.tiltX, pebble.rotationY, pebble.tiltZ, 'YXZ')
          pebbleQuaternion.multiply(pebbleTilt.setFromEuler(pebbleEuler))
          pebbleScale.set(pebble.radiusX, pebble.radiusY, pebble.radiusZ)
          pebbleMatrix.compose(pebblePosition, pebbleQuaternion, pebbleScale)
          state.pebbleMeshes[variant].setMatrixAt(index, pebbleMatrix)
          counts[variant] = index + 1
        }
        state.pebbleMeshes.forEach((mesh, index) => {
          mesh.count = counts[index]
          mesh.instanceMatrix.needsUpdate = true
        })
      }

      // Only the rocks a beam could actually reach. The field is anchored to
      // the whole route and runs to 500 m, but the sensor sees 60; handing
      // the raycaster all of them made every one of the 270 x 16 beams
      // bounding-sphere test a couple of thousand meshes it had no chance of
      // hitting, several times a second, for nothing.
      const scanReachM = LIDAR_CONFIG.maxRangeM + ROCK_FIELD.maxDiameterM
      const rockMeshes = state.lidarRockMeshes.filter(
        (rock) => Math.hypot(rock.position.x - state.lidarOrigin.x, rock.position.z - state.lidarOrigin.z) <= scanReachM,
      )
      const scanSeed = ((row + 1) * 73856093) ^ ((col + 1) * 19349663)

      // The terrain half of this scan is now the real thing: a ray march
      // over the actual loaded DEM, computed by backend/app/main.py's
      // /api/lidar-scan (lunapath/src/virtual_lidar.py), not a second
      // client-side reimplementation of it. Rocks stay local regardless --
      // the backend's 5 m/px DEM cannot resolve them, by that module's own
      // documented limitation, so this merges the backend's terrain return
      // with a local raycast against the meshes the backend cannot see.
      let scan: LidarScanResult
      if (isPlaying) {
        // See the isPlaying prop's own comment: the backend scan measures
        // ~4.7 s round trip, so fetching it while actively driving would
        // just abort every attempt but the last -- the local march is used
        // here purely for speed, not accuracy, to keep the cloud visibly
        // live while moving.
        scan = simulateLidarScan(state.lidarOrigin, terrain, rockMeshes, scanSeed)
      } else {
        try {
          const backendScan = await fetchBackendLidarScan(row, col, 1.6, controller.signal)
          if (cancelled) return
          scan = buildLidarScanFromBackend(
            state.lidarOrigin,
            terrain,
            backendScan.points,
            rockMeshes,
            scanSeed,
          )
        } catch (error) {
          if (cancelled || (error instanceof DOMException && error.name === 'AbortError')) return
          // Backend unreachable or erroring: fall back to the local DEM march
          // rather than leaving the scene showing a stale or empty scan.
          console.warn('LiDAR: /api/lidar-scan failed, using local fallback', error)
          scan = simulateLidarScan(state.lidarOrigin, terrain, rockMeshes, scanSeed)
        }
      }
      if (cancelled) return

      state.lidarScan = scan
      state.lidarRevolutionStartedAt = performance.now()

      // Visibility aids are deliberately visual-only. Ray intersections above
      // were computed against the unscaled physical meshes. Rocks scale in
      // place (each mesh's own .scale, not the shared rockGroup's) because
      // rockGroup's children sit at real WORLD positions -- scaling the
      // group itself would fling every rock outward from the scene origin
      // instead of growing each one around its own centre.
      const orbitRockScale = cameraMode === 'orbit' ? 3 : 1
      // Marker visibility is the lidarEnabled/cameraMode effect's job now
      // (below) -- it reacts immediately, where this effect is debounced.
      for (const child of state.rockGroup.children) {
        const baseScale = child.userData.rockBaseScale as THREE.Vector3 | undefined
        if (baseScale) child.scale.copy(baseScale).multiplyScalar(orbitRockScale)
        else child.scale.setScalar(orbitRockScale)
      }

      const pointGeometry = state.lidarPoints.geometry
      pointGeometry.setAttribute('position', new THREE.BufferAttribute(scan.positions, 3))
      pointGeometry.setAttribute('color', new THREE.BufferAttribute(scan.colors, 3))
      pointGeometry.computeBoundingSphere()

      const netPositions = buildTerrainNetPositions(terrain, roverX, roverZ, LIDAR_CONFIG.maxRangeM)
      state.terrainNet.geometry.dispose()
      state.terrainNet.geometry = new THREE.BufferGeometry()
      state.terrainNet.geometry.setAttribute('position', new THREE.BufferAttribute(netPositions, 3))

      // This is the only route from scene sensing into local navigation:
      // first returns -> anonymous obstacle hypotheses -> occupancy -> bounded
      // local decision. No mesh ID or pre-generated rock list reaches the
      // planner, and the global API is never called from this path.
      const observations = observeObstaclesFromLidar(scan, performance.now() / 1000)
      const occupancy = buildLocalOccupancyGrid({ x_m: roverX, z_m: roverZ }, observations)
      const activeIndex = source && waypoints
        ? waypoints.findIndex((waypoint) => waypoint === source || (
          waypoint.row === source.row && waypoint.col === source.col
        ))
        : -1
      const nextWaypoint = activeIndex >= 0 ? waypoints?.[activeIndex + 1] : undefined
      const localPlan = nextWaypoint
        ? planLocalDetour({
          pose: { x_m: roverX, z_m: roverZ },
          lookahead: {
            x_m: nextWaypoint.col * stepX - width / 2,
            z_m: nextWaypoint.row * stepZ - depth / 2,
          },
          obstacles: observations,
          rover_radius_m: 0.5,
          safety_margin_m: 0.35,
          max_deviation_m: 5,
        })
        : null
      const decision = localPlan?.decision ?? 'FOLLOW'
      setLocalNavigation({
        observedObstacles: observations.length,
        occupiedCells: occupancy.cells.filter((cell) => cell === 'occupied').length,
        decision,
      })
      if (decision !== 'FOLLOW' && onLocalNavigation) {
        const confirmed = observations.filter((obstacle) => obstacle.confidence >= 0.65)
        const obstacleCells = confirmed.map((obstacle) => ({
          row: THREE.MathUtils.clamp(Math.round((obstacle.z_m + depth / 2) / stepZ), 0, rows - 1),
          col: THREE.MathUtils.clamp(Math.round((obstacle.x_m + width / 2) / stepX), 0, cols - 1),
          radius_m: obstacle.radius_m,
          confidence: obstacle.confidence,
          observed_at_s: obstacle.observed_at_s,
          source: obstacle.source,
        }))
        const localWaypoints = (localPlan?.waypoints ?? []).map((point) => ({
          row: THREE.MathUtils.clamp(Math.round((point.z_m + depth / 2) / stepZ), 0, rows - 1),
          col: THREE.MathUtils.clamp(Math.round((point.x_m + width / 2) / stepX), 0, cols - 1),
        }))
        const currentRow = THREE.MathUtils.clamp(Math.round((roverZ + depth / 2) / stepZ), 0, rows - 1)
        const currentCol = THREE.MathUtils.clamp(Math.round((roverX + width / 2) / stepX), 0, cols - 1)
        // Do not use observed_at_s here. It changes on every scan even when
        // the rover, obstacle footprint and local decision are unchanged,
        // which previously caused a completed replan to be issued again.
        const stopKey = localNavigationSnapshotKey({
          current: { row: currentRow, col: currentCol },
          decision,
          local_waypoints: localWaypoints,
          observed_obstacles: obstacleCells,
        })
        if (obstacleCells.length > 0 && stopKey !== lastLocalStopKeyRef.current) {
          lastLocalStopKeyRef.current = stopKey
          onLocalNavigation({
            current: { row: currentRow, col: currentCol },
            decision,
            local_waypoints: localWaypoints,
            observed_obstacles: obstacleCells,
          })
        }
      } else {
        lastLocalStopKeyRef.current = null
      }
      setLidarTelemetry(scan.summary)
    }, delay)

    return () => {
      cancelled = true
      controller.abort()
      window.clearTimeout(timer)
    }
    // rockTemplatesReady forces exactly one extra run once the NASA rock
    // shapes arrive, so the field does not stay on icosahedra all session
    // just because nothing else happened to change afterwards.
  }, [activeWaypoint, cameraMode, exaggeration, status, waypoints, rockTemplatesReady, rockVisualTemplatesReady, isPlaying, onLocalNavigation])

  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready') return
    // The point cloud and terrain net now show in both camera modes -- a
    // real perception HUD (see reference captures) reads the scan the same
    // way whether you're standing on the surface or looking down at it. Only
    // the animated rotating sweep beam stays FPS-only: at orbit's pulled-back
    // distance it collapses to a barely visible line, not worth the draw.
    state.lidarPoints.visible = lidarEnabled
    state.terrainNet.visible = lidarEnabled
    state.lidarSweep.visible = lidarEnabled && cameraMode === 'fps'
    state.rockBoxContainer.style.display = lidarEnabled ? '' : 'none'
    // The physical sensor mast/dome model is never shown -- see where
    // rover.mast/rover.lidarHead are created, just below createRoverModel().
  }, [lidarEnabled, cameraMode, status])

  // Start/Goal are useful while composing a mission, then the generated route
  // has its own endpoint markers. Keep the placement cursors only for the
  // former so a planned route does not show two competing marker systems.
  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready') return
    const routeIsGenerated = Boolean(waypoints && waypoints.length >= 2)
    for (const marker of Object.values(state.endpointMarkers)) {
      marker.group.visible = Boolean(marker.group.userData.placed) && !routeIsGenerated
    }
  }, [status, waypoints])

  // ── Planned route, drawn in the same metric frame as the mesh. ─────────────
  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready') return
    const { routeGroup, manifest, mesh } = state

    for (const child of routeGroup.children) {
      if (child instanceof THREE.Mesh || child instanceof THREE.Line) {
        child.geometry.dispose()
        ;(child.material as THREE.Material).dispose()
      }
    }
    routeGroup.clear()
    if (!waypoints || waypoints.length < 2) return

    const { rows, cols, resolution_m: res } = manifest.grid
    const { min_m: minM } = manifest.elevation
    const vx = mesh.scale.z
    // Match PlaneGeometry's own vertex placement exactly rather than assuming
    // a res-sized step: it spans cols*res across cols-1 segments, so the step
    // is very slightly wider than res and the edge vertices sit on +/- half
    // the full span. Close enough to ignore over one cell, half a cell off by
    // the far corner if you don't.
    const stepX = (cols * res) / (cols - 1)
    const stepZ = (rows * res) / (rows - 1)
    const halfX = (cols * res) / 2
    const halfZ = (rows * res) / 2
    // The route has to stand on the SAME surface the rover drives on, and
    // that surface is the mesh's own geometry -- sampleTerrainHeight reads
    // the very heights array the vertices were built from, then applies
    // mesh.scale.z. The waypoint's own altitude_m is a different source (the
    // backend's DEM lookup at cell centres, unscaled), so using it drew the
    // path in a frame the mesh does not share: in FPS mode, where the mesh
    // is life-size but the route was still lifted by the orbit exaggeration,
    // the ribbon hung in the sky above the terrain entirely. Falling back to
    // the waypoint altitude only where the sample misses (off-grid, or a
    // NaN in the DEM) keeps a route drawn at all rather than collapsing it
    // to y=0.
    const terrainField: TerrainField = {
      rows,
      cols,
      resolutionM: res,
      minElevationM: minM,
      heights: state.heights ?? new Float32Array(0),
      verticalScale: vx,
    }
    const points = waypoints.map((w) => {
      // Row 0 is the north (-Z) edge after the -90 deg tilt.
      const x = w.col * stepX - halfX
      const z = w.row * stepZ - halfZ
      const sampled = state.heights ? sampleTerrainHeight(terrainField, x, z) : null
      const groundY = sampled ?? ((w.altitude_m ?? minM) - minM) * vx
      // Just clear of the surface: enough that z-fighting never speckles the
      // ribbon, far too little to read as floating. The old +4 m was a
      // rover-height hover even when the rest of the frame was right.
      return new THREE.Vector3(x, groundY + ROUTE_RIBBON_LIFT_M, z)
    })

    // Re-sample along each planned chord so the ribbon follows the ground
    // between waypoints instead of spanning it. Heights come from the same
    // terrain sample as the nodes themselves, so a resampled point is no
    // more approximate than a planned one -- it is simply the surface, read
    // more often.
    const sampleGroundY = (x: number, z: number, fallback: number) => {
      const sampled = state.heights ? sampleTerrainHeight(terrainField, x, z) : null
      return (sampled ?? fallback) + ROUTE_RIBBON_LIFT_M
    }
    const path: THREE.Vector3[] = [points[0]]
    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i]
      const b = points[i + 1]
      const span = Math.hypot(b.x - a.x, b.z - a.z)
      const steps = Math.max(1, Math.ceil(span / ROUTE_RESAMPLE_STEP_M))
      for (let k = 1; k <= steps; k++) {
        const t = k / steps
        const x = THREE.MathUtils.lerp(a.x, b.x, t)
        const z = THREE.MathUtils.lerp(a.z, b.z, t)
        // The straight-line height between the two nodes is the fallback,
        // used only where the DEM sample misses.
        const chordY = THREE.MathUtils.lerp(a.y, b.y, t) - ROUTE_RIBBON_LIFT_M
        path.push(new THREE.Vector3(x, sampleGroundY(x, z, chordY), z))
      }
    }
    // A flat, glowing ribbon rather than a thin wire: reference perception
    // HUDs draw the planned path as a road-width band on the ground, not a
    // 1px line lost against a metre-scale rock field. Each segment gets its
    // own perpendicular (cross of travel direction with world-up), so a
    // sharp turn seams rather than mitres -- fine at this width.
    // Two attributes drive the look: `across` (-1..1 edge-to-edge) lets the
    // shader fade the corridor's rim and burn its two rails, and `along`
    // (metres travelled) carries the energy pulse down the path at a real
    // speed rather than a per-vertex-index one, so pulse spacing stays
    // constant whether waypoints are 2 m or 20 m apart.
    const ribbonVerts: number[] = []
    const ribbonAcross: number[] = []
    const ribbonAlong: number[] = []
    const up = new THREE.Vector3(0, 1, 0)
    let travelled = 0
    const distances: number[] = [0]
    for (let i = 1; i < path.length; i++) {
      travelled += path[i].distanceTo(path[i - 1])
      distances.push(travelled)
    }
    const totalLength = travelled

    for (let i = 0; i < path.length - 1; i++) {
      const a = path[i]
      const b = path[i + 1]
      const dir = new THREE.Vector3().subVectors(b, a)
      if (dir.lengthSq() < 1e-6) continue
      dir.normalize()
      const perp = new THREE.Vector3()
        .crossVectors(dir, up)
        .normalize()
        .multiplyScalar(ROUTE_RIBBON_HALF_WIDTH_M)
      // Each rail is re-sampled at its OWN offset position rather than
      // inheriting the centreline's height. Across any cross-slope the two
      // edges sit at different elevations, and holding both at the centre
      // height tips the band out of the hillside -- one rail buried, the
      // other standing off the ground on a visible skirt. Sampling per
      // corner banks the ribbon into the slope instead.
      const edge = (base: THREE.Vector3, sign: 1 | -1) => {
        const x = base.x + perp.x * sign
        const z = base.z + perp.z * sign
        return new THREE.Vector3(x, sampleGroundY(x, z, base.y - ROUTE_RIBBON_LIFT_M), z)
      }
      const aL = edge(a, 1)
      const aR = edge(a, -1)
      const bL = edge(b, 1)
      const bR = edge(b, -1)
      const da = distances[i]
      const db = distances[i + 1]
      ribbonVerts.push(
        aL.x, aL.y, aL.z, aR.x, aR.y, aR.z, bR.x, bR.y, bR.z,
        aL.x, aL.y, aL.z, bR.x, bR.y, bR.z, bL.x, bL.y, bL.z,
      )
      ribbonAcross.push(1, -1, -1, 1, -1, 1)
      ribbonAlong.push(da, da, db, da, db, db)
    }
    const ribbonGeometry = new THREE.BufferGeometry()
    ribbonGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(ribbonVerts), 3))
    ribbonGeometry.setAttribute('across', new THREE.BufferAttribute(new Float32Array(ribbonAcross), 1))
    ribbonGeometry.setAttribute('along', new THREE.BufferAttribute(new Float32Array(ribbonAlong), 1))

    // Hand-written shader rather than a stack of meshes: the rails, the
    // scanline hatching, the travelling pulse and the edge falloff are all
    // functions of the same two attributes, so one draw call does what half
    // a dozen overlaid ribbons would have.
    const ribbonMaterial = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uColor: { value: new THREE.Color(0x36f5c8) },
        uRailColor: { value: new THREE.Color(0xaefff0) },
        uProgress: { value: -1 },
        uTotal: { value: Math.max(totalLength, 1e-3) },
      },
      vertexShader: `
        attribute float across;
        attribute float along;
        varying float vAcross;
        varying float vAlong;
        void main() {
          vAcross = across;
          vAlong = along;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform float uTime;
        uniform vec3 uColor;
        uniform vec3 uRailColor;
        uniform float uProgress;
        uniform float uTotal;
        varying float vAcross;
        varying float vAlong;

        void main() {
          float edge = abs(vAcross);

          // Two bright rails at the corridor edges, a dim floor between.
          float rail = smoothstep(0.72, 0.98, edge) * (1.0 - smoothstep(0.98, 1.0, edge));
          float floorFill = (1.0 - smoothstep(0.0, 0.95, edge)) * 0.16;

          // Rungs every 3 m: a surveyed corridor, not a painted stripe.
          float rung = smoothstep(0.86, 1.0, sin(vAlong * 2.094) * 0.5 + 0.5) * 0.22;

          // Energy pulses running toward the goal at 9 m/s.
          float pulse = fract((vAlong - uTime * 9.0) / 14.0);
          float pulseGlow = pow(1.0 - pulse, 8.0) * 0.85;

          // Everything behind the rover dims to a surveyed-but-driven trail,
          // so the path reads as progress rather than decoration. uProgress
          // < 0 means "not driving" and leaves the whole route lit.
          float driven = uProgress < 0.0 ? 0.0 : step(vAlong, uProgress);
          float wake = 1.0 - driven * 0.62;

          float intensity = (rail * 1.15 + floorFill + rung + pulseGlow) * wake;
          vec3 color = mix(uColor, uRailColor, rail * 0.75 + pulseGlow * 0.5);

          // Fade the last centimetre of the rim so the band has no hard
          // sawtooth edge against the regolith.
          float alpha = intensity * (1.0 - smoothstep(0.97, 1.0, edge));
          if (alpha < 0.01) discard;
          gl_FragColor = vec4(color, alpha);
        }
      `,
    })
    const ribbon = new THREE.Mesh(ribbonGeometry, ribbonMaterial)
    // Drawn after the terrain and the rocks so the additive glow lands on
    // top of them rather than being sorted behind whatever it crosses.
    ribbon.renderOrder = 3
    routeGroup.add(ribbon)
    routeRibbonRef.current = { material: ribbonMaterial, distances, totalLength }
    // Endpoint markers. A solid ball works from orbit and fails completely on
    // the surface: the start sits exactly where the rover -- and therefore the
    // FPS eye -- begins, so at 3 m radius against a 3.2 m eye height it filled
    // the screen with flat colour on the first frame of every drive. On the
    // ground these are drawn instead as a flat ring painted on the regolith,
    // which is what a landing/target marker looks like from a rover's own
    // camera and cannot swallow the view however close you stand to it.
    const onSurface = cameraMode === 'fps'
    const marker = (p: THREE.Vector3, color: number) => {
      if (onSurface) {
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(res * 0.34, res * 0.5, 40),
          new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity: 0.85,
            side: THREE.DoubleSide,
            depthWrite: false,
          }),
        )
        // RingGeometry is built in the XY plane; lay it flat on the ground.
        ring.rotation.x = -Math.PI / 2
        ring.position.set(p.x, p.y + ROUTE_RIBBON_LIFT_M, p.z)
        ring.renderOrder = 4
        return ring
      }
      return new THREE.Mesh(
        new THREE.SphereGeometry(res * 0.6, 12, 12),
        new THREE.MeshBasicMaterial({ color }),
      ).translateX(p.x).translateY(p.y).translateZ(p.z)
    }
    routeGroup.add(marker(points[0], 0x2ee59d))
    routeGroup.add(marker(points[points.length - 1], 0xff5252))
  }, [waypoints, exaggeration, cameraMode, status])

  // ── 3D Camera Mode (FPS Surface View vs Orbit Overview) ─────────────────────
  const fpsAngles = useRef({ yaw: 0.35, pitch: 0.02 })
  /**
   * Set once the driver drags the view in FPS mode. From then on the camera
   * effect below moves the eye with the rover but leaves the AIM alone.
   *
   * Without this the two fought each other and the driver always lost: the
   * effect re-runs on every activeWaypoint/roverFraction change -- about 20
   * times a second during playback -- and each run ended in a camera.lookAt()
   * back down the terrain gradient. Dragging while parked worked, because
   * nothing re-ran; dragging while driving appeared to do nothing at all,
   * since the next tick (~50 ms later) overwrote it. Reset when the camera
   * mode is re-entered or a new route is loaded, so the automatic framing
   * still gets to introduce each drive.
   */
  const fpsLookOwnedByUser = useRef(false)

  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready' || !state.camera || !state.controls || cameraMode !== 'fps') return
    const { camera, controls, manifest, heights } = state
    const { rows, cols, resolution_m: res } = manifest.grid
    const { min_m: minM } = manifest.elevation

    const stepX = (cols * res) / (cols - 1)
    const stepZ = (rows * res) / (rows - 1)
    const halfX = (cols * res) / 2
    const halfZ = (rows * res) / 2

    controls.enabled = false

    const poseWaypoint = activeWaypoint ?? waypoints?.[0]
    const r = THREE.MathUtils.clamp(poseWaypoint?.row ?? Math.floor(rows / 2), 1, rows - 2)
    const c = THREE.MathUtils.clamp(poseWaypoint?.col ?? Math.floor(cols / 2), 1, cols - 2)
    const idx = r * cols + c
    const altM = heights && idx < heights.length && !Number.isNaN(heights[idx]) ? heights[idx] : minM + 325

    // Same interpolation the rover body itself uses (see the lightweight
    // rover-position effect) -- without it the FPS eye would visibly snap
    // from node to node every ~50 ms while the rover it is supposedly
    // riding glides smoothly between them, the two falling out of sync.
    const nextWaypointIndex = poseWaypoint
      ? (waypoints?.findIndex((w) => w.step === poseWaypoint.step) ?? -1)
      : -1
    const nextWaypoint = nextWaypointIndex >= 0 ? waypoints?.[nextWaypointIndex + 1] : null
    let rx = c * stepX - halfX
    let rz = r * stepZ - halfZ
    let ry = altM - minM + 3.2 // eye height above surface
    if (nextWaypoint) {
      const nr = THREE.MathUtils.clamp(nextWaypoint.row, 1, rows - 2)
      const nc = THREE.MathUtils.clamp(nextWaypoint.col, 1, cols - 2)
      const nIdx = nr * cols + nc
      const nAltM = heights && nIdx < heights.length && !Number.isNaN(heights[nIdx]) ? heights[nIdx] : altM
      const t = THREE.MathUtils.clamp(roverFraction, 0, 1)
      rx = THREE.MathUtils.lerp(rx, nc * stepX - halfX, t)
      rz = THREE.MathUtils.lerp(rz, nr * stepZ - halfZ, t)
      ry = THREE.MathUtils.lerp(altM, nAltM, t) - minM + 3.2
    }

    camera.position.set(rx, ry, rz)
    camera.up.set(0, 1, 0)

    // Look across the lunar plain towards the horizon and the Earth in the sky.
    // A fixed shallow pitch is not safe here: this site's terrain carries
    // real local slopes up to ~20 deg, and a pitch shallower than the
    // ground's own downhill slope never re-intersects the surface -- the
    // sightline flies over the terrain forever, rendering nothing but the
    // background colour. Aiming at an actual point ON the terrain some
    // distance ahead makes the pitch self-correct to whatever the ground
    // requires, on any slope.
    const sample = (row: number, col: number) => heights?.[row * cols + col] ?? altM
    const gradientX = (sample(r, c + 1) - sample(r, c - 1)) / (2 * stepX)
    const gradientZ = (sample(r + 1, c) - sample(r - 1, c)) / (2 * stepZ)
    // This bearing points down the local gradient instead of directly into
    // an uphill face.
    const yaw = Math.atan2(-gradientX, gradientZ)

    const LOOKAHEAD_M = 60 // matches the LiDAR's own max range
    const targetWorldX = rx + Math.sin(yaw) * LOOKAHEAD_M
    const targetWorldZ = rz - Math.cos(yaw) * LOOKAHEAD_M
    const targetCol = THREE.MathUtils.clamp(Math.round((targetWorldX + halfX) / stepX), 0, cols - 1)
    const targetRow = THREE.MathUtils.clamp(Math.round((targetWorldZ + halfZ) / stepZ), 0, rows - 1)
    const targetIdx = targetRow * cols + targetCol
    const targetAltM =
      heights && targetIdx < heights.length && !Number.isNaN(heights[targetIdx])
        ? heights[targetIdx]
        : altM
    const targetWorldY = targetAltM - minM + 1.6

    if (fpsLookOwnedByUser.current) {
      // The driver is aiming. Keep the eye travelling with the rover, but
      // re-apply THEIR angles instead of the gradient-derived ones.
      const { yaw: heldYaw, pitch: heldPitch } = fpsAngles.current
      const dir = new THREE.Vector3(
        Math.sin(heldYaw) * Math.cos(heldPitch),
        Math.sin(heldPitch),
        -Math.cos(heldYaw) * Math.cos(heldPitch),
      )
      camera.lookAt(camera.position.clone().add(dir))
      camera.updateProjectionMatrix()
      return
    }

    camera.lookAt(targetWorldX, targetWorldY, targetWorldZ)
    camera.updateProjectionMatrix()

    const forward = new THREE.Vector3(targetWorldX - rx, targetWorldY - ry, targetWorldZ - rz).normalize()
    fpsAngles.current = { yaw, pitch: Math.asin(THREE.MathUtils.clamp(forward.y, -1, 1)) }
  }, [activeWaypoint, roverFraction, cameraMode, waypoints, status])

  // A fresh drive, or a return to first person, gets the automatic framing
  // back -- otherwise one drag early in a session would leave every later
  // route staring off at whatever the driver last looked at.
  useEffect(() => {
    fpsLookOwnedByUser.current = false
  }, [cameraMode, waypoints])

  // ── Orbit camera setup ───────────────────────────────────────────────────────
  // Deliberately NOT keyed on activeWaypoint/roverFraction: this used to share
  // one effect with the FPS branch above, so every playback tick re-ran
  // camera.position.set(...)/controls.target.set(...) here too and snapped the
  // view back to the default far overview -- the rover would start driving
  // and the camera would immediately "pull back", and any zoom the user had
  // dialled in with the scroll wheel got wiped every ~50 ms. This now runs
  // only when orbit mode is actually entered (or the DEM changes), leaving
  // OrbitControls' own zoom/pan/rotate alone for the rest of playback.
  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready' || !state.camera || !state.controls || cameraMode !== 'orbit') return
    const { camera, controls, manifest } = state
    const { rows, cols, resolution_m: res } = manifest.grid
    const span = Math.max(rows, cols) * res

    controls.enabled = true
    camera.fov = 45
    camera.updateProjectionMatrix()
    const relief = manifest.elevation.max_m - manifest.elevation.min_m
    const targetY = relief * 0.35
    camera.position.set(
      span * 0.72,
      Math.max(targetY + span * 0.75, relief + span * 0.45),
      span * 0.75,
    )
    controls.target.set(0, targetY, 0)
    controls.minDistance = 150
    controls.maxDistance = span * 4.0
    controls.maxPolarAngle = Math.PI / 2 - 0.02
    controls.update()
  }, [cameraMode, status])

  // ── FPS Mouse Drag Look Handler ─────────────────────────────────────────────
  useEffect(() => {
    const container = containerRef.current
    const state = sceneRef.current
    if (!container || !state || status !== 'ready' || cameraMode !== 'fps') return

    const { camera } = state
    if (!camera) return

    let isDown = false
    let startX = 0
    let startY = 0

    const isSceneControl = (target: EventTarget | null) =>
      target instanceof Element &&
      Boolean(target.closest('button, input, label, .terrain3d-lidar, .terrain3d-camera-switch'))

    const updateLook = () => {
      const { yaw, pitch } = fpsAngles.current
      const dir = new THREE.Vector3(
        Math.sin(yaw) * Math.cos(pitch),
        Math.sin(pitch),
        -Math.cos(yaw) * Math.cos(pitch),
      )
      camera.lookAt(camera.position.clone().add(dir))
      camera.up.set(0, 1, 0)
    }

    const onPointerDown = (e: PointerEvent) => {
      // Camera controls live inside the same container as the WebGL canvas.
      // Capturing their pointer here retargets pointerup to the container and
      // prevents the browser from emitting the button's click event.
      if (e.button !== 0 || isSceneControl(e.target)) return
      isDown = true
      startX = e.clientX
      startY = e.clientY
      container.setPointerCapture?.(e.pointerId)
    }

    const onPointerMove = (e: PointerEvent) => {
      if (!isDown) return
      const dx = e.clientX - startX
      const dy = e.clientY - startY
      startX = e.clientX
      startY = e.clientY

      // Any real drag hands the aim to the driver for the rest of this
      // route. A stationary click (dx = dy = 0) must not, or simply
      // clicking to place a waypoint would freeze the automatic framing.
      if (dx !== 0 || dy !== 0) fpsLookOwnedByUser.current = true

      fpsAngles.current.yaw -= dx * 0.003
      fpsAngles.current.pitch = THREE.MathUtils.clamp(
        fpsAngles.current.pitch - dy * 0.003,
        -0.45,
        0.65,
      )
      updateLook()
    }

    const onPointerUp = (e: PointerEvent) => {
      isDown = false
      container.releasePointerCapture?.(e.pointerId)
    }

    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      camera.fov = THREE.MathUtils.clamp(camera.fov + e.deltaY * 0.03, 28, 65)
      camera.updateProjectionMatrix()
    }

    container.addEventListener('pointerdown', onPointerDown)
    container.addEventListener('pointermove', onPointerMove)
    container.addEventListener('pointerup', onPointerUp)
    container.addEventListener('pointercancel', onPointerUp)
    container.addEventListener('wheel', onWheel, { passive: false })

    return () => {
      container.removeEventListener('pointerdown', onPointerDown)
      container.removeEventListener('pointermove', onPointerMove)
      container.removeEventListener('pointerup', onPointerUp)
      container.removeEventListener('pointercancel', onPointerUp)
      container.removeEventListener('wheel', onWheel)
    }
  }, [cameraMode, status])

  // Live terrain cursor for Start/Goal selection. It intersects the actual
  // DEM height field, then snaps to the same cell the click handler commits,
  // without raycasting the 500 x 500 render mesh on every mouse-move.
  useEffect(() => {
    const container = containerRef.current
    const state = sceneRef.current
    if (!container || !state || status !== 'ready' || !onCellClick || !clickMode || clickMode === 'idle') return
    const { camera, manifest, heights, mesh, selectionCursor } = state
    if (!camera || !heights) return

    const { rows, cols, resolution_m: resolutionM } = manifest.grid
    const width = cols * resolutionM
    const depth = rows * resolutionM
    const stepX = width / (cols - 1)
    const stepZ = depth / (rows - 1)
    const terrain: TerrainField = {
      rows, cols, resolutionM,
      minElevationM: manifest.elevation.min_m,
      heights,
      verticalScale: mesh.scale.z,
    }
    const raycaster = new THREE.Raycaster()
    const groundPoint = new THREE.Vector3()
    const terrainNormal = new THREE.Vector3()
    const up = new THREE.Vector3(0, 1, 0)

    const clearPreview = () => {
      selectionPreviewRef.current = null
      selectionCursor.group.visible = false
    }

    const onMove = (event: PointerEvent) => {
      if (event.target instanceof Element && event.target.closest('button, input, label, .terrain3d-lidar, .terrain3d-camera-switch')) {
        clearPreview()
        return
      }
      const rect = container.getBoundingClientRect()
      const ndc = new THREE.Vector2(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1,
      )
      raycaster.setFromCamera(ndc, camera)
      if (!intersectTerrainHeightfield(raycaster.ray, terrain, groundPoint)) {
        clearPreview()
        return
      }

      const col = Math.round((groundPoint.x + width / 2) / stepX)
      const row = Math.round((groundPoint.z + depth / 2) / stepZ)
      if (row < 0 || row >= rows || col < 0 || col >= cols) {
        clearPreview()
        return
      }
      const x = col * stepX - width / 2
      const z = row * stepZ - depth / 2
      const y = sampleTerrainHeight(terrain, x, z)
      if (y === null) {
        clearPreview()
        return
      }

      terrainNormal.copy(sampleTerrainNormal(terrain, x, z))
      selectionCursor.setMode(clickMode)
      selectionCursor.group.position.set(x, y + 0.16, z)
      selectionCursor.group.quaternion.setFromUnitVectors(up, terrainNormal)
      selectionCursor.group.visible = true
      selectionPreviewRef.current = { row, col, clientX: event.clientX, clientY: event.clientY }
    }

    selectionCursor.setMode(clickMode)
    selectionCursor.group.visible = false
    container.style.cursor = 'crosshair'
    container.addEventListener('pointermove', onMove)
    container.addEventListener('pointerleave', clearPreview)
    return () => {
      clearPreview()
      container.style.cursor = ''
      container.removeEventListener('pointermove', onMove)
      container.removeEventListener('pointerleave', clearPreview)
    }
  }, [cameraMode, clickMode, onCellClick, status])

  // ── Click-to-select start/goal ──────────────────────────────────────────────
  // Mirrors MapCanvas's own picker exactly (same onCellClick(row, col)
  // signature, same clickMode) so App.tsx wires this in without a second
  // start/goal state machine. A plain 'click' event would also fire after
  // dragging to orbit or FPS-look around -- the down/up position tracked
  // here is what tells a real click from a released drag.
  useEffect(() => {
    const container = containerRef.current
    const state = sceneRef.current
    if (!container || !state || status !== 'ready' || !onCellClick || !clickMode || clickMode === 'idle') {
      return
    }
    const { camera, mesh, manifest, selectionCursor, endpointMarkers } = state
    if (!camera) return

    let downX = 0
    let downY = 0
    let tracking = false
    const raycaster = new THREE.Raycaster()

    const placeEndpointMarker = (mode: Exclude<ClickMode, 'idle'>, point: THREE.Vector3, normal: THREE.Vector3) => {
      const marker = endpointMarkers[mode]
      marker.setMode(mode)
      marker.group.position.copy(point).addScaledVector(normal, 0.16)
      marker.group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal)
      marker.group.userData.placed = true
      marker.group.visible = true
    }

    const onDown = (e: PointerEvent) => {
      if (e.button !== 0) return
      downX = e.clientX
      downY = e.clientY
      tracking = true
    }

    const onUp = (e: PointerEvent) => {
      if (!tracking) return
      tracking = false
      if (Math.hypot(e.clientX - downX, e.clientY - downY) > 6) return

      // Prefer the cell visibly marked under the pointer. The proximity check
      // prevents a stale preview from being used if a click arrives before a
      // matching pointermove event.
      const preview = selectionPreviewRef.current
      if (preview && Math.hypot(e.clientX - preview.clientX, e.clientY - preview.clientY) <= 8) {
        const marker = endpointMarkers[clickMode]
        marker.setMode(clickMode)
        marker.group.position.copy(selectionCursor.group.position)
        marker.group.quaternion.copy(selectionCursor.group.quaternion)
        marker.group.userData.placed = true
        marker.group.visible = true
        onCellClick(preview.row, preview.col)
        return
      }

      const rect = container.getBoundingClientRect()
      const ndc = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1,
      )
      raycaster.setFromCamera(ndc, camera)
      const hit = raycaster.intersectObject(mesh, false)[0]
      if (!hit) return

      // The exact inverse of the x = col*stepX - halfX / z = row*stepZ -
      // halfZ mapping every rock, the rover and the route line already use
      // to go the other way -- hit.point is already world-space, so no
      // rotation math is needed here.
      const { rows, cols, resolution_m: res } = manifest.grid
      const width = cols * res
      const depth = rows * res
      const stepX = width / (cols - 1)
      const stepZ = depth / (rows - 1)
      const col = Math.round((hit.point.x + width / 2) / stepX)
      const row = Math.round((hit.point.z + depth / 2) / stepZ)
      if (row < 0 || row > rows - 1 || col < 0 || col > cols - 1) return
      const normal = hit.face
        ? hit.face.normal.clone().transformDirection(mesh.matrixWorld).normalize()
        : new THREE.Vector3(0, 1, 0)
      placeEndpointMarker(clickMode, hit.point, normal)
      onCellClick(row, col)
    }

    container.addEventListener('pointerdown', onDown)
    container.addEventListener('pointerup', onUp)
    return () => {
      container.removeEventListener('pointerdown', onDown)
      container.removeEventListener('pointerup', onUp)
    }
  }, [status, clickMode, onCellClick])

  return (
    <div
      className={`terrain3d-root${clickMode && clickMode !== 'idle' ? ' is-picking' : ''}`}
      ref={containerRef}
    >
      {status === 'loading' && <div className="terrain3d-status">Loading terrain…</div>}
      {status === 'error' && (
        <div className="terrain3d-status">3-D terrain failed to load — is the API running?</div>
      )}

      {status === 'ready' && (
        <aside className={`terrain3d-lidar ${lidarEnabled ? 'is-live' : 'is-off'}`}>
          <div className="terrain3d-lidar-head">
            <div className="terrain3d-lidar-title">
              <span className="terrain3d-radar-icon" aria-hidden="true"><span /></span>
              <div>
                <strong>LiDAR perception</strong>
                <small>FIRST RETURN · 16 CH · {LIDAR_CONFIG.scanRateHz} HZ</small>
              </div>
            </div>
            <button
              type="button"
              className="terrain3d-lidar-toggle"
              aria-pressed={lidarEnabled}
              onClick={() => setLidarEnabled((enabled) => !enabled)}
            >
              {lidarEnabled ? 'LIVE' : 'OFF'}
            </button>
          </div>

          {lidarEnabled && lidarTelemetry && (
            <>
              <div className="terrain3d-lidar-grid">
                <div><span>RANGE</span><strong>{LIDAR_CONFIG.maxRangeM} m</strong></div>
                <div><span>RETURNS</span><strong>{lidarTelemetry.returns.toLocaleString()}</strong></div>
                <div><span>ROCK HITS</span><strong>{lidarTelemetry.rockReturns}</strong></div>
                <div><span>OCCUPIED</span><strong>{localNavigation?.occupiedCells ?? 0}</strong></div>
                <div>
                  <span>NEAREST</span>
                  <strong className={
                    lidarTelemetry.nearestObstacleM !== null && lidarTelemetry.nearestObstacleM < 12
                      ? 'is-danger'
                      : ''
                  }>
                    {lidarTelemetry.nearestObstacleM === null
                      ? '--'
                      : `${lidarTelemetry.nearestObstacleM.toFixed(1)} m`}
                  </strong>
                </div>
              </div>
              <div className="terrain3d-lidar-footer">
                <span className="terrain3d-lidar-ramp-label">
                  <i className="terrain3d-lidar-ramp" />
                  LOW&nbsp;&rarr;&nbsp;HIGH (elev.)
                </span>
                <b className={
                  lidarTelemetry.nearestObstacleM !== null && lidarTelemetry.nearestObstacleM < 12
                    ? 'is-danger'
                    : ''
                }>
                  {lidarTelemetry.detectedRocks} rocks tracked
                </b>
                {localNavigation && (
                  <b className={localNavigation.decision === 'FOLLOW' ? '' : 'is-danger'}>
                    {localNavigation.observedObstacles} observed · {localNavigation.decision}
                  </b>
                )}
              </div>
            </>
          )}
        </aside>
      )}

      {/* Camera mode: on the surface with the rover, or above it. */}
      {status === 'ready' && (
        <div className="terrain3d-camera-switch">
          <button
            type="button"
            className={`terrain3d-cam-btn ${cameraMode === 'fps' ? 'is-active' : ''}`}
            onClick={() => setCameraMode('fps')}
            title="First-person view from the surface, at rover eye height"
          >
            <Icon name="target" className="cam-icon" />
            <span>First person</span>
          </button>
          <button
            type="button"
            className={`terrain3d-cam-btn ${cameraMode === 'orbit' ? 'is-active' : ''}`}
            onClick={() => setCameraMode('orbit')}
            title="Orbit view, looking down on the site"
          >
            <Icon name="map" className="cam-icon" />
            <span>Orbit</span>
          </button>

          {canFullscreen && onToggleFullscreen && (
            <>
              {/* Divider: fullscreen changes the viewport, not the camera, so
                  it should not read as a third mutually-exclusive mode. */}
              <span className="terrain3d-cam-divider" aria-hidden="true" />
              <button
                type="button"
                className="terrain3d-cam-btn terrain3d-cam-btn--icon"
                aria-pressed={fullscreen}
                onClick={onToggleFullscreen}
                title={
                  fullscreen
                    ? 'Exit fullscreen (Esc)'
                    : 'Fill the screen with the 3-D view'
                }
              >
                <Icon
                  name={fullscreen ? 'fullscreenexit' : 'fullscreen'}
                  className="cam-icon"
                />
                <span className="lp-visually-hidden">
                  {fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
                </span>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
