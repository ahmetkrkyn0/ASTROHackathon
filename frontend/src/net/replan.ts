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
}

export async function requestReplan(
  body: ReplanBody,
  signal?: AbortSignal,
): Promise<ReplanResponse> {
  return postJson<ReplanResponse>('/replan', body, signal)
}
