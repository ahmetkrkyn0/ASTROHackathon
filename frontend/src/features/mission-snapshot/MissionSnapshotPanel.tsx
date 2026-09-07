import React from 'react'
import { useMission, useMissionActions } from '../../mission/MissionContext'

export const MissionSnapshotPanel: React.FC = () => {
  const { rover, start, goal, weights } = useMission()
  const { setMissionMode } = useMissionActions()
  // Edit & Replan: keeps the endpoints and goes back to the planning stage.
  const onEditReplan = () => setMissionMode('plan')

  return (
    <div className="lp-panel-content">
      {/* Top Banner & Replan Button */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Mission snapshot</span>
          <span className="lp-status-pill is-locked">LOCKED</span>
        </div>
        <p className="lp-panel-desc-text">
          Active mission telemetry and route trajectory are locked for analysis.
        </p>

        <button
          type="button"
          className="lp-replan-btn"
          onClick={onEditReplan}
        >
          <span className="lp-btn-icon">↺</span>
          Edit & Replan
        </button>
      </section>

      {/* Rover Vehicle Snapshot */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Active rover</span>
        </div>
        {rover ? (
          <div className="lp-snapshot-card">
            <div className="lp-snapshot-head">
              <strong>{rover.name}</strong>
              <span className="lp-code-tag">{rover.id.toUpperCase()}</span>
            </div>
            <div className="lp-snapshot-specs">
              <span>{rover.e_cap_wh.toFixed(0)} Wh Cap</span>
              <span>{rover.v_max_ms.toFixed(2)} m/s Vmax</span>
              <span>Max {rover.slope_max_deg.toFixed(0)}°</span>
            </div>
          </div>
        ) : null}
      </section>

      {/* Target Points Snapshot */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Trajectory waypoints</span>
        </div>
        <div className="lp-snapshot-points">
          <div className="lp-point-pill lp-point-start">
            <span className="lp-point-dot lp-dot-mint" />
            <div className="lp-point-info">
              <span className="lp-point-type">START</span>
              <strong className="lp-point-coord">
                {start ? `[${start[0]}, ${start[1]}]` : '--'}
              </strong>
            </div>
          </div>

          <div className="lp-point-pill lp-point-goal">
            <span className="lp-point-dot lp-dot-coral" />
            <div className="lp-point-info">
              <span className="lp-point-type">GOAL</span>
              <strong className="lp-point-coord">
                {goal ? `[${goal[0]}, ${goal[1]}]` : '--'}
              </strong>
            </div>
          </div>
        </div>
      </section>

      {/* Read-Only Priority Weights Snapshot */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">SOLVER WEIGHTS (READ-ONLY)</span>
        </div>
        <div className="lp-readonly-weights">
          <div className="lp-readonly-row">
            <span className="lp-readonly-name">Slope Safety</span>
            <span className="lp-readonly-val">{weights.w_slope.toFixed(3)}</span>
          </div>
          <div className="lp-readonly-row">
            <span className="lp-readonly-name">Energy Use</span>
            <span className="lp-readonly-val">{weights.w_energy.toFixed(3)}</span>
          </div>
          <div className="lp-readonly-row">
            <span className="lp-readonly-name">Shadow Exposure</span>
            <span className="lp-readonly-val">{weights.w_shadow.toFixed(3)}</span>
          </div>
          <div className="lp-readonly-row">
            <span className="lp-readonly-name">Thermal Risk</span>
            <span className="lp-readonly-val">{weights.w_thermal.toFixed(3)}</span>
          </div>
        </div>
        <p className="lp-section-explainer">
          To modify solver weights or select new endpoints, use <strong>Edit & Replan</strong>.
        </p>
      </section>
    </div>
  )
}

export default MissionSnapshotPanel

