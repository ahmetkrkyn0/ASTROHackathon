import React from 'react'
import { useMission } from '../../mission/MissionContext'

export const RouteSolvingOverlay: React.FC = () => {
  const { isSolving, start, goal, rover } = useMission()
  const roverName = rover?.name ?? 'Rover'

  if (!isSolving) return null

  return (
    <div className="lp-solving-overlay">
      {/* The overlay was a purely visual account of a computation that runs
          for seconds: a screen-reader user pressed Generate Route and heard
          nothing until the result landed. One sentence, not the whole card --
          announcing the kicker, the title, the detail and three tags would be
          three seconds of speech for one fact. */}
      <p className="lp-visually-hidden" role="status" aria-live="polite">
        Computing route for {roverName}. This may take a few seconds.
      </p>

      {/* Scanning laser beam effect */}
      <div className="lp-scan-sweep" />

      {/* Floating status badge */}
      <div className="lp-solving-card">
        <div className="lp-solving-header">
          <span className="lp-radar-spinner" />
          <div className="lp-solving-title-group">
            <span className="lp-solving-kicker">A* PATHFINDER · KINEMATIC SOLVER</span>
            <h3 className="lp-solving-title">COMPUTING ROUTE SOLUTION</h3>
          </div>
        </div>
        <p className="lp-solving-detail">
          Evaluating terrain slope, thermal constraints, shadow exposure, and energy consumption for{' '}
          <strong>{roverName}</strong>.
        </p>
        <div className="lp-solving-meta">
          {start && (
            <span className="lp-solving-tag">
              START: [{start[0]}, {start[1]}]
            </span>
          )}
          {goal && (
            <span className="lp-solving-tag">
              GOAL: [{goal[0]}, {goal[1]}]
            </span>
          )}
          <span className="lp-solving-tag lp-solving-tag--active">OPTIMIZING PATH</span>
        </div>
      </div>
    </div>
  )
}

export default RouteSolvingOverlay

