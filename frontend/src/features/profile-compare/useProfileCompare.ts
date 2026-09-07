import { useCallback, useState } from 'react'
import { compareProfiles } from '../../net/compare'
import { useMission } from '../../mission/MissionContext'
import type { ProfileResult } from '../../net/types'

export interface ConstraintVerdict {
  name: string
  limit: number | null
  actual: number | null
  enforcedInSearch: boolean
  checked: boolean
  satisfied: boolean
}

export function readConstraints(result: ProfileResult): ConstraintVerdict[] {
  const raw = (result.constraint_check ?? {}) as Record<string, Record<string, unknown>>
  return Object.entries(raw).map(([name, entry]) => ({
    name,
    limit: typeof entry.limit === 'number' ? entry.limit : null,
    actual: typeof entry.actual === 'number' ? entry.actual : null,
    enforcedInSearch: entry.enforced_in_search === true,
    // A constraint the backend could not test is not a pass. It reports
    // checked:false precisely so a client does not read silence as success
    // (scenarios.py:104-108). satisfied arrives as null in that case, which
    // is why both are compared against true rather than coerced.
    checked: entry.checked === true,
    satisfied: entry.satisfied === true,
  }))
}

export function useProfileCompare() {
  const { start, goal, roverId } = useMission()
  const [results, setResults] = useState<ProfileResult[]>([])
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async () => {
    if (!start || !goal) {
      setError('Pick a start and a goal first.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const response = await compareProfiles({ start, goal, rover_id: roverId })
      setResults(response.results)
      setComparison(response.comparison)
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Profile comparison failed')
    } finally {
      setBusy(false)
    }
  }, [goal, roverId, start])

  return { results, comparison, run, busy, error }
}
