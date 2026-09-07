/**
 * Coarse fields as overlay commands.
 *
 * Pure and separately tested. Two rules matter here and neither is visible in
 * the rendered image if it is broken:
 *
 * A coarse field keeps its own 125x125 shape. `drawField` blits at that
 * resolution with smoothing off, so each value stays a 20 m block. Passing the
 * fine grid's dimensions would interpolate a product that has no business
 * being interpolated and claim a precision four times what it has.
 *
 * A code field becomes one mask per category. Never a ramp.
 */

import type { OverlayCommand } from '../../overlay/types'
import { fieldValues, type BinaryField } from '../../net/layers'
import type { CoarseFieldSpec, FieldCategory } from './fields'

/**
 * Cells whose code is in this category, everything else null.
 *
 * Exact integer comparison after rounding: the payload is float32 carrying
 * small integers, so 254 arrives as exactly 254 and there is no tolerance to
 * choose. A NaN block is not in any category and stays null -- it is not
 * traversable, which is a different statement from "no action helps" (255).
 */
export function categoryValues(
  field: BinaryField,
  category: FieldCategory,
): (number | null)[] {
  const wanted = new Set(category.codes)
  const values: (number | null)[] = new Array(field.data.length)
  for (let index = 0; index < field.data.length; index += 1) {
    const value = field.data[index]
    values[index] = !Number.isNaN(value) && wanted.has(Math.round(value)) ? 1 : null
  }
  return values
}

/**
 * One field, ready to draw. A ramp yields one command; a code field yields one
 * per category that actually has cells.
 *
 * Empty categories are dropped rather than drawn: an all-null field command
 * still costs a full-grid ImageData allocation and a blit, and on this window
 * `wait` covers three blocks out of 15 625.
 */
export function coarseFieldCommands(
  spec: CoarseFieldSpec,
  field: BinaryField,
): OverlayCommand[] {
  if (field.rows <= 0 || field.cols <= 0) return []

  if (spec.render.mode === 'categorical') {
    const commands: OverlayCommand[] = []
    for (const category of spec.render.categories) {
      const values = categoryValues(field, category)
      if (!values.some((value) => value !== null)) continue
      commands.push({
        kind: 'field',
        id: `coarse-${spec.id}-${category.key}`,
        rows: field.rows,
        cols: field.cols,
        values,
        // One colour, twice. There is exactly one value in this mask, so a
        // two-stop gradient would have nothing to interpolate between -- which
        // is the property that makes this encoding categorical.
        ramp: { min: 0, max: 1, colors: [category.color, category.color] },
        style: { opacity: spec.opacity },
      })
    }
    return commands
  }

  const min = field.min
  const max = field.max
  if (min === null || max === null || !(max > min)) return []

  return [
    {
      kind: 'field',
      id: `coarse-${spec.id}`,
      rows: field.rows,
      cols: field.cols,
      values: fieldValues(field),
      ramp: { min, max, colors: spec.render.stops },
      style: { opacity: spec.opacity },
    },
  ]
}

/**
 * How many cells each category holds, for the legend.
 *
 * Published because a legend without counts invites reading a colour that
 * covers three blocks as though it covered a region. `null` counts the NaN
 * cells, which belong to no category.
 */
export function categoryCounts(
  field: BinaryField,
  categories: readonly FieldCategory[],
): Record<string, number> {
  const byCode = new Map<number, string>()
  for (const category of categories) {
    for (const code of category.codes) byCode.set(code, category.key)
  }
  const counts: Record<string, number> = {}
  for (const category of categories) counts[category.key] = 0
  let unknown = 0

  for (let index = 0; index < field.data.length; index += 1) {
    const value = field.data[index]
    if (Number.isNaN(value)) continue
    const key = byCode.get(Math.round(value))
    if (key === undefined) {
      unknown += 1
      continue
    }
    counts[key] += 1
  }
  // A code the table does not cover is reported rather than silently dropped:
  // it means the backend grew a category this frontend does not know about.
  if (unknown > 0) counts.__unknown = unknown
  return counts
}
