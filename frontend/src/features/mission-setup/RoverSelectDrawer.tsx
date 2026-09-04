import React from 'react'
import type { RoverEntry } from '../../api'

interface RoverSelectDrawerProps {
  isOpen: boolean
  onClose: () => void
  rovers: RoverEntry[]
  selectedRoverId: string
  onSelectRover: (rover: RoverEntry) => void
}

const ROVER_DESCRIPTIONS: Record<string, { desc: string; agency: string; highlight: string }> = {
  lpr_1: {
    desc: 'High-endurance lunar exploratory platform with regenerative battery packs and solar arrays.',
    agency: 'ESA / LUNAPATH',
    highlight: 'Balanced general-purpose polar scout',
  },
  luvm_m: {
    desc: 'Medium-weight autonomous micro-rover engineered for steep crater rim descents and nimble maneuvers.',
    agency: 'LUNAPATH EXP',
    highlight: 'Agile crater explorer with high max slope',
  },
  viper: {
    desc: 'Volatiles Investigating Polar Exploration Rover equipped for deep PSR drill operations and sub-surface science.',
    agency: 'NASA',
    highlight: 'Heavy science payload with high battery capacity',
  },
  yutu_2: {
    desc: 'Lightweight solar lunar rover equipped with ground-penetrating radar and panoramic cameras.',
    agency: 'CNSA',
    highlight: 'Ultra-lightweight endurance vehicle',
  },
}

export const RoverSelectDrawer: React.FC<RoverSelectDrawerProps> = ({
  isOpen,
  onClose,
  rovers,
  selectedRoverId,
  onSelectRover,
}) => {
  if (!isOpen) return null

  return (
    <div className="lp-slide-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="lp-slide-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="lp-drawer-header">
          <div>
            <span className="lp-meta-label">FLEET SPECIFICATIONS</span>
            <h2 className="lp-drawer-title">Select Mission Rover</h2>
          </div>
          <button
            type="button"
            className="lp-drawer-close"
            onClick={onClose}
            aria-label="Close fleet catalog"
          >
            ✕
          </button>
        </div>

        <p className="lp-drawer-subtitle">
          Rover mass, speed envelope, maximum climbing slope, and battery capacity directly dictate
          kinematic A* path feasibility, traversability masks, and energy depletion.
        </p>

        <div className="lp-drawer-rover-list">
          {rovers.map((rover) => {
            const isSelected = rover.id === selectedRoverId
            const meta = ROVER_DESCRIPTIONS[rover.id] ?? {
              desc: 'Autonomous lunar surface exploratory rover.',
              agency: 'LUNAR MISSION',
              highlight: 'Standard rover profile',
            }

            return (
              <div
                key={rover.id}
                className={`lp-drawer-rover-card ${isSelected ? 'is-selected' : ''}`}
                onClick={() => {
                  onSelectRover(rover)
                  onClose()
                }}
              >
                <div className="lp-drawer-card-top">
                  <div className="lp-drawer-card-badges">
                    <span className="lp-agency-badge">{meta.agency}</span>
                    <span className="lp-highlight-badge">{meta.highlight}</span>
                  </div>
                  {isSelected && <span className="lp-active-pill">ACTIVE ROVER</span>}
                </div>

                <div className="lp-rover-card-name-row">
                  <h3 className="lp-rover-name">{rover.name}</h3>
                  <span className="lp-rover-id-code">{rover.id.toUpperCase()}</span>
                </div>

                <p className="lp-rover-desc">{meta.desc}</p>

                <div className="lp-rover-specs-table">
                  <div className="lp-spec-cell">
                    <span className="lp-spec-label">BATTERY</span>
                    <strong className="lp-spec-val">{rover.e_cap_wh.toFixed(0)} Wh</strong>
                  </div>
                  <div className="lp-spec-cell">
                    <span className="lp-spec-label">SPEED</span>
                    <strong className="lp-spec-val">{rover.v_max_ms.toFixed(2)} m/s</strong>
                  </div>
                  <div className="lp-spec-cell">
                    <span className="lp-spec-label">MAX SLOPE</span>
                    <strong className="lp-spec-val">{rover.slope_max_deg.toFixed(0)}°</strong>
                  </div>
                  <div className="lp-spec-cell">
                    <span className="lp-spec-label">MASS</span>
                    <strong className="lp-spec-val">{rover.mass_kg.toFixed(0)} kg</strong>
                  </div>
                </div>

                <div className="lp-drawer-card-footer">
                  <span className="lp-default-weights-note">
                    Default weights: Slope {(rover.default_weights.w_slope * 100).toFixed(0)}% · Energy {(rover.default_weights.w_energy * 100).toFixed(0)}% · Shadow {(rover.default_weights.w_shadow * 100).toFixed(0)}% · Thermal {(rover.default_weights.w_thermal * 100).toFixed(0)}%
                  </span>
                  <button
                    type="button"
                    className={`lp-assign-btn ${isSelected ? 'is-assigned' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelectRover(rover)
                      onClose()
                    }}
                  >
                    {isSelected ? '✓ Assigned' : 'Deploy This Rover'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default RoverSelectDrawer
