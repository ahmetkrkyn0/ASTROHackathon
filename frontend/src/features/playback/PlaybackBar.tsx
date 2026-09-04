import React, { useState, useEffect, useRef } from 'react'
import { batteryToHex } from '../../colormap'
import { useMission, useMissionActions } from '../../mission/MissionContext'
import { useMissionRuntime } from '../../mission/MissionRuntimeContext'

export const PlaybackBar: React.FC = () => {
  const { planResult } = useMission()
  const { routePlaybackStep: currentStep } = useMissionRuntime()
  const { setPlaybackStep: onStepChange } = useMissionActions()
  const [isPlaying, setIsPlaying] = useState(false)
  const timerRef = useRef<number | null>(null)

  // Not memoised, unlike App's own copy of this list: the only thing derived
  // from it that reaches a dependency array here is totalSteps, a number.
  const waypoints = planResult?.waypoints ?? []
  const totalSteps = waypoints.length
  const activeStep = currentStep !== null ? Math.min(currentStep, totalSteps - 1) : 0
  const activeWp = waypoints[activeStep]

  // Playback timer loop
  useEffect(() => {
    if (isPlaying) {
      timerRef.current = window.setInterval(() => {
        onStepChange((prev) => {
          const next = (prev ?? 0) + 1
          if (next >= totalSteps) {
            setIsPlaying(false)
            return totalSteps - 1
          }
          return next
        })
      }, 50)
    } else {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }

    return () => {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current)
      }
    }
  }, [isPlaying, totalSteps, onStepChange])

  const togglePlay = () => {
    const nextPlay = !isPlaying
    if (nextPlay && activeStep >= totalSteps - 1) {
      onStepChange(0)
    }
    setIsPlaying(nextPlay)
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
            const step = parseInt(e.target.value)
            onStepChange(step)
          }}
        />
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

