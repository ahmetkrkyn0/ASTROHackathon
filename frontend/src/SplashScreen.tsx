import { useEffect, useState } from 'react'

/**
 * The boot screen.
 *
 * What it reports is real. App's bootstrap runs four steps in order -- reach
 * the backend, load the elevation model if it is not already resident, read the
 * rover catalogue, fetch seven terrain layers -- and this names the one that is
 * running. A bar that fills on a timer while the app does something else is a
 * progress bar in the same sense that a drawn thermometer is a temperature.
 *
 * It is held on screen for a minimum, and that IS a deliberate delay. Against a
 * warm local backend the whole sequence answers in under a tenth of a second,
 * so an honest splash would appear and vanish inside two frames -- a flash that
 * reads as a rendering fault rather than as a product. MIN_VISIBLE_MS is the
 * floor that makes it legible; when the backend is cold, or the DEM has to be
 * preprocessed, the real work outlasts it and the floor costs nothing.
 */

export type BootStage = 'health' | 'dem' | 'rovers' | 'layers' | 'ready'

/** What each stage is called, and how far along it is. */
const STAGES: Record<BootStage, { label: string; percent: number }> = {
  health: { label: 'Contacting mission backend', percent: 12 },
  dem: { label: 'Loading lunar elevation model', percent: 34 },
  rovers: { label: 'Reading rover catalogue', percent: 52 },
  layers: { label: 'Fetching terrain layers', percent: 88 },
  ready: { label: 'Mission systems ready', percent: 100 },
}

/** Long enough to read the wordmark; short enough not to be in the way. */
const MIN_VISIBLE_MS = 1400

/** Matches the .splash-screen exit transition in App.css. */
const EXIT_MS = 520

/**
 * How long the boot may sit on one step before the screen says so.
 *
 * Not a timeout -- nothing is cancelled, and a boot that finishes at twelve
 * seconds still finishes. It exists because the failure it catches is silent.
 * A request to an API that is down does not always come back refused: a port
 * left listening by a dead worker accepts the connection and never answers, so
 * the health promise never settles, the catch never runs, and App stays in
 * 'loading' with nothing wrong recorded. Reproduced by killing the uvicorn
 * worker while its reloader kept :8000 open -- thirteen seconds on "Contacting
 * mission backend", 12%, no error anywhere. A stuck boot should say it is
 * stuck.
 */
const STALL_MS = 9000

interface SplashScreenProps {
  stage: BootStage
  /** The bootstrap's failure, if it had one. Holds the splash open. */
  error: string | null
  /** Called once the screen has finished leaving, so App can stop rendering it. */
  onDone: () => void
}

export default function SplashScreen({ stage, error, onDone }: SplashScreenProps) {
  const [floorPassed, setFloorPassed] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const [stalled, setStalled] = useState(false)

  useEffect(() => {
    const id = window.setTimeout(() => setFloorPassed(true), MIN_VISIBLE_MS)
    return () => window.clearTimeout(id)
  }, [])

  /* Restarted per stage, so a boot that is merely slow keeps resetting the
     clock and only a boot that is actually stuck trips it. */
  useEffect(() => {
    if (stage === 'ready') return
    setStalled(false)
    const id = window.setTimeout(() => setStalled(true), STALL_MS)
    return () => window.clearTimeout(id)
  }, [stage])

  /* A failed bootstrap keeps the screen: there is nothing behind it to use, and
     the landing page's "Launch Mission Workstation" would open a cockpit with
     no terrain in it. */
  useEffect(() => {
    if (error || !floorPassed || stage !== 'ready') return
    setLeaving(true)
    const id = window.setTimeout(onDone, EXIT_MS)
    return () => window.clearTimeout(id)
  }, [error, floorPassed, stage, onDone])

  const { label, percent } = STAGES[stage]
  const stallNote = stalled && !error ? `Still waiting on ${label.toLowerCase()}.` : null
  const failed = Boolean(error) || stalled

  return (
    <section
      className={`splash-screen ${leaving ? 'is-leaving' : ''}`}
      role="status"
      aria-live="polite"
    >
      <div className="splash-content">
        <div className="splash-identity">
          <span className="loading-brand">LunaPath</span>
          <span className="splash-tagline">Lunar south pole mission planning</span>
        </div>

        <div className="splash-progress">
          <div className="loading-copy-row">
            <span className="loading-copy">{error ? 'Boot failed' : label}</span>
            <span className="loading-percent">{error ? '--' : `${percent}%`}</span>
          </div>
          <div className="loading-bar-track">
            <div
              className={`loading-bar-fill ${failed ? 'is-failed' : ''}`}
              style={{ width: `${error ? 100 : percent}%` }}
            />
          </div>
        </div>

        {/* The backend's own words when it gave any. A boot that cannot reach
            the planner is the one moment where the exact failure is worth more
            than a tidy line -- and when it gave none, saying which step is
            hanging beats a bar that has stopped moving for no stated reason. */}
        {error ? (
          <p className="splash-error">{error}</p>
        ) : stallNote ? (
          <p className="splash-error">
            {stallNote} Check that the API is running on port 8000.
          </p>
        ) : null}
      </div>
    </section>
  )
}
