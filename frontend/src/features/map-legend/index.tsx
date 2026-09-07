import { useFocusTelemetry } from '../../mission/MissionContext'
import { riskToDashArray, riskToHex } from '../../colormap'
import './map-legend.css'

/**
 * Scale and risk key, on the map rather than under it.
 *
 * Both of these describe what the map is showing -- how far a pixel is, and
 * what a line's colour and dash mean -- so they belong on the thing they
 * describe. In the status strip they were a band of chrome the eye had to
 * leave the terrain to read, and they took vertical room from the map to do
 * it.
 *
 * Bottom centre, which is the one edge free in both renderers: the 3-D scene
 * already holds all four corners (surface telemetry, the LiDAR readout, the
 * camera toggle and the photo drape), and a scale bar that hid behind one of
 * them in 3-D and not in 2-D would be worse than either place.
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
    <div className="map-overlay map-overlay-bottom-center lp-map-key">
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
