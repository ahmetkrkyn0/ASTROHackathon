import { useCallback, useMemo, useState } from 'react'
import { requestReplan } from '../../net/replan'
import { useMission } from '../../mission/MissionContext'
import type { ReplanResponse, SkippedTrigger, TriggerId } from '../../net/types'
import {
  TRIGGER_IDS,
  initialTelemetry,
  telemetryPayload,
  type TelemetryValue,
} from '../../mission/triggers'

export type TriggerStatus = 'fired' | 'clear' | 'unchecked'

export interface TriggerRow {
  id: TriggerId
  status: TriggerStatus
  detail: string | null
}

export function useReplan() {
  const { start, goal, roverId, weights } = useMission()
  const [form, setForm] = useState<Record<string, TelemetryValue>>(initialTelemetry)
  const [result, setResult] = useState<ReplanResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const setField = useCallback((key: string, value: TelemetryValue) => {
    setForm((current) => ({ ...current, [key]: value }))
  }, [])

  const submit = useCallback(
    async (force: boolean) => {
      if (!start || !goal) {
        setError('Pick a start and a goal first — a replan starts from where the rover is.')
        return
      }
      setBusy(true)
      setError(null)
      try {
        const response = await requestReplan({
          current: { row: start[0], col: start[1] },
          goal: { row: goal[0], col: goal[1] },
          rover_id: roverId,
          weights,
          state: telemetryPayload(form),
          force,
        })
        setResult(response)
      } catch (cause: unknown) {
        setError(cause instanceof Error ? cause.message : 'Replan request failed')
      } finally {
        setBusy(false)
      }
    },
    [form, goal, roverId, start, weights],
  )

  const rows = useMemo<TriggerRow[]>(() => {
    if (!result) return []
    const fired = new Map(result.triggers.map((t) => [t.trigger_id, t.detail]))
    // skipped carries objects, not ids (replan_triggers.py:219-223). Keyed by
    // trigger_id so the lookup below actually matches -- a Set of the raw
    // entries would never contain a plain id, and every unevaluated trigger
    // would fall through to "clear".
    const skipped = new Map<string, SkippedTrigger>(
      result.skipped.map((entry) => [entry.trigger_id, entry]),
    )

    return TRIGGER_IDS.map((id) => {
      if (fired.has(id)) {
        return { id, status: 'fired' as const, detail: fired.get(id) ?? null }
      }
      // A trigger the backend could NOT evaluate is never "clear". Missing
      // telemetry once answered "no replan needed" at 1% battery; the
      // backend reports it in `skipped` precisely so a client cannot repeat
      // that (main.py:748-763).
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

  return { form, setField, submit, result, busy, error, rows }
}
