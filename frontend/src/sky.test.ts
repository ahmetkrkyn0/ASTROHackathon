import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import {
  ZENITH_DEC_DEG,
  ZENITH_RA_DEG,
  colourIndexToKelvin,
  equatorialToVector,
  kelvinToColour,
  magnitudeToUnit,
} from './sky'

/** The rotation createSky() applies: ecliptic south pole to the zenith. */
function skyOrientation(): THREE.Quaternion {
  return new THREE.Quaternion().setFromUnitVectors(
    equatorialToVector(ZENITH_RA_DEG, ZENITH_DEC_DEG),
    new THREE.Vector3(0, 1, 0),
  )
}

/** Degrees above the horizon once the sky is rotated into the scene. */
function altitudeDeg(raDeg: number, decDeg: number): number {
  const placed = equatorialToVector(raDeg, decDeg).applyQuaternion(skyOrientation())
  return THREE.MathUtils.radToDeg(Math.asin(THREE.MathUtils.clamp(placed.y, -1, 1)))
}

describe('equatorialToVector', () => {
  it('puts the celestial poles on the polar axis and the equinox on +X', () => {
    expect(equatorialToVector(0, 90).z).toBeCloseTo(1, 6)
    expect(equatorialToVector(0, -90).z).toBeCloseTo(-1, 6)
    expect(equatorialToVector(0, 0).x).toBeCloseTo(1, 6)
    // RA 6h is a quarter turn round to +Y, which is what puts the zenith
    // constant (RA 90 deg) where it belongs.
    expect(equatorialToVector(90, 0).y).toBeCloseTo(1, 6)
  })

  it('returns unit vectors', () => {
    for (const [ra, dec] of [[0, 0], [123.4, -56.7], [359.9, 89.9], [266.4, -28.9]]) {
      expect(equatorialToVector(ra, dec).length()).toBeCloseTo(1, 6)
    }
  })
})

describe('colourIndexToKelvin', () => {
  // Ballesteros is calibrated on the Sun, so this is the check that the
  // constants were transcribed correctly rather than approximately.
  it('returns the solar temperature for the solar colour index', () => {
    expect(colourIndexToKelvin(0.65)).toBeCloseTo(5778, -1)
  })

  it('orders the spectral sequence: bluer is hotter', () => {
    const vega = colourIndexToKelvin(0.0)
    const sun = colourIndexToKelvin(0.65)
    const arcturus = colourIndexToKelvin(1.23)
    const betelgeuse = colourIndexToKelvin(1.85)
    expect(vega).toBeGreaterThan(sun)
    expect(sun).toBeGreaterThan(arcturus)
    expect(arcturus).toBeGreaterThan(betelgeuse)
    expect(vega).toBeGreaterThan(9000)
    expect(betelgeuse).toBeLessThan(4000)
  })
})

describe('kelvinToColour', () => {
  it('makes hot stars blue-leaning and cool stars red-leaning', () => {
    const hot = kelvinToColour(20000)
    const cool = kelvinToColour(3000)
    expect(hot.b).toBeGreaterThan(hot.r)
    expect(cool.r).toBeGreaterThan(cool.b)
  })

  it('normalises so colour carries hue only, never brightness', () => {
    // Magnitude sets how bright a star is drawn. If the colour dimmed it too,
    // red giants would be dimmed twice and Betelgeuse would disappear.
    for (const kelvin of [2500, 4000, 5778, 9600, 30000]) {
      const colour = kelvinToColour(kelvin)
      expect(Math.max(colour.r, colour.g, colour.b)).toBeCloseTo(1, 5)
    }
  })
})

describe('magnitudeToUnit', () => {
  it('runs from 0 at the naked-eye limit to 1 at the brightest star', () => {
    expect(magnitudeToUnit(6.5)).toBeCloseTo(0, 6)
    expect(magnitudeToUnit(-1.46)).toBeGreaterThan(0.99)
    expect(magnitudeToUnit(2.0)).toBeGreaterThan(magnitudeToUnit(4.0))
  })

  it('clamps rather than extrapolating past either end', () => {
    expect(magnitudeToUnit(12)).toBe(0)
    expect(magnitudeToUnit(-30)).toBe(1)
  })
})

describe('the sky as seen from the lunar south pole', () => {
  it('holds the ecliptic south pole at the zenith', () => {
    expect(altitudeDeg(ZENITH_RA_DEG, ZENITH_DEC_DEG)).toBeCloseTo(90, 4)
  })

  // A star's altitude here is minus its ecliptic latitude, because the zenith
  // IS the ecliptic pole. That makes the southern ecliptic sky the visible
  // half, which these four independently confirm.
  it('raises the far-southern sky and sets the far-northern sky', () => {
    // Canopus, ecliptic latitude -75.8 deg: all but overhead.
    expect(altitudeDeg(95.988, -52.696)).toBeGreaterThan(70)
    // Sirius, ecliptic latitude -39.6 deg.
    expect(altitudeDeg(101.287, -16.716)).toBeGreaterThan(30)
    // Vega, ecliptic latitude +61.7 deg: well below the horizon.
    expect(altitudeDeg(279.234, 38.784)).toBeLessThan(-50)
    // Polaris, ecliptic latitude +66.1 deg: never rises, as it must not --
    // the north celestial pole is under the floor at the lunar SOUTH pole.
    expect(altitudeDeg(37.955, 89.264)).toBeLessThan(-60)
  })

  it('keeps the galactic centre above the horizon', () => {
    // Sgr A*, ecliptic latitude -5.6 deg. The Milky Way's brightest region
    // sits low but visible, which is what the glow is built around.
    expect(altitudeDeg(266.405, -28.936)).toBeGreaterThan(0)
  })
})
