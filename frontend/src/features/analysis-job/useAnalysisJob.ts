import { useCallback, useEffect, useRef, useState } from 'react'
import { classifyFailure, type EndpointKind, type Failure } from '../../net/errors'
import { matchesRoute } from '../../mission/routeIdentity'

/**
 * The lifecycle of a post-route analysis.
 *
 * Sections 24, 25 and 26 of the integration plan, in one place, because the
 * five analyses that need it -- Monte Carlo, DEM route uncertainty, the risk
 * sweep, PSR validation, the STL safety check -- have identical shapes and
 * writing the state machine five times is how five slightly different ones
 * appear.
 *
 * Three things this makes structurally impossible rather than merely
 * discouraged:
 *
 * NO FAKE PROGRESS. There is no `percent` field, in any state, and there is
 * nowhere to put one. The backend reports no progress for these jobs, so any
 * number on screen would be an animation pretending to be telemetry. A
 * thousand Monte Carlo runs take as long as they take; "running" is the whole
 * truth and it is what this reports.
 *
 * NO STALE RESULT ON A NEW ROUTE. Every run records the route identity it
 * started for. A response that lands after the operator has changed the rover,
 * the endpoints, the weights or a constraint is dropped rather than displayed,
 * because it describes a traverse nobody is flying any more. A result already
 * on screen when the mission changes goes to `stale` rather than disappearing,
 * so the panel can grey out what it was showing instead of flashing empty.
 *
 * NO DUPLICATE SUBMIT. `start` while a run is in flight is ignored. The button
 * is not the guard -- the guard is the guard.
 *
 * A held route is never hidden by any of this. These analyses are about a
 * route; none of them is a reason to stop drawing it.
 */
export type AnalysisJob<T> =
  /** Never run for this route. */
  | { state: 'idle' }
  /** In flight. Indeterminate, and nothing here pretends otherwise. */
  | { state: 'running' }
  /** Done, and about the route currently on screen. */
  | { state: 'success'; value: T; computedFor: string }
  /**
   * The run failed. Classified, so an infeasible mission and an unreachable
   * backend do not read the same. The route this was about is untouched.
   */
  | { state: 'failure'; failure: Failure }
  /** Done, but about a route that is no longer current. */
  | { state: 'stale'; value: T; computedFor: string }

/**
 * Move a job to match a new route identity.
 *
 * Pulled out of the hook and exported because it is the only part of this
 * machine with a decision in it, and this repo has no React test environment
 * -- every one of its tests runs pure functions under node. Leaving the
 * transition inside the effect would have made the one piece worth pinning
 * down the one piece that could not be.
 */
export function reconcileIdentity<T>(
  job: AnalysisJob<T>,
  identity: string | null,
): AnalysisJob<T> {
  if (job.state === 'success' && !matchesRoute(job.computedFor, identity)) {
    return { state: 'stale', value: job.value, computedFor: job.computedFor }
  }
  if (job.state === 'stale' && matchesRoute(job.computedFor, identity)) {
    // The operator undid whatever they changed. The result is about this route
    // again, and recomputing it would be twenty seconds spent reaching the
    // same answer.
    return { state: 'success', value: job.value, computedFor: job.computedFor }
  }
  return job
}

export interface AnalysisJobOptions<T> {
  /** Performs the call. Must pass the signal through to fetch. */
  run: (signal: AbortSignal) => Promise<T>
  /**
   * Identity of the route this analysis would be about, from
   * `routeIdentity()`. Null means there is no route, and `start` refuses.
   */
  identity: string | null
  /** How a failure should be read. Analyses classify as 'analysis'. */
  endpoint?: EndpointKind
}

export interface AnalysisJobHandle<T> {
  job: AnalysisJob<T>
  /** Begins a run. Ignored while one is in flight, or with no route. */
  start: () => void
  /** Abandons the run in flight and returns to idle. */
  cancel: () => void
}

export function useAnalysisJob<T>({
  run,
  identity,
  endpoint = 'analysis',
}: AnalysisJobOptions<T>): AnalysisJobHandle<T> {
  const [job, setJob] = useState<AnalysisJob<T>>({ state: 'idle' })
  const controllerRef = useRef<AbortController | null>(null)
  // Read inside the async callback rather than closed over, so a run started
  // before the mission changed still compares against the identity it began
  // with instead of one captured at render time.
  const identityRef = useRef(identity)
  identityRef.current = identity

  /* A result outlives the mission it was computed for only as `stale`. This
     runs on every identity change, including back to null when the route is
     cleared, which is itself a mission change. */
  useEffect(() => {
    setJob((current) => reconcileIdentity(current, identity))
  }, [identity])

  /* Abandon anything in flight when the component goes away. Mount-only: the
     ref is stable and re-running this on every render would abort each run the
     moment it started. */
  useEffect(() => () => controllerRef.current?.abort(), [])

  const cancel = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    setJob((current) => (current.state === 'running' ? { state: 'idle' } : current))
  }, [])

  const start = useCallback(() => {
    if (controllerRef.current) return
    const startedFor = identityRef.current
    if (startedFor === null) return

    const controller = new AbortController()
    controllerRef.current = controller
    setJob({ state: 'running' })

    run(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        // The mission moved while this was in flight. Attaching the result to
        // the route now on screen would be reporting a different traverse's
        // numbers as this one's.
        if (!matchesRoute(startedFor, identityRef.current)) {
          setJob({ state: 'stale', value, computedFor: startedFor })
          return
        }
        setJob({ state: 'success', value, computedFor: startedFor })
      })
      .catch((cause: unknown) => {
        // An abort is something we did, not something that went wrong. Showing
        // the operator a connectivity warning for their own navigation is the
        // error message equivalent of a fake progress bar.
        if (controller.signal.aborted) return
        setJob({ state: 'failure', failure: classifyFailure(cause, endpoint) })
      })
      .finally(() => {
        if (controllerRef.current === controller) controllerRef.current = null
      })
  }, [endpoint, run])

  return { job, start, cancel }
}
