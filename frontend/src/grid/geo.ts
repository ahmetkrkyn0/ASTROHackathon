import type { TerrainManifest } from '../net/types'

export interface PixelPoint {
  row: number
  col: number
}

/**
 * The grid geometry every pixel/metre conversion needs.
 *
 * Never hard-coded. The shipped grid is 500x500 at 5 m/px today and was
 * 500x500 at 80 m/px before; the backend reads this from
 * lunapath/data/processed/metadata.json at runtime and so does this.
 */
export interface GridFrame {
  originX: number
  originY: number
  resolutionM: number
  rows: number
  cols: number
}

/** null when the manifest carries no georeference (origin can be absent). */
export function frameFromManifest(manifest: TerrainManifest): GridFrame | null {
  const origin = manifest.georeference.origin
  if (!origin) return null
  return {
    originX: origin.x,
    originY: origin.y,
    resolutionM: manifest.grid.resolution_m,
    rows: manifest.grid.rows,
    cols: manifest.grid.cols,
  }
}

/**
 * Projected CRS metres -> fine grid pixel.
 *
 * The y term is SUBTRACTED: origin.y is the window's north edge and rows
 * increase southward. Getting this backwards mirrors the corridor about the
 * middle row, which looks plausible and is wrong. Mirrors
 * serializer.pixel_to_lonlat (serializer.py:152-157).
 */
export function metresToPixel(x: number, y: number, frame: GridFrame): PixelPoint {
  return {
    row: (frame.originY - y) / frame.resolutionM,
    col: (x - frame.originX) / frame.resolutionM,
  }
}

/** Fine grid pixel -> projected CRS metres. Inverse of metresToPixel. */
export function pixelToMetres(
  row: number,
  col: number,
  frame: GridFrame,
): { x: number; y: number } {
  return {
    x: frame.originX + col * frame.resolutionM,
    y: frame.originY - row * frame.resolutionM,
  }
}

/**
 * Coarse planning pixel -> fine pixel, at the block's CENTRE CELL.
 *
 * The offset is `floor(coarsen / 2)`, not `(coarsen - 1) / 2`. Those differ
 * by half a cell on every even factor, and the integer one is what the
 * backend means by "centre" in both places it matters: cost_cube.coarsen_grid
 * samples `arr[coarsen // 2 :: coarsen]` when reducing elevation with
 * how="center" (cost_cube.py:57-59), and /api/plan-4d publishes
 * `path_pixels` as `r * coarsen + coarsen // 2` (main.py:1143-1147).
 *
 * So a coarse waypoint converted here lands on the SAME fine pixel the
 * backend already published for it, and on the fine cell whose elevation the
 * planner actually solved against. The geometric block centre would sit half
 * a block away from both -- close enough to look right on screen.
 */
export function coarseToFine(row: number, col: number, coarsen: number): PixelPoint {
  const offset = Math.floor(coarsen / 2)
  return { row: row * coarsen + offset, col: col * coarsen + offset }
}
