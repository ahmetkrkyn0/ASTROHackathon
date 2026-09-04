import type { SeriesCube } from '../../net/series'
import type { Plan4DResponse, SeriesManifest } from '../../net/types'
import type { OverlayLayer } from '../../overlay/types'
import type { SeriesField } from './useTimeAxis'

const RAMP = { shadow: 'grayReverse', surface_temp_c: 'thermal' } as const

export function timeAxisOverlays(
  cube: SeriesCube | null,
  sliceIndex: number,
  field: SeriesField,
  manifest: SeriesManifest | null,
  plan4d: Plan4DResponse | null,
): OverlayLayer[] {
  const layers: OverlayLayer[] = []

  if (cube && manifest) {
    const entry = manifest.fields[field]
    // The manifest's own min/max across the WHOLE cube, not this slice's:
    // a per-slice domain would re-normalise the colours every frame and the
    // animation would show contrast changing rather than illumination.
    const min = entry.min ?? 0
    const max = entry.max ?? 1
    layers.push({
      kind: 'field',
      id: 'time-axis-field',
      data: cube.sliceAt(Math.min(sliceIndex, cube.slices - 1)),
      rows: cube.rows,
      cols: cube.cols,
      domain: [min, max],
      ramp: RAMP[field],
      opacity: 0.6,
    })
  }

  if (plan4d && plan4d.path_pixels.length > 1) {
    // path_pixels, not path_pixels_coarse: the fine array is the one in the
    // same frame as /api/plan and as the canvas (spec T4).
    layers.push({
      kind: 'polyline',
      id: 'time-axis-route',
      points: plan4d.path_pixels.map(([row, col]) => ({ row, col })),
      style: { color: '#facc15', lineWidth: 2.5, opacity: 0.95 },
    })
  }

  return layers
}
