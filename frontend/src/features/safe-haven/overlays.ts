/**
 * The safe-haven fields as overlay commands.
 *
 * Pure and separately tested. The NaN rule here is the one that matters most
 * in this whole track: on `time_to_safe_haven`, NaN means "no reachable safe
 * haven", and any number at all -- especially zero -- is the opposite claim.
 */

import type { OverlayCommand } from '../../overlay/types'
import { fieldValues, maskValues, type BinaryField } from '../../net/layers'
import { START_MINT, TIME_TO_HAVEN_STOPS, type RGB } from '../../colormap'
import type { SafeHavenView } from './useSafeHaven'

/** Hours-since-dark ramps, cool to warm. Long dark is the thing to notice. */
const DARK_HOURS_STOPS: RGB[] = [
  [24, 40, 58],
  [42, 92, 116],
  [104, 138, 132],
  [196, 168, 96],
  [214, 120, 78],
]

function hexToRgb(hex: string): RGB {
  const value = hex.replace('#', '')
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ]
}

/**
 * One field, ready to draw.
 *
 * `safe_haven` is a boolean and is drawn as a mask: a haven is a small
 * minority of this window (10% of traversable cells), so painting the
 * complement would put a wash over nine tenths of the map that says nothing.
 *
 * The three hour fields are ramps over the layer's own measured range. Cells
 * with no value stay null and are left unpainted -- which is the entire point
 * on `time_to_safe_haven`: an unpainted cell reads as "nothing to say here",
 * and every alternative reads as a number.
 */
export function safeHavenCommand(
  view: SafeHavenView,
  field: BinaryField,
): OverlayCommand | null {
  if (field.rows <= 0 || field.cols <= 0) return null

  if (view === 'safe_haven') {
    const mint = hexToRgb(START_MINT)
    return {
      kind: 'field',
      id: 'safe-haven-mask',
      rows: field.rows,
      cols: field.cols,
      values: maskValues(field, 0.5),
      ramp: { min: 0, max: 1, colors: [mint, mint] },
      style: { opacity: 0.6 },
    }
  }

  const min = field.min
  const max = field.max
  if (min === null || max === null || !(max > min)) return null

  return {
    kind: 'field',
    id: `safe-haven-${view}`,
    rows: field.rows,
    cols: field.cols,
    // NaN becomes null and stays null. On time_to_safe_haven that is "no
    // reachable haven"; a zero there would say the cell IS one.
    values: fieldValues(field),
    ramp: {
      min,
      max,
      colors: view === 'time_to_safe_haven' ? TIME_TO_HAVEN_STOPS : DARK_HOURS_STOPS,
    },
    style: { opacity: 0.58 },
  }
}

export function safeHavenOverlays(
  view: SafeHavenView,
  field: BinaryField | null,
): OverlayCommand[] {
  if (!field) return []
  const command = safeHavenCommand(view, field)
  return command ? [command] : []
}
