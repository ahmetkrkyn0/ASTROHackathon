import React, { useState } from 'react'
import type { PlanWeights } from '../../api'
import { useMission, useMissionActions } from '../../mission/MissionContext'
import type { ProfileConstraints } from '../../net/types'
import { useMissionProfiles } from './useMissionProfiles'
import RoverSelectDrawer from './RoverSelectDrawer'

const WEIGHT_CONTROLS: Array<{
  key: keyof PlanWeights
  label: string
  desc: string
}> = [
  { key: 'w_slope', label: 'Slope Safety', desc: 'Avoids steep inclines and cliff edges' },
  { key: 'w_energy', label: 'Energy Use', desc: 'Minimizes battery kWh draw during transit' },
  { key: 'w_shadow', label: 'Shadow Exposure', desc: 'Avoids permanently shadowed cold traps' },
  { key: 'w_thermal', label: 'Thermal Risk', desc: 'Steers clear of extreme cryogenic zones' },
]

/** Display order + formatting for the four constraints a profile carries. */
const CONSTRAINT_CONTROLS: Array<{
  key: keyof ProfileConstraints
  label: string
  format: (v: number) => string
}> = [
  { key: 'max_slope_deg', label: 'Max Slope', format: (v) => `${v.toFixed(0)}°` },
  { key: 'max_shadow_h', label: 'Max Shadow', format: (v) => `${v.toFixed(0)} h` },
  { key: 'max_energy_wh', label: 'Energy Budget', format: (v) => `${v.toFixed(0)} Wh` },
  { key: 'min_soc', label: 'Min SoC', format: (v) => `${(v * 100).toFixed(0)}%` },
]

export const MissionSetupPanel: React.FC = () => {
  const { rover: selectedRover, rovers, weights, start, goal, planResult, clickMode, isSolving } =
    useMission()
  const {
    selectRover: onSelectRover,
    setWeights: onWeightsChange,
    setClickMode: onSetClickMode,
    planRoute: onPlanRoute,
    resetMission: onReset,
    setMissionMode,
  } = useMissionActions()
  const hasRoute = Boolean(planResult)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { profiles, activeId, applyProfile, loading: profilesLoading } = useMissionProfiles()
  const activeProfile = activeId && profiles ? profiles[activeId] : null

  const handleWeightChange = (key: keyof PlanWeights, val: number) => {
    onWeightsChange({
      ...weights,
      [key]: val,
    })
  }

  return (
    <div className="lp-panel-content">
      <RoverSelectDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        rovers={rovers}
        selectedRoverId={selectedRover?.id ?? ''}
        onSelectRover={onSelectRover}
      />

      {/* ── 1. VEHICLE ASSIGNMENT & QUICK SELECTOR TABS ── */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">VEHICLE ASSIGNMENT</span>
          <button
            type="button"
            className="lp-text-action-btn"
            onClick={() => setMissionMode('fleet')}
            title="Open comprehensive full-screen fleet hangar"
          >
            Fleet Hangar ⤢
          </button>
        </div>

        {/* Quick Rover Switcher Tabs */}
        {rovers.length > 0 && (
          <div className="lp-rover-segmented-tabs" role="tablist" aria-label="Select Rover Profile">
            {rovers.map((rover) => {
              const isSelected = rover.id === selectedRover?.id
              return (
                <button
                  key={rover.id}
                  type="button"
                  role="tab"
                  aria-selected={isSelected}
                  className={`lp-rover-tab ${isSelected ? 'is-active' : ''}`}
                  onClick={() => onSelectRover(rover)}
                >
                  {rover.name.split(' ')[0]}
                </button>
              )
            })}
          </div>
        )}

        {/* Selected Rover Specs Card */}
        {selectedRover ? (
          <div className="lp-selected-rover-card">
            <div className="lp-rover-header">
              <div className="lp-rover-avatar-box">
                <span className="lp-rover-avatar-icon">▲</span>
              </div>
              <div className="lp-rover-title-block">
                <h3 className="lp-rover-card-name">{selectedRover.name}</h3>
                <span className="lp-rover-model-code">{selectedRover.id.toUpperCase()}</span>
              </div>
            </div>

            <div className="lp-rover-metric-grid">
              <div className="lp-rover-metric">
                <span className="lp-metric-name">Battery</span>
                <strong className="lp-metric-val">{selectedRover.e_cap_wh.toFixed(0)} Wh</strong>
              </div>
              <div className="lp-rover-metric">
                <span className="lp-metric-name">Speed</span>
                <strong className="lp-metric-val">{selectedRover.v_max_ms.toFixed(2)} m/s</strong>
              </div>
              <div className="lp-rover-metric">
                <span className="lp-metric-name">Max Slope</span>
                <strong className="lp-metric-val">{selectedRover.slope_max_deg.toFixed(0)}°</strong>
              </div>
              <div className="lp-rover-metric">
                <span className="lp-metric-name">Mass</span>
                <strong className="lp-metric-val">{selectedRover.mass_kg.toFixed(0)} kg</strong>
              </div>
            </div>
          </div>
        ) : (
          <div className="lp-empty-rover-box">Loading rover specifications...</div>
        )}
      </section>

      {/* ── 2. MISSION SEQUENCE & TARGET PICKERS ── */}
      <section className="lp-panel-section lp-mission-sequence-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">MISSION SEQUENCE & TARGETS</span>
        </div>

        <div className="lp-sequence-list">
          {/* Step 01: Rover */}
          <div className="lp-sequence-item is-complete">
            <span className="lp-seq-num">01</span>
            <div className="lp-seq-info">
              <span className="lp-seq-title">Rover Profile</span>
              <span className="lp-seq-sub">{selectedRover?.name ?? 'Assigned'}</span>
            </div>
            <span className="lp-seq-status is-ready">{selectedRover?.id.toUpperCase() ?? 'SET'}</span>
          </div>

          {/* Step 02: Start Point Button */}
          <div className={`lp-sequence-item ${start ? 'is-complete' : 'is-active'}`}>
            <span className="lp-seq-num">02</span>
            <div className="lp-seq-info">
              <span className="lp-seq-title">Start Point</span>
              <span className="lp-seq-sub">
                {start ? `Grid: ${start[0]}, ${start[1]}` : 'Click button to place on map'}
              </span>
            </div>
            <button
              type="button"
              className={`lp-seq-action-btn ${clickMode === 'start' ? 'is-picking-start' : ''} ${start ? 'is-set-start' : ''}`}
              onClick={() => onSetClickMode(clickMode === 'start' ? 'idle' : 'start')}
            >
              {start
                ? `START [${start[0]}, ${start[1]}]`
                : clickMode === 'start'
                  ? 'Pick on Map...'
                  : 'Select Start'}
            </button>
          </div>

          {/* Step 03: Goal Target Button */}
          <div className={`lp-sequence-item ${goal ? 'is-complete' : start ? 'is-active' : ''}`}>
            <span className="lp-seq-num">03</span>
            <div className="lp-seq-info">
              <span className="lp-seq-title">Goal Target</span>
              <span className="lp-seq-sub">
                {goal ? `Grid: ${goal[0]}, ${goal[1]}` : 'Click button to place on map'}
              </span>
            </div>
            <button
              type="button"
              className={`lp-seq-action-btn ${clickMode === 'goal' ? 'is-picking-goal' : ''} ${goal ? 'is-set-goal' : ''}`}
              onClick={() => onSetClickMode(clickMode === 'goal' ? 'idle' : 'goal')}
            >
              {goal
                ? `GOAL [${goal[0]}, ${goal[1]}]`
                : clickMode === 'goal'
                  ? 'Pick on Map...'
                  : 'Select Goal'}
            </button>
          </div>

          {/* Step 04: Path Solution Status */}
          <div className={`lp-sequence-item ${hasRoute ? 'is-complete' : ''}`}>
            <span className="lp-seq-num">04</span>
            <div className="lp-seq-info">
              <span className="lp-seq-title">Path Solution</span>
              <span className="lp-seq-sub">
                {hasRoute ? 'Ready for engineering review' : 'Kinematic A* solver'}
              </span>
            </div>
            <span className={`lp-seq-status ${hasRoute ? 'is-ready' : ''}`}>
              {hasRoute ? 'LOCKED' : 'WAITING'}
            </span>
          </div>
        </div>

        {/* Action Controls directly in the Left Dashboard */}
        <div className="lp-panel-action-row">
          <button
            type="button"
            className="lp-panel-clear-btn"
            onClick={onReset}
            disabled={isSolving || (!start && !goal)}
            title="Clear start and goal points"
          >
            Clear
          </button>
          <button
            type="button"
            className="lp-panel-plan-btn"
            onClick={onPlanRoute}
            disabled={!start || !goal || isSolving}
            title={!start || !goal ? 'Select both Start and Goal on the terrain map' : 'Generate optimal rover route'}
          >
            {isSolving ? 'Computing Route...' : 'Generate Route'}
          </button>
        </div>
      </section>

      {/* ── 3. ROUTE PRIORITIES SLIDERS ── */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">ROUTE PRIORITIES</span>
        </div>

        {/* Mission profile presets (GET /api/profiles). Selecting one writes
            its four weights into the sliders below; its constraints ride along
            as read-only context. */}
        {profiles && Object.keys(profiles).length > 0 && (
          <div className="lp-profile-block">
            <div className="lp-profile-head">
              <span className="lp-profile-caption">MISSION PROFILE</span>
              <span className={`lp-profile-active-tag ${activeProfile ? '' : 'is-custom'}`}>
                {activeProfile ? activeProfile.name : 'Custom'}
              </span>
            </div>

            <div className="lp-profile-chips" role="group" aria-label="Mission profile presets">
              {Object.entries(profiles).map(([id, profile]) => {
                const isActive = id === activeId
                return (
                  <button
                    key={id}
                    type="button"
                    className={`lp-profile-chip ${isActive ? 'is-active' : ''}`}
                    style={{ '--profile-color': profile.color } as React.CSSProperties}
                    onClick={() => applyProfile(id)}
                    title={profile.description}
                    aria-pressed={isActive}
                  >
                    <span className="lp-profile-dot" />
                    {profile.name}
                  </button>
                )
              })}
            </div>

            {activeProfile && (
              <div className="lp-profile-constraints">
                {CONSTRAINT_CONTROLS.map(({ key, label, format }) => {
                  const enforced = activeProfile.constraint_handling[key] === 'enforced_in_search'
                  return (
                    <div key={key} className="lp-profile-constraint">
                      <span className="lp-constraint-label">{label}</span>
                      <strong className="lp-constraint-value">
                        {format(activeProfile.constraints[key])}
                      </strong>
                      <span
                        className={`lp-constraint-badge ${enforced ? 'is-enforced' : 'is-verified'}`}
                        title={
                          enforced
                            ? 'Enforced in search: the A* solver refuses cells that violate this limit.'
                            : 'Verified after simulation: checked against the simulated route; a plan can exceed it.'
                        }
                      >
                        {enforced ? 'IN SEARCH' : 'POST-SIM'}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
        {profilesLoading && !profiles && (
          <p className="lp-section-explainer">Loading mission profiles…</p>
        )}

        <p className="lp-section-explainer">
          Higher priority weights force the A* solver to penalize and circumvent that hazard more aggressively.
        </p>

        <div className="lp-priority-sliders">
          {WEIGHT_CONTROLS.map(({ key, label, desc }) => {
            const val = weights[key]
            return (
              <div key={key} className="lp-slider-block">
                <div className="lp-slider-head">
                  <span className="lp-slider-label">{label}</span>
                  <span className="lp-slider-number">{val.toFixed(3)}</span>
                </div>
                <input
                  type="range"
                  className="lp-range-input"
                  min={0}
                  max={2}
                  step={0.01}
                  value={val}
                  onChange={(e) => handleWeightChange(key, parseFloat(e.target.value))}
                  title={desc}
                />
              </div>
            )
          })}
        </div>
      </section>
    </div>
  )
}

export default MissionSetupPanel
