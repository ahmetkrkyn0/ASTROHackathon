import { useEffect, useMemo, useState } from 'react'

import { useOverlays } from '../../overlay/useOverlays'
import { capabilityValue } from '../../mission/capability'
import { AnalysisLayersPanel } from './AnalysisLayersPanel'
import { analysisOverlays } from './overlays'
import { useAnalysisLayers } from './useAnalysisLayers'
import './analysis-layers.css'

const OVERLAY_ID = 'analysis-layers'

export function AnalysisLayers() {
  const state = useAnalysisLayers()
  const overlays = useOverlays()
  const [isOpen, setIsOpen] = useState(false)

  // MEMOISED: `register` keys off array identity, and each command carries a
  // converted grid, so an array rebuilt per render is both an infinite effect
  // loop and a quarter-million pointless writes per layer.
  const commands = useMemo(
    () =>
      analysisOverlays(
        state.entries.map((entry) => ({
          spec: entry.spec,
          // Drawn only while the toggle is on: a capability can still hold a
          // field from before it was switched off, and drawing that would
          // leave a layer on the map the control says is off.
          field: entry.enabled ? capabilityValue(entry.capability) : null,
        })),
      ),
    [state.entries],
  )

  useEffect(() => overlays.register(OVERLAY_ID, commands), [overlays, commands])

  const onCount = state.enabledIds.length

  return (
    // The canvas slot turns pointer events off so an empty overlay layer
    // cannot swallow map clicks; a control that wants them turns them back on.
    <div className="map-overlay-analysis" style={{ pointerEvents: 'auto' }}>
      <div className="lp-analysis-dock">
        <button
          type="button"
          className={`lp-analysis-trigger ${isOpen ? 'is-open' : ''} ${
            onCount > 0 ? 'has-active' : ''
          }`}
          onClick={() => setIsOpen((previous) => !previous)}
          aria-expanded={isOpen}
        >
          <span className="lp-layer-label-hint">Analysis</span>
          <strong className="lp-layer-current-name">
            {onCount === 0 ? 'None' : `${onCount} on`}
          </strong>
          <span className="lp-dropdown-chevron" aria-hidden="true">
            {isOpen ? '▴' : '▾'}
          </span>
        </button>

        {isOpen && <AnalysisLayersPanel {...state} />}
      </div>
    </div>
  )
}

export default AnalysisLayers
