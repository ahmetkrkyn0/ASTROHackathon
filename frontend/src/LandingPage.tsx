import { useEffect, useRef, useState } from 'react'

interface LandingPageProps {
  onExplore: () => void
}

/** Matches the .landing-screen exit transition in App.css. */
const EXPLORE_DURATION_MS = 760

/**
 * The way in.
 *
 * There used to be a Three.js moon here -- a textured sphere you could drag
 * and zoom. It came out because the backdrop clip is also a moon, and two of
 * them on one screen read as a mistake rather than a feature. The clip is the
 * subject now; this file is type over it.
 *
 * Everything visible here is markup and CSS. No WebGL context, no 1024px
 * texture to decode before the page can paint.
 */
export default function LandingPage({ onExplore }: LandingPageProps) {
  const [isExploring, setIsExploring] = useState(false)
  const exploreTimer = useRef<number | null>(null)

  useEffect(() => {
    if (!isExploring) return

    exploreTimer.current = window.setTimeout(onExplore, EXPLORE_DURATION_MS)
    return () => {
      if (exploreTimer.current !== null) window.clearTimeout(exploreTimer.current)
    }
  }, [isExploring, onExplore])

  return (
    <section className={`landing-screen ${isExploring ? 'is-exiting' : ''}`}>
      <div className="landing-content">
        <div className="landing-brand">
          <span className="landing-brand-mark">LUNAPATH</span>
          <span className="landing-brand-sub">Lunar south pole route planning workspace</span>
        </div>

        <div className="landing-main">
          <div className="landing-copy">
            <p className="landing-kicker">LUNAR SOUTH POLE MISSION PLANNING</p>
            <h1>Plan and analyze rover routes across the lunar south pole.</h1>
            <p className="landing-description">
              LunaPath combines terrain, slope, shadow, thermal and energy-aware route planning with 2D/3D mission analysis.
            </p>
            <div className="landing-feature-list" aria-label="Key mission planning features">
              <span className="landing-feature">Terrain Analysis</span>
              <span className="landing-feature">Energy-Aware Routing</span>
              <span className="landing-feature">3D Mission Simulation</span>
            </div>
          </div>

          <div className="landing-actions">
            <button
              type="button"
              className="landing-explore-button"
              onClick={() => {
                setIsExploring(true)
                onExplore()
              }}
              disabled={isExploring}
            >
              Open Mission Planner
            </button>
            <span className="landing-hint">
              Terrain Analysis &middot; Energy-Aware Routing &middot; 3D Mission Simulation
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}
