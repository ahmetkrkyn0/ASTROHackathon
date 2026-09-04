import { COOLWARM_STOPS } from '../../colormap'
import type { SeriesCube } from '../../net/series'
import type { Plan4DResponse, SeriesManifest } from '../../net/types'
import type { OverlayCommand } from '../../overlay/types'
import type { SeriesField } from './useTimeAxis'

/**
 * The stops each field is painted with.
 *
 * The canonical field command carries its own colours rather than a ramp
 * name, so the names this module used are resolved here. thermal is
 * colormap's own cool-warm ramp; shadow was grayReverseToRgb, which is white
 * at the minimum and black at the maximum -- two stops say the same thing.
 */
const RAMP_STOPS: Record<SeriesField, Array<[number, number, number]>> = {
  shadow: [
    [255, 255, 255],
    [0, 0, 0],
  ],
  surface_temp_c: COOLWARM_STOPS,
}

export function timeAxisOverlays(
  cube: SeriesCube | null,
  sliceIndex: number,
  field: SeriesField,
  manifest: SeriesManifest | null,
  plan4d: Plan4DResponse | null,
): OverlayCommand[] {
  const commands: OverlayCommand[] = []

  if (cube && manifest) {
    const entry = manifest.fields[field]
    // The manifest's own min/max across the WHOLE cube, not this slice's:
    // a per-slice domain would re-normalise the colours every frame and the
    // animation would show contrast changing rather than illumination.
    const min = entry.min ?? 0
    const max = entry.max ?? 1
    const slice = cube.sliceAt(Math.min(sliceIndex, cube.slices - 1))
    // The contract marks an empty cell with null, where the cube uses NaN.
    // One pass over the slice converts it; measured at 250k cells it costs
    // well under a frame, and it happens once per slice, not once per draw.
    const values: (number | null)[] = new Array(slice.length)
    for (let i = 0; i < slice.length; i++) {
      const value = slice[i]
      values[i] = Number.isNaN(value) ? null : value
    }
    commands.push({
      kind: 'field',
      id: 'time-axis-field',
      rows: cube.rows,
      cols: cube.cols,
      values,
      ramp: { min, max, colors: RAMP_STOPS[field] },
      style: { opacity: 0.6 },
    })
  }

  if (plan4d && plan4d.path_pixels.length > 1) {
    // path_pixels, not path_pixels_coarse: the fine array is the one in the
    // same frame as /api/plan and as the canvas (spec T4).
    commands.push({
      kind: 'polyline',
      id: 'time-axis-route',
      points: plan4d.path_pixels.map(([row, col]) => ({ row, col })),
      style: { color: '#facc15', widthPx: 2.5, opacity: 0.95 },
    })
  }

  return commands
}
