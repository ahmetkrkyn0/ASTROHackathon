import { useFocusTelemetry } from '../../mission/MissionContext'
import { riskToDashArray, riskToHex } from '../../colormap'
import './map-legend.css'

/**
 * Scale and risk key, in the status strip under the map.
 *
 * This used to float over the terrain, on the argument that a key belongs on
 * the thing it describes. In practice it is a wide band -- a scale bar plus
 * four risk levels -- and the map is what the operator actually works in: in
 * 2-D it sat across the bottom of the plate, covering the ground start/goal
 * markers get picked on. Reading it now costs a glance down; leaving it on
 * the map cost pixels that carry data.
 *
 * The dash pattern is in the key as well as the colour, because the map
 * encodes risk in both and a key showing only colour would document half of
 * it.
 */

const LEGEND_ITEMS = [
  { label: 'Safe', level: 'LOW' },
  { label: 'Caution', level: 'MEDIUM' },
  { label: 'High', level: 'HIGH' },
  { label: 'Critical', level: 'CRITICAL' },
] as const

export function MapLegend() {
  const focusTelemetry = useFocusTelemetry()

  return (
    <div className="lp-map-key">
      <div className="lp-map-key-scale">
        <span className="lp-map-key-rule" aria-hidden="true" />
        <span className="lp-map-key-copy">
          0 – {focusTelemetry.spanKm.toFixed(1)} km · {focusTelemetry.resolutionM.toFixed(0)} m/px
        </span>
      </div>

      <span className="lp-map-key-sep" aria-hidden="true" />

      <div className="lp-map-key-risk">
        <span className="lp-map-key-label">RISK</span>
        {LEGEND_ITEMS.map((item) => (
          <span key={item.label} className="lp-map-key-item">
            <svg className="lp-map-key-line" viewBox="0 0 20 8" aria-hidden="true" focusable="false">
              <line
                x1="1"
                y1="4"
                x2="19"
                y2="4"
                stroke={riskToHex(item.level)}
                strokeWidth="2.4"
                strokeDasharray={riskToDashArray(item.level)}
              />
            </svg>
            {item.label}
          </span>
        ))}
      </div>
    </div>
  )
}
