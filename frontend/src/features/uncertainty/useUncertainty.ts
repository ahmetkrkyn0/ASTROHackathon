import { useCallback, useMemo } from 'react'
import { useMission } from '../../mission/MissionContext'
import { useAnalysisJob } from '../analysis-job'
import { fetchRouteUncertainty, type UncertaintyBody, type UncertaintyResponse } from '../../net/uncertainty'

/**
 * DEM uncertainty for the route on screen (B3).
 *
 * Two halves at different prices. The `uncertainty` block rides along with
 * every plan response and costs milliseconds -- how traversable the route's
 * cells are across the clone ensemble -- but it is absent entirely when the
 * ensemble has not been built. The band is a separate call that re-prices the
 * whole route on all hundred clones and takes seconds, so it is asked for
 * rather than fetched.
 */

/** The cheap summary that rides along with the plan, when the cache exists. */
export interface UncertaintySummary {
  nClones: number | null
  coarsen: number | null
  pTraversableMin: number | null
  pTraversableMean: number | null
  routeFeasibleFraction: number | null
  productUrl: string | null
}

function num(source: Record<string, unknown> | null, key: string): number | null {
  if (!source) return null
  const value = source[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function readUncertaintySummary(result: unknown): UncertaintySummary | null {
  if (typeof result !== 'object' || result === null) return null
  const block = (result as Record<string, unknown>).uncertainty
  if (typeof block !== 'object' || block === null) return null
  const record = block as Record<string, unknown>
  return {
    nClones: num(record, 'n_clones'),
    coarsen: num(record, 'coarsen'),
    pTraversableMin: num(record, 'p_traversable_min'),
    pTraversableMean: num(record, 'p_traversable_mean'),
    routeFeasibleFraction: num(record, 'route_feasible_fraction'),
    productUrl: typeof record.product_url === 'string' ? record.product_url : null,
  }
}

export function useUncertainty() {
  const { planResult, roverId, routeIdentity, missionTime } = useMission()

  const summary = useMemo(() => readUncertaintySummary(planResult), [planResult])

  /**
   * The route as the endpoint wants it: a state per waypoint with its slice
   * index, and the slice length the indices are counted in. Derived from the
   * planner's own elapsed hours so the two describe the same traverse.
   */
  const body = useMemo<UncertaintyBody | null>(() => {
    const waypoints = planResult?.waypoints
    if (!waypoints || waypoints.length < 2) return null
    const last = waypoints[waypoints.length - 1]
    const totalHours = typeof last.elapsed_hours === 'number' ? last.elapsed_hours : 0
    // A slice per step. Zero-length would make every state slice 0, which is
    // a different traverse from the one that was planned.
    const sliceHours = totalHours > 0 ? totalHours / (waypoints.length - 1) : 0.1
    return {
      path_states: waypoints.map((waypoint, index) => [waypoint.row, waypoint.col, index]),
      rover_id: roverId,
      slice_hours: sliceHours,
      start_utc: missionTime,
    }
  }, [missionTime, planResult, roverId])

  const run = useCallback(
    (signal: AbortSignal): Promise<UncertaintyResponse> => {
      if (!body) return Promise.reject(new Error('No route to price.'))
      return fetchRouteUncertainty(body, signal)
    },
    [body],
  )

  const { job, start, cancel } = useAnalysisJob<UncertaintyResponse>({
    run,
    identity: routeIdentity,
    endpoint: 'analysis',
  })

  return { summary, job, start, cancel, canRun: body !== null }
}
