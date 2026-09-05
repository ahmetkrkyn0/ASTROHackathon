import React from 'react'
import type { PlanWeights, RoverEntry } from '../../api'

interface FleetSelectionViewProps {
  rovers: RoverEntry[]
  selectedRover: RoverEntry | null
  onSelectRover: (rover: RoverEntry) => void
  weights: PlanWeights
  onWeightsChange: (weights: PlanWeights) => void
  onDeployToMap: () => void
}

interface RoverDetailMeta {
  agency: string
  agencyColor: string
  highlight: string
  payload: string
  image: string
  description: string
}

const ROVER_META: Record<string, RoverDetailMeta> = {
  lpr_1: {
    agency: 'ESA / LUNAPATH',
    agencyColor: '#4fd8f0',
    highlight: 'Flagship Autonomous Polar Explorer',
    payload: '360° LiDAR Turret, Panoramic Stereo NavCam, Deep Regolith Temperature Probes',
    image: '/rovers/lpr_1.jpg',
    description:
      'High-endurance heavy science explorer engineered for long-distance polar traverses. Features dual solar arrays and regenerative cryogenic battery packs.',
  },
  luvmi_m: {
    agency: 'LUNAPATH EXP',
    agencyColor: '#b3a5ff',
    highlight: 'Agile Crater Descent Micro-Rover',
    payload: 'High-Torque Mesh Wheels, Micro-LiDAR, Stereo Camera Mast, Rock Abrasion Tool',
    image: '/rovers/luvmi_m.jpg',
    description:
      'Ultra-compact robotic scout specifically designed to descend steep crater slopes and explore narrow shadowed terrain inaccessible to larger vehicles.',
  },
  luvm_m: {
    agency: 'LUNAPATH EXP',
    agencyColor: '#b3a5ff',
    highlight: 'Agile Crater Descent Micro-Rover',
    payload: 'High-Torque Mesh Wheels, Micro-LiDAR, Stereo Camera Mast, Rock Abrasion Tool',
    image: '/rovers/luvmi_m.jpg',
    description:
      'Ultra-compact robotic scout specifically designed to descend steep crater slopes and explore narrow shadowed terrain inaccessible to larger vehicles.',
  },
  nasa_viper: {
    agency: 'NASA',
    agencyColor: '#e8c85a',
    highlight: 'Subsurface Volatiles Prospector',
    payload: 'The TRIDENT 1-Meter Hammer Drill, Neutron Spectrometer System (NSS), NIRVSS',
    image: '/rovers/nasa_viper.jpg',
    description:
      'NASA premier volatile prospecting rover equipped with a heavy hammer drill and spectrometers to hunt for sub-surface water ice inside permanently shadowed regions.',
  },
  viper: {
    agency: 'NASA',
    agencyColor: '#e8c85a',
    highlight: 'Subsurface Volatiles Prospector',
    payload: 'The TRIDENT 1-Meter Hammer Drill, Neutron Spectrometer System (NSS), NIRVSS',
    image: '/rovers/nasa_viper.jpg',
    description:
      'NASA premier volatile prospecting rover equipped with a heavy hammer drill and spectrometers to hunt for sub-surface water ice inside permanently shadowed regions.',
  },
  cnsa_yutu_2: {
    agency: 'CNSA',
    agencyColor: '#ee5a52',
    highlight: 'Far-Side Lunar Endurance Rover',
    payload: 'Lunar Penetrating Radar (LPR), Visible & Near-Infrared Imaging Spectrometer (VNIS)',
    image: '/rovers/cnsa_yutu_2.jpg',
    description:
      'Lightweight solar-powered lunar rover holding world records for lunar surface operational longevity on the rugged terrain of the Moon.',
  },
  yutu_2: {
    agency: 'CNSA',
    agencyColor: '#ee5a52',
    highlight: 'Far-Side Lunar Endurance Rover',
    payload: 'Lunar Penetrating Radar (LPR), Visible & Near-Infrared Imaging Spectrometer (VNIS)',
    image: '/rovers/cnsa_yutu_2.jpg',
    description:
      'Lightweight solar-powered lunar rover holding world records for lunar surface operational longevity on the rugged terrain of the Moon.',
  },
}

function getRoverMeta(id: string): RoverDetailMeta {
  const norm = id.toLowerCase().trim()
  if (ROVER_META[norm]) return ROVER_META[norm]
  if (norm.includes('viper')) return ROVER_META.nasa_viper
  if (norm.includes('yutu')) return ROVER_META.cnsa_yutu_2
  if (norm.includes('luvm')) return ROVER_META.luvmi_m
  if (norm.includes('lpr')) return ROVER_META.lpr_1
  return ROVER_META.lpr_1
}

const WEIGHT_CONTROLS: Array<{
  key: keyof PlanWeights
  label: string
  desc: string
}> = [
  { key: 'w_slope', label: 'Slope Safety', desc: 'Avoids steep inclines, cliff faces, and high-tilt zones' },
  { key: 'w_energy', label: 'Energy Optimization', desc: 'Minimizes Watt-hour electrical drain from rover batteries' },
  { key: 'w_shadow', label: 'Shadow Exposure', desc: 'Avoids permanently shadowed, light-deprived cold traps' },
  { key: 'w_thermal', label: 'Cryogenic Thermal Risk', desc: 'Steers away from severe -200°C thermal shock zones' },
]

export const FleetSelectionView: React.FC<FleetSelectionViewProps> = ({
  rovers,
  selectedRover,
  onSelectRover,
  weights,
  onWeightsChange,
  onDeployToMap,
}) => {
  const handleWeightChange = (key: keyof PlanWeights, val: number) => {
    onWeightsChange({
      ...weights,
      [key]: val,
    })
  }

  return (
    <div className="lp-fleet-view">
      {/* ── Top Header Banner ── */}
      <header className="lp-fleet-header">
        <div className="lp-fleet-header-content">
          <div className="lp-fleet-badge-row">
            <span className="lp-fleet-phase-badge">Fleet command</span>
            <span className="lp-fleet-site-badge">SITE 11 · LUNAR SOUTH POLE (89.5°S)</span>
          </div>
          <h1 className="lp-fleet-headline">Select Mission Exploration Rover</h1>
          <p className="lp-fleet-subhead">
            Each rover possesses distinct mass, climbing capabilities, battery storage, and scientific payloads.
            Select a vehicle to configure kinematic routing parameters before deploying to the lunar surface map.
          </p>
        </div>
      </header>

      {/* ── 4-Column Rover Fleet Showcase ── */}
      <div className="lp-fleet-grid">
        {rovers.map((rover) => {
          const isSelected = rover.id === selectedRover?.id
          const meta = getRoverMeta(rover.id)

          return (
            <article
              key={rover.id}
              className={`lp-fleet-card ${isSelected ? 'is-selected' : ''}`}
              onClick={() => onSelectRover(rover)}
            >
              {/* Rover Photographic Showcase Frame */}
              <div className="lp-card-photo-box">
                <img
                  src={meta.image}
                  alt={rover.name}
                  className="lp-card-photo"
                  loading="lazy"
                />
                <div className="lp-card-photo-gradient" />
                
                {/* Agency & Status Badges */}
                <div className="lp-card-photo-badges">
                  <span
                    className="lp-card-agency"
                    style={{ borderColor: meta.agencyColor, color: meta.agencyColor }}
                  >
                    {meta.agency}
                  </span>
                  {isSelected && (
                    <span className="lp-card-active-pill">
                      <span className="lp-pulse-dot" />
                      SELECTED VEHICLE
                    </span>
                  )}
                </div>

                <div className="lp-card-photo-footer">
                  <span className="lp-card-highlight">{meta.highlight}</span>
                </div>
              </div>

              {/* Rover Identity & Description */}
              <div className="lp-card-body">
                <div className="lp-card-title-row">
                  <h2 className="lp-card-name">{rover.name}</h2>
                  <span className="lp-card-code">{rover.id.toUpperCase()}</span>
                </div>

                <p className="lp-card-description">{meta.description}</p>

                {/* Key Technical Specifications Table */}
                <div className="lp-card-specs-grid">
                  <div className="lp-card-spec-item">
                    <span className="lp-card-spec-k">Battery capacity</span>
                    <strong className="lp-card-spec-v">{rover.e_cap_wh.toFixed(0)} Wh</strong>
                  </div>
                  <div className="lp-card-spec-item">
                    <span className="lp-card-spec-k">Max speed</span>
                    <strong className="lp-card-spec-v">{rover.v_max_ms.toFixed(2)} m/s</strong>
                  </div>
                  <div className="lp-card-spec-item">
                    <span className="lp-card-spec-k">Max climb slope</span>
                    <strong className="lp-card-spec-v">{rover.slope_max_deg.toFixed(0)}°</strong>
                  </div>
                  <div className="lp-card-spec-item">
                    <span className="lp-card-spec-k">Total mass</span>
                    <strong className="lp-card-spec-v">{rover.mass_kg.toFixed(0)} kg</strong>
                  </div>
                </div>

                {/* Scientific Payload Suite */}
                <div className="lp-card-payload-box">
                  <span className="lp-card-payload-title">Science and sensor suite</span>
                  <p className="lp-card-payload-text">{meta.payload}</p>
                </div>
              </div>

              {/* Card Selection Action Footer */}
              <div className="lp-card-action-bar">
                <button
                  type="button"
                  className={`lp-card-select-btn ${isSelected ? 'is-selected' : ''}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    onSelectRover(rover)
                  }}
                >
                  {isSelected ? '✓ Assigned For Mission' : 'Select Rover'}
                </button>
              </div>
            </article>
          )
        })}
      </div>

      {/* ── Mission Parameters & Deployment Dock ── */}
      <section className="lp-fleet-bottom-dock">
        <div className="lp-dock-weights-col">
          <div className="lp-dock-section-title">
            <span className="lp-meta-label">ROUTE A* OPTIMIZATION WEIGHTS</span>
            <span className="lp-dock-hint">Fine-tune cost heuristics for this rover's transit</span>
          </div>

          <div className="lp-dock-sliders-row">
            {WEIGHT_CONTROLS.map(({ key, label, desc }) => {
              const val = weights[key]
              return (
                <div key={key} className="lp-dock-slider-cell">
                  <div className="lp-dock-slider-head">
                    <span className="lp-dock-slider-label">{label}</span>
                    <strong className="lp-dock-slider-val">{val.toFixed(2)}</strong>
                  </div>
                  <input
                    type="range"
                    className="lp-range-input"
                    min={0}
                    max={2}
                    step={0.05}
                    value={val}
                    onChange={(e) => handleWeightChange(key, parseFloat(e.target.value))}
                    title={desc}
                  />
                </div>
              )
            })}
          </div>
        </div>

        {/* Big Deployment Action Button */}
        <div className="lp-dock-action-col">
          <div className="lp-dock-rover-summary">
            <span className="lp-meta-label">Ready to deploy</span>
            <strong className="lp-dock-rover-name">
              {selectedRover ? selectedRover.name : 'Choose a vehicle above'}
            </strong>
          </div>

          <button
            type="button"
            className="lp-deploy-btn"
            onClick={onDeployToMap}
            disabled={!selectedRover}
          >
            <span>Deploy Rover & Open Surface Map</span>
            <span className="lp-deploy-arrow">→</span>
          </button>
        </div>
      </section>
    </div>
  )
}

export default FleetSelectionView

