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
  fieldVisible: boolean,
): OverlayCommand[] {
  const commands: OverlayCommand[] = []

  // The route is drawn whenever there is one; the field only when it has been
  // asked for. They are separate answers: the 4D route is the result of a
  // request the operator made, the field is a layer over the terrain.
  if (fieldVisible && cube && manifest) {
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
      // 0.35, down from 0.6. The shadow ramp runs white to black, so at 0.6
      // this did not read as a field painted over the terrain -- it read as
      // the lighting being switched off. The hillshade underneath is what
      // makes the surface legible as terrain at all, and a field laid over it
      // has to let it through. Lowering the alpha was not enough on its own,
      // which is why the layer is now off until asked for: even at 0.35 it
      // darkened shadowed ground by about 50 levels, across the whole map,
      // for an operator who had only switched to ANALYZE to read a route.
      style: { opacity: 0.35 },
    })
  }

  if (plan4d && plan4d.path_pixels.length > 1) {
    // path_pixels, not path_pixels_coarse: the fine array is the one in the
    // same frame as /api/plan and as the canvas (spec T4).
    commands.push({
      kind: 'polyline',
      id: 'time-axis-route',
      points: plan4d.path_pixels.map(([row, col]) => ({ row, col })),
      // Lavender, not the ramp's amber. A yellow line on this map means
      // MEDIUM risk everywhere else, and the time-expanded route is not a
      // risk reading at all -- it is a second plan. Borrowing a ramp colour
      // for it made the map say something it did not mean.
      style: { color: '#baaff5', widthPx: 2.5, opacity: 0.95 },
    })
  }

  return commands
}
