import React, { useCallback, useEffect, useState } from 'react'
import type { RoverEntry } from '../../api'
import RoutePriorities from '../../features/mission-setup/RoutePriorities'
import { Icon, type IconName } from './SpecIcons'
import { getRoverMeta } from './roverMeta'

interface FleetSelectionViewProps {
  rovers: RoverEntry[]
  selectedRover: RoverEntry | null
  onSelectRover: (rover: RoverEntry) => void
  onDeployToMap: () => void
}

/** The four numbers every rover card prints, each with the glyph that names it. */
const SPEC_ROWS: Array<{
  icon: IconName
  label: string
  value: (r: RoverEntry) => string
}> = [
  { icon: 'battery', label: 'Battery capacity', value: (r) => `${r.e_cap_wh.toFixed(0)} Wh` },
  { icon: 'speed', label: 'Max speed', value: (r) => `${r.v_max_ms.toFixed(2)} m/s` },
  { icon: 'climb', label: 'Max climb slope', value: (r) => `${r.slope_max_deg.toFixed(0)}\u00b0` },
  { icon: 'mass', label: 'Total mass', value: (r) => `${r.mass_kg.toFixed(0)} kg` },
]


export const FleetSelectionView: React.FC<FleetSelectionViewProps> = ({
  rovers,
  selectedRover,
  onSelectRover,
  onDeployToMap,
}) => {
  /* Which rover the carousel is showing. Deliberately NOT derived from
     `selectedRover`: browsing and choosing are separate acts here. If moving the
     carousel also selected, the scroll-to-dock below would fire on every arrow
     press and drag the screen to the weights while you were still reading
     rovers. You look with the arrows; you commit with the button. */
  const [viewIndex, setViewIndex] = useState(0)

  /* The catalogue loads asynchronously and "Change vehicle" can come back here
     with a different list, so an index that was valid once need not stay valid. */
  useEffect(() => {
    if (viewIndex > rovers.length - 1) setViewIndex(0)
  }, [rovers.length, viewIndex])

  const step = useCallback(
    (delta: number) => {
      if (rovers.length === 0) return
      setViewIndex((i) => (i + delta + rovers.length) % rovers.length)
    },
    [rovers.length],
  )

  /* Arrow keys move the carousel, as they would in any gallery. Ignored while
     the caret is in a field so typing a weight into the dock's number boxes
     does not also flip the rover. */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = document.activeElement
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return
      if (e.key === 'ArrowLeft') step(-1)
      else if (e.key === 'ArrowRight') step(1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [step])

  const rover = rovers[viewIndex]
  if (!rover) return null

  const meta = getRoverMeta(rover.id)
  const selectedMeta = selectedRover ? getRoverMeta(selectedRover.id) : null
  const isSelected = rover.id === selectedRover?.id

  return (
    <div className="lp-fleet-view">
      {/* ── Top Header Banner ── */}
      <header className="lp-fleet-header">
        <div className="lp-fleet-header-content">
          <h1 className="lp-fleet-headline">Select Mission Exploration Rover</h1>
          <p className="lp-fleet-subhead">
            Each rover possesses distinct mass, climbing capabilities, battery storage, and scientific payloads.
            Select a vehicle to configure kinematic routing parameters before deploying to the lunar surface map.
          </p>
        </div>
      </header>

      {/* ── One rover, full size, with the fleet reachable either side ── */}
      <div className="lp-fleet-carousel">
        <button
          type="button"
          className="lp-carousel-arrow"
          onClick={() => step(-1)}
          disabled={rovers.length < 2}
          aria-label="Previous rover"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M15 4 7 12l8 8" fill="none" stroke="currentColor" strokeWidth="1.6" />
          </svg>
        </button>

        <article className={`lp-fleet-card ${isSelected ? 'is-selected' : ''}`}>
          {/* Rover Photographic Showcase Frame */}
          <div className="lp-card-photo-box">
            <img src={meta.image} alt={rover.name} className="lp-card-photo" />
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
              {SPEC_ROWS.map(({ icon, label, value }) => (
                <div key={label} className="lp-card-spec-item">
                  <span className="lp-card-spec-k">
                    <Icon name={icon} />
                    {label}
                  </span>
                  <strong className="lp-card-spec-v">{value(rover)}</strong>
                </div>
              ))}
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
              onClick={() => onSelectRover(rover)}
            >
              {isSelected ? '✓ Assigned For Mission' : 'Select Rover'}
            </button>
          </div>
        </article>

        <button
          type="button"
          className="lp-carousel-arrow"
          onClick={() => step(1)}
          disabled={rovers.length < 2}
          aria-label="Next rover"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="m9 4 8 8-8 8" fill="none" stroke="currentColor" strokeWidth="1.6" />
          </svg>
        </button>
      </div>

      {/* The rest of the fleet. Showing one rover at a time costs you the sense
          that there are four; this is what pays it back, and it doubles as the
          way to jump straight to one rather than stepping past the others. */}
      <div className="lp-fleet-thumbs" aria-label="Rover catalogue">
        {rovers.map((r, i) => (
          <button
            key={r.id}
            type="button"
            className={`lp-fleet-thumb ${i === viewIndex ? 'is-current' : ''} ${
              r.id === selectedRover?.id ? 'is-assigned' : ''
            }`}
            onClick={() => setViewIndex(i)}
            aria-current={i === viewIndex ? 'true' : undefined}
            aria-label={r.id === selectedRover?.id ? `${r.name} (selected for mission)` : r.name}
          >
            <img src={getRoverMeta(r.id).image} alt="" loading="lazy" />
            <span className="lp-fleet-thumb-name">{r.name}</span>
          </button>
        ))}
      </div>

      {/* ── Mission Parameters & Deployment Dock ──
          The rover is only half the decision; what the solver should optimise
          for is the other half, and both are made here before the map opens.
          RoutePriorities carries the presets, their constraints and the four
          weights -- it reads the mission context directly, so nothing about
          them passes through this component. */}
      <section className="lp-fleet-bottom-dock">
        <header className="lp-dock-header">
          <div className="lp-dock-header-text">
            <h2 className="lp-dock-title">
              <Icon name="tune" />
              Mission Configuration
            </h2>
            <p className="lp-dock-subtitle">
              Set your exploration profile and route priorities for the selected rover.
            </p>
          </div>
          <span className="lp-dock-tagline">Real science. A brighter tomorrow.</span>
        </header>

        <div className="lp-dock-body">
          <div className="lp-dock-priorities-col">
            <RoutePriorities />
          </div>

          {/* What you are about to send, and where it goes. The column used to
              be a label, a name and a button; a rover is picked several screens
              of scrolling above this, so the deploy button is worth naming the
              vehicle, its class and the two numbers that decide a traverse. */}
          <div className="lp-dock-action-col">
            <div className="lp-dock-ready">
              <span className={`lp-dock-ready-state ${selectedRover ? 'is-ready' : ''}`}>
                <span className="lp-pulse-dot" />
                {selectedRover ? 'Mission ready' : 'Awaiting rover'}
              </span>

              <span className="lp-meta-label">Selected rover</span>

              {selectedRover && selectedMeta ? (
                <>
                  <div className="lp-dock-rover-id">
                    <span
                      className="lp-card-agency"
                      style={{ borderColor: selectedMeta.agencyColor, color: selectedMeta.agencyColor }}
                    >
                      {selectedMeta.agency}
                    </span>
                    <strong className="lp-dock-rover-name">{selectedRover.name}</strong>
                  </div>
                  <span className="lp-dock-rover-facts">
                    {selectedMeta.roverClass} &middot; {selectedRover.mass_kg.toFixed(0)} kg &middot;{' '}
                    {selectedRover.e_cap_wh.toFixed(0)} Wh
                  </span>
                </>
              ) : (
                <strong className="lp-dock-rover-name is-empty">Choose a vehicle above</strong>
              )}
            </div>

            <button
              type="button"
              className="lp-deploy-btn"
              onClick={onDeployToMap}
              disabled={!selectedRover}
            >
              <span>Deploy Rover &amp; Open Surface Map</span>
              <span className="lp-deploy-arrow">&rarr;</span>
            </button>

            <p className="lp-dock-deploy-note">
              <Icon name="map" />
              Configure the rover and generate an optimal route on the lunar surface map.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}

export default FleetSelectionView
