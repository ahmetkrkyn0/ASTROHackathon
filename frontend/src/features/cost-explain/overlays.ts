import type { OverlayCommand } from '../../overlay/types'

/** A ring on the cell whose cost is being explained. */
export function hoverCellOverlay(cell: [number, number] | null): OverlayCommand[] {
  if (!cell) return []
  return [
    {
      kind: 'points',
      id: 'cost-explain-hover',
      points: [{ row: cell[0], col: cell[1] }],
      style: { color: '#e7eaf1', radiusPx: 5, opacity: 0.95 },
    },
  ]
}
