import type { Cell, CellRef } from './types'

/**
 * The cell an analysis feature may treat as chosen.
 *
 * Deliberately NOT the map's hover cell. onHoverCellChange fires as the pointer
 * moves and clears on leave, so a hover cell is a transient pointer position,
 * not a selection: it would make an assistant's answer depend on where the
 * mouse happened to rest, and it would make an "analyse the selected cell"
 * suggestion appear and vanish under the operator's hand.
 *
 * Start and goal are set by an explicit click and persist, so they are the only
 * stable cell context this app has. The preference order mirrors the map's own
 * focusPoint rule (goal, then start), and the result is null when neither has
 * been placed -- fail closed, rather than inventing a focus.
 *
 * This is a policy, not a selection, which is why it lives here as a pure
 * function rather than as a MissionContext field. Start and goal mean "route
 * from here" and "route to here"; reading them as "the cell the operator
 * selected" is a choice an analysis feature makes, and it should have to say
 * so at the call site.
 */
export function selectStableAnalysisCell(
  start: Cell | null,
  goal: Cell | null,
): CellRef | null {
  const point = goal ?? start
  return point ? { row: point[0], col: point[1] } : null
}
