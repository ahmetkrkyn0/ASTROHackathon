import { describe, expect, it } from 'vitest'
import {
  ROVER_CHASSIS_WIDTH_M,
  ribbonHalfWidthM,
  ribbonHeight,
  ribbonSurfaceOffsetM,
} from './routeRibbon'

/** FPS eye height, from TerrainCanvas3D's own pose code. */
const EYE_HEIGHT_M = 1.6

describe('ribbonSurfaceOffsetM', () => {
  it('stays well below eye height on the surface', () => {
    // The bug this guards: a 4 m lift put the route 2.4 m above the driver,
    // so the planned path rendered as a green ceiling instead of a road.
    expect(ribbonSurfaceOffsetM('fps')).toBeLessThan(EYE_HEIGHT_M)
  })

  it('still lifts clear of the mesh in orbit, where z-fighting is the risk', () => {
    expect(ribbonSurfaceOffsetM('orbit')).toBeGreaterThan(ribbonSurfaceOffsetM('fps'))
  })

  it('is positive in both modes, so the ribbon never sinks into the terrain', () => {
    expect(ribbonSurfaceOffsetM('fps')).toBeGreaterThan(0)
    expect(ribbonSurfaceOffsetM('orbit')).toBeGreaterThan(0)
  })
})

describe('ribbonHeight', () => {
  const base = { minM: 800, verticalScale: 1, cameraMode: 'fps' as const }

  it('sits just above the ground the waypoint reports', () => {
    const h = ribbonHeight({ ...base, altitudeM: 857.85 })
    expect(h).toBeCloseTo(57.85 + ribbonSurfaceOffsetM('fps'), 6)
  })

  it('keeps the route under the driver at a real waypoint altitude', () => {
    // Ground and ribbon at the same waypoint: the gap has to read as a road
    // surface underfoot, not as something overhead.
    const ground = 857.85 - base.minM
    const ribbon = ribbonHeight({ ...base, altitudeM: 857.85 })
    expect(ribbon - ground).toBeLessThan(EYE_HEIGHT_M)
  })

  it('rises with the terrain exaggeration rather than drifting off it', () => {
    const flat = ribbonHeight({ ...base, altitudeM: 900, verticalScale: 1 })
    const tall = ribbonHeight({ ...base, altitudeM: 900, verticalScale: 3 })
    expect(tall - ribbonSurfaceOffsetM('fps')).toBeCloseTo((flat - ribbonSurfaceOffsetM('fps')) * 3, 6)
  })

  it('falls back to the DEM floor when a waypoint carries no altitude', () => {
    expect(ribbonHeight({ ...base, altitudeM: null })).toBeCloseTo(ribbonSurfaceOffsetM('fps'), 6)
  })

  it('lifts the same route higher in orbit than on the surface', () => {
    const surface = ribbonHeight({ ...base, altitudeM: 870, cameraMode: 'fps' })
    const orbit = ribbonHeight({ ...base, altitudeM: 870, cameraMode: 'orbit' })
    expect(orbit).toBeGreaterThan(surface)
  })
})

describe('ribbonHalfWidthM', () => {
  it('stays narrower than the rover on the surface', () => {
    // The bug this guards: a band wider than the 1.45 m chassis swallowed the
    // rover, so the vehicle disappeared inside the route meant to guide it.
    expect(ribbonHalfWidthM('fps') * 2).toBeLessThan(ROVER_CHASSIS_WIDTH_M)
  })

  it('widens in orbit, where the surface width would be sub-pixel', () => {
    expect(ribbonHalfWidthM('orbit')).toBeGreaterThan(ribbonHalfWidthM('fps'))
  })

  it('is positive in both modes', () => {
    expect(ribbonHalfWidthM('fps')).toBeGreaterThan(0)
    expect(ribbonHalfWidthM('orbit')).toBeGreaterThan(0)
  })
})
