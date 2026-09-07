/**
 * The full telemetry record for the cell the pointer settled on.
 *
 * `useFocusTelemetry()` already follows the pointer, but it publishes eight
 * derived values and drops the rest of the response: App fetches the whole
 * `CellTelemetryResponse`, reads latitude, elevation and temperature out of
 * it, and lets the roughness, PSR and safe-haven blocks fall on the floor.
 * This asks again for what it needs rather than widening the focus contract,
 * which is a 33 ms value that a dozen consumers read.
 *
 * The debounce is what makes that affordable, and it also gives the two
 * readouts the right feel: the coordinate block under the map tracks the
 * pointer live, while the detail panel settles on the cell you stopped on.
 * Chasing a moving pointer with a request per frame would be both a worse
 * panel and a request storm.
 */

import { useEffect, useState } from 'react'

import { fetchCellTelemetry } from '../../api'
import { useFocusTelemetry, useMission } from '../../mission/MissionContext'
import { hasMissionEpoch } from '../../mission/missionTime'
import { isDataUnavailable } from '../../net/errors'
import {
  CAPABILITY_IDLE,
  CAPABILITY_LOADING,
  capabilityFromError,
  capabilityReady,
  type Capability,
} from '../../mission/capability'
import type { CellTelemetryResponse } from '../../net/types'

/** Long enough that a pointer crossing the map fires nothing. */
const SETTLE_MS = 220

export type CellDetail = Capability<CellTelemetryResponse>

export function useCellDetail(): CellDetail {
  const focus = useFocusTelemetry()
  const { roverId, missionTime, goal } = useMission()
  const [detail, setDetail] = useState<CellDetail>(CAPABILITY_IDLE)

  // The epoch is what turns the safe-haven block on. Without it the backend
  // answers `safe_haven: null` and says why in `safe_haven_model.reason`,
  // which the panel shows rather than hiding the row.
  const startUtc = hasMissionEpoch(missionTime) ? missionTime.startUtc : null

  useEffect(() => {
    if (!Number.isFinite(focus.row) || !Number.isFinite(focus.col)) {
      setDetail(CAPABILITY_IDLE)
      return
    }

    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setDetail(CAPABILITY_LOADING)
      fetchCellTelemetry(focus.row, focus.col, controller.signal, {
        roverId,
        startUtc,
        // Both are opt-in on the backend and cost real compute, so they are
        // asked for only when their inputs exist. Survival's `leg` safe set is
        // defined against a goal: without one the backend answers 422, and a
        // 422 for a question we chose to ask badly is not worth showing.
        survival: startUtc !== null && goal !== null,
        goal,
        thermalDwell: startUtc !== null,
      })
        .then((response) => {
          if (controller.signal.aborted) return
          setDetail(capabilityReady(response))
        })
        .catch((error: unknown) => {
          const next = capabilityFromError(error, {
            isDataUnavailable: isDataUnavailable(error),
            signal: controller.signal,
          })
          if (next) setDetail(next)
        })
    }, SETTLE_MS)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [focus.row, focus.col, roverId, startUtc, goal])

  return detail
}
