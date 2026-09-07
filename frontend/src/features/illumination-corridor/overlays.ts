/**
 * One slice of the corridor cube, as an overlay command.
 *
 * NOT `features/corridor/` -- that is the route corridor, a ribbon around a
 * planned path. This is the illumination corridor: the volume of (block,
 * slice) that is lit, passable and connected to both ends of the horizon. The
 * two share a word and nothing else.
 *
 * Pure so the slicing arithmetic can be tested. A cube read at the wrong
 * offset draws a real, plausible corridor for the wrong hour, which no visual
 * check would catch.
 */

import type { OverlayCommand } from '../../overlay/types'
import type { SeriesCube } from '../../net/series'
import { CORRIDOR_RGB, DWELL_STOPS, LIT_SAFE_RGB, type RGB } from '../../colormap'
import type { CorridorFieldName } from '../../net/analysis'

/** How each of the three fields is drawn. Two are masks, one is a ramp. */
export const CORRIDOR_FIELDS: ReadonlyArray<{
  id: CorridorFieldName
  label: string
  blurb: string
}> = [
  {
    id: 'corridor',
    label: 'Corridor',
    blurb: 'Lit, passable, and reachable from both ends of the horizon.',
  },
  {
    id: 'lit_safe',
    label: 'Lit & passable',
    blurb: 'Before pruning: lit and passable, whether or not it connects.',
  },
  {
    id: 'dwell_hours',
    label: 'Dwell hours',
    blurb: 'How long a rover could stay in the corridor from this slice on.',
  },
]

/**
 * The slice for `sliceIndex`, ready to draw.
 *
 * `corridor` and `lit_safe` are 0/1 and drawn as masks: the zeros are the rest
 * of the map, and painting them would wash everything the corridor is defined
 * against. `dwell_hours` is a real scale and gets a ramp.
 *
 * Zero dwell is kept as a value, not nulled. A block in the corridor now with
 * zero hours ahead of it is a different statement from a block outside the
 * corridor, and only the ramp's low end can say the first.
 */
export function corridorSliceCommand(
  field: CorridorFieldName,
  cube: SeriesCube,
  sliceIndex: number,
  range: { min: number; max: number },
): OverlayCommand | null {
  if (cube.slices <= 0 || cube.rows <= 0 || cube.cols <= 0) return null

  const index = Math.min(Math.max(sliceIndex, 0), cube.slices - 1)
  const slice = cube.sliceAt(index)

  if (field === 'dwell_hours') {
    if (!(range.max > range.min)) return null
    const values: (number | null)[] = new Array(slice.length)
    for (let i = 0; i < slice.length; i += 1) {
      values[i] = Number.isNaN(slice[i]) ? null : slice[i]
    }
    return {
      kind: 'field',
      id: 'illumination-corridor-dwell',
      rows: cube.rows,
      cols: cube.cols,
      values,
      ramp: { min: range.min, max: range.max, colors: DWELL_STOPS },
      style: { opacity: 0.6 },
    }
  }

  const colour: RGB = field === 'corridor' ? CORRIDOR_RGB : LIT_SAFE_RGB
  const values: (number | null)[] = new Array(slice.length)
  for (let i = 0; i < slice.length; i += 1) {
    const value = slice[i]
    values[i] = !Number.isNaN(value) && value >= 0.5 ? 1 : null
  }
  return {
    kind: 'field',
    id: `illumination-corridor-${field}`,
    rows: cube.rows,
    cols: cube.cols,
    values,
    ramp: { min: 0, max: 1, colors: [colour, colour] },
    style: { opacity: 0.55 },
  }
}

/**
 * How many blocks the slice holds, for the readout under the slider.
 *
 * The corridor shrinks and grows across the horizon -- it is the whole reason
 * this is a cube and not a layer -- and a number that moves as the slider does
 * is what makes that visible without watching the colours.
 */
export function sliceCellCount(cube: SeriesCube, sliceIndex: number): number {
  if (cube.slices <= 0) return 0
  const index = Math.min(Math.max(sliceIndex, 0), cube.slices - 1)
  const slice = cube.sliceAt(index)
  let count = 0
  for (let i = 0; i < slice.length; i += 1) {
    if (!Number.isNaN(slice[i]) && slice[i] >= 0.5) count += 1
  }
  return count
}
