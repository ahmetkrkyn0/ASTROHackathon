import { useCallback, useEffect, useRef, useState } from 'react'
import { planRoute4D } from '../../net/plan4d'
import { fetchSeriesCube, fetchSeriesManifest, type SeriesCube } from '../../net/series'
import { useMission } from '../../mission/MissionContext'
import type { Plan4DResponse, SeriesManifest } from '../../net/types'

export type SeriesField = 'shadow' | 'surface_temp_c'

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

/**
 * The epoch the whole panel is anchored to, taken once when the module loads.
 *
 * Illumination is a function of time, so without a start epoch the backend
 * holds the shadow field constant and says so: shadow_model.model comes back
 * "static" with reason "no start epoch given". Both the series and the 4-D
 * plan need it, and they need the SAME one, or the route would be solved
 * against a different sky than the one being drawn.
 */
const START_UTC = new Date().toISOString()

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
  const { start, goal, roverId, weights } = useMission()

  const [manifest, setManifest] = useState<SeriesManifest | null>(null)
  const [cube, setCube] = useState<SeriesCube | null>(null)
  const [field, setField] = useState<SeriesField>('shadow')
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
        startUtc: START_UTC,
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
  }, [field])

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

  const runPlan4D = useCallback(async () => {
    if (!start || !goal) {
      setError('Pick a start and a goal first.')
      return
    }
    setPlanning(true)
    setError(null)
    try {
      const response = await planRoute4D({
        start: { row: start[0], col: start[1] },
        goal: { row: goal[0], col: goal[1] },
        rover_id: roverId,
        weights,
        n_slices: PLAN_SLICES,
        coarsen: 4,
        // slice_hours is deliberately omitted: the backend derives it from
        // the grid, and a hand-picked value made the time axis count steps
        // instead of hours (Faz 3 review, C1).
        start_utc: START_UTC,
      })
      setPlan4d(response)
    } catch (cause: unknown) {
      // The backend's 404 detail is the useful part -- it names how many
      // moves the shortest gated route needs against how many slices were
      // offered. client.ts already lifts `detail` into the message.
      setError(cause instanceof Error ? cause.message : '4-D plan failed')
    } finally {
      setPlanning(false)
    }
  }, [goal, roverId, start, weights])

  // "static" means the cube did NOT vary with time. Playing it would be a
  // lie told at 8 fps (spec T7). Unknown until the manifest lands, so this
  // is false rather than true while loading.
  const timeVarying = manifest !== null && manifest.shadow_model.model !== 'static'

  return {
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
  }
}
