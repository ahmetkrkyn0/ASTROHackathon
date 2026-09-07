import { useCallback, useMemo } from 'react'
import { useMission } from '../../mission/MissionContext'
import { missionTimeUtc } from '../../mission/missionTime'
import { useAnalysisJob } from '../analysis-job'
import { runStressTest, type StressTestBody, type StressTestResponse } from '../../net/stressTest'

/**
 * The Monte Carlo stress test for the route on screen (B5).
 *
 * Never run without a route -- there is nothing to perturb -- and never run
 * automatically: a thousand executions of the traverse takes seconds, and the
 * plan puts everything in this class behind the route being shown rather than
 * in front of it.
 */
export function useStressTest() {
  const { planResult, roverId, routeIdentity, missionTime } = useMission()

  const body = useMemo<StressTestBody | null>(() => {
    const waypoints = planResult?.waypoints
    if (!waypoints || waypoints.length < 2) return null
    const last = waypoints[waypoints.length - 1]
    const totalHours = typeof last.elapsed_hours === 'number' ? last.elapsed_hours : 0
    const sliceHours = totalHours > 0 ? totalHours / (waypoints.length - 1) : 0.1
    const startUtc = missionTimeUtc(missionTime)
    if (!startUtc) return null
    return {
      path_states: waypoints.map((waypoint, index) => [waypoint.row, waypoint.col, index]),
      rover_id: roverId,
      // The states above are fine cells, so the grid they are counted in has
      // to be the fine one. The endpoint defaults to 4, where a state is a
      // 20 m block and is traversable only if all sixteen 5 m cells inside it
      // are -- which a 2-D route can legitimately violate, and which comes
      // back as "state N is not traversable" for a route that plainly is.
      coarsen: 1,
      slice_hours: sliceHours,
      // The shared clock is an epoch plus an offset; this endpoint wants the
      // instant. Null propagates as "no body", which stops the run rather
      // than asking a different question with a substituted "now".
      start_utc: startUtc,
      // The backend's own default. Stated rather than omitted so the number
      // the histogram counts is visible in the request that produced it.
      n_runs: 1000,
      // Fixed, so the same route re-tested gives the same answer. A stress
      // test whose numbers move on their own is one nobody can act on.
      seed: 0,
    }
  }, [missionTime, planResult, roverId])

  const run = useCallback(
    (signal: AbortSignal): Promise<StressTestResponse> => {
      if (!body) return Promise.reject(new Error('No route to stress-test.'))
      return runStressTest(body, signal)
    },
    [body],
  )

  const { job, start, cancel } = useAnalysisJob<StressTestResponse>({
    run,
    identity: routeIdentity,
    endpoint: 'analysis',
  })

  return { job, start, cancel, canRun: body !== null, runs: body?.n_runs ?? 0 }
}
