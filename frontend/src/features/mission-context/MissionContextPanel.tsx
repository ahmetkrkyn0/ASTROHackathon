import { useFocusTelemetry } from '../../mission/MissionContext'

/**
 * What the pointer is over.
 *
 * This panel used to carry four sections and now carries one. The three that
 * went:
 *
 *  - "Mission context" -- sector, resolution, extent, system state. Every value
 *    was fixed for the session or already stated elsewhere: the extent and the
 *    resolution are printed on the scale bar under the map, and the system
 *    state is the top bar's `Mission LOCKED`. It was a card restating chrome.
 *  - "Active raster layer" -- the name of the layer currently drawn. The layer
 *    picker sits on the map with that name in it, so this was the same word
 *    twice on one screen, one of them 900px from the control that sets it.
 *  - "No route analysed yet" -- an empty state that rendered unconditionally.
 *    It sat above a solved route's full analysis telling the operator no route
 *    had been analysed, with a checklist ticking off the two points they had
 *    just placed. Wrong, not merely redundant.
 *
 * What stays is the only thing here that answers a question the operator is
 * actually asking: where is the pointer, and what is under it. The feature is
 * still registered as `mission-context` -- the id is placement, and renaming it
 * would edit a test about which rail this mounts in to say nothing new.
 */
export default function MissionContextPanel() {
  const focus = useFocusTelemetry()

  return (
    <div className="lp-panel-content">
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Surface picker telemetry</span>
        </div>

        <div className="lp-telemetry-mono-grid">
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">Pixel [row, col]</span>
            <span className="lp-mono-val">{focus.row}, {focus.col}</span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">Latitude</span>
            <span className="lp-mono-val">
              {Number.isFinite(focus.lat) ? `${focus.lat.toFixed(4)}°` : '--'}
            </span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">Longitude</span>
            <span className="lp-mono-val">
              {Number.isFinite(focus.lon) ? `${focus.lon.toFixed(4)}°` : '--'}
            </span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">Elevation</span>
            <span className="lp-mono-val">
              {focus.altitudeM !== null ? `${focus.altitudeM.toFixed(1)} m` : '--'}
            </span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">Surface temp</span>
            <span className="lp-mono-val">
              {focus.thermalC !== null ? `${focus.thermalC.toFixed(1)} °C` : '--'}
            </span>
          </div>
        </div>
      </section>
    </div>
  )
}
