import React from 'react'
import { batteryToHex } from '../../colormap'
import { useMission, useMissionActions } from '../../mission/MissionContext'
import { useMissionRuntime } from '../../mission/MissionRuntimeContext'

/**
 * Simulated seconds per wall-clock second.
 *
 * 1x is the default and the point of the list: at 1x the rover crosses the
 * ground at exactly the speed the planner charged it for, so the time the
 * traverse takes on screen IS the time it takes. The larger steps exist
 * because a real lunar traverse is measured in hours -- but they are now a
 * number the operator picked and can read, not a hidden compression factor
 * baked into the animation.
 */
const TIME_SCALES = [1, 10, 60, 300] as const

/** "T+04:12:30" from the planner's own elapsed hours. */
function formatElapsed(hours: number): string {
  const totalSeconds = Math.max(0, Math.round(hours * 3600))
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = totalSeconds % 60
  return `T+${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export const PlaybackBar: React.FC = () => {
  const { planResult } = useMission()
  const {
    routePlaybackStep: currentStep,
    playbackHours,
    playbackTotalHours,
    isPlaying,
    timeScale,
    isRecharging,
    groundSpeedMs,
  } = useMissionRuntime()
  const { setPlaybackStep: onStepChange, setPlaying, setTimeScale } = useMissionActions()

  // Not memoised, unlike App's own copy of this list: the only thing derived
  // from it that reaches a dependency array here is totalSteps, a number.
  const waypoints = planResult?.waypoints ?? []
  const totalSteps = waypoints.length
  const activeStep = currentStep !== null ? Math.min(currentStep, totalSteps - 1) : 0
  const activeWp = waypoints[activeStep]

  const togglePlay = () => {
    // Replaying from the end restarts rather than sitting at the finish.
    if (!isPlaying && playbackHours >= playbackTotalHours - 1e-6) onStepChange(0)
    setPlaying(!isPlaying)
  }

  if (totalSteps === 0) return null

  return (
    // Lives in the status strip now, which is in flow and takes its own
    // clicks; the pointer-events opt-in the canvas overlay needed is gone.
    <div className="lp-playback-dock">
      <div className="lp-playback-controls">
        <button
          type="button"
          className="lp-play-btn"
          onClick={togglePlay}
          aria-label={isPlaying ? 'Pause simulation playback' : 'Play simulation playback'}
        >
          {isPlaying ? '❚❚ Pause' : '▶ Play'}
        </button>

        <div className="lp-playback-meta">
          <span className="lp-mono-label">WAYPOINT</span>
          <strong className="lp-mono-val">
            {String(activeStep + 1).padStart(3, '0')} / {String(totalSteps).padStart(3, '0')}
          </strong>
        </div>
      </div>

      <div className="lp-playback-slider-block">
        <input
          type="range"
          className="lp-playback-range"
          min={0}
          max={totalSteps - 1}
          value={activeStep}
          onChange={(e) => {
            onStepChange(parseInt(e.target.value))
          }}
        />
      </div>

      {/* The honesty panel: what time it is on the mission clock, how fast
          that clock is running, and how fast the rover is actually moving.
          Without these three the drive is just an animation at whatever
          rate the code felt like. */}
      <div className="lp-playback-clock">
        <div className="lp-playback-stat">
          <span className="lp-stat-name">MISSION TIME</span>
          <strong className="lp-stat-val">{formatElapsed(playbackHours)}</strong>
        </div>
        <div className="lp-playback-stat">
          <span className="lp-stat-name">SPEED</span>
          <strong className="lp-stat-val">
            {isRecharging ? 'RECHARGING' : `${groundSpeedMs.toFixed(2)} m/s`}
          </strong>
        </div>
        <div className="lp-playback-scale" role="group" aria-label="Simulation time scale">
          {TIME_SCALES.map((scale) => (
            <button
              key={scale}
              type="button"
              className={`lp-scale-btn ${timeScale === scale ? 'is-active' : ''}`}
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

      <div className="lp-playback-readouts">
        <div className="lp-playback-stat">
          <span className="lp-stat-name">DISTANCE</span>
          <strong className="lp-stat-val">
            {activeWp ? `${(activeWp.distance_m / 1000).toFixed(2)} km` : '--'}
          </strong>
        </div>

        <div className="lp-playback-stat">
          <span className="lp-stat-name">BATTERY</span>
          <strong
            className="lp-stat-val"
            style={{ color: activeWp ? batteryToHex(activeWp.battery_pct) : undefined }}
          >
            {activeWp ? `${activeWp.battery_pct.toFixed(1)}%` : '--'}
          </strong>
        </div>

        <div className="lp-playback-stat">
          <span className="lp-stat-name">SLOPE</span>
          <strong className="lp-stat-val">
            {activeWp ? `${activeWp.slope_deg.toFixed(1)}°` : '--'}
          </strong>
        </div>
      </div>
    </div>
  )
}

export default PlaybackBar
