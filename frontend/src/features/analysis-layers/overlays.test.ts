import { describe, expect, it } from 'vitest'

import type { BinaryField } from '../../net/layers'
import { PSR_MASK_RGB } from '../../colormap'
import { analysisFieldCommand, analysisOverlays } from './overlays'
import { analysisLayerById } from './layers'

const ROUGHNESS = analysisLayerById('roughness')
const PSR = analysisLayerById('psr')
const EARTH = analysisLayerById('earth_visibility')

function field(overrides: Partial<BinaryField> & { data: Float32Array }): BinaryField {
  return {
    rows: 2,
    cols: 3,
    resolutionM: 5,
    downsample: 1,
    validity: 'MEASURED',
    min: 0,
    max: 1,
    nodataCount: 0,
    layerName: 'test',
    ...overrides,
  }
}

describe('analysisFieldCommand', () => {
  it('draws a ramp over the layer’s own measured range', () => {
    // Not a rounded 0..5. Substituting a tidy domain makes every colour on the
    // map mean something slightly different from what the legend says.
    const command = analysisFieldCommand(
      ROUGHNESS,
      field({ data: new Float32Array([0.2, 1, 2, 3, 4, 4.6]), min: 0.1193, max: 4.603 }),
    )
    expect(command).not.toBeNull()
    if (command?.kind !== 'field') throw new Error('expected a field command')
    expect(command.ramp.min).toBeCloseTo(0.1193, 4)
    expect(command.ramp.max).toBeCloseTo(4.603, 3)
    expect(command.ramp.colors.length).toBeGreaterThan(1)
  })

  it('carries the field’s own shape, not the fine grid’s', () => {
    const command = analysisFieldCommand(
      EARTH,
      field({ data: new Float32Array(4), rows: 2, cols: 2, downsample: 4, min: 0, max: 1 }),
    )
    if (command?.kind !== 'field') throw new Error('expected a field command')
    // drawField blits at these dimensions with smoothing off, which is how a
    // coarse product keeps its block boundaries instead of being stretched.
    expect(command.rows).toBe(2)
    expect(command.cols).toBe(2)
  })

  it('leaves NaN cells unpainted', () => {
    const command = analysisFieldCommand(
      ROUGHNESS,
      field({ data: new Float32Array([1, NaN, 3, 4, NaN, 6]), min: 1, max: 6 }),
    )
    if (command?.kind !== 'field') throw new Error('expected a field command')
    expect(command.values).toEqual([1, null, 3, 4, null, 6])
  })

  it('draws a boolean mask as a mask, not as a two-stop ramp', () => {
    const command = analysisFieldCommand(
      PSR,
      field({ data: new Float32Array([0, 1, 0, 0, 1, 0]), min: 0, max: 1 }),
    )
    if (command?.kind !== 'field') throw new Error('expected a field command')
    // Outside cells are null, so nothing is painted over them at all. A ramp
    // would have washed 99.7% of this window in its low colour.
    expect(command.values).toEqual([null, 1, null, null, 1, null])
    expect(command.ramp.colors).toEqual([PSR_MASK_RGB, PSR_MASK_RGB])
  })

  it('draws nothing for a layer with no gradient', () => {
    // A constant layer, or one the backend measured no finite value in. A flat
    // wash over the map would read as data.
    expect(
      analysisFieldCommand(ROUGHNESS, field({ data: new Float32Array(6), min: 2, max: 2 })),
    ).toBeNull()
    expect(
      analysisFieldCommand(
        ROUGHNESS,
        field({ data: new Float32Array(6), min: null, max: null }),
      ),
    ).toBeNull()
  })

  it('gives every layer a distinct overlay id', () => {
    const ids = [ROUGHNESS, PSR, EARTH].map((spec) => {
      const command = analysisFieldCommand(
        spec,
        field({ data: new Float32Array([0, 1, 0, 1, 0, 1]), min: 0, max: 1 }),
      )
      return command?.id
    })
    expect(new Set(ids).size).toBe(3)
  })
})

describe('analysisOverlays', () => {
  it('emits nothing when no layer has data', () => {
    const commands = analysisOverlays([
      { spec: ROUGHNESS, field: null },
      { spec: PSR, field: null },
    ])
    expect(commands).toEqual([])
  })

  it('keeps declaration order, which is paint order', () => {
    const ready = field({ data: new Float32Array([0, 1, 0, 1, 0, 1]), min: 0, max: 1 })
    const commands = analysisOverlays([
      { spec: ROUGHNESS, field: ready },
      { spec: PSR, field: ready },
    ])
    // The mask is declared after the ramp so it draws on top: a mask over a
    // ramp still shows the ramp through its opacity, the reverse buries it.
    expect(commands.map((command) => command.id)).toEqual([
      'analysis-roughness',
      'analysis-psr',
    ])
  })
})
