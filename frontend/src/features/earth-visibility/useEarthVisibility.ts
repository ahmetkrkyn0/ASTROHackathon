/**
 * A4 -- when the direct-to-Earth link is open, here and over the window.
 *
 * Two questions with two different shapes. `GET /api/comm-window` answers "at
 * this cell, right now, and how long" and follows the pointer. `GET
 * /api/earth-series` answers "across the whole site, slice by slice" and feeds
 * a timeline. Both need an epoch, and neither invents one.
 *
 * The `earth_visibility` raster is a third thing again -- a long-run average,
 * not a moment -- and it belongs to the analysis-layers toggles rather than
 * here, because it is a layer and answers no question about time.
 */

import { useEffect, useState } from 'react'

import { useMission } from '../../mission/MissionContext'
import { hasMissionEpoch, missionTimeSliceIndex, missionTimeUtc } from '../../mission/missionTime'
import { useFocusTelemetry } from '../../mission/MissionContext'
import {
  CAPABILITY_IDLE,
  CAPABILITY_LOADING,
  capabilityFromError,
  capabilityFromModel,
  capabilityValue,
  type Capability,
} from '../../mission/capability'
import { isDataUnavailable } from '../../net/errors'
import {
  fetchCommWindow,
  fetchEarthSeries,
  type CommWindow,
  type EarthSeriesManifest,
} from '../../net/analysis'

/** 28 days at one slice a day: a full synodic month, which is the period. */
const N_SLICES = 28
const SLICE_HOURS = 24
/** The series is only read for its per-slice fractions here, not drawn. */
const DOWNSAMPLE = 8
/** Long enough that a pointer crossing the map fires no requests. */
const SETTLE_MS = 260

export interface EarthVisibilityState {
  readonly series: Capability<EarthSeriesManifest>
  readonly window: Capability<CommWindow>
  /** Which slice of the series the mission clock is in. */
  readonly sliceIndex: number
  /** True when the mission clock has no epoch, which is why nothing loaded. */
  readonly needsEpoch: boolean
  readonly focusCell: { row: number; col: number }
}

export function useEarthVisibility(): EarthVisibilityState {
  const { missionTime } = useMission()
  const focus = useFocusTelemetry()
  const [series, setSeries] = useState<Capability<EarthSeriesManifest>>(CAPABILITY_IDLE)
  const [window_, setWindow] = useState<Capability<CommWindow>>(CAPABILITY_IDLE)

  const startUtc = hasMissionEpoch(missionTime) ? missionTime.startUtc : null
  const needsEpoch = startUtc === null
  const utcNow = missionTimeUtc(missionTime)

  useEffect(() => {
    if (!startUtc) {
      setSeries(CAPABILITY_IDLE)
      return
    }

    const controller = new AbortController()
    setSeries(CAPABILITY_LOADING)

    fetchEarthSeries(
      { startUtc, nSlices: N_SLICES, sliceHours: SLICE_HOURS, downsample: DOWNSAMPLE },
      controller.signal,
    )
      .then((response) => {
        if (controller.signal.aborted) return
        // `static` is not unavailable -- it is real data that does not vary
        // with time, and the timeline says so rather than hiding.
        setSeries(capabilityFromModel(response.earth_model, response))
      })
      .catch((error: unknown) => {
        const next = capabilityFromError(error, {
          isDataUnavailable: isDataUnavailable(error),
          signal: controller.signal,
        })
        if (next) setSeries(next)
      })

    return () => controller.abort()
  }, [startUtc])

  useEffect(() => {
    if (!utcNow || !Number.isFinite(focus.row) || !Number.isFinite(focus.col)) {
      setWindow(CAPABILITY_IDLE)
      return
    }

    const controller = new AbortController()
    const timer = globalThis.setTimeout(() => {
      setWindow(CAPABILITY_LOADING)
      fetchCommWindow(focus.row, focus.col, utcNow, controller.signal)
        .then((response) => {
          if (controller.signal.aborted) return
          setWindow(capabilityFromModel({ model: 'spice_horizon' }, response))
        })
        .catch((error: unknown) => {
          const next = capabilityFromError(error, {
            isDataUnavailable: isDataUnavailable(error),
            signal: controller.signal,
          })
          if (next) setWindow(next)
        })
    }, SETTLE_MS)

    return () => {
      globalThis.clearTimeout(timer)
      controller.abort()
    }
  }, [focus.row, focus.col, utcNow])

  const manifest = capabilityValue(series)
  const sliceIndex = missionTimeSliceIndex(missionTime, manifest?.slices ?? 0)

  return {
    series,
    window: window_,
    sliceIndex,
    needsEpoch,
    focusCell: { row: focus.row, col: focus.col },
  }
}
