import { getJson } from './client'
import type { PlanWeights } from '../api'
import type { TerrainManifest } from './types'

/**
 * The scene manifest: units, provenance and value range for every layer,
 * plus the georeference, in one call.
 *
 * cost and traversable depend on the rover and the weights, so those travel
 * as query parameters and the manifest bakes them into each binary_url.
 */
export async function fetchTerrain(
  params: { roverId?: string; weights?: PlanWeights } = {},
  signal?: AbortSignal,
): Promise<TerrainManifest> {
  const query = new URLSearchParams()
  if (params.roverId) query.set('rover_id', params.roverId)
  if (params.weights) {
    query.set('w_slope', String(params.weights.w_slope))
    query.set('w_energy', String(params.weights.w_energy))
    query.set('w_shadow', String(params.weights.w_shadow))
    query.set('w_thermal', String(params.weights.w_thermal))
  }
  const suffix = query.toString()
  return getJson<TerrainManifest>(`/terrain${suffix ? `?${suffix}` : ''}`, signal)
}
