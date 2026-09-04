import { getJson } from './client'
import type { ReferenceMissions } from './types'

export async function fetchReferenceMissions(
  signal?: AbortSignal,
): Promise<ReferenceMissions> {
  return getJson<ReferenceMissions>('/reference-missions', signal)
}
