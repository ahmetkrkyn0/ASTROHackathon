import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import { createLunarHorizon } from './lunarHorizon'

// A rectangular DEM catches row/column swaps and mismatched terrain seams.
const terrain = {
  rows: 3, cols: 4, resolutionM: 10, minM: 100,
  heights: new Float32Array([100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210]),
}

describe('lunar environment boundary', () => {
  it('joins every DEM edge vertex without covering the measured interior', () => {
    const horizon = createLunarHorizon(terrain)
    const points = horizon.mesh.geometry.getAttribute('position')
    const expected = [
      [-20, 0, -15], [-20 + 40 / 3, 10, -15], [-20 + 80 / 3, 20, -15], [20, 30, -15],
      [20, 70, 0], [20, 110, 15], [-20 + 80 / 3, 100, 15], [-20 + 40 / 3, 90, 15],
      [-20, 80, 15], [-20, 40, 0],
    ]
    expected.forEach(([x, y, z], i) => {
      expect(points.getX(i)).toBeCloseTo(x, 4)
      expect(points.getY(i)).toBeCloseTo(y, 4)
      expect(points.getZ(i)).toBeCloseTo(z, 4)
    })
    horizon.group.updateMatrixWorld(true)
    const ray = new THREE.Raycaster(new THREE.Vector3(0, 1000, 0), new THREE.Vector3(0, -1, 0))
    expect(ray.intersectObject(horizon.mesh)).toHaveLength(0)
    ray.ray.origin.x = 25
    expect(ray.intersectObject(horizon.mesh).length).toBeGreaterThan(0)
    horizon.dispose()
  })

  it('keeps missing edge heights finite and follows vertical exaggeration', () => {
    const heights = terrain.heights.slice()
    heights[0] = NaN
    const horizon = createLunarHorizon({ ...terrain, heights })
    const points = horizon.mesh.geometry.getAttribute('position')
    expect(Array.from(points.array).every(Number.isFinite)).toBe(true)
    horizon.group.scale.y = 3
    horizon.group.updateMatrixWorld(true)
    const edge = new THREE.Vector3().fromBufferAttribute(points, 1)
    horizon.mesh.localToWorld(edge)
    expect(edge.y).toBe(30)
    expect(Array.from(heights)).toEqual(Array.from(new Float32Array([NaN, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210])))
    horizon.dispose()
  })
})
