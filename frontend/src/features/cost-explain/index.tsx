import { useEffect, useMemo } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { CostExplainPanel } from './CostExplainPanel'
import { hoverCellOverlay } from './overlays'
import { useCostExplain } from './useCostExplain'

const OVERLAY_ID = 'cost-explain'

export function CostExplain() {
  const state = useCostExplain()
  const overlays = useOverlays()

  // MEMOISED on the coordinates, not on the array: state.cell is a fresh
  // tuple every render, so keying the effect on it would re-register forever.
  const commands = useMemo(
    () => hoverCellOverlay(state.cell),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [state.cell?.[0], state.cell?.[1]],
  )

  useEffect(() => overlays.register(OVERLAY_ID, commands), [overlays, commands])

  return (
    <section className="rail-section">
      <p className="panel-kicker">Cost Breakdown</p>
      <CostExplainPanel {...state} />
    </section>
  )
}
