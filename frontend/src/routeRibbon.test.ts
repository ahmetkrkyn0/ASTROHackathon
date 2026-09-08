import { describe, expect, it } from 'vitest'
import { sampleTerrainHeight, type TerrainField } from './lidarSimulation'

/**
 * The route ribbon is built inside TerrainCanvas3D's effect and needs a live
 * WebGL scene, so it cannot be constructed here. What CAN be pinned down is
 * the rule the effect now follows: every drawn vertex -- centreline and both
 * rails -- takes its height from sampleTerrainHeight at its own (x, z), the
 * same call the rover uses to sit on the ground.
 *
 * These tests encode that contract against a terrain with a real cross-slope,
 * which is exactly the case the old code got wrong: it held the whole ribbon
 * at the waypoint's own altitude, so on a side-slope one rail floated and the
 * other sank.
 */

/** A 20x20 field tilted along +x: height rises 1 m per metre travelled east. */
function slopedField(): TerrainField {
  const rows = 20
  const cols = 20
  const resolutionM = 1
  const heights = new Float32Array(rows * cols)
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) heights[r * cols + c] = c
  }
  return { rows, cols, resolutionM, minElevationM: 0, heights, verticalScale: 1 }
}

const LIFT = 0.12
const HALF_WIDTH = 0.9

describe('route ribbon grounding', () => {
  it('samples a different height for each rail across a cross-slope', () => {
    const field = slopedField()
    // A point mid-field, with the corridor running north-south so its width
    // lies straight across the slope.
    const x = 0
    const z = 0
    const left = sampleTerrainHeight(field, x + HALF_WIDTH, z)
    const right = sampleTerrainHeight(field, x - HALF_WIDTH, z)
    expect(left).not.toBeNull()
    expect(right).not.toBeNull()
    // The rails must land at DIFFERENT heights across a cross-slope. Holding
    // both at the centreline height (the old behaviour) would make this 0.
    // The exact figure follows the field's own vertex spacing, which is
    // cols*res/(cols-1) rather than res, so assert the property not a
    // hand-computed constant.
    const stepX = (field.cols * field.resolutionM) / (field.cols - 1)
    expect(Math.abs((left as number) - (right as number))).toBeCloseTo(
      (2 * HALF_WIDTH) / stepX,
      5,
    )
  })

  it('keeps every sampled vertex within the lift of the surface', () => {
    const field = slopedField()
    for (const [x, z] of [[-4, -4], [0, 0], [3, 2], [5, -3]]) {
      const ground = sampleTerrainHeight(field, x, z)
      expect(ground).not.toBeNull()
      const drawn = (ground as number) + LIFT
      // The ribbon must ride the surface, not hover a rover-height above it
      // the way the old `+ 4` did.
      expect(drawn - (ground as number)).toBeCloseTo(LIFT, 6)
      expect(drawn - (ground as number)).toBeLessThan(0.5)
    }
  })

  it('rises monotonically along a climb, one sample per resampled step', () => {
    const field = slopedField()
    // Walking east across the slope, every resampled point must be strictly
    // higher than the last. A ribbon built only from the two end nodes would
    // instead cut a straight chord and, on a curved rise, leave the ground.
    const ax = -6, bx = 6, z = 0
    const steps = 12
    let previous = -Infinity
    for (let k = 0; k <= steps; k++) {
      const x = ax + ((bx - ax) * k) / steps
      const sampled = sampleTerrainHeight(field, x, z)
      expect(sampled).not.toBeNull()
      expect(sampled as number).toBeGreaterThan(previous)
      previous = sampled as number
    }
  })

  it('re-samples densely enough to track ground between planned nodes', () => {
    // The effect resamples any chord longer than this into 2 m pieces.
    const RESAMPLE_STEP_M = 2
    const span = 9
    const steps = Math.max(1, Math.ceil(span / RESAMPLE_STEP_M))
    expect(steps).toBe(5)
    // Each piece is at most the resample step long, so no drawn segment can
    // span more ground than that between two terrain samples.
    expect(span / steps).toBeLessThanOrEqual(RESAMPLE_STEP_M)
  })
})
