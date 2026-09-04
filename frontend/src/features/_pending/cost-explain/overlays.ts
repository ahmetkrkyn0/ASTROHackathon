import type { OverlayLayer } from '../../overlay/types'

/** A ring on the cell whose cost is being explained. */
export function hoverCellOverlay(cell: [number, number] | null): OverlayLayer[] {
  if (!cell) return []
  return [
    {
      kind: 'points',
      id: 'cost-explain-hover',
      points: [{ row: cell[0], col: cell[1] }],
      style: { color: '#f8fafc', radius: 5, opacity: 0.95 },
    },
  ]
}
