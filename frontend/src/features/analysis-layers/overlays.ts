/**
 * Analysis rasters as overlay commands.
 *
 * Pure, and separated from the hook so it can be tested: this project has
 * neither jsdom nor testing-library, so arithmetic left inside a component is
 * arithmetic nothing can check.
 */

import type { OverlayCommand } from '../../overlay/types'
import { fieldValues, maskValues, type BinaryField } from '../../net/layers'
import type { AnalysisLayerSpec } from './layers'

/**
 * One field, ready to draw.
 *
 * Two things this must not do, both of which look like tidying up:
 *
 * The field's own `rows`/`cols` go into the command, never the fine grid's.
 * `drawField` blits at the field's resolution with smoothing off, so a coarse
 * product keeps its block boundaries -- which is the honest rendering, because
 * a 320 m cell interpolated to look like 5 m data claims a precision the
 * product does not have.
 *
 * The ramp domain is the layer's own measured range, not a rounded one. The
 * backend reports what it actually found (`X-Layer-Min` / `Max`), and
 * substituting a tidy 0..5 for a real 0.12..4.60 makes every colour on the map
 * mean something slightly different from what the legend says.
 */
export function analysisFieldCommand(
  spec: AnalysisLayerSpec,
  field: BinaryField,
): OverlayCommand | null {
  if (field.rows <= 0 || field.cols <= 0) return null

  if (spec.render.mode === 'mask') {
    const { color, threshold } = spec.render
    return {
      kind: 'field',
      id: `analysis-${spec.id}`,
      rows: field.rows,
      cols: field.cols,
      values: maskValues(field, threshold),
      // One colour, twice. maskValues has already nulled everything below the
      // threshold, so this ramp only ever serves the value 1 -- a two-stop
      // gradient here would be a gradient with nothing to interpolate.
      ramp: { min: 0, max: 1, colors: [color, color] },
      style: { opacity: spec.opacity },
    }
  }

  // A degenerate range (a constant layer, or one the backend measured no
  // finite value in) has no gradient to draw. Painting it would put a flat
  // wash over the map that reads as data.
  const min = field.min
  const max = field.max
  if (min === null || max === null || !(max > min)) return null

  return {
    kind: 'field',
    id: `analysis-${spec.id}`,
    rows: field.rows,
    cols: field.cols,
    values: fieldValues(field),
    ramp: { min, max, colors: spec.render.stops },
    style: { opacity: spec.opacity },
  }
}

/**
 * The full command list, in the order the specs are declared.
 *
 * Registration order is paint order, and the table puts the mask last on
 * purpose: a mask over a ramp still shows the ramp's shape through its
 * opacity, whereas a ramp over a mask buries it.
 */
export function analysisOverlays(
  entries: readonly { spec: AnalysisLayerSpec; field: BinaryField | null }[],
): OverlayCommand[] {
  const commands: OverlayCommand[] = []
  for (const { spec, field } of entries) {
    if (!field) continue
    const command = analysisFieldCommand(spec, field)
    if (command) commands.push(command)
  }
  return commands
}
