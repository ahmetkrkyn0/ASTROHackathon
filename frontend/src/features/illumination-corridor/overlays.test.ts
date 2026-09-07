import { describe, expect, it } from 'vitest'

import { cubeFrom } from '../../net/series'
import type { CorridorManifest } from '../../net/analysis'
import { CORRIDOR_FIELDS, corridorSliceCommand, sliceCellCount } from './overlays'

import corridorFixture from '../../net/__fixtures__/illumination-corridor.available.json'

const MANIFEST = corridorFixture as unknown as CorridorManifest

/**
 * A 2x2 grid over 3 slices, each value encoding `slice*100 + row*10 + col`
 * so a slice read at the wrong offset is visible in the assertion rather than
 * plausible. Membership is derived from that: even values are in.
 */
function maskCube() {
  const data = new Float32Array(3 * 2 * 2)
  let i = 0
  for (let s = 0; s < 3; s += 1) {
    for (let r = 0; r < 2; r += 1) {
      for (let c = 0; c < 2; c += 1) {
        // Slice 0: one member. Slice 1: two. Slice 2: four.
        data[i++] = c <= s ? 1 : 0
      }
    }
  }
  return cubeFrom(data, { slices: 3, rows: 2, cols: 2 })
}

describe('corridorSliceCommand', () => {
  it('draws membership as a mask, leaving everything else untouched', () => {
    const command = corridorSliceCommand('corridor', maskCube(), 0, { min: 0, max: 1 })
    if (command?.kind !== 'field') throw new Error('expected a field command')
    // Zeros are the rest of the map. Painting them washes over the very thing
    // the corridor is defined against.
    expect(command.values).toEqual([1, null, 1, null])
    expect(command.ramp.colors[0]).toEqual(command.ramp.colors[1])
  })

  it('reads the slice the clock asks for, not the first', () => {
    const cube = maskCube()
    expect(sliceCellCount(cube, 0)).toBe(2)
    expect(sliceCellCount(cube, 1)).toBe(4)
    const first = corridorSliceCommand('corridor', cube, 0, { min: 0, max: 1 })
    const second = corridorSliceCommand('corridor', cube, 1, { min: 0, max: 1 })
    if (first?.kind !== 'field' || second?.kind !== 'field') throw new Error('fields')
    expect(first.values).not.toEqual(second.values)
  })

  it('clamps an out-of-range slice instead of reading past the cube', () => {
    const cube = maskCube()
    const past = corridorSliceCommand('corridor', cube, 99, { min: 0, max: 1 })
    const last = corridorSliceCommand('corridor', cube, 2, { min: 0, max: 1 })
    if (past?.kind !== 'field' || last?.kind !== 'field') throw new Error('fields')
    expect(past.values).toEqual(last.values)
    expect(sliceCellCount(cube, -5)).toBe(sliceCellCount(cube, 0))
  })

  it('keeps zero dwell as a value rather than nulling it', () => {
    // A block in the corridor now with no hours ahead is a different statement
    // from a block outside the corridor, and only the ramp's low end says the
    // first.
    const data = new Float32Array([0, 4, 8, NaN])
    const cube = cubeFrom(data, { slices: 1, rows: 2, cols: 2 })
    const command = corridorSliceCommand('dwell_hours', cube, 0, { min: 0, max: 8 })
    if (command?.kind !== 'field') throw new Error('expected a field command')
    expect(command.values).toEqual([0, 4, 8, null])
  })

  it('keeps the coarse shape', () => {
    const command = corridorSliceCommand('corridor', maskCube(), 0, { min: 0, max: 1 })
    if (command?.kind !== 'field') throw new Error('expected a field command')
    expect([command.rows, command.cols]).toEqual([2, 2])
  })

  it('gives each field its own overlay id', () => {
    const cube = maskCube()
    const ids = CORRIDOR_FIELDS.map(
      (entry) => corridorSliceCommand(entry.id, cube, 0, { min: 0, max: 8 })?.id,
    )
    expect(new Set(ids).size).toBe(CORRIDOR_FIELDS.length)
  })

  it('draws no dwell ramp without a range', () => {
    const cube = maskCube()
    expect(corridorSliceCommand('dwell_hours', cube, 0, { min: 4, max: 4 })).toBeNull()
  })
})

describe('GET /api/illumination-corridor contract', () => {
  it('is a slice-major cube on the coarse grid', () => {
    expect(MANIFEST.binary_format.order).toContain('slice-major')
    expect(MANIFEST.binary_format.shape).toEqual([
      MANIFEST.n_slices,
      MANIFEST.grid.rows,
      MANIFEST.grid.cols,
    ])
    expect(MANIFEST.coarsen).toBe(4)
    expect(MANIFEST.grid.resolution_m).toBeGreaterThan(5)
  })

  it('publishes all three fields', () => {
    for (const entry of CORRIDOR_FIELDS) {
      expect(MANIFEST.fields[entry.id]?.binary_url).toContain(`field=${entry.id}`)
    }
    expect(MANIFEST.fields.corridor?.units).toBe('0/1')
    expect(MANIFEST.fields.dwell_hours?.units).toBe('h')
  })

  it('says the planner was not gated on it', () => {
    // The layer half. A corridor drawn beside a route without this flag read
    // would imply the route respected it.
    expect(MANIFEST.corridor.enforced).toBe(false)
  })

  it('carries the rules it was built from, for quoting', () => {
    expect(MANIFEST.corridor.lit_rule_definition.length).toBeGreaterThan(40)
    expect(MANIFEST.corridor.pruning.length).toBeGreaterThan(40)
    expect(MANIFEST.corridor.edge_rule.length).toBeGreaterThan(40)
  })

  it('reports a corridor strictly inside what is lit and passable', () => {
    const v = MANIFEST.corridor.voxels
    expect(v.corridor).toBeLessThanOrEqual(v.lit_safe)
    expect(v.lit_safe).toBeLessThanOrEqual(v.traversable)
    expect(v.pruned_fraction).toBeGreaterThan(0)
  })

  it('leaves route and endpoint blocks null in the layer-only case', () => {
    expect(MANIFEST.corridor.start).toBeNull()
    expect(MANIFEST.corridor.goal).toBeNull()
  })
})
