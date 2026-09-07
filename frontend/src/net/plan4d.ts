import { postJson } from './client'
import type { PlanWeights } from '../api'
import type { Plan4DResponse } from './types'

export interface Plan4DBody {
  start: { row: number; col: number }
  goal: { row: number; col: number }
  rover_id: string
  weights: PlanWeights
  /** State the window as n_slices OR horizon_hours -- not both (main.py:895). */
  n_slices?: number
  horizon_hours?: number
  slice_hours?: number
  coarsen?: number
  start_utc?: string
}

export async function planRoute4D(
  body: Plan4DBody,
  signal?: AbortSignal,
): Promise<Plan4DResponse> {
  return postJson<Plan4DResponse>('/plan-4d', body, signal)
}
