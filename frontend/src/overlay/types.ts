import type { CellRef } from '../mission/types'

/**
 * What a feature asks the map to draw.
 *
 * The one rule: coordinates are ALWAYS fine-grid `{row, col}`. Not CRS metres,
 * not coarse pixels, not canvas pixels. A feature holding metres converts once,
 * through mission/geo.ts, and every renderer downstream reads the same space --
 * which is what will let this same list feed a 3-D renderer later without the
 * features changing.
 */

export interface OverlayStyle {
  /** CSS colour. Required: a command with no colour has no defensible default. */
  color: string
  opacity?: number
  /** Stroke width in canvas pixels, for polyline and ribbon outlines. */
  widthPx?: number
  /** Dash pattern in canvas pixels. */
  dash?: number[]
  /** Marker radius in canvas pixels, for points. */
  radiusPx?: number
}

interface OverlayCommandBase {
  /** Unique within the registering feature. Used for nothing but diagnosis. */
  id: string
}

/** A route-like line through a sequence of cells. */
export interface PolylineCommand extends OverlayCommandBase {
  kind: 'polyline'
  points: CellRef[]
  style: OverlayStyle
}

/**
 * A variable-width band around a centreline -- a corridor, a tolerance sleeve.
 *
 * `halfWidthCells` is either one width for the whole band or one per point, in
 * which case it must be the same length as `points`.
 */
export interface RibbonCommand extends OverlayCommandBase {
  kind: 'ribbon'
  points: CellRef[]
  halfWidthCells: number | number[]
  style: OverlayStyle
}

/** Discrete markers: shelters, samples, rejected candidates. */
export interface PointsCommand extends OverlayCommandBase {
  kind: 'points'
  points: CellRef[]
  style: OverlayStyle
}

/**
 * A colour ramp, sampled between `min` and `max`.
 *
 * Data, not a callback. A `colorFor` function would be a new identity on every
 * render, which is precisely what makes a registration effect loop, so the
 * hazard is kept out of the type rather than warned about in prose.
 */
export interface FieldRamp {
  min: number
  max: number
  /** Two or more RGB stops, evenly spaced across [min, max]. */
  colors: Array<[number, number, number]>
}

/**
 * A scalar painted over the whole grid.
 *
 * `values` is row-major and `rows * cols` long. `null` is not zero: a null cell
 * is left unpainted, so whatever the map already drew shows through.
 */
export interface FieldCommand extends OverlayCommandBase {
  kind: 'field'
  rows: number
  cols: number
  values: (number | null)[]
  ramp: FieldRamp
  style?: { opacity?: number }
}

export type OverlayCommand =
  | PolylineCommand
  | RibbonCommand
  | PointsCommand
  | FieldCommand
