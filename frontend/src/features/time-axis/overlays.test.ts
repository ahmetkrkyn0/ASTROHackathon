import { describe, expect, it } from 'vitest'
import type { SeriesCube } from '../../net/series'
import type { Plan4DResponse, SeriesManifest } from '../../net/types'
import { timeAxisOverlays } from './overlays'

/**
 * The smallest cube and manifest the builder reads: it asks for rows, cols,
 * slices and one slice's values, plus the field's min/max.
 */
const cube = {
  rows: 2,
  cols: 2,
  slices: 1,
  sliceAt: () => new Float32Array([0, 0.5, 1, NaN]),
} as unknown as SeriesCube

const manifest = {
  fields: { shadow: { min: 0, max: 1 }, surface_temp_c: { min: -180, max: 120 } },
} as unknown as SeriesManifest

const plan4d = {
  path_pixels: [
    [0, 0],
    [1, 1],
  ],
} as unknown as Plan4DResponse

describe('timeAxisOverlays', () => {
  it('paints no field until the layer is switched on', () => {
    // The defect this guards: the layer used to appear the moment ANALYZE
    // mounted. The shadow ramp runs white to black, so an unrequested field
    // darkened shadowed ground by ~50 levels and the map read as having had
    // its lighting turned off between one tab and the next.
    const commands = timeAxisOverlays(cube, 0, 'shadow', manifest, null, false)
    expect(commands.filter((command) => command.kind === 'field')).toHaveLength(0)
  })

  it('paints the field once it is', () => {
    const commands = timeAxisOverlays(cube, 0, 'shadow', manifest, null, true)
    const field = commands.find((command) => command.kind === 'field')

    expect(field).toBeDefined()
    // Low enough to let the hillshade through: the relief underneath is what
    // makes the surface legible as terrain rather than as a chart.
    expect(field?.style?.opacity).toBeLessThanOrEqual(0.35)
  })

  it('still draws the 4D route with the layer off', () => {
    // The route is the result of a request the operator made; the field is a
    // layer over the terrain. Switching the layer off must not withdraw the
    // answer to a question they asked.
    const commands = timeAxisOverlays(cube, 0, 'shadow', manifest, plan4d, false)

    expect(commands.filter((command) => command.kind === 'field')).toHaveLength(0)
    expect(commands.filter((command) => command.kind === 'polyline')).toHaveLength(1)
  })

  it('draws both when the layer is on and a 4D route exists', () => {
    const commands = timeAxisOverlays(cube, 0, 'shadow', manifest, plan4d, true)
    expect(commands.filter((command) => command.kind === 'field')).toHaveLength(1)
    expect(commands.filter((command) => command.kind === 'polyline')).toHaveLength(1)
  })

  it('paints nothing at all with no cube, however the layer is set', () => {
    expect(timeAxisOverlays(null, 0, 'shadow', manifest, null, true)).toHaveLength(0)
    expect(timeAxisOverlays(null, 0, 'shadow', manifest, null, false)).toHaveLength(0)
  })
})
