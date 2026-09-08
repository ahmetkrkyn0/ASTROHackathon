import { postJson } from './client'
import type { PlanWeights } from '../api'
import type { ReplanResponse } from './types'

export interface ReplanBody {
  current: { row: number; col: number }
  goal: { row: number; col: number }
  rover_id: string
  weights: PlanWeights
  /** Telemetry snapshot. Every value must be finite -- the backend rejects NaN. */
  state: Record<string, number>
  force?: boolean
  /**
   * Confirmed local observations, projected into the active grid. The normal
   * `/plan` request deliberately has no equivalent field: an obstacle first
   * becomes eligible only after LiDAR has observed it.
   */
  observed_obstacles?: Array<{
    row: number
    col: number
    radius_m: number
    confidence: number
    observed_at_s: number
    source: 'lidar'
  }>
}

export async function requestReplan(
  body: ReplanBody,
  signal?: AbortSignal,
): Promise<ReplanResponse> {
  return postJson<ReplanResponse>('/replan', body, signal)
}
