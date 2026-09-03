import { useEffect, useMemo, useState } from 'react'
import type { PlanWeights } from '../api'
import { frameFromManifest, type GridFrame } from '../grid/geo'
import { fetchTerrain } from '../net/terrain'
import type { TerrainManifest } from '../net/types'

/**
 * One in-flight request per (rover, weights), shared by every consumer.
 *
 * Keyed on exactly what the manifest depends on -- cost and traversable are
 * rover- and weight-dependent, so changing either must fetch again. This is
 * a dedupe, not a freeze.
 */
const inFlight = new Map<string, Promise<TerrainManifest>>()

function cacheKey(roverId: string, weights: PlanWeights): string {
  return [
    roverId,
    weights.w_slope,
    weights.w_energy,
    weights.w_shadow,
    weights.w_thermal,
  ].join('|')
}

/**
 * The terrain manifest and the grid frame derived from it.
 *
 * No AbortSignal: the promise is shared, so one unmounting consumer must not
 * cancel the request the other two are still waiting on. The `alive` flag
 * drops the result instead, which costs one response nobody reads and never
 * fails the modules that are still mounted.
 */
export function useTerrainManifest(roverId: string, weights: PlanWeights) {
  const [manifest, setManifest] = useState<TerrainManifest | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const key = cacheKey(roverId, weights)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)

    let pending = inFlight.get(key)
    if (!pending) {
      pending = fetchTerrain({ roverId, weights })
      inFlight.set(key, pending)
      // A failure must not be cached as the answer forever -- the next
      // mount, or the next weight change back, should try again.
      pending.catch(() => inFlight.delete(key))
    }

    pending
      .then((next) => {
        if (!alive) return
        setManifest(next)
        setLoading(false)
      })
      .catch((cause: unknown) => {
        if (!alive) return
        setError(cause instanceof Error ? cause.message : 'Terrain manifest unavailable')
        setLoading(false)
      })

    return () => {
      alive = false
    }
    // `key` is the value identity of roverId + weights. Listing the objects
    // themselves would refetch on every parent render -- with the same key,
    // so the same response -- because App rebuilds `weights` by identity on
    // each slider commit. The disable has to sit on the line directly above
    // the dependency array, which is where the rule reports.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  /**
   * null when the manifest carries no georeference. A module that draws CRS
   * metres must say so rather than place the corridor at the origin.
   */
  const frame = useMemo<GridFrame | null>(
    () => (manifest ? frameFromManifest(manifest) : null),
    [manifest],
  )

  return { manifest, frame, loading, error }
}
