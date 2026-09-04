import type { CellRef } from './types'

/**
 * The single frontend conversion between fine-grid cells and 2-D canvas pixels.
 *
 * Feature-facing overlay coordinates are always fine-grid `{row, col}`. This is
 * where that becomes something a canvas can draw, and the only place the
 * arithmetic is written down.
 *
 * Deliberately not here: the 3-D world transform. `cellToWorldXZ` in
 * TerrainView3D.tsx is already authoritative for the scene's own frame and
 * carries the row-axis reasoning next to the mesh it applies to. Re-exporting
 * it would make this module import a WebGL component; copying it would create
 * the second implementation this file exists to prevent. When the overlay
 * contract grows a 3-D renderer, that renderer calls the function where it
 * lives.
 */
export interface CanvasGeometry {
  /** Rows and columns of the fine grid the commands are expressed in. */
  rows: number
  cols: number
  /** Edge length of the square canvas, in device-independent pixels. */
  canvasSize: number
}

/**
 * Cell -> canvas pixel, at the centre of the cell.
 *
 * Centre rather than corner: a one-cell marker drawn at the corner sits half a
 * cell north-west of the cell it names, which at 5 m/px is a 2.5 m lie.
 */
export function cellToCanvasXY(cell: CellRef, geometry: CanvasGeometry): [number, number] {
  const { rows, cols, canvasSize } = geometry
  return [
    ((cell.col + 0.5) * canvasSize) / cols,
    ((cell.row + 0.5) * canvasSize) / rows,
  ]
}

/** Canvas pixel -> cell, or null when the point is outside the grid. */
export function canvasXYToCell(x: number, y: number, geometry: CanvasGeometry): CellRef | null {
  const { rows, cols, canvasSize } = geometry
  const col = Math.floor((x * cols) / canvasSize)
  const row = Math.floor((y * rows) / canvasSize)
  if (row < 0 || row >= rows || col < 0 || col >= cols) {
    return null
  }
  return { row, col }
}

/** Cell pitch in canvas pixels, for anything that has to size itself to a cell. */
export function cellSizePx(geometry: CanvasGeometry): { widthPx: number; heightPx: number } {
  return {
    widthPx: geometry.canvasSize / geometry.cols,
    heightPx: geometry.canvasSize / geometry.rows,
  }
}
