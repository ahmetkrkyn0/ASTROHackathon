import { metresToPixel, type GridFrame, type PixelPoint } from '../../grid/geo'
import type { OverlayLayer } from '../../overlay/types'
import type { Corridor } from '../../net/types'

/**
 * Per-vertex half-width from the per-segment array.
 *
 * There are N waypoints but only N-1 segment widths (corridor.py:126). A
 * vertex takes the NARROWER of the segments meeting there: widening a
 * corner to the roomier neighbour would draw permission the planner never
 * granted.
 */
function vertexHalfWidths(halfWidthM: number[], vertexCount: number): number[] {
  const out: number[] = []
  for (let i = 0; i < vertexCount; i++) {
    const before = i > 0 ? halfWidthM[i - 1] : Number.POSITIVE_INFINITY
    const after = i < halfWidthM.length ? halfWidthM[i] : Number.POSITIVE_INFINITY
    const width = Math.min(before, after)
    out.push(Number.isFinite(width) ? width : 0)
  }
  return out
}

export function corridorOverlays(
  corridor: Corridor | null,
  frame: GridFrame | null,
): OverlayLayer[] {
  if (!corridor || !frame || corridor.waypoints.length < 2) return []

  const center: PixelPoint[] = corridor.waypoints.map(([x, y]) =>
    metresToPixel(x, y, frame),
  )
  const widthsM = vertexHalfWidths(corridor.half_width_m, center.length)
  const halfWidthPx = widthsM.map((metres) => metres / frame.resolutionM)

  const fallback: PixelPoint[] = corridor.fallback_points.map(([x, y]) =>
    metresToPixel(x, y, frame),
  )

  return [
    {
      kind: 'ribbon',
      id: 'corridor-band',
      center,
      halfWidthPx,
      style: { color: '#38bdf8', opacity: 0.22 },
    },
    {
      kind: 'points',
      id: 'corridor-havens',
      points: fallback,
      style: { color: '#34d399', radius: 2.5, opacity: 0.7 },
    },
  ]
}
