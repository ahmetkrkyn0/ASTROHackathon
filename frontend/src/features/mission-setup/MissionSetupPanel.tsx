import React, { useEffect, useRef } from 'react'
import type { PlanWeights, RoverEntry } from '../../api'
import { Icon, type IconName } from '../../components/Fleet/SpecIcons'
import { getRoverMeta } from '../../components/Fleet/roverMeta'
import { useMission, useMissionActions } from '../../mission/MissionContext'

/**
 * The four weights, in the order the hangar sets them and this panel reports
 * them. Labels only: the controls live in RoutePriorities now.
 */
const WEIGHT_READOUT: Array<{ key: keyof PlanWeights; label: string }> = [
  { key: 'w_slope', label: 'Slope Safety' },
  { key: 'w_energy', label: 'Energy Use' },
  { key: 'w_shadow', label: 'Shadow Exposure' },
  { key: 'w_thermal', label: 'Thermal Risk' },
]

/** The four numbers the cockpit reports about the assigned vehicle. */
const ROVER_METRICS: Array<{
  icon: IconName
  label: string
  value: (r: RoverEntry) => string
}> = [
  { icon: 'battery', label: 'Battery', value: (r) => `${r.e_cap_wh.toFixed(0)} Wh` },
  { icon: 'speed', label: 'Speed', value: (r) => `${r.v_max_ms.toFixed(2)} m/s` },
  { icon: 'climb', label: 'Max slope', value: (r) => `${r.slope_max_deg.toFixed(0)}\u00b0` },
  { icon: 'mass', label: 'Mass', value: (r) => `${r.mass_kg.toFixed(0)} kg` },
]

export const MissionSetupPanel: React.FC = () => {
  const { rover: selectedRover, weights, start, goal, planResult, clickMode, isSolving } =
    useMission()
  const {
    setClickMode: onSetClickMode,
    planRoute: onPlanRoute,
    resetMission: onReset,
    undoPlacement: onUndoPlacement,
    openFleetSelect: onOpenFleetSelect,
  } = useMissionActions()
  const hasRoute = Boolean(planResult)

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
      {/* ── 1. THE TWO PICKERS, FIRST ──
          These are the only controls in the rail that require the map, and
          placing a point is the one thing the operator is here to do before
          anything else on this screen means much. They used to sit below the
          rover card and the four-step sequence list -- roughly 380px down,
          under everything that only reports state -- so the panel opened on
          a readout and buried its own call to action. The sequence list below
          still reports what they set. */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Mission targets</span>
        </div>

        <div className="lp-pick-actions">
          <button
            type="button"
            className={`lp-pick-btn ${clickMode === 'start' ? 'is-picking' : ''} ${start ? 'is-set-start' : ''}`}
            onClick={() => onSetClickMode(clickMode === 'start' ? 'idle' : 'start')}
          >
            <Icon name="pin" />
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
            <Icon name="flag" />
            {goal
              ? `GOAL ${goal[0]}, ${goal[1]}`
              : clickMode === 'goal'
                ? 'Pick on map…'
                : 'Select Goal'}
          </button>
        </div>
      </section>

      {/* ── 2. MISSION SEQUENCE & ACTIONS ── */}
      <section className="lp-panel-section lp-mission-sequence-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Mission sequence</span>
        </div>

        <div className="lp-sequence-list">
          {/* Step 01: Rover */}
          <div className="lp-sequence-item is-complete">
            <span className="lp-seq-num">
              <Icon name="rover" />
            </span>
            <span className="lp-seq-title">Rover</span>
            <span className="lp-seq-status is-ready">
              {selectedRover?.id.toUpperCase() ?? 'SET'}
            </span>
          </div>

          {/* Step 02: Start Point */}
          <div className={`lp-sequence-item ${start ? 'is-complete' : 'is-active'}`}>
            <span className="lp-seq-num">
              <Icon name="pin" />
            </span>
            <span className="lp-seq-title">Start</span>
            <span className={`lp-seq-status ${start ? 'is-ready' : ''}`}>
              {start ? `${start[0]}, ${start[1]}` : clickMode === 'start' ? 'PICKING' : 'SELECT'}
            </span>
          </div>

          {/* Step 03: Goal Target */}
          <div className={`lp-sequence-item ${goal ? 'is-complete' : start ? 'is-active' : ''}`}>
            <span className="lp-seq-num">
              <Icon name="flag" />
            </span>
            <span className="lp-seq-title">Goal</span>
            <span className={`lp-seq-status ${goal ? 'is-ready' : ''}`}>
              {goal ? `${goal[0]}, ${goal[1]}` : clickMode === 'goal' ? 'PICKING' : 'WAITING'}
            </span>
          </div>

          {/* Step 04: Path Solution Status */}
          <div className={`lp-sequence-item ${hasRoute ? 'is-complete' : ''}`}>
            <span className="lp-seq-num">
              <Icon name="route" />
            </span>
            <span className="lp-seq-title">Route</span>
            <span className={`lp-seq-status ${hasRoute ? 'is-ready' : ''}`}>
              {hasRoute ? 'LOCKED' : 'NOT GENERATED'}
            </span>
          </div>
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
            <Icon name="undo" />
            Undo
          </button>
          <button
            type="button"
            className="lp-panel-clear-btn"
            onClick={onReset}
            disabled={isSolving || (!start && !goal)}
            title="Clear start and goal points"
          >
            <Icon name="clear" />
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
            <Icon name={isSolving ? 'restart' : routeIsStale ? 'restart' : 'route'} />
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

      {/* ── 3. THE ASSIGNED VEHICLE ──
          Mostly a readout: the rover is chosen in the hangar. It opened the
          panel for a long time, which put four specs the operator had just
          finished reading above the two buttons they came here to press.
          Step 01 of the sequence above already names the rover; this is the
          detail behind that line, and detail belongs under the summary.

          The way back to the hangar lives here, under the card, rather than
          as an arrow in the top bar. An arrow in the corner has to be
          guessed at -- it says a direction, not a destination -- and it sat
          three sections away from the rover it would change. Here the label
          says where it goes, next to the thing that prompts the thought. */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Assigned vehicle</span>
        </div>

        {/* Photograph left, everything read about the vehicle right. The rail
            is wide enough for both now, and the picture is the same one the
            hangar showed -- arriving in the cockpit to a 64px thumbnail of it
            was the smallest this could usefully be. */}
        {selectedRover ? (
          <div className="lp-selected-rover-card">
            <img
              className="lp-rover-photo"
              src={getRoverMeta(selectedRover.id).image}
              alt=""
              loading="lazy"
            />

            <div className="lp-rover-info">
              <div className="lp-rover-title-block">
                <h3 className="lp-rover-card-name">{selectedRover.name}</h3>
                <span className="lp-rover-model-code">{selectedRover.id.toUpperCase()}</span>
                <span className="lp-rover-class">{getRoverMeta(selectedRover.id).roverClass}</span>
              </div>

              <div className="lp-rover-metric-grid">
                {ROVER_METRICS.map(({ icon, label, value }) => (
                  <div key={label} className="lp-rover-metric">
                    <span className="lp-metric-name">
                      <Icon name={icon} />
                      {label}
                    </span>
                    <strong className="lp-metric-val">{value(selectedRover)}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="lp-empty-rover-box">Loading rover specifications...</div>
        )}
      
        {/* Enabled even while solving: leaving for the hangar is how you
            abandon a solve you no longer want, and the mission state that
            matters -- rover, weights, start, goal -- survives the trip. */}
        <button
          type="button"
          className="lp-change-vehicle-btn"
          onClick={onOpenFleetSelect}
          title="Return to the fleet hangar to pick a different rover or change route priorities"
        >
          Change vehicle
        </button>
      </section>

      {/* ── 4. ROUTE PRIORITIES, AS SET IN THE HANGAR ── */}
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Route priorities</span>
        </div>

        {/* Read-only, and that is the point: /api/plan reads these at solve
            time, so a slider here would have been editing the description of
            a route already drawn. They are chosen in the hangar, before there
            is a map to argue with. Same markup as the ANALYZE snapshot, which
            has always reported them this way. */}
        <div className="lp-readonly-weights">
          {WEIGHT_READOUT.map(({ key, label }) => (
            <div key={key} className="lp-readonly-row">
              <span className="lp-readonly-name">{label}</span>
              <span className="lp-readonly-val">{weights[key].toFixed(3)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default MissionSetupPanel
