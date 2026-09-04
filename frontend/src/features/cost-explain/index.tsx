import { useEffect } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { CostExplainPanel } from './CostExplainPanel'
import { hoverCellOverlay } from './overlays'
import { useCostExplain } from './useCostExplain'

const OVERLAY_ID = 'cost-explain'

export function CostExplain() {
  const state = useCostExplain()
  const { register, unregister } = useOverlays()

  useEffect(() => {
    register(OVERLAY_ID, hoverCellOverlay(state.cell))
    return () => unregister(OVERLAY_ID)
  }, [register, state.cell, unregister])

  return (
    <section className="rail-section">
      <p className="panel-kicker">Cost Breakdown</p>
      <CostExplainPanel {...state} />
    </section>
  )
}
