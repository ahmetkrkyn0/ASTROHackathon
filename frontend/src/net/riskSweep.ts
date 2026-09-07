import { postJson } from './client'

/**
 * Risk appetite sweep (B2's second half): the same start and goal planned at
 * several alphas at once, so what the tail actually buys is visible instead of
 * argued.
 *
 * The backend computes the comparison and the matrix. Neither is recomputed
 * here -- the plan says so explicitly, and a client-side re-derivation would
 * be a second opinion nobody asked for.
 */

export interface SweepDelta {
  risk_alpha: number
  distance_km: number
  hours: number
  energy_wh: number
  min_battery_pct: number
  mean_slip: number
  max_slip: number
  /** 1.0 means the route did not move at all. */
  overlap_with_nominal: number
}

export interface RiskSweepResponse {
  alphas?: Array<number | null>
  comparison?: {
    nominal?: Record<string, number>
    deltas?: SweepDelta[]
  }
  risk_matrix?: Record<string, unknown>
  /** The sentence that keeps alpha a ranking preference. Shown verbatim. */
  note?: string
  claim?: string
  measure?: string
}

export interface RiskSweepBody {
  start: { row: number; col: number }
  goal: { row: number; col: number }
  rover_id: string
  weights?: Record<string, number>
  alphas?: number[]
}

export async function runRiskSweep(
  body: RiskSweepBody,
  signal?: AbortSignal,
): Promise<RiskSweepResponse> {
  return postJson<RiskSweepResponse>('/risk-sweep', body, signal)
}
