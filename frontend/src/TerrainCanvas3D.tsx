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
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import type { MapViewMode } from './MapCanvas'
import type { Waypoint } from './api'
import {
  buildLidarScanFromBackend,
  fetchBackendLidarScan,
  generateRockField,
  LIDAR_CONFIG,
  sampleTerrainHeight,
  seededRandom,
  simulateLidarScan,
} from './lidarSimulation'
import type { LidarScanResult, LidarScanSummary, TerrainField } from './lidarSimulation'

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

async function fetchF32(url: string): Promise<Float32Array> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`${url} -> ${response.status}`)
  return new Float32Array(await response.arrayBuffer())
}

// ── 3D Deep Space Environment Generators ──────────────────────────────────────

function createStarfieldTexture(): THREE.Texture {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')
  if (!ctx) return new THREE.Texture()
  const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  grad.addColorStop(0, 'rgba(255, 255, 255, 1.0)')
  grad.addColorStop(0.15, 'rgba(240, 245, 255, 0.9)')
  grad.addColorStop(0.4, 'rgba(180, 220, 255, 0.35)')
  grad.addColorStop(0.7, 'rgba(120, 170, 255, 0.08)')
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 64, 64)
  return new THREE.CanvasTexture(canvas)
}

function createStarfield(count = 3500, radius = 70000): THREE.Points {
  const geometry = new THREE.BufferGeometry()
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)
  const colorObj = new THREE.Color()

  const starPalettes = [
    new THREE.Color(0xffffff), // Pure white
    new THREE.Color(0xdbeafe), // O/B blue-white
    new THREE.Color(0x93c5fd), // High-temp electric blue
    new THREE.Color(0xfef08a), // Solar yellow
    new THREE.Color(0xfdcba8), // K-type orange
    new THREE.Color(0xfca5a5), // Red giant
  ]

  for (let i = 0; i < count; i++) {
    const u = Math.random()
    const v = Math.random()
    const theta = u * 2.0 * Math.PI
    const phi = Math.acos(2.0 * v - 1.0)
    const r = radius * (0.95 + Math.random() * 0.1)

    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
    positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
    positions[i * 3 + 2] = r * Math.cos(phi)

    const pick = Math.random()
    if (pick < 0.55) colorObj.copy(starPalettes[0])
    else if (pick < 0.75) colorObj.copy(starPalettes[1])
    else if (pick < 0.88) colorObj.copy(starPalettes[2])
    else if (pick < 0.95) colorObj.copy(starPalettes[3])
    else if (pick < 0.98) colorObj.copy(starPalettes[4])
    else colorObj.copy(starPalettes[5])

    const brightness = 0.5 + Math.random() * 0.5
    colors[i * 3] = colorObj.r * brightness
    colors[i * 3 + 1] = colorObj.g * brightness
    colors[i * 3 + 2] = colorObj.b * brightness
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  const material = new THREE.PointsMaterial({
    size: 26,
    map: createStarfieldTexture(),
    transparent: true,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })

  return new THREE.Points(geometry, material)
}

function createMilkyWayDust(count = 2000, radius = 68000): THREE.Points {
  const geometry = new THREE.BufferGeometry()
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)

  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2
    const spread = (Math.random() - 0.5) * 0.28
    const r = radius * (0.92 + Math.random() * 0.16)

    const bx = Math.cos(angle) * r
    const by = spread * r
    const bz = Math.sin(angle) * r

    const cosInc = Math.cos(0.6)
    const sinInc = Math.sin(0.6)
    const x = bx
    const y = by * cosInc - bz * sinInc
    const z = by * sinInc + bz * cosInc

    positions[i * 3] = x
    positions[i * 3 + 1] = y
    positions[i * 3 + 2] = z

    const t = Math.random()
    colors[i * 3] = 0.35 * t + 0.15
    colors[i * 3 + 1] = 0.45 * t + 0.25
    colors[i * 3 + 2] = 0.85 * t + 0.35
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  const material = new THREE.PointsMaterial({
    size: 40,
    map: createStarfieldTexture(),
    transparent: true,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
    opacity: 0.35,
    depthWrite: false,
  })

  return new THREE.Points(geometry, material)
}

function createEarth(span: number): { group: THREE.Group; mesh: THREE.Mesh } {
  const group = new THREE.Group()

  const canvas = document.createElement('canvas')
  canvas.width = 1024
  canvas.height = 512
  const ctx = canvas.getContext('2d')!

  const oceanGrad = ctx.createLinearGradient(0, 0, 0, 512)
  oceanGrad.addColorStop(0, '#0a1d4a')
  oceanGrad.addColorStop(0.5, '#0e2b6e')
  oceanGrad.addColorStop(1, '#0a1d4a')
  ctx.fillStyle = oceanGrad
  ctx.fillRect(0, 0, 1024, 512)

  ctx.fillStyle = '#1e3a29'
  ctx.beginPath()
  ctx.ellipse(560, 220, 160, 100, 0.2, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.ellipse(530, 310, 80, 90, -0.1, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.ellipse(280, 200, 90, 110, -0.25, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.ellipse(330, 340, 70, 100, 0.2, 0, Math.PI * 2)
  ctx.fill()

  ctx.fillStyle = '#785428'
  ctx.beginPath()
  ctx.ellipse(520, 250, 70, 35, 0.05, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.ellipse(750, 360, 60, 45, 0.1, 0, Math.PI * 2)
  ctx.fill()

  ctx.fillStyle = '#f8fafc'
  ctx.beginPath()
  ctx.ellipse(512, 18, 480, 26, 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.ellipse(512, 496, 440, 30, 0, 0, Math.PI * 2)
  ctx.fill()

  ctx.fillStyle = 'rgba(255, 255, 255, 0.72)'
  ctx.beginPath()
  ctx.ellipse(340, 180, 120, 35, 0.3, 0, Math.PI * 2)
  ctx.ellipse(600, 260, 180, 40, -0.2, 0, Math.PI * 2)
  ctx.ellipse(260, 310, 100, 25, 0.15, 0, Math.PI * 2)
  ctx.ellipse(720, 170, 140, 30, 0.25, 0, Math.PI * 2)
  ctx.fill()

  ctx.strokeStyle = 'rgba(255, 255, 255, 0.65)'
  ctx.lineWidth = 10
  ctx.beginPath()
  ctx.arc(380, 210, 40, 0, Math.PI * 1.5)
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(680, 230, 45, Math.PI * 0.5, Math.PI * 2)
  ctx.stroke()

  const textureLoader = new THREE.TextureLoader()
  const earthTexture = textureLoader.load('/textures/earth_disc.jpg')
  earthTexture.colorSpace = THREE.SRGBColorSpace

  const earthRadius = span * 0.18
  const earthGeo = new THREE.SphereGeometry(earthRadius, 48, 48)
  const earthMat = new THREE.MeshStandardMaterial({
    map: earthTexture,
    roughness: 0.55,
    metalness: 0.05,
    emissive: new THREE.Color(0x112244),
    emissiveIntensity: 0.12,
  })
  const mesh = new THREE.Mesh(earthGeo, earthMat)
  group.add(mesh)

  const atmoGeo = new THREE.SphereGeometry(earthRadius * 1.06, 48, 48)
  const atmoMat = new THREE.MeshBasicMaterial({
    color: 0x38bdf8,
    transparent: true,
    opacity: 0.45,
    blending: THREE.AdditiveBlending,
    side: THREE.BackSide,
  })
  const atmoMesh = new THREE.Mesh(atmoGeo, atmoMat)
  group.add(atmoMesh)

  // Position Earth high in the upper-right sky above the lunar horizon (matching user screenshot)
  group.position.set(span * 1.5, span * 1.05, -span * 2.4)
  mesh.rotation.z = THREE.MathUtils.degToRad(23.4)

  return { group, mesh }
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
      const broad = 12 * Math.sin(x * 0.17) * Math.cos(y * 0.11)
      const grain = (random() - 0.5) * 34
      const value = THREE.MathUtils.clamp(104 + broad + grain, 55, 148)
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

/** Soft round sprite for locator markers -- a flat square SpriteMaterial dot
 * reads as a pixelated smear at any scale; this alpha-fades to the edge so
 * clusters blend instead of tiling visibly. */
function createSoftDotTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')!
  const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  grad.addColorStop(0, 'rgba(255, 255, 255, 1.0)')
  grad.addColorStop(0.5, 'rgba(255, 255, 255, 0.65)')
  grad.addColorStop(1, 'rgba(255, 255, 255, 0)')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 64, 64)
  return new THREE.CanvasTexture(canvas)
}

/** Point-cloud dot: a solid disc with only a 1-2 px antialiased rim, not a
 * soft glow. A LiDAR return is a discrete measurement -- CloudCompare, RViz
 * and PDAL all draw it as a crisp, fully-opaque dot, and the wide soft
 * falloff createSoftDotTexture uses reads as a faint, sparse haze at typical
 * point counts instead of the dense, confident cloud a real one shows. */
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
    return geometry
  } catch {
    return null
  }
}

const NASA_ROCK_TEMPLATE_URLS = [
  '/models/nasa_rocks/rock-15016.json',
  '/models/nasa_rocks/rock-15556.json',
]

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

interface Props {
  viewMode: MapViewMode
  waypoints: Waypoint[] | null
  /** Playback pose; the rover and its local LiDAR follow this waypoint. */
  activeWaypoint: Waypoint | null
  exaggeration: number | null
  sliceIndex: number
  /** Drape the real NAC photograph instead of shading a flat albedo. */
  photo: boolean
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
  exaggeration,
  sliceIndex,
  photo,
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
  // Real NASA Astromaterials 3D lunar sample scans (decimated offline --
  // see frontend/simplify_rock.mjs -- from ~100k verts down to a few
  // hundred), used as the rock field's shape templates once they arrive.
  // A ref, not state holding the geometries themselves: they are mutated
  // in place by nothing, read by the rock-generation effect on demand, and
  // do not need to trigger a re-render on their own -- rockTemplatesReady
  // is the flag that does that, exactly once, when loading finishes.
  const rockTemplatesRef = useRef<THREE.BufferGeometry[]>([])
  const [rockTemplatesReady, setRockTemplatesReady] = useState(false)

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
    rockGroup: THREE.Group
    rockMarkerGroup: THREE.Group
    rockMarkerMaterial: THREE.SpriteMaterial
    rockMaterial: THREE.MeshStandardMaterial
    rockTexture: THREE.Texture
    roverGroup: THREE.Group
    lidarHead: THREE.Group
    lidarPoints: THREE.Points
    lidarSweep: THREE.LineSegments
    lidarScan: LidarScanResult | null
    lidarOrigin: THREE.Vector3
    lidarRevolutionStartedAt: number
    earthMesh?: THREE.Mesh
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
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x020308)

    // Deep space celestial environment: Starfield & Milky Way
    const starfield = createStarfield(3500, 70000)
    scene.add(starfield)

    const milkyWay = createMilkyWayDust(2000, 68000)
    scene.add(milkyWay)

    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100000)
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
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
      color: 0x8b867f,
      map: rockTexture,
      roughness: 1,
      metalness: 0,
      // Smooth (not flat) shading: the NASA scan templates and the
      // icosahedron fallback both carry proper computeVertexNormals()
      // output, and interpolating between them is what keeps a few hundred
      // triangles reading as a rounded rock instead of a faceted gemstone.
      flatShading: false,
      // Defensive, not decorative: independent per-vertex displacement below
      // can fold a facet back on itself at high subdivision, flipping its
      // winding relative to the camera. FrontSide culls that facet outright,
      // which reads as a torn hole with the void showing through. DoubleSide
      // costs nothing visible on a convex rock and guarantees no gaps.
      side: THREE.DoubleSide,
    })
    const rockGroup = new THREE.Group()
    scene.add(rockGroup)

    const softDotTexture = createSoftDotTexture()
    const solidDotTexture = createSolidDotTexture()

    // Metre-scale rocks are correctly tiny across a 2.5 km overview. These
    // non-colliding markers make their locations inspectable in orbit mode;
    // the actual meshes and LiDAR intersections remain at physical scale.
    const rockMarkerMaterial = new THREE.SpriteMaterial({
      map: softDotTexture,
      color: 0xff9b52,
      transparent: true,
      opacity: 0.75,
      depthTest: false,
    })
    const rockMarkerGroup = new THREE.Group()
    scene.add(rockMarkerGroup)

    const regolithTexture = createRegolithTexture()

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
    // "Gerçek boyutlu" means it reads correctly next to the 0.3-2 m rocks
    // and the physically-scaled terrain, not a claim that every proportion
    // is a laser-measured replica of the real rover.
    const ROVER_MODEL_LENGTH_M = 1.5
    new GLTFLoader().load(
      '/models/viper-rover.glb',
      (gltf) => {
        if (disposed) return
        const model = gltf.scene
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
        const scaledHeight = size.y * scale

        // The procedural chassis/wheels are hidden, not removed: the mast
        // and LiDAR head stay the exact objects the sweep animation and the
        // orbit-mode scale toggle already reference, just resized and
        // repositioned onto the new body's roofline instead of the
        // placeholder box's. Sized for the OLD 1.85 m boxy chassis (0.82 m
        // mast on a 0.6 m body), the mast alone was nearly as tall as this
        // flatter model's entire body -- reading as a stuck-on antenna
        // rather than part of the vehicle. Scaling the sensor rig itself
        // down keeps it proportionate to whatever body it ends up sitting
        // on, model-generated or procedural.
        rover.chassis.visible = false
        rover.wheels.forEach((wheel) => {
          wheel.visible = false
        })
        const sensorScale = 0.55
        rover.mast.scale.setScalar(sensorScale)
        rover.lidarHead.scale.setScalar(sensorScale)
        const mastHeight = 0.82 * sensorScale
        rover.mast.position.y = scaledHeight + mastHeight / 2
        rover.lidarHead.position.y = scaledHeight + mastHeight + 0.03 * sensorScale

        rover.group.add(model)
      },
      undefined,
      (error) => {
        // Placeholder box+wheels stays visible; the scene still works.
        console.warn('Rover GLB failed to load, keeping the procedural placeholder', error)
      },
    )

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
      controls.minDistance = 150
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
        rockGroup,
        rockMarkerGroup,
        rockMarkerMaterial,
        rockMaterial,
        rockTexture,
        roverGroup: rover.group,
        lidarHead: rover.lidarHead,
        lidarPoints,
        lidarSweep,
        lidarScan: null,
        lidarOrigin: new THREE.Vector3(),
        lidarRevolutionStartedAt: performance.now(),
        earthMesh: earth.mesh,
        sunSprite: sunFlare,
        camera,
        controls,
        heights,
        dispose: () => {
          geometry.dispose()
          material.dispose()
          starfield.geometry.dispose()
          milkyWay.geometry.dispose()
          earth.mesh.geometry.dispose()
          rockGroup.children.forEach((rock) => {
            if (rock instanceof THREE.Mesh) rock.geometry.dispose()
          })
          rockMaterial.dispose()
          rockTexture.dispose()
          rockMarkerMaterial.dispose()
          regolithTexture.dispose()
          softDotTexture.dispose()
          solidDotTexture.dispose()
          rockTemplatesRef.current.forEach((geometry) => geometry.dispose())
          rockTemplatesRef.current = []
          disposeObjectTree(rover.group)
          lidarPointGeometry.dispose()
          lidarPointMaterial.dispose()
          sweepGeometry.dispose()
          ;(lidarSweep.material as THREE.Material).dispose()
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
    }

    build().catch((error: unknown) => {
      if (disposed) return
      setStatus('error')
      onError?.(error instanceof Error ? error.message : String(error))
    })

    const animate = () => {
      frame = requestAnimationFrame(animate)
      // OrbitControls.update() re-aims the camera at controls.target every
      // call, independent of `enabled` -- calling it unconditionally here
      // fought FPS mode's own camera.lookAt() every frame and snapped the
      // "surface" view back to staring down at the orbit target.
      if (controls.enabled) controls.update()
      const state = sceneRef.current
      if (state?.earthMesh) {
        state.earthMesh.rotation.y += 0.0004
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
      renderer.render(scene, camera)
    }
    animate()

    return () => {
      disposed = true
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
        () => onError?.('NAC dokusu yüklenemedi'),
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
        onError?.(`${layerName} katmanı yüklenemedi`)
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
    const roverGroundY = sampleTerrainHeight(terrain, roverX, roverZ) ?? 0

    state.roverGroup.position.set(roverX, roverGroundY, roverZ)
    const waypointIndex = source
      ? waypoints?.findIndex((waypoint) => waypoint.step === source.step) ?? -1
      : -1
    const nextWaypoint = waypointIndex >= 0 ? waypoints?.[waypointIndex + 1] : null
    if (nextWaypoint) {
      const nextX = nextWaypoint.col * stepX - width / 2
      const nextZ = nextWaypoint.row * stepZ - depth / 2
      state.roverGroup.rotation.y = Math.atan2(nextX - roverX, nextZ - roverZ)
    }
    state.roverGroup.scale.setScalar(cameraMode === 'orbit' ? 10 : 1)
    state.roverGroup.updateMatrixWorld(true)
    state.lidarOrigin.set(roverX, roverGroundY + 1.6, roverZ)
  }, [activeWaypoint, cameraMode, exaggeration, status, waypoints])

  // Local rock field + real first-return scan. Debounced (300 ms of no
  // further activeWaypoint change) so scrubbing or auto-playing the route
  // does not rebuild every rock mesh and re-fetch a backend LiDAR scan on
  // each of the playback timer's ~50 ms ticks -- the rover's own position
  // above is not gated on this and keeps up regardless.
  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready' || !state.heights) return
    const heights = state.heights

    const controller = new AbortController()
    let cancelled = false

    const timer = window.setTimeout(async () => {
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
      for (const child of [...state.rockGroup.children]) {
        state.rockGroup.remove(child)
        if (child instanceof THREE.Mesh) child.geometry.dispose()
      }
      state.rockMarkerGroup.clear()

      const rockTemplates = rockTemplatesRef.current
      for (const descriptor of generateRockField(roverX, roverZ)) {
        const groundY = sampleTerrainHeight(terrain, descriptor.x, descriptor.z)
        if (groundY === null) continue
        const random = seededRandom(descriptor.seed)
        let geometry: THREE.BufferGeometry
        if (rockTemplates.length > 0) {
          // A real Apollo sample's scanned shape (unit sphere, centred --
          // see fetchRockGeometryTemplate) is already organically irregular,
          // so it just needs the field's existing per-instance stretch, not
          // the synthetic per-vertex weathering the icosahedron fallback
          // below applies to make a symmetric polyhedron look like a rock.
          const templateIndex = Math.abs(descriptor.seed) % rockTemplates.length
          geometry = rockTemplates[templateIndex].clone()
          const positions = geometry.getAttribute('position') as THREE.BufferAttribute
          for (let i = 0; i < positions.count; i++) {
            positions.setXYZ(
              i,
              positions.getX(i) * descriptor.radiusX,
              positions.getY(i) * descriptor.radiusY,
              positions.getZ(i) * descriptor.radiusZ,
            )
          }
          positions.needsUpdate = true
          geometry.computeVertexNormals()
          geometry.computeBoundingSphere()
        } else {
          // Detail 1 (12 vertices) reads as a crumpled polyhedron, not a
          // rock -- detail 2 (42 vertices) gives enough facets for the
          // per-vertex weathering below to read as texture rather than as
          // the whole shape.
          geometry = new THREE.IcosahedronGeometry(1, 2)
          const positions = geometry.getAttribute('position') as THREE.BufferAttribute
          for (let i = 0; i < positions.count; i++) {
            const x = positions.getX(i)
            const y = positions.getY(i)
            const z = positions.getZ(i)
            // ONE factor per vertex, applied to all three axes: a radial
            // displacement along the vertex's own direction. Three
            // independent per-axis factors sheared neighbouring facets
            // against each other at this subdivision level, folding a
            // facet back on itself often enough to be the torn-hole look
            // DoubleSide above now also guards against.
            const weathering = 0.93 + random() * 0.12
            positions.setXYZ(
              i,
              x * descriptor.radiusX * weathering,
              y * descriptor.radiusY * weathering,
              z * descriptor.radiusZ * weathering,
            )
          }
          positions.needsUpdate = true
          geometry.computeVertexNormals()
          geometry.computeBoundingSphere()
        }
        const rock = new THREE.Mesh(geometry, state.rockMaterial)
        rock.position.set(descriptor.x, groundY - descriptor.radiusY * 0.12, descriptor.z)
        rock.rotation.set((random() - 0.5) * 0.18, descriptor.rotationY, (random() - 0.5) * 0.18)
        rock.userData.lidarRockId = descriptor.id
        state.rockGroup.add(rock)

        const marker = new THREE.Sprite(state.rockMarkerMaterial)
        marker.position.set(descriptor.x, groundY + descriptor.radiusY + 3, descriptor.z)
        marker.scale.set(4, 4, 1)
        marker.userData.rockId = descriptor.id
        state.rockMarkerGroup.add(marker)
      }

      // Position, heading, orbit-mode scale and lidarOrigin are the other
      // effect's job now (it is not debounced) -- rockGroup still needs its
      // own matrix refreshed here since it was just rebuilt above.
      state.rockGroup.updateMatrixWorld(true)

      const rockMeshes = state.rockGroup.children.filter(
        (object): object is THREE.Mesh => object instanceof THREE.Mesh,
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
      try {
        const backendScan = await fetchBackendLidarScan(row, col, 1.6, controller.signal)
        if (cancelled) return
        scan = buildLidarScanFromBackend(
          state.lidarOrigin,
          terrain.verticalScale,
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
      state.roverGroup.scale.setScalar(cameraMode === 'orbit' ? 10 : 1)
      // Marker visibility is the lidarEnabled/cameraMode effect's job now
      // (below) -- it reacts immediately, where this effect is debounced.
      for (const child of state.rockGroup.children) {
        child.scale.setScalar(orbitRockScale)
      }

      const pointGeometry = state.lidarPoints.geometry
      pointGeometry.setAttribute('position', new THREE.BufferAttribute(scan.positions, 3))
      pointGeometry.setAttribute('color', new THREE.BufferAttribute(scan.colors, 3))
      pointGeometry.computeBoundingSphere()
      setLidarTelemetry(scan.summary)
    }, 300)

    return () => {
      cancelled = true
      controller.abort()
      window.clearTimeout(timer)
    }
    // rockTemplatesReady forces exactly one extra run once the NASA rock
    // shapes arrive, so the field does not stay on icosahedra all session
    // just because nothing else happened to change afterwards.
  }, [activeWaypoint, cameraMode, exaggeration, status, waypoints, rockTemplatesReady])

  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready') return
    // The raw return cloud and sweep line are legible at FPS range -- each
    // point is metres from the sensor. At orbit scale the whole 60 m scan
    // collapses into a few dozen screen pixels around the rover and reads as
    // noise, not data; the rock markers already say "something is here" at
    // that scale, so the point cloud stays hidden there.
    const showLidarDetail = lidarEnabled && cameraMode === 'fps'
    state.lidarPoints.visible = showLidarDetail
    state.lidarSweep.visible = showLidarDetail
    // Rock markers are this scan's orbit-scale stand-in (see their own
    // comment at creation) -- turning the sensor off should hide every
    // trace of "detected rocks", not just the FPS-range point cloud.
    state.rockMarkerGroup.visible = lidarEnabled && cameraMode === 'orbit'
    // The physical sensor mast/dome model is never shown -- see where
    // rover.mast/rover.lidarHead are created, just below createRoverModel().
  }, [lidarEnabled, cameraMode, status])

  // ── Planned route, drawn in the same metric frame as the mesh. ─────────────
  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready') return
    const { routeGroup, manifest, mesh } = state

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
    const points = waypoints.map((w) => {
      // Row 0 is the north (-Z) edge after the -90 deg tilt.
      const x = w.col * stepX - halfX
      const z = w.row * stepZ - halfZ
      const y = ((w.altitude_m ?? minM) - minM) * vx + 4
      return new THREE.Vector3(x, y, z)
    })
    routeGroup.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(points),
        new THREE.LineBasicMaterial({ color: 0x00e5ff }),
      ),
    )
    // res * 2.5 = 12.5 m radius, a 25 m ball -- fine as a landmark against a
    // 2.5 km overview, but the scene now also renders 0.3-2 m rocks and a
    // LiDAR cloud at metre scale, and up close this dwarfed all of it. res
    // * 0.6 = 3 m radius still reads clearly from orbit while sitting only
    // a little larger than the rover itself at ground level.
    const marker = (p: THREE.Vector3, color: number) =>
      new THREE.Mesh(
        new THREE.SphereGeometry(res * 0.6, 12, 12),
        new THREE.MeshBasicMaterial({ color }),
      ).translateX(p.x).translateY(p.y).translateZ(p.z)
    routeGroup.add(marker(points[0], 0x2ee59d))
    routeGroup.add(marker(points[points.length - 1], 0xff5252))
  }, [waypoints, exaggeration, cameraMode, status])

  // ── 3D Camera Mode (FPS Surface View vs Orbit Overview) ─────────────────────
  const fpsAngles = useRef({ yaw: 0.35, pitch: 0.02 })

  useEffect(() => {
    const state = sceneRef.current
    if (!state || status !== 'ready' || !state.camera || !state.controls) return
    const { camera, controls, manifest, heights } = state
    const { rows, cols, resolution_m: res } = manifest.grid
    const { min_m: minM } = manifest.elevation
    const span = Math.max(rows, cols) * res

    const stepX = (cols * res) / (cols - 1)
    const stepZ = (rows * res) / (rows - 1)
    const halfX = (cols * res) / 2
    const halfZ = (rows * res) / 2

    if (cameraMode === 'fps') {
      controls.enabled = false

      const poseWaypoint = activeWaypoint ?? waypoints?.[0]
      const r = THREE.MathUtils.clamp(poseWaypoint?.row ?? Math.floor(rows / 2), 1, rows - 2)
      const c = THREE.MathUtils.clamp(poseWaypoint?.col ?? Math.floor(cols / 2), 1, cols - 2)
      const idx = r * cols + c
      const altM = heights && idx < heights.length && !Number.isNaN(heights[idx]) ? heights[idx] : minM + 325

      const rx = c * stepX - halfX
      const rz = r * stepZ - halfZ
      const ry = altM - minM + 3.2 // eye height above surface

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

      camera.lookAt(targetWorldX, targetWorldY, targetWorldZ)
      camera.updateProjectionMatrix()

      const forward = new THREE.Vector3(targetWorldX - rx, targetWorldY - ry, targetWorldZ - rz).normalize()
      fpsAngles.current = { yaw, pitch: Math.asin(THREE.MathUtils.clamp(forward.y, -1, 1)) }
    } else {
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
    }
  }, [activeWaypoint, cameraMode, waypoints, status])

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

  return (
    <div className="terrain3d-root" ref={containerRef}>
      {status === 'loading' && <div className="terrain3d-status">Arazi yükleniyor…</div>}
      {status === 'error' && (
        <div className="terrain3d-status">3B arazi yüklenemedi — API çalışıyor mu?</div>
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
              </div>
            </>
          )}
        </aside>
      )}

      {/* 3D Camera Mode Switcher (FPS vs Kuşbakışı Orbit) */}
      {status === 'ready' && (
        <div className="terrain3d-camera-switch">
          <button
            type="button"
            className={`terrain3d-cam-btn ${cameraMode === 'fps' ? 'is-active' : ''}`}
            onClick={() => setCameraMode('fps')}
            title="Birinci Şahıs (FPS) Yüzey Bakış Açısı - Düz Zemin"
          >
            <span className="cam-icon">🎯</span>
            <span>FPS Bakış Açısı</span>
          </button>
          <button
            type="button"
            className={`terrain3d-cam-btn ${cameraMode === 'orbit' ? 'is-active' : ''}`}
            onClick={() => setCameraMode('orbit')}
            title="Kuşbakışı Yörünge İnceleme Görünümü"
          >
            <span className="cam-icon">🛰️</span>
            <span>Kuşbakışı (Orbit)</span>
          </button>
        </div>
      )}
    </div>
  )
}
