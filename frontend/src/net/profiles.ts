import { getJson } from './client'
import type { MissionProfiles } from './types'

/**
 * The curated mission profiles (weights + constraints frozen at the v3.2 spec).
 * `src/api.ts` also has a `fetchProfiles`, but it was never called and returns
 * an untyped record; this is the net-layer version the mission features use.
 */
export async function fetchMissionProfiles(
  signal?: AbortSignal,
): Promise<MissionProfiles> {
  return getJson<MissionProfiles>('/profiles', signal)
}
