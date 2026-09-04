import React from 'react'

interface RouteSolvingOverlayProps {
  isSolving: boolean
  start: [number, number] | null
  goal: [number, number] | null
  roverName?: string
}

export const RouteSolvingOverlay: React.FC<RouteSolvingOverlayProps> = ({
  isSolving,
  start,
  goal,
  roverName = 'Rover',
}) => {
  if (!isSolving) return null

  return (
    <div className="lp-solving-overlay">
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

