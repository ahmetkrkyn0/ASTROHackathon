import { postJson } from './client'
import type { CompareResponse, PlanMultiResponse } from './types'

/** start and goal are PIXEL PAIRS here -- [row, col], not {row, col}
 *  (CompareRequest uses PixelPair, main.py:430-433). */
export interface CompareBody {
  start: [number, number]
  goal: [number, number]
  rover_id: string
}

export async function compareProfiles(
  body: CompareBody,
  signal?: AbortSignal,
): Promise<CompareResponse> {
  return postJson<CompareResponse>('/compare', body, signal)
}

export interface PlanMultiBody extends CompareBody {
  profiles: string[]
}

export async function planMulti(
  body: PlanMultiBody,
  signal?: AbortSignal,
): Promise<PlanMultiResponse> {
  return postJson<PlanMultiResponse>('/plan-multi', body, signal)
}
