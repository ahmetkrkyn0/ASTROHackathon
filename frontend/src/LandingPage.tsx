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
 * Three rows, taken from the design canvas: a status header, the pitch, and a
 * footer that names the capabilities and admits what the terrain actually is.
 * The capability line used to appear twice -- once as a row of chips and again
 * as the footer -- which is the kind of duplication the box policy exists to
 * stop. It is the footer's job.
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
        <header className="landing-topline">
          <div className="landing-brand">
            <span className="landing-brand-mark">LUNAPATH</span>
            <span className="landing-brand-sub">Mission Workstation</span>
          </div>
          <div className="landing-status">
            <span>REGION LSP · 89.15°S</span>
            <span className="landing-link">
              <i className="landing-link-dot" aria-hidden="true" />
              DATA LINK ACTIVE
            </span>
          </div>
        </header>

        <div className="landing-main">
          <div className="landing-copy">
            <p className="landing-kicker">LUNAR SOUTH POLE MISSION PLANNING</p>
            <h1>Plan and analyze rover routes across the lunar south pole.</h1>
            <p className="landing-description">
              LunaPath combines terrain, slope, shadow, thermal and energy-aware route planning with
              2D/3D mission analysis.
            </p>

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
              <span className="landing-hint">ENTER COCKPIT · NO ROUTE LOADED</span>
            </div>
          </div>
        </div>

        <footer className="landing-footline">
          <div className="landing-capabilities" aria-label="Key mission planning features">
            <span>Terrain Analysis</span>
            <span className="landing-sep">·</span>
            <span>Energy-Aware Routing</span>
            <span className="landing-sep">·</span>
            <span>3D Mission Simulation</span>
          </div>
          {/* Data honesty, section 29: the terrain is synthetic, and the screen
              that introduces the product is where that has to be said. */}
          <span className="landing-dataset">DATASET: SYNTHETIC DEMO TERRAIN · NOT FLIGHT LDEM</span>
        </footer>
      </div>
    </section>
  )
}
