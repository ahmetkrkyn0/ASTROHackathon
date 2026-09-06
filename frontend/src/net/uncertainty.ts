import { postJson } from './client'

/**
 * DEM uncertainty (B3): the route re-priced on NASA's hundred statistical
 * clones of the elevation model, so a duration or an energy figure comes back
 * as a band rather than a single number.
 *
 * Post-route by definition -- it takes the states of a route that already
 * exists -- and it needs the clone ensemble to have been built, which is a
 * preprocessing step a deployment may simply not have run. When it has not,
 * the backend answers 404 naming the script rather than inventing a band, and
 * this is one of the two cases the error taxonomy exists to keep apart from
 * "no feasible route".
 */

export interface UncertaintyBody {
  /** [row, col, slice] per state along the route. */
  path_states: Array<[number, number, number]>
  rover_id: string
  slice_hours: number
  start_utc?: string
  coarsen?: number
  initial_soc_pct?: number
  /** Capped at what the cache holds; more is a 422. */
  n_clones?: number
  seed?: number
  label?: string
}

/** One metric's spread across the clones. */
export interface UncertaintyBand {
  p5: number
  p50: number
  p95: number
  mean: number
  std: number
  min: number
  max: number
  n: number
}

export interface UncertaintyResponse {
  n_clones?: number
  clones_priced?: number
  route_feasible?: { count: number; fraction: number; ci95?: [number, number] }
  p_traversable?: { min: number; mean: number }
  metrics?: Record<string, UncertaintyBand>
  /** The same computation on the surface DEM, for the band to be read against. */
  nominal?: Record<string, number>
  provenance?: Record<string, unknown>
  sky_model?: Record<string, unknown>
}

export async function fetchRouteUncertainty(
  body: UncertaintyBody,
  signal?: AbortSignal,
): Promise<UncertaintyResponse> {
  return postJson<UncertaintyResponse>('/dem-uncertainty', body, signal)
}
