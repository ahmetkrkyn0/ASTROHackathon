import React, { useEffect, useRef } from 'react'
import type { PlanWeights } from '../../api'
import { useMission, useMissionActions } from '../../mission/MissionContext'
import type { ProfileConstraints } from '../../net/types'
import { useMissionProfiles } from './useMissionProfiles'

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
  const { rover: selectedRover, weights, start, goal, planResult, clickMode, isSolving } =
    useMission()
  const {
    setWeights: onWeightsChange,
    setClickMode: onSetClickMode,
    planRoute: onPlanRoute,
    resetMission: onReset,
    undoPlacement: onUndoPlacement,
    openFleetSelect: onOpenFleetSelect,
  } = useMissionActions()
  const hasRoute = Boolean(planResult)
  const { profiles, activeId, applyProfile, loading: profilesLoading } = useMissionProfiles()
  const activeProfile = activeId && profiles ? profiles[activeId] : null

  const handleWeightChange = (key: keyof PlanWeights, val: number) => {
    onWeightsChange({
      ...weights,
      [key]: val,
    })
  }

  /**
   * The weights the route on screen was actually solved with.
   *
   * planRoute reads the current weights, so the moment a new planResult
   * arrives those weights are by definition the ones that produced it.
   * Snapshotting them here is what lets the panel tell the operator that the
   * sliders and the drawn route no longer agree -- before this, moving a
   * slider changed nothing visible and nothing said so, so the effect of the
   * change could not be synthesised from the screen.
   */
  const plannedWeightsRef = useRef<PlanWeights | null>(null)
  useEffect(() => {
    if (planResult) {
      plannedWeightsRef.current = weights
    } else {
      plannedWeightsRef.current = null
    }
    // Deliberately keyed on the response identity alone: adding `weights`
    // would re-snapshot on every slider move and the comparison below could
    // never be true.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planResult])

  const routeIsStale =
    hasRoute &&
    plannedWeightsRef.current !== null &&
    (Object.keys(weights) as Array<keyof PlanWeights>).some(
      (key) => weights[key] !== plannedWeightsRef.current?.[key],
    )

  // F3: the reason the plan button is unavailable, as text rather than as a
  // `title`. A disabled button is not focusable and its tooltip is not
  // announced, so the hint reached only the user who could already see the
  // map and hover it.
  const planBlockedReason = !start
    ? 'Select a Start point on the terrain first.'
    : !goal
      ? 'Select a Goal point on the terrain to enable routing.'
      : null

  return (
    <div className="lp-panel-content">
      {/* ── 1. VEHICLE ASSIGNMENT & QUICK SELECTOR TABS ── */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Mission setup</span>
          <button
            type="button"
            className="lp-text-action-btn"
            onClick={onOpenFleetSelect}
            title="Return to the fleet hangar and pick a different rover"
          >
            Change Rover
          </button>
        </div>

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
          <span className="lp-meta-label">Mission sequence</span>
        </div>

        <div className="lp-sequence-list">
          {/* Step 01: Rover */}
          <div className="lp-sequence-item is-complete">
            <span className="lp-seq-num">01</span>
            <span className="lp-seq-title">Rover</span>
            <span className="lp-seq-status is-ready">
              {selectedRover?.id.toUpperCase() ?? 'SET'}
            </span>
          </div>

          {/* Step 02: Start Point */}
          <div className={`lp-sequence-item ${start ? 'is-complete' : 'is-active'}`}>
            <span className="lp-seq-num">02</span>
            <span className="lp-seq-title">Start</span>
            <span className={`lp-seq-status ${start ? 'is-ready' : ''}`}>
              {start ? `${start[0]}, ${start[1]}` : clickMode === 'start' ? 'PICKING' : 'SELECT'}
            </span>
          </div>

          {/* Step 03: Goal Target */}
          <div className={`lp-sequence-item ${goal ? 'is-complete' : start ? 'is-active' : ''}`}>
            <span className="lp-seq-num">03</span>
            <span className="lp-seq-title">Goal</span>
            <span className={`lp-seq-status ${goal ? 'is-ready' : ''}`}>
              {goal ? `${goal[0]}, ${goal[1]}` : clickMode === 'goal' ? 'PICKING' : 'WAITING'}
            </span>
          </div>

          {/* Step 04: Path Solution Status */}
          <div className={`lp-sequence-item ${hasRoute ? 'is-complete' : ''}`}>
            <span className="lp-seq-num">04</span>
            <span className="lp-seq-title">Route</span>
            <span className={`lp-seq-status ${hasRoute ? 'is-ready' : ''}`}>
              {hasRoute ? 'LOCKED' : 'NOT GENERATED'}
            </span>
          </div>
        </div>

        {/* The pickers, full width under the list they report on. Cramming a
            button into each row squeezed the sub-line to one word per line at
            the 264px the design actually asks for. */}
        <div className="lp-pick-actions">
          <button
            type="button"
            className={`lp-pick-btn ${clickMode === 'start' ? 'is-picking' : ''} ${start ? 'is-set-start' : ''}`}
            onClick={() => onSetClickMode(clickMode === 'start' ? 'idle' : 'start')}
          >
            {start
              ? `START ${start[0]}, ${start[1]}`
              : clickMode === 'start'
                ? 'Pick on map…'
                : 'Select Start'}
          </button>
          <button
            type="button"
            className={`lp-pick-btn ${clickMode === 'goal' ? 'is-picking' : ''} ${goal ? 'is-set-goal' : ''}`}
            onClick={() => onSetClickMode(clickMode === 'goal' ? 'idle' : 'goal')}
            disabled={!start}
          >
            {goal
              ? `GOAL ${goal[0]}, ${goal[1]}`
              : clickMode === 'goal'
                ? 'Pick on map…'
                : 'Select Goal'}
          </button>
        </div>

        {/* Action Controls directly in the Left Dashboard */}
        <div className="lp-panel-action-row">
          {/* Undo sits beside Clear rather than replacing it: they answer two
              different questions. Ctrl+Z does the same thing, but a shortcut
              nobody can see is not a recovery path for the operator who has
              just made their first mistake. */}
          <button
            type="button"
            className="lp-panel-clear-btn"
            onClick={onUndoPlacement}
            disabled={isSolving || (!start && !goal)}
            title="Undo the last point placed (Ctrl+Z)"
          >
            Undo
          </button>
          <button
            type="button"
            className="lp-panel-clear-btn"
            onClick={onReset}
            disabled={isSolving || (!start && !goal)}
            title="Clear start and goal points"
          >
            Clear
          </button>
        </div>

        <div className="lp-panel-plan-row">
          <button
            type="button"
            className="lp-panel-plan-btn"
            onClick={onPlanRoute}
            disabled={!start || !goal || isSolving}
          >
            {isSolving
              ? 'Computing Route...'
              : routeIsStale
                ? 'Re-plan with new weights'
                : 'Generate Route'}
          </button>
        </div>

        {planBlockedReason && <p className="lp-panel-hint">{planBlockedReason}</p>}

        {routeIsStale && (
          <p className="lp-panel-hint is-stale" role="status">
            Route priorities changed. The route on the map still reflects the
            previous weights.
          </p>
        )}
      </section>

      {/* ── 3. ROUTE PRIORITIES SLIDERS ── */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Route priorities</span>
        </div>

        {/* Mission profile presets (GET /api/profiles). Selecting one writes
            its four weights into the sliders below; its constraints ride along
            as read-only context. */}
        {profiles && Object.keys(profiles).length > 0 && (
          <div className="lp-profile-block">
            <div className="lp-profile-head">
              <span className="lp-profile-caption">Mission profile</span>
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

            {/* `title` alone reached neither touch nor keyboard, so the one
                sentence that distinguishes four profiles was invisible to a
                user who had not hovered each chip in turn. The backend
                already sends it. */}
            {activeProfile?.description && (
              <p className="lp-profile-desc">{activeProfile.description}</p>
            )}

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
