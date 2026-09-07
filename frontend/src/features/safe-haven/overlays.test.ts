import { describe, expect, it } from 'vitest'

import type { BinaryField } from '../../net/layers'
import { safeHavenCommand, safeHavenOverlays } from './overlays'

function field(overrides: Partial<BinaryField> & { data: Float32Array }): BinaryField {
  return {
    rows: 2,
    cols: 3,
    resolutionM: 10,
    downsample: 2,
    validity: 'DERIVED',
    min: 0,
    max: 1,
    nodataCount: 0,
    layerName: 'safe_haven',
    ...overrides,
  }
}

describe('safeHavenCommand', () => {
  it('draws havens as a mask, leaving everything else untouched', () => {
    // Havens are a tenth of the traversable ground here. Painting the
    // complement would wash nine tenths of the map to say nothing.
    const command = safeHavenCommand(
      'safe_haven',
      field({ data: new Float32Array([0, 1, 0, 0, 1, 0]) }),
    )
    if (command?.kind !== 'field') throw new Error('expected a field command')
    expect(command.values).toEqual([null, 1, null, null, 1, null])
  })

  it('leaves an unreachable haven unpainted rather than giving it a number', () => {
    // THE rule of this feature. NaN on time_to_safe_haven means "no reachable
    // safe haven". Zero would mean the cell IS one -- the opposite fact.
    const command = safeHavenCommand(
      'time_to_safe_haven',
      field({
        // Values chosen to round-trip exactly through float32, so the
        // assertion is about the NaN rule and not about f32 precision.
        data: new Float32Array([0, NaN, 4.5, NaN, 12, 17.25]),
        min: 0,
        max: 17.25,
        layerName: 'time_to_safe_haven',
      }),
    )
    if (command?.kind !== 'field') throw new Error('expected a field command')
    expect(command.values).toEqual([0, null, 4.5, null, 12, 17.25])
    // And the ramp has no stop reserved for it: an unreachable cell is off the
    // scale entirely, not at its far end.
    expect(command.ramp.min).toBe(0)
  })

  it('keeps a genuine zero, which means the cell is itself a haven', () => {
    const command = safeHavenCommand(
      'time_to_safe_haven',
      field({ data: new Float32Array([0, 0, NaN, 1, 2, 3]), min: 0, max: 3 }),
    )
    if (command?.kind !== 'field') throw new Error('expected a field command')
    expect(command.values[0]).toBe(0)
    expect(command.values[1]).toBe(0)
    expect(command.values[2]).toBeNull()
  })

  it('draws the hour fields over their own measured range', () => {
    const command = safeHavenCommand(
      'earth_below_hours',
      field({ data: new Float32Array([0, 100, 300, 500, 700, 710]), min: 0, max: 710 }),
    )
    if (command?.kind !== 'field') throw new Error('expected a field command')
    expect(command.ramp.max).toBe(710)
  })

  it('keeps the field’s own coarse shape', () => {
    const command = safeHavenCommand(
      'safe_haven',
      field({ data: new Float32Array(4), rows: 2, cols: 2, downsample: 4 }),
    )
    if (command?.kind !== 'field') throw new Error('expected a field command')
    expect(command.rows).toBe(2)
    expect(command.cols).toBe(2)
  })

  it('draws nothing for an hour field with no gradient', () => {
    expect(
      safeHavenCommand(
        'earth_below_hours',
        field({ data: new Float32Array(6), min: 710, max: 710 }),
      ),
    ).toBeNull()
  })

  it('gives each view its own overlay id', () => {
    const ready = field({ data: new Float32Array([0, 1, 2, 3, 4, 5]), min: 0, max: 5 })
    const ids = (
      ['safe_haven', 'time_to_safe_haven', 'earth_below_hours'] as const
    ).map((view) => safeHavenCommand(view, ready)?.id)
    expect(new Set(ids).size).toBe(3)
  })
})

describe('safeHavenOverlays', () => {
  it('emits nothing without a field', () => {
    expect(safeHavenOverlays('safe_haven', null)).toEqual([])
  })
})
