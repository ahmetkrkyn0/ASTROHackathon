import React from 'react'
import { useMission, useMissionActions } from '../../mission/MissionContext'
import { useMissionRuntime } from '../../mission/MissionRuntimeContext'
import './scene-transport.css'

/**
 * The transport controls, small enough to live inside the 3-D scene.
 *
 * The full PlaybackBar sits in the status strip under the map -- outside
 * .map-stage, which is the element that goes fullscreen. So in 3-D fullscreen
 * the drive could be watched but not driven: no play, no pause, no time
 * scale, no way back to a waypoint. This is the same controls against the
 * same mission state, laid out for a corner of the viewport instead of a
 * 44px strip.
 *
 * Deliberately NOT the whole bar. Fullscreen is for watching the terrain, and
 * the six readouts the strip carries (covered, battery, slope, mission clock)
 * are numbers to study, not controls to reach for mid-drive -- they stay in
 * the strip, one Esc away. What is here is what you cannot do without: start
 * and stop, how fast, and where in the route you are.
 */

/** Matches PlaybackBar's own list -- one meaning of "1x" in the app. */
const TIME_SCALES = [1, 10, 60, 300] as const

export const SceneTransport: React.FC = () => {
  const { planResult } = useMission()
  const {
    routePlaybackStep: currentStep,
    playbackHours,
    playbackTotalHours,
    isPlaying,
    timeScale,
  } = useMissionRuntime()
  const { setPlaybackStep: onStepChange, setPlaying, setTimeScale } = useMissionActions()

  const waypoints = planResult?.waypoints ?? []
  const totalSteps = waypoints.length
  const activeStep = currentStep !== null ? Math.min(currentStep, totalSteps - 1) : 0

  const togglePlay = () => {
    // Replaying from the end restarts rather than sitting at the finish --
    // the same rule the status-strip transport follows.
    if (!isPlaying && playbackHours >= playbackTotalHours - 1e-6) onStepChange(0)
    setPlaying(!isPlaying)
  }

  // No route, nothing to transport. Same guard as PlaybackBar, so the two
  // appear and disappear together rather than one leaving an empty frame.
  if (totalSteps === 0) return null

  return (
    <div className="lp-scene-transport">
      <button
        type="button"
        className="lp-scene-play"
        onClick={togglePlay}
        aria-label={isPlaying ? 'Pause simulation playback' : 'Play simulation playback'}
        title={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? '❚❚' : '▶'}
      </button>

      <input
        type="range"
        className="lp-scene-range"
        min={0}
        max={totalSteps - 1}
        value={activeStep}
        onChange={(e) => onStepChange(parseInt(e.target.value))}
        aria-label="Route position"
      />

      <span className="lp-scene-step">
        {String(activeStep + 1).padStart(3, '0')}/{String(totalSteps).padStart(3, '0')}
      </span>

      <div className="lp-scene-scale" role="group" aria-label="Simulation time scale">
        {TIME_SCALES.map((scale) => (
          <button
            key={scale}
            type="button"
            className={`lp-scene-scale-btn ${timeScale === scale ? 'is-active' : ''}`}
            onClick={() => setTimeScale(scale)}
            title={
              scale === 1
                ? 'Real time: one second on screen is one second of mission'
                : `${scale} seconds of mission per second on screen`
            }
          >
            {scale}&times;
          </button>
        ))}
      </div>
    </div>
  )
}

export default SceneTransport
