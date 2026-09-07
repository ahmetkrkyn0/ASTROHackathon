import { describe, expect, it } from 'vitest'
import { normaliseToDomain, ribbonEdges, sampleRamp } from './draw2d'
import type { CellRef } from '../mission/types'

// A straight run east: col increases, row does not. The perpendicular is
// therefore purely in row, which makes every offset readable by eye.
const EAST: CellRef[] = [
  { row: 10, col: 0 },
  { row: 10, col: 1 },
  { row: 10, col: 2 },
]

describe('ribbonEdges', () => {
  it('offsets both edges perpendicular to the run', () => {
    const { left, right } = ribbonEdges(EAST, [2, 2])
    expect(left).toEqual([
      { row: 8, col: 0 },
      { row: 8, col: 1 },
      { row: 8, col: 2 },
    ])
    expect(right).toEqual([
      { row: 12, col: 0 },
      { row: 12, col: 1 },
      { row: 12, col: 2 },
    ])
  })

  it('widens and narrows with the per-segment half-width', () => {
    // The band is not a constant-width tube: clearance is what the corridor
    // publishes per segment, and a ribbon drawn at one width hides exactly
    // the place a driver needs to see -- the pinch.
    const { left, right } = ribbonEdges(EAST, [1, 4])
    expect(left[0]).toEqual({ row: 9, col: 0 })
    expect(right[0]).toEqual({ row: 11, col: 0 })
    expect(left[1]).toEqual({ row: 6, col: 1 })
    expect(right[1]).toEqual({ row: 14, col: 1 })
  })

  it('gives N centre points N edge points from N-1 widths', () => {
    // corridor.py:126: the budget arrays are per segment. The last vertex
    // reuses the last segment's width instead of falling off the end to 0,
    // which would taper the corridor to a point exactly at the goal.
    const { left, right } = ribbonEdges(EAST, [4, 4])
    expect(left).toHaveLength(3)
    expect(right).toHaveLength(3)
    expect(left[2]).toEqual({ row: 6, col: 2 })
  })

  it('survives a repeated waypoint without emitting NaN', () => {
    // Zero-length segment: Math.hypot is 0 and the perpendicular would be
    // 0/0. One NaN in the path blanks the whole fill, so the ribbon would
    // vanish rather than look wrong.
    const { left, right } = ribbonEdges(
      [
        { row: 3, col: 3 },
        { row: 3, col: 3 },
      ],
      [5],
    )
    for (const point of [...left, ...right]) {
      expect(Number.isFinite(point.row)).toBe(true)
      expect(Number.isFinite(point.col)).toBe(true)
    }
  })
})

describe('normaliseToDomain', () => {
  it('places a value on the unit interval', () => {
    expect(normaliseToDomain(5, [0, 10])).toBe(0.5)
    expect(normaliseToDomain(-20, [-40, 0])).toBe(0.5)
  })

  it('returns null for NaN instead of clamping it', () => {
    // The whole point. NaN is the backend's nodata; clamped to 0 it would
    // paint missing data as the coldest real value in the field, which
    // reads as a measurement rather than as an absence.
    expect(normaliseToDomain(Number.NaN, [0, 10])).toBeNull()
    expect(normaliseToDomain(Number.POSITIVE_INFINITY, [0, 10])).toBeNull()
  })

  it('clamps a value outside the domain', () => {
    expect(normaliseToDomain(-5, [0, 10])).toBe(0)
    expect(normaliseToDomain(99, [0, 10])).toBe(1)
  })

  it('returns 0 for a flat field rather than NaN', () => {
    // min === max happens for real: a fully shadowed slice has shadow = 1
    // everywhere. Dividing by the zero span would blank the layer.
    expect(normaliseToDomain(7, [7, 7])).toBe(0)
  })
})

// sampleRamp replaces the four named ramps the old contract carried. A field
// command now brings its own stops, so this is the only thing standing between
// a normalised value and a pixel -- and every way it can be wrong still paints
// a plausible picture: reversed stops invert the reading, an off-by-one on the
// segment index shifts every colour one band, and a missing round leaves
// fractional channel values that Canvas silently truncates.
describe('sampleRamp', () => {
  const BLACK_TO_WHITE: Array<[number, number, number]> = [
    [0, 0, 0],
    [255, 255, 255],
  ]

  it('returns the end stops at the ends of the interval', () => {
    expect(sampleRamp(BLACK_TO_WHITE, 0)).toEqual([0, 0, 0])
    expect(sampleRamp(BLACK_TO_WHITE, 1)).toEqual([255, 255, 255])
  })

  it('interpolates between two stops', () => {
    expect(sampleRamp(BLACK_TO_WHITE, 0.5)).toEqual([128, 128, 128])
  })

  it('places a value inside the correct band of three stops', () => {
    // Evenly spaced: stop 0 at t=0, stop 1 at t=0.5, stop 2 at t=1. So
    // t=0.25 is halfway through the FIRST band, not the second.
    const stops: Array<[number, number, number]> = [
      [0, 0, 0],
      [100, 0, 0],
      [200, 0, 0],
    ]
    expect(sampleRamp(stops, 0.25)).toEqual([50, 0, 0])
    expect(sampleRamp(stops, 0.5)).toEqual([100, 0, 0])
    expect(sampleRamp(stops, 0.75)).toEqual([150, 0, 0])
  })

  it('returns integer channels', () => {
    // Canvas truncates a fractional channel rather than rounding it, so a
    // ramp that never rounds reads consistently one unit dark.
    const [r, g, b] = sampleRamp(BLACK_TO_WHITE, 1 / 3)
    for (const channel of [r, g, b]) {
      expect(Number.isInteger(channel)).toBe(true)
    }
  })

  it('handles a single stop as a flat colour', () => {
    const one: Array<[number, number, number]> = [[10, 20, 30]]
    expect(sampleRamp(one, 0)).toEqual([10, 20, 30])
    expect(sampleRamp(one, 1)).toEqual([10, 20, 30])
  })
})
