import React from 'react'
import type { MapViewMode } from '../../MapCanvas'

interface FocusTelemetry {
  row: number
  col: number
  lat: number
  lon: number
  altitudeM: number | null
  thermalC: number | null
  resolutionM: number
  spanKm: number
}

interface MissionContextPanelProps {
  dataLinkActive: boolean
  missionStatus: string
  activeLayer: MapViewMode
  telemetry: FocusTelemetry
  start: [number, number] | null
  goal: [number, number] | null
}

const LAYER_TITLES: Record<MapViewMode, string> = {
  surface: 'Lunar Surface DEM (Digital Elevation Model)',
  thermal: 'Surface Temperature (Heat1D / Diviner)',
  cost: 'Multi-Factor A* Weighted Cost Grid',
  shadow: 'Permanent Shadow Region (PSR) Ratio',
  traversability: 'Traversability & Slope Envelope Mask',
  slope: 'Topographic Slope Incline Grid',
  aspect: 'Topographic Aspect Orientation Grid',
}

export const MissionContextPanel: React.FC<MissionContextPanelProps> = ({
  dataLinkActive,
  missionStatus,
  activeLayer,
  telemetry,
  start,
  goal,
}) => {
  return (
    <div className="lp-panel-content">
      {/* Telemetry Header */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">MISSION CONTEXT</span>
          <span className={`lp-live-badge ${dataLinkActive ? 'is-live' : ''}`}>
            {dataLinkActive ? 'TELEMETRY LIVE' : 'OFFLINE'}
          </span>
        </div>
        <p className="lp-panel-desc-text">
          Site 11 Lunar South Pole exploration sector. Real-time georeferenced raster metadata.
        </p>

        <div className="lp-context-grid">
          <div className="lp-context-cell">
            <span className="lp-spec-label">SECTOR</span>
            <strong className="lp-spec-val">Site 11 (89.5°S)</strong>
          </div>
          <div className="lp-context-cell">
            <span className="lp-spec-label">RESOLUTION</span>
            <strong className="lp-spec-val">{telemetry.resolutionM} m/px</strong>
          </div>
          <div className="lp-context-cell">
            <span className="lp-spec-label">EXTENT</span>
            <strong className="lp-spec-val">{telemetry.spanKm.toFixed(1)} × {telemetry.spanKm.toFixed(1)} km</strong>
          </div>
          <div className="lp-context-cell">
            <span className="lp-spec-label">SYSTEM STATE</span>
            <strong className="lp-spec-val lp-text-mint">{missionStatus}</strong>
          </div>
        </div>
      </section>

      {/* Active Layer Inspector */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">ACTIVE RASTER LAYER</span>
        </div>
        <div className="lp-active-layer-card">
          <div className="lp-layer-card-tag">{activeLayer.toUpperCase()}</div>
          <strong className="lp-layer-card-title">{LAYER_TITLES[activeLayer]}</strong>
        </div>
      </section>

      {/* Cursor / Focus Telemetry Readout */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">SURFACE PICKER TELEMETRY</span>
        </div>

        <div className="lp-telemetry-mono-grid">
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">PIXEL [R, C]</span>
            <span className="lp-mono-val">{telemetry.row}, {telemetry.col}</span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">LATITUDE</span>
            <span className="lp-mono-val">
              {Number.isFinite(telemetry.lat) ? `${telemetry.lat.toFixed(4)}°` : '--'}
            </span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">LONGITUDE</span>
            <span className="lp-mono-val">
              {Number.isFinite(telemetry.lon) ? `${telemetry.lon.toFixed(4)}°` : '--'}
            </span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">ELEVATION</span>
            <span className="lp-mono-val">
              {telemetry.altitudeM !== null ? `${telemetry.altitudeM.toFixed(1)} m` : '--'}
            </span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">SURFACE TEMP</span>
            <span className="lp-mono-val">
              {telemetry.thermalC !== null ? `${telemetry.thermalC.toFixed(1)} °C` : '--'}
            </span>
          </div>
        </div>
      </section>

      {/* Honest No-Route Empty State */}
      <section className="lp-panel-section lp-no-route-section">
        <div className="lp-no-route-card">
          <div className="lp-no-route-icon">◎</div>
          <h4 className="lp-no-route-title">NO ROUTE ANALYSIS YET</h4>
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

export default MissionContextPanel

