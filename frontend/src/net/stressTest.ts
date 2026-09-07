import { postJson } from './client'

/**
 * SHERPA Monte Carlo stress test (B5): the planned route executed a thousand
 * times under perturbed conditions, reported as distributions.
 *
 * Post-route by definition, and slow enough to be asked for rather than
 * fetched. Its result never overwrites the route's own status: a planner that
 * returned a route and a stress test that completes 30% of the time are two
 * different statements about two different questions, and the plan is explicit
 * that neither may be presented as the other.
 */

export interface Rate {
  count: number
  rate: number
  /** Wilson 95% interval. The rate alone would hide how few runs support it. */
  ci95: [number, number]
}

export interface MetricBand {
  mean: number
  std: number
  p5: number
  p50: number
  p95: number
  min: number
  max: number
  n: number
}

/** Bins the backend prepared. Never re-binned here -- the contract forbids it. */
export interface Histogram {
  edges: number[]
  counts: number[]
}

export interface StressTestBody {
  path_states: Array<[number, number, number]>
  rover_id: string
  slice_hours: number
  /**
   * Cell size the states are counted in, as a multiple of the fine grid.
   * 1 means the states ARE fine cells, which is what a 2-D plan produces.
   * The default is 4, and sending fine states under it is rejected: a coarse
   * cell is the AND of sixteen fine ones, so a route that is traversable at
   * 5 m can cross a 20 m block that is not.
   */
  coarsen?: number
  start_utc?: string
  initial_soc_pct?: number
  /** 1..20000. */
  n_runs?: number
  /** 5..100. */
  n_bins?: number
  seed?: number
  label?: string
  perturbations?: Record<string, number>
}

export interface StressTestResponse {
  route?: Record<string, unknown>
  rates?: Record<string, Rate | null>
  failures?: Record<string, number>
  metrics?: Record<string, MetricBand | null>
  histograms?: Record<string, Histogram>
  nominal?: Record<string, unknown>
  /** The backend's own decision sentence. Shown verbatim. */
  verdict?: {
    reaches_goal_at_95pct?: boolean
    full_success_at_95pct?: boolean
    haven_rule_known?: boolean
    text?: string
  }
  perturbations?: Record<string, unknown>
  sky_model?: Record<string, unknown>
}

export async function runStressTest(
  body: StressTestBody,
  signal?: AbortSignal,
): Promise<StressTestResponse> {
  return postJson<StressTestResponse>('/stress-test', body, signal)
}
