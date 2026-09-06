import { useEffect, useState } from 'react'
import LunaPathMark from './components/LunaPathMark'

/**
 * The screen between one thing and the next.
 *
 * Two jobs, told apart by `mode` rather than by a pile of optional props,
 * because almost nothing about them is shared beyond the picture.
 *
 * BOOT reports something real. App's bootstrap runs four steps in order --
 * reach the backend, load the elevation model if it is not already resident,
 * read the rover catalogue, fetch seven terrain layers -- and this names the
 * one that is running. A bar that fills on a timer while the app does
 * something else is a progress bar in the same sense that a drawn thermometer
 * is a temperature.
 *
 * TRANSITION covers a stage change: the landing screen giving way to the
 * hangar, the hangar to the cockpit. There is no measurable work behind it, so
 * it does not pretend there is -- no percentage, and the bar is timed to the
 * curtain rather than to anything underneath. That stays honest because the
 * thing it times IS the wait. The stage swaps at the midpoint, while the
 * screen is opaque, so what the curtain lifts on is already the next one.
 */

export type BootStage = 'health' | 'dem' | 'rovers' | 'layers' | 'ready'

/** What each boot step is called, and how far along it is. */
const STAGES: Record<BootStage, { label: string; percent: number }> = {
  health: { label: 'Contacting mission backend', percent: 12 },
  dem: { label: 'Loading lunar elevation model', percent: 34 },
  rovers: { label: 'Reading rover catalogue', percent: 52 },
  layers: { label: 'Fetching terrain layers', percent: 88 },
  ready: { label: 'Mission systems ready', percent: 100 },
}

/** Long enough to read the wordmark; short enough not to be in the way. */
const MIN_VISIBLE_MS = 3000

/** Matches the .splash-screen exit transition in App.css. */
const EXIT_MS = 520

/**
 * A stage change is a curtain, not a boot. Three seconds is a title card you
 * watch once; on the two screens you cross on the way to a route it would be
 * six seconds of nothing. This is the shortest beat that still reads as
 * deliberate rather than as a flicker.
 */
const TRANSITION_MS = 1500

/** When the stage swaps behind the curtain -- opaque, and clear of both edges. */
const SWAP_AT_MS = 620

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

type SplashScreenProps =
  | {
      mode: 'boot'
      stage: BootStage
      /** The bootstrap's failure, if it had one. Holds the screen open. */
      error: string | null
      onDone: () => void
    }
  | {
      mode: 'transition'
      /** What is being opened, in the operator's words. */
      caption: string
      /** Fired under cover, to swap the stage. */
      onMidpoint: () => void
      onDone: () => void
    }

export default function SplashScreen(props: SplashScreenProps) {
  return props.mode === 'boot' ? <BootSplash {...props} /> : <TransitionSplash {...props} />
}

function BootSplash({ stage, error, onDone }: Extract<SplashScreenProps, { mode: 'boot' }>) {
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

  return (
    <SplashFrame leaving={leaving}>
      <div className="splash-progress">
        <div className="loading-copy-row">
          <span className="loading-copy">{error ? 'Boot failed' : label}</span>
          <span className="loading-percent">{error ? '--' : `${percent}%`}</span>
        </div>
        <div className="loading-bar-track">
          <div
            className={`loading-bar-fill ${error || stalled ? 'is-failed' : ''}`}
            style={{ width: `${error ? 100 : percent}%` }}
          />
        </div>
      </div>

      {/* The backend's own words when it gave any. A boot that cannot reach the
          planner is the one moment where the exact failure is worth more than a
          tidy line -- and when it gave none, saying which step is hanging beats
          a bar that has stopped moving for no stated reason. */}
      {error ? (
        <p className="splash-error">{error}</p>
      ) : stallNote ? (
        <p className="splash-error">{stallNote} Check that the API is running on port 8000.</p>
      ) : null}
    </SplashFrame>
  )
}

function TransitionSplash({
  caption,
  onMidpoint,
  onDone,
}: Extract<SplashScreenProps, { mode: 'transition' }>) {
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    const swap = window.setTimeout(onMidpoint, SWAP_AT_MS)
    const exit = window.setTimeout(() => setLeaving(true), TRANSITION_MS)
    const done = window.setTimeout(onDone, TRANSITION_MS + EXIT_MS)
    return () => {
      window.clearTimeout(swap)
      window.clearTimeout(exit)
      window.clearTimeout(done)
    }
    // Mount-only: the curtain owns its clock from the moment it appears, and
    // re-running these on a prop identity change would restart it mid-cross.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <SplashFrame leaving={leaving} entering>
      <div className="splash-progress">
        <div className="loading-copy-row">
          <span className="loading-copy">{caption}</span>
        </div>
        {/* No percentage: nothing here is measured. The bar is the curtain's own
            clock, which is the one thing it can honestly report. */}
        <div className="loading-bar-track">
          <div className="loading-bar-fill is-timed" />
        </div>
      </div>
    </SplashFrame>
  )
}

/** The picture both modes share. */
function SplashFrame({
  leaving,
  entering,
  children,
}: {
  leaving: boolean
  entering?: boolean
  children: React.ReactNode
}) {
  return (
    <section
      className={`splash-screen ${leaving ? 'is-leaving' : ''} ${entering ? 'is-entering' : ''}`}
      role="status"
      aria-live="polite"
    >
      <div className="splash-content">
        <div className="splash-identity">
          <LunaPathMark size={128} className="splash-mark" />
          <span className="loading-brand">LunaPath</span>
          <span className="splash-tagline">Lunar south pole mission planning</span>
        </div>
        {children}
      </div>
    </section>
  )
}
