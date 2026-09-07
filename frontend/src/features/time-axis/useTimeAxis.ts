import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { planRoute4D } from '../../net/plan4d'
import { fetchSeriesCube, fetchSeriesManifest, type SeriesCube } from '../../net/series'
import { useMission } from '../../mission/MissionContext'
import { cleanShadowReason } from './reason'
import { SESSION_MISSION_TIME } from '../../mission/missionTime'
import { useLayerAvailability } from '../../mission/useLayerAvailability'
import {
  applyPlanRequestContributors,
  type PlanRequestContext,
} from '../plan-request/contributors'
import type { Plan4DResponse, SeriesManifest } from '../../net/types'

export type SeriesField = 'shadow' | 'surface_temp_c'

/**
 * The forward constraints A owns, as the 4-D planner takes them.
 *
 * They live beside the button that uses them rather than in each layer's
 * own panel. A toggle in the safe-haven card that silently changed what a
 * button in a different panel sent would be worse than the cross-feature
 * coupling it saved, and these are planner inputs, not layer settings.
 *
 * All three default OFF, and an off constraint contributes no field at all
 * -- the request stays byte-identical to what the cockpit sent before any
 * of this existed. `planRequest.nonregression.test.ts` pins that down.
 */
export interface PlanConstraints {
  requireEarthVisibility: boolean
  requireSafeHaven: boolean
  requireIlluminationCorridor: boolean
  /** So the shape satisfies the contributor context, which reads by name. */
  [key: string]: boolean
}

const NO_CONSTRAINTS: PlanConstraints = {
  requireEarthVisibility: false,
  requireSafeHaven: false,
  requireIlluminationCorridor: false,
}

const N_SLICES = 24
/**
 * Six hours a slice, so 24 slices span six days.
 *
 * Not one hour. A lunar day is ~29.5 Earth days, so at this polar site a
 * 24-hour window does not change at all: the backend reports shadow min and
 * max both exactly 1.0 across every slice, and the animation plays 24
 * identical frames. Over six days the same request spans shadow 0.0-1.0 and
 * surface temperature -183 to +41 C, which is the illumination this panel
 * exists to show.
 */
const SLICE_HOURS = 6
// 24 x 500 x 500 x 4 B is 24 MB per field. Halving each axis makes it 6 MB,
// which is what a slider scrubbing at 10 fps can afford to keep resident.
const DOWNSAMPLE = 2

/*
 * The epoch this panel anchors to is the mission clock's, not its own.
 *
 * It used to be a module-level `new Date()` here. Five other products --
 * safe haven, Earth visibility, uncertainty, corridor, thermal dwell -- vary
 * over the same axis, and each holding its own instant would put two layers
 * on one map showing two different moments, which looks exactly like two
 * layers showing one. `SESSION_MISSION_TIME` is now that single instant and
 * this panel reads it like everything else (spec 5.8). Without an epoch the
 * backend holds the shadow field constant and says so -- shadow_model.model
 * comes back "static" -- which the honesty gate below already checks for.
 */

/**
 * Slice budget for the 4-D plan.
 *
 * Deliberately large. The planner derives its own slice length from the grid
 * (cost_cube.auto_slice_hours, ~0.03 h here) because a fixed hour was longer
 * than any real edge traversal and made every move round up to a whole slice.
 * A move therefore costs one slice, so the slice count is a move budget: at
 * 24 the backend answers "the shortest gated coarse route needs at least 96
 * moves" and no route can ever fit.
 */
const PLAN_SLICES = 256

export function useTimeAxis() {
  const { start, goal, roverId, weights, missionTime } = useMission()

  // The shared clock. `SESSION_MISSION_TIME` seeds it, so this is set from
  // the first render; the fallback covers a caller that cleared it.
  const startUtc = missionTime.startUtc ?? SESSION_MISSION_TIME.startUtc ?? ''

  const [manifest, setManifest] = useState<SeriesManifest | null>(null)
  const [cube, setCube] = useState<SeriesCube | null>(null)
  const [field, setField] = useState<SeriesField>('shadow')
  /**
   * Whether the field is painted over the terrain.
   *
   * Off by default, and that is the whole point. The layer used to appear the
   * moment ANALYZE mounted, without anyone asking for it: the shadow ramp runs
   * white to black, so the same DEM arrived roughly 50 levels darker in
   * shadowed ground than it had been one tab earlier, and the map read as
   * having had its lighting turned off rather than as carrying a measurement.
   *
   * Separate from `field` rather than folded into it as an 'off' member: the
   * field name drives which cube is fetched, and a viewer who turns the layer
   * on should not then wait for a download that could have happened while
   * they were reading the route. The cube still loads; only the paint is
   * withheld.
   */
  const [fieldVisible, setFieldVisible] = useState(false)
  const [sliceIndex, setSliceIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [plan4d, setPlan4d] = useState<Plan4DResponse | null>(null)
  const [planning, setPlanning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const timerRef = useRef<number | null>(null)

  // Manifest first, cube second: the manifest publishes the binary_url and
  // the shape the cube must fill, so neither is guessed.
  useEffect(() => {
    const controller = new AbortController()
    setError(null)

    fetchSeriesManifest(
      {
        startUtc,
        nSlices: N_SLICES,
        sliceHours: SLICE_HOURS,
        downsample: DOWNSAMPLE,
      },
      controller.signal,
    )
      .then(async (next) => {
        setManifest(next)
        const entry = next.fields[field]
        const loaded = await fetchSeriesCube(
          entry.binary_url,
          { slices: next.slices, rows: next.grid.rows, cols: next.grid.cols },
          controller.signal,
        )
        setCube(loaded)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(cause instanceof Error ? cause.message : 'Illumination series unavailable')
      })

    return () => controller.abort()
    // startUtc as well as field: a cube fetched against one epoch describes
    // a different sky than a manifest fetched against another, and the
    // mission clock is now something else can move.
  }, [field, startUtc])

  const stop = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!playing || !cube) {
      stop()
      return
    }
    timerRef.current = window.setInterval(() => {
      setSliceIndex((current) => (current + 1) % cube.slices)
    }, 120)
    return stop
  }, [cube, playing, stop])

  useEffect(() => stop, [stop])

  const togglePlay = useCallback(() => setPlaying((current) => !current), [])

  const [constraints, setConstraints] = useState<PlanConstraints>(NO_CONSTRAINTS)
  const layers = useLayerAvailability(roverId, weights)

  /*
   * What the backend can actually enforce here.
   *
   * A4 needs the earth_visibility layer; without it plan-4d answers 422.
   * A1 and A2 are computed from the horizon cube rather than a manifest
   * layer, and the honest proxy for "the cube exists" is that the shadow
   * series came back time-varying: a static series means no epoch reached
   * SPICE, and neither deadline nor corridor can be built from it.
   */
  const shadowIsTimeVarying =
    manifest !== null && manifest.shadow_model.model !== 'static'

  /*
   * Why a constraint cannot be enforced, in words, not just a disabled button.
   *
   * The two reasons are different and were previously collapsed into one
   * tooltip that said "not available on this deployment" -- which for the
   * static case is a misdiagnosis: the data is installed, the ephemeris just
   * did not resolve for this epoch. A control that goes dark without saying
   * why sends the operator looking for a missing file that is not missing.
   *
   * The static reason is the backend's own sentence, run through
   * cleanShadowReason first: when SPICE fails it arrives as a whole CSPICE
   * error banner, and a toolkit dump under a button is not an explanation.
   */
  const constraintReasons = useMemo<Record<string, string | null>>(() => {
    const staticReason = !shadowIsTimeVarying
      ? manifest === null
        ? 'The illumination series has not loaded yet.'
        : `The shadow series came back static, so there is no time axis to enforce this against.${
            cleanShadowReason(manifest.shadow_model.reason)
              ? ' ' + cleanShadowReason(manifest.shadow_model.reason)
              : ''
          }`
      : null
    return {
      'earth-visibility': layers.has('earth_visibility')
        ? null
        : 'The earth_visibility layer is not loaded on this deployment.',
      'safe-haven': staticReason,
      'illumination-corridor': staticReason,
    }
  }, [layers, manifest, shadowIsTimeVarying])

  // The boolean view the plan-request contributors take.
  const constraintAvailable = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(constraintReasons).map(([key, reason]) => [key, reason === null]),
      ),
    [constraintReasons],
  )

  const toggleConstraint = useCallback((key: keyof PlanConstraints) => {
    setConstraints((previous) => ({ ...previous, [key]: !previous[key] }))
  }, [])

  const runPlan4D = useCallback(async () => {
    if (!start || !goal) {
      setError('Pick a start and a goal first.')
      return
    }
    setPlanning(true)
    setError(null)
    try {
      const base = {
        start: { row: start[0], col: start[1] },
        goal: { row: goal[0], col: goal[1] },
        rover_id: roverId,
        weights,
        n_slices: PLAN_SLICES,
        coarsen: 4,
        // slice_hours is deliberately omitted: the backend derives it from
        // the grid, and a hand-picked value made the time axis count steps
        // instead of hours (Faz 3 review, C1).
        start_utc: startUtc,
      }
      // Every advanced constraint enters here and nowhere else. With all of
      // them off this returns `base` unchanged, which is the non-regression
      // rule holding at the one call site that could break it.
      const context: PlanRequestContext = {
        endpoint: 'plan-4d',
        constraints,
        available: constraintAvailable,
      }
      const response = await planRoute4D(
        applyPlanRequestContributors(base, context),
      )
      setPlan4d(response)
    } catch (cause: unknown) {
      // The backend's 404 detail is the useful part -- it names how many
      // moves the shortest gated route needs against how many slices were
      // offered. client.ts already lifts `detail` into the message.
      setError(cause instanceof Error ? cause.message : '4-D plan failed')
    } finally {
      setPlanning(false)
    }
  }, [goal, roverId, start, weights, startUtc, constraints, constraintAvailable])

  // "static" means the cube did NOT vary with time. Playing it would be a
  // lie told at 8 fps (spec T7). Unknown until the manifest lands, so this
  // is false rather than true while loading.
  const timeVarying = manifest !== null && manifest.shadow_model.model !== 'static'

  return {
    fieldVisible,
    setFieldVisible,
    manifest,
    cube,
    field,
    setField,
    sliceIndex,
    setSliceIndex,
    playing,
    togglePlay,
    plan4d,
    planning,
    runPlan4D,
    error,
    timeVarying,
    constraints,
    toggleConstraint,
    constraintAvailable,
    constraintReasons,
  }
}
