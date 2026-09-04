import { useMemo } from 'react'
import { useMission } from '../../mission/MissionContext'
import { useTerrainManifest } from '../../mission/useTerrainManifest'
import type { Corridor } from '../../net/types'

export interface SegmentRow {
  index: number
  halfWidthM: number
  maxSlopeDeg: number
  energyWh: number
  thermalKs: number
}

export function useCorridor() {
  const { planResult, roverId, weights } = useMission()

  // The georeference, not the layers: the corridor speaks CRS metres and the
  // canvas speaks pixels, and the manifest is where origin/resolution live.
  // Shared with F1 and F7 -- one request, one frame, no chance of three
  // modules disagreeing about where the grid is while a rover change is in
  // flight.
  const { frame, loading, error: manifestError } = useTerrainManifest(roverId, weights)

  // `loading` guards the frame check. Before the first manifest lands the
  // frame is null for the ordinary reason that nobody has asked yet, and
  // reporting that as "the grid has no georeference" would put a warning on
  // screen for a fetch that is simply in flight.
  const error =
    manifestError ??
    (!loading && frame === null
      ? 'Grid has no georeference; corridor cannot be placed.'
      : null)

  // /api/plan carries corridor, execution and route_statistics beside the
  // fields api.ts declares. Narrowed here rather than widening PlanResponse,
  // which would be a third edit to a file this plan keeps closed.
  const corridor = (planResult as { corridor?: Corridor | null } | null)?.corridor ?? null

  const segments = useMemo<SegmentRow[]>(() => {
    if (!corridor) return []
    // All four budget arrays are per-segment and therefore N-1 long
    // (corridor.py:126). half_width_m is the shortest of them by definition
    // of the loop, so its length is the segment count.
    return corridor.half_width_m.map((halfWidth, index) => ({
      index,
      halfWidthM: halfWidth,
      maxSlopeDeg: corridor.max_slope_deg[index] ?? Number.NaN,
      energyWh: corridor.energy_budget_wh[index] ?? Number.NaN,
      thermalKs: corridor.thermal_budget_K_s[index] ?? Number.NaN,
    }))
  }, [corridor])

  return { corridor, frame, segments, loading, error }
}
