import { useEffect, useState } from 'react'
import { fetchReferenceMissions } from '../../net/missions'
import { useMission } from '../../mission/MissionContext'
import type { ReferenceMissions, RouteStatistics } from '../../net/types'

export function useMissionValidation() {
  const { planResult } = useMission()
  const [reference, setReference] = useState<ReferenceMissions | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    fetchReferenceMissions(controller.signal)
      .then((next) => {
        setReference(next)
        setLoading(false)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(cause instanceof Error ? cause.message : 'Reference missions unavailable')
        setLoading(false)
      })
    return () => controller.abort()
  }, [])

  const stats =
    (planResult as { route_statistics?: RouteStatistics | null } | null)
      ?.route_statistics ?? null

  /**
   * This route's DRIVING rate: metres per 24 h of simulated traverse clock.
   *
   * Deliberately not called comparable to the published column. The flown
   * figures are distance over CALENDAR days including lunar-night dormancy,
   * which is why the backend calls them lower bounds; this one excludes
   * every night the rover would have slept through. On the shipped grid the
   * two differ by five orders of magnitude -- 16,667 m/day against Yutu-2's
   * 0.10 -- so the panel labels this number rather than letting the column
   * header imply they measure the same thing.
   */
  const summary = planResult?.summary ?? null
  const ourDrivingRateMPerDay =
    summary && summary.total_elapsed_hours > 0
      ? (summary.total_distance_km * 1000) / (summary.total_elapsed_hours / 24)
      : null

  return { reference, stats, ourDrivingRateMPerDay, loading, error }
}
