import * as THREE from 'three'

/**
 * The sky over the lunar south pole, from the Yale Bright Star Catalogue.
 *
 * What was here before drew 3500 points at uniformly random directions, every
 * one the same size, coloured by picking from a six-entry palette at random,
 * plus 2000 electric-blue points in a tilted ring standing in for the Milky
 * Way. It reads as noise because it is noise: no constellations, no magnitude
 * range, and a Milky Way the wrong colour in the wrong place. Every other
 * surface in this product is measured data. The sky was the one screen making
 * numbers up, and it is also the one an operator can check by walking outside.
 *
 * So the stars are the real ones: 9096 entries from BSC5 (`scripts/
 * build_star_catalogue.py` packs it), essentially every star the unaided eye
 * can see, each at its J2000 position with its own visual magnitude and B-V
 * colour index. Orion, Crux, Scorpius and the Magellanic-cloud region are all
 * where they belong, and the brightest stars are the ones that are actually
 * brightest.
 *
 * Two things are modelled rather than catalogued, and both are marked as such
 * below: the Milky Way's unresolved glow, and the sky's rotation about the
 * zenith, which is not calibrated to an epoch.
 */

/** Where the catalogue lands. Float32 x4 per star; count is length / 4. */
const CATALOGUE_URL = '/data/bsc5.bin'

/**
 * Faintest star drawn at full strength. 6.5 is the naked-eye limit under a
 * dark sky and is also where BSC5 itself stops being complete.
 */
const MAG_LIMIT = 6.5

/** Sirius, the brightest star there is, at -1.46. Anchors the other end. */
const MAG_BRIGHTEST = -1.5

/**
 * The ecliptic south pole, J2000: RA 6h, Dec -66.561 deg, in Dorado.
 *
 * This is what sits at the zenith. The Moon's rotation axis is tilted only
 * 1.54 degrees from the ecliptic normal -- against Earth's 23.4 -- so from the
 * lunar south pole the ecliptic pole is overhead to within a degree and a
 * half, and the sky wheels around it once a month rather than once a night.
 */
export const ZENITH_RA_DEG = 90.0
export const ZENITH_DEC_DEG = -66.561

/** Galactic north pole and galactic centre, J2000. Used to place the glow. */
const GAL_POLE_RA_DEG = 192.85948
const GAL_POLE_DEC_DEG = 27.12825
const GAL_CENTRE_RA_DEG = 266.40500
const GAL_CENTRE_DEC_DEG = -28.93617

/** Far enough that moving a rover across 2.5 km shifts nothing. */
const SKY_RADIUS = 70000

/** Equatorial spherical to Cartesian, +Z on the north celestial pole. */
export function equatorialToVector(raDeg: number, decDeg: number): THREE.Vector3 {
  const ra = THREE.MathUtils.degToRad(raDeg)
  const dec = THREE.MathUtils.degToRad(decDeg)
  return new THREE.Vector3(
    Math.cos(dec) * Math.cos(ra),
    Math.cos(dec) * Math.sin(ra),
    Math.sin(dec),
  )
}

/**
 * B-V colour index to effective temperature, then temperature to RGB.
 *
 * Ballesteros (2012), which treats a star as two black bodies seen through the
 * B and V passbands. It is calibrated on the Sun and lands on it exactly:
 * B-V 0.65 comes back 5779 K against the true 5778. Vega (B-V 0.00) gives
 * 10126 K and Betelgeuse (B-V 1.85) 3334 K, both the right side of the right
 * order. Reproducing this is why the packer keeps the colour index at all --
 * the alternative is inventing colours, which is what the old palette did.
 */
export function colourIndexToKelvin(bv: number): number {
  const x = 0.92 * bv
  return 4600 * (1 / (x + 1.7) + 1 / (x + 0.62))
}

/**
 * Black body temperature to linear RGB (Helland's piecewise fit to the
 * Planckian locus), normalised so the strongest channel is 1.
 *
 * Normalising matters: a star's brightness has to come from its magnitude
 * alone, so the colour carries hue only. Without it a red giant would be dimmed
 * twice -- once for being cool, once for being far -- and Betelgeuse would
 * disappear.
 */
export function kelvinToColour(kelvin: number): THREE.Color {
  const t = THREE.MathUtils.clamp(kelvin, 1000, 40000) / 100
  let r: number
  let g: number
  let b: number

  if (t <= 66) {
    r = 255
    g = 99.4708025861 * Math.log(t) - 161.1195681661
  } else {
    r = 329.698727446 * Math.pow(t - 60, -0.1332047592)
    g = 288.1221695283 * Math.pow(t - 60, -0.0755148492)
  }

  if (t >= 66) b = 255
  else if (t <= 19) b = 0
  else b = 138.5177312231 * Math.log(t - 10) - 305.0447927307

  const peak = Math.max(r, g, b, 1)
  return new THREE.Color(
    THREE.MathUtils.clamp(r / peak, 0, 1),
    THREE.MathUtils.clamp(g / peak, 0, 1),
    THREE.MathUtils.clamp(b / peak, 0, 1),
  )
}

/** 0 at the faint limit, 1 at Sirius. Everything visual is driven off this. */
export function magnitudeToUnit(vmag: number): number {
  return THREE.MathUtils.clamp((MAG_LIMIT - vmag) / (MAG_LIMIT - MAG_BRIGHTEST), 0, 1)
}

/** The soft dot every star is drawn with. One texture, shared. */
function createStarSprite(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')!
  // A solid core with a wide, faint skirt. The skirt is what makes a bright
  // star read as bright rather than merely large: the eye reads the halo, and
  // a hard-edged disc at ten pixels looks like a bug instead of Sirius. The
  // core is held at full alpha out to a fifth of the radius so that even a
  // two-pixel star lands at least one opaque texel and does not wash out.
  const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  grad.addColorStop(0.0, 'rgba(255, 255, 255, 1)')
  grad.addColorStop(0.20, 'rgba(255, 255, 255, 0.95)')
  grad.addColorStop(0.38, 'rgba(255, 255, 255, 0.45)')
  grad.addColorStop(0.62, 'rgba(255, 255, 255, 0.14)')
  grad.addColorStop(1.0, 'rgba(255, 255, 255, 0)')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 64, 64)
  return new THREE.CanvasTexture(canvas)
}

/**
 * The halo drawn under the brightest stars only.
 *
 * A star's real brightness range is far wider than a screen's. Across this
 * catalogue it is about 630 to one, and no amount of pushing size and alpha on
 * a single sprite buys that back -- past a point a bright star just becomes a
 * big pale blob. What actually separates first magnitude from fourth, in the
 * eye and in every photograph, is the bloom around it, so the brightest stars
 * get a second, much wider and much fainter sprite laid under the first.
 *
 * The four spikes are the same artefact: they come from a camera, not from the
 * sky. They belong here because this view IS a camera -- the scene already
 * draws a lens flare for the sun -- and they are the fastest way to read
 * "this one is very bright" at a glance.
 */
function createStarGlowSprite(): THREE.CanvasTexture {
  const size = 128
  const half = size / 2
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!

  const grad = ctx.createRadialGradient(half, half, 0, half, half, half)
  grad.addColorStop(0.0, 'rgba(255, 255, 255, 0.50)')
  grad.addColorStop(0.10, 'rgba(255, 255, 255, 0.26)')
  grad.addColorStop(0.26, 'rgba(255, 255, 255, 0.09)')
  grad.addColorStop(0.55, 'rgba(255, 255, 255, 0.02)')
  grad.addColorStop(1.0, 'rgba(255, 255, 255, 0)')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, size, size)

  // Spikes, added over the halo. Drawn as four tapering gradients so they fade
  // out rather than ending in a hard tip.
  ctx.globalCompositeOperation = 'lighter'
  for (const angle of [0, Math.PI / 2]) {
    ctx.save()
    ctx.translate(half, half)
    ctx.rotate(angle)
    const spike = ctx.createLinearGradient(-half, 0, half, 0)
    spike.addColorStop(0.0, 'rgba(255, 255, 255, 0)')
    spike.addColorStop(0.34, 'rgba(255, 255, 255, 0.05)')
    spike.addColorStop(0.5, 'rgba(255, 255, 255, 0.30)')
    spike.addColorStop(0.66, 'rgba(255, 255, 255, 0.05)')
    spike.addColorStop(1.0, 'rgba(255, 255, 255, 0)')
    ctx.fillStyle = spike
    ctx.fillRect(-half, -1.1, size, 2.2)
    ctx.restore()
  }
  ctx.globalCompositeOperation = 'source-over'

  return new THREE.CanvasTexture(canvas)
}

/**
 * Points with a per-star size, which PointsMaterial cannot do -- its `size` is
 * one number for the whole cloud, and a sky whose every star is the same size
 * is most of what made the old one look fake.
 *
 * Sizes are in pixels and deliberately do not attenuate with distance: stars
 * are at infinity, so their apparent size is set by brightness alone.
 */
function createStarPoints(sprite: THREE.Texture, pixelRatio: number): THREE.Points {
  const material = new THREE.ShaderMaterial({
    uniforms: {
      starSprite: { value: sprite },
      pixelRatio: { value: pixelRatio },
    },
    vertexShader: `
      attribute vec3 aColour;
      attribute float aSize;
      varying vec3 vColour;
      uniform float pixelRatio;
      void main() {
        vColour = aColour;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = aSize * pixelRatio;
      }
    `,
    fragmentShader: `
      uniform sampler2D starSprite;
      varying vec3 vColour;
      void main() {
        vec4 sprite = texture2D(starSprite, gl_PointCoord);
        gl_FragColor = vec4(vColour, 1.0) * sprite;
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    // Writes no depth -- a star is a point, not an occluder -- but TESTS it,
    // so the terrain hides the stars behind it.
    //
    // This was `depthTest: false`, which made the Moon transparent. A material
    // marked `transparent` goes in three.js's transparent queue, drawn AFTER
    // all opaque geometry, and renderOrder only sorts within that queue -- it
    // does not move the sky in front of the terrain. So the stars were painted
    // over the surface every frame and the ground showed the sky beneath it.
    depthWrite: false,
    depthTest: true,
  })

  const points = new THREE.Points(new THREE.BufferGeometry(), material)
  // Never culled: at 70 km the bounding sphere would drop the whole sky the
  // moment the camera looks along the terrain. renderOrder keeps it first
  // among the transparent objects, so the Earth and the sun flare draw over
  // it rather than under it.
  points.frustumCulled = false
  points.renderOrder = -1
  return points
}

export interface Sky {
  group: THREE.Group
  /** Resolves once the catalogue is in. Rejects only on a genuine load error. */
  ready: Promise<void>
  dispose: () => void
}

/**
 * Build the sky and start loading the catalogue.
 *
 * Returns immediately with an empty star cloud so the scene can finish
 * building; the geometry is filled in when the fetch lands, the same way the
 * rock templates and the Earth texture arrive.
 */
export function createSky(pixelRatio: number, signal?: AbortSignal): Sky {
  const group = new THREE.Group()

  // Rotate the celestial sphere so the ecliptic south pole sits at the scene's
  // zenith. The rotation ABOUT that axis is not calibrated -- fixing it needs
  // an epoch and the Moon's orientation at it, which is a SPICE job and not
  // one the sky's appearance justifies. So: the right stars, at the right
  // altitudes above the horizon, at an arbitrary azimuth.
  const zenith = equatorialToVector(ZENITH_RA_DEG, ZENITH_DEC_DEG)
  group.quaternion.setFromUnitVectors(zenith, new THREE.Vector3(0, 1, 0))

  const sprite = createStarSprite()
  const glowSprite = createStarGlowSprite()
  const stars = createStarPoints(sprite, pixelRatio)
  const glow = createStarPoints(glowSprite, pixelRatio)
  const milkyWay = createStarPoints(sprite, pixelRatio)
  buildMilkyWay(milkyWay)
  // Order is the draw order: unresolved glow first, then the haloes, then the
  // stars themselves on top. Additive blending makes the result independent of
  // it, but a bright star's own core should be the last thing written where
  // they overlap.
  group.add(milkyWay)
  group.add(glow)
  group.add(stars)

  const ready = fetch(CATALOGUE_URL, { signal })
    .then((response) => {
      if (!response.ok) throw new Error(`star catalogue: HTTP ${response.status}`)
      return response.arrayBuffer()
    })
    .then((buffer) => {
      buildStars(stars, glow, new Float32Array(buffer))
    })

  return {
    group,
    ready,
    dispose: () => {
      for (const cloud of [stars, glow, milkyWay]) {
        cloud.geometry.dispose()
        ;(cloud.material as THREE.Material).dispose()
      }
      sprite.dispose()
      glowSprite.dispose()
    },
  }
}

/**
 * Magnitude at which a star earns a halo. About 170 stars in the catalogue --
 * roughly the ones with proper names.
 */
const GLOW_MAG_LIMIT = 3.0

/** Fill the star cloud, and the halo cloud, from the packed catalogue. */
function buildStars(points: THREE.Points, glow: THREE.Points, data: Float32Array): void {
  const count = Math.floor(data.length / 4)
  const positions = new Float32Array(count * 3)
  const colours = new Float32Array(count * 3)
  const sizes = new Float32Array(count)
  // The halo cloud is sized for the whole catalogue and trimmed to what it
  // actually takes; counting the bright stars first would mean reading the
  // magnitude column twice to save 100 KB for the length of this function.
  const glowPositions = new Float32Array(count * 3)
  const glowColours = new Float32Array(count * 3)
  const glowSizes = new Float32Array(count)
  let glowCount = 0
  const vector = new THREE.Vector3()

  for (let i = 0; i < count; i++) {
    const raDeg = data[i * 4]
    const decDeg = data[i * 4 + 1]
    const vmag = data[i * 4 + 2]
    const bv = data[i * 4 + 3]

    vector.copy(equatorialToVector(raDeg, decDeg)).multiplyScalar(SKY_RADIUS)
    positions[i * 3] = vector.x
    positions[i * 3 + 1] = vector.y
    positions[i * 3 + 2] = vector.z

    const unit = magnitudeToUnit(vmag)
    const colour = kelvinToColour(colourIndexToKelvin(bv))
    // Magnitude is logarithmic in flux over a range of about 630 to one across
    // this catalogue. Mapped straight to size, Sirius would be a beach ball;
    // mapped straight to brightness, everything below third magnitude would be
    // black. Both curves are compressed, and the size exponent is the steeper
    // of the two so the bright stars separate by size while the faint ones
    // stay a pixel apart. The floor is what the sixth-magnitude majority is
    // drawn at, and it sets how populated the sky looks: too low and the
    // constellations lose the stars that join them up.
    const intensity = 0.46 + 0.54 * Math.pow(unit, 1.3)
    colours[i * 3] = colour.r * intensity
    colours[i * 3 + 1] = colour.g * intensity
    colours[i * 3 + 2] = colour.b * intensity
    sizes[i] = 2.6 + Math.pow(unit, 2.0) * 16.0

    if (vmag <= GLOW_MAG_LIMIT) {
      glowPositions[glowCount * 3] = vector.x
      glowPositions[glowCount * 3 + 1] = vector.y
      glowPositions[glowCount * 3 + 2] = vector.z
      // Faint on purpose. The halo is meant to be read as brightness around
      // the star, not seen as a disc in its own right, so it climbs steeply
      // with magnitude and stays low even at the top.
      const halo = 0.10 + 0.34 * Math.pow(unit, 2.4)
      glowColours[glowCount * 3] = colour.r * halo
      glowColours[glowCount * 3 + 1] = colour.g * halo
      glowColours[glowCount * 3 + 2] = colour.b * halo
      glowSizes[glowCount] = 12.0 + Math.pow(unit, 2.0) * 34.0
      glowCount++
    }
  }

  points.geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  points.geometry.setAttribute('aColour', new THREE.BufferAttribute(colours, 3))
  points.geometry.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1))

  glow.geometry.setAttribute('position', new THREE.BufferAttribute(glowPositions.subarray(0, glowCount * 3), 3))
  glow.geometry.setAttribute('aColour', new THREE.BufferAttribute(glowColours.subarray(0, glowCount * 3), 3))
  glow.geometry.setAttribute('aSize', new THREE.BufferAttribute(glowSizes.subarray(0, glowCount), 1))
}

/**
 * The Milky Way, as what it actually is: starlight too faint to resolve.
 *
 * This is the one part of the sky that is modelled rather than catalogued,
 * because BSC5 stops at the naked-eye limit and the galaxy's glow is the sum
 * of everything below it. Rather than paint a band, it draws the faint stars
 * themselves -- concentrated toward the galactic plane, and thickened toward
 * the real galactic centre in Sagittarius -- which is why the glow comes out
 * brightest where the sky really is brightest and fades toward Perseus.
 *
 * Its colour is pale and slightly warm. The old version's electric blue was
 * backwards: integrated starlight reddens through the dust it passes.
 */
function buildMilkyWay(points: THREE.Points, count = 42000): void {
  // Galactic frame, built from the two directions that define it.
  const gz = equatorialToVector(GAL_POLE_RA_DEG, GAL_POLE_DEC_DEG)
  const gx = equatorialToVector(GAL_CENTRE_RA_DEG, GAL_CENTRE_DEC_DEG)
  const gy = new THREE.Vector3().crossVectors(gz, gx).normalize()

  const positions = new Float32Array(count * 3)
  const colours = new Float32Array(count * 3)
  const sizes = new Float32Array(count)
  const vector = new THREE.Vector3()
  const warm = new THREE.Color(1.0, 0.96, 0.88)

  let placed = 0
  let guard = 0
  while (placed < count && guard < count * 40) {
    guard++
    const l = Math.random() * Math.PI * 2
    // Latitude from a Gaussian: a thin disc plus a much wider, sparser skirt,
    // which is what stops the band ending at a hard edge.
    const thin = Math.random() < 0.72
    const b = gaussian() * (thin ? 0.055 : 0.20)
    if (Math.abs(b) > 0.9) continue

    // Rejection-sample the along-plane density so the bulge toward the centre
    // is real rather than a brightness trick: more stars there, not brighter
    // ones. Longitude 0 is the galactic centre by construction.
    const fromCentre = Math.abs(((l + Math.PI) % (Math.PI * 2)) - Math.PI)
    const density = 0.34 + 0.66 * Math.exp(-(fromCentre * fromCentre) / (2 * 0.85 * 0.85))
    if (Math.random() > density) continue

    const cosB = Math.cos(b)
    vector
      .set(0, 0, 0)
      .addScaledVector(gx, cosB * Math.cos(l))
      .addScaledVector(gy, cosB * Math.sin(l))
      .addScaledVector(gz, Math.sin(b))
      .multiplyScalar(SKY_RADIUS)

    positions[placed * 3] = vector.x
    positions[placed * 3 + 1] = vector.y
    positions[placed * 3 + 2] = vector.z

    // Individually almost invisible; the band is what 42000 of them add up to.
    const intensity = 0.07 + Math.random() * 0.20
    colours[placed * 3] = warm.r * intensity
    colours[placed * 3 + 1] = warm.g * intensity
    colours[placed * 3 + 2] = warm.b * intensity
    sizes[placed] = 1.1 + Math.random() * 1.5
    placed++
  }

  points.geometry.setAttribute('position', new THREE.BufferAttribute(positions.subarray(0, placed * 3), 3))
  points.geometry.setAttribute('aColour', new THREE.BufferAttribute(colours.subarray(0, placed * 3), 3))
  points.geometry.setAttribute('aSize', new THREE.BufferAttribute(sizes.subarray(0, placed), 1))
}

/** Box-Muller. Two uniforms in, one standard normal out. */
function gaussian(): number {
  let u = 0
  while (u === 0) u = Math.random()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * Math.random())
}
