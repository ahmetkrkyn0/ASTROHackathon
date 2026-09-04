import { useEffect, useMemo, useState } from 'react'
import type { PlanWeights } from '../../api'
import { fetchMissionProfiles } from '../../net/profiles'
import { useMission, useMissionActions } from '../../mission/MissionContext'
import type { MissionProfiles } from '../../net/types'

const WEIGHT_KEYS: Array<keyof PlanWeights> = ['w_slope', 'w_energy', 'w_shadow', 'w_thermal']

/**
 * Weights round-trip through range inputs at step 0.01 and the profile spec
 * carries three decimals, so an exact-equality match would call a profile
 * "Custom" the instant a slider quantised it. A tolerance just above the slider
 * step treats "the sliders are where this profile put them" as still that
 * profile.
 */
const MATCH_EPSILON = 0.011

function weightsMatch(a: PlanWeights, b: PlanWeights): boolean {
  return WEIGHT_KEYS.every((k) => Math.abs(a[k] - b[k]) <= MATCH_EPSILON)
}

/**
 * Surfaces GET /api/profiles as a preset selector for the four route-priority
 * weights. Selecting a profile only writes its weights -- that is the whole of
 * what /api/plan consumes -- while its constraints ride along for display.
 * `activeId` is derived from the live weights, so hand-tuning a slider off a
 * preset reports as no active profile ("Custom") without any extra state.
 */
export function useMissionProfiles() {
  const { weights } = useMission()
  const { setWeights } = useMissionActions()

  const [profiles, setProfiles] = useState<MissionProfiles | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchMissionProfiles(controller.signal)
      .then((next) => {
        setProfiles(next)
        setLoading(false)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(cause instanceof Error ? cause.message : 'Mission profiles unavailable')
        setLoading(false)
      })
    return () => controller.abort()
  }, [])

  const activeId = useMemo(() => {
    if (!profiles) return null
    const hit = Object.entries(profiles).find(([, p]) => weightsMatch(weights, p.weights))
    return hit ? hit[0] : null
  }, [profiles, weights])

  const applyProfile = (id: string) => {
    const profile = profiles?.[id]
    if (profile) setWeights({ ...profile.weights })
  }

  return { profiles, activeId, applyProfile, loading, error }
}
