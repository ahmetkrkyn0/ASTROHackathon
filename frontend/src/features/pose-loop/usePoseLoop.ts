import { useCallback, useMemo, useState } from 'react'
import { submitPose, type PoseEstimateBody } from '../../net/pose'
import { useMission } from '../../mission/MissionContext'
import type { Corridor, PoseResponse, SkippedTrigger, TriggerId } from '../../net/types'
import { TRIGGER_IDS } from '../../mission/triggers'

export type PoseStatus = 'fired' | 'clear' | 'unchecked'

export interface PoseTriggerRow {
  id: TriggerId
  status: PoseStatus
  detail: string | null
}

/** Mirrors PoseEstimateBody. Every field is required by the backend. */
export type PoseForm = PoseEstimateBody

export function usePoseLoop() {
  const { planResult } = useMission()
  const corridor =
    (planResult as { corridor?: Corridor | null } | null)?.corridor ?? null

  const [form, setForm] = useState<PoseForm>({
    x_m: 0,
    y_m: 0,
    heading_deg: 0,
    covariance_m: 3,
    heading_covariance_deg: 5,
    timestamp_utc: new Date().toISOString(),
    source: 'dead_reckoning',
    distance_travelled_m: 0,
  })
  const [result, setResult] = useState<PoseResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const setField = useCallback(<K extends keyof PoseForm>(key: K, value: PoseForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
  }, [])

  /** Seed the form from a corridor waypoint so the metres are plausible. */
  const seedFromCorridor = useCallback(
    (index: number) => {
      if (!corridor || !corridor.waypoints[index]) return
      const [x, y] = corridor.waypoints[index]
      setForm((current) => ({ ...current, x_m: x, y_m: y }))
    },
    [corridor],
  )

  const submit = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      const response = await submitPose({
        // The whole estimate: every PoseEstimate field is required
        // (pose.py:80-113). The timestamp is stamped at send time rather
        // than when the form was first rendered.
        pose: { ...form, timestamp_utc: new Date().toISOString() },
        // Echoing both closes the loop the way the backend documents it:
        // corridor_id pins the judgement to THIS route rather than whichever
        // plan ran last, and along_track_m is the progress prior that stops a
        // switchback's outbound leg from capturing a pose on the return leg.
        corridor_id: corridor?.corridor_id,
        previous_along_track_m: result?.corridor_fix.along_track_m,
      })
      setResult(response)
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Pose evaluation failed')
    } finally {
      setBusy(false)
    }
  }, [corridor, form, result])

  const rows = useMemo<PoseTriggerRow[]>(() => {
    if (!result) return []
    const fired = new Map(result.fired_triggers.map((t) => [t.trigger_id, t.detail]))
    // Same object shape as /api/replan, plus a `reason` this endpoint fills
    // in when it can explain the absence (localization.py:317-327).
    const skipped = new Map<string, SkippedTrigger>(
      result.skipped.map((entry) => [entry.trigger_id, entry]),
    )

    return TRIGGER_IDS.map((id) => {
      if (fired.has(id)) return { id, status: 'fired' as const, detail: fired.get(id) ?? null }
      const skip = skipped.get(id)
      if (skip) {
        const missing = skip.missing.length
          ? `Missing telemetry: ${skip.missing.join(', ')}`
          : 'Telemetry field missing'
        return {
          id,
          status: 'unchecked' as const,
          detail: skip.reason ? `${missing} — ${skip.reason}` : missing,
        }
      }
      return { id, status: 'clear' as const, detail: null }
    })
  }, [result])

  return { form, setField, seedFromCorridor, submit, result, busy, error, rows, corridor }
}
