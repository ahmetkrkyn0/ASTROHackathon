import type { MapViewMode } from '../../MapCanvas'
import { useFocusTelemetry, useMission } from '../../mission/MissionContext'

const LAYER_TITLES: Record<MapViewMode, string> = {
  surface: 'Lunar Surface DEM (Digital Elevation Model)',
  thermal: 'Surface Temperature (Heat1D / Diviner)',
  cost: 'Multi-Factor A* Weighted Cost Grid',
  shadow: 'Permanent Shadow Region (PSR) Ratio',
  traversability: 'Traversability & Slope Envelope Mask',
  slope: 'Topographic Slope Incline Grid',
  aspect: 'Topographic Aspect Orientation Grid',
}

export default function MissionContextPanel() {
  const { gridMeta, layerError, isSolving, planResult, activeViewMode, start, goal } = useMission()
  const focus = useFocusTelemetry()
  const dataLinkActive = Boolean(gridMeta)
  const missionStatus = layerError ? 'ATTN' : isSolving ? 'SOLVING' : planResult ? 'LOCKED' : 'NOMINAL'
  const activeLayer = activeViewMode
  return (
    <div className="lp-panel-content">
      {/* Telemetry Header */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Mission context</span>
          <span className={`lp-live-badge ${dataLinkActive ? 'is-live' : ''}`}>
            {dataLinkActive ? 'TELEMETRY LIVE' : 'OFFLINE'}
          </span>
        </div>
        <p className="lp-panel-desc-text">
          Site 11 Lunar South Pole exploration sector. Real-time georeferenced raster metadata.
        </p>

        <div className="lp-context-grid">
          <div className="lp-context-cell">
            <span className="lp-spec-label">Sector</span>
            <strong className="lp-spec-val">Site 11 (89.5°S)</strong>
          </div>
          <div className="lp-context-cell">
            <span className="lp-spec-label">Resolution</span>
            <strong className="lp-spec-val">{focus.resolutionM} m/px</strong>
          </div>
          <div className="lp-context-cell">
            <span className="lp-spec-label">Extent</span>
            <strong className="lp-spec-val">{focus.spanKm.toFixed(1)} × {focus.spanKm.toFixed(1)} km</strong>
          </div>
          <div className="lp-context-cell">
            <span className="lp-spec-label">System state</span>
            <strong className="lp-spec-val lp-text-mint">{missionStatus}</strong>
          </div>
        </div>
      </section>

      {/* Active Layer Inspector */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Active raster layer</span>
        </div>
        <div className="lp-active-layer-card">
          <div className="lp-layer-card-tag">{activeLayer.toUpperCase()}</div>
          <strong className="lp-layer-card-title">{LAYER_TITLES[activeLayer]}</strong>
        </div>
      </section>

      {/* Cursor / Focus Telemetry Readout */}
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

      {/* Honest No-Route Empty State */}
      <section className="lp-panel-section lp-no-route-section">
        <div className="lp-no-route-card">
          <div className="lp-no-route-icon">◎</div>
          <h4 className="lp-no-route-title">No route analysed yet</h4>
          <p className="lp-no-route-text">
            Select a rover, click <strong>Select Start</strong> and <strong>Select Goal</strong> on the terrain, then click <strong>Generate Route</strong> to trigger kinematic A* optimization and view mission telemetry.
          </p>
          <div className="lp-no-route-checklist">
            <div className={`lp-check-row ${start ? 'is-done' : ''}`}>
              <span className="lp-check-icon">{start ? '✓' : '○'}</span>
              <span>Start point placed ({start ? `${start[0]}, ${start[1]}` : 'Unset'})</span>
            </div>
            <div className={`lp-check-row ${goal ? 'is-done' : ''}`}>
              <span className="lp-check-icon">{goal ? '✓' : '○'}</span>
              <span>Goal point placed ({goal ? `${goal[0]}, ${goal[1]}` : 'Unset'})</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
