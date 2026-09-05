import type { Plan4DResponse, SeriesManifest } from '../../net/types'
import { cleanShadowReason } from './reason'
import type { SeriesField } from './useTimeAxis'
import './time-axis.css'

export function TimeAxisPanel({
  manifest,
  field,
  setField,
  fieldVisible,
  setFieldVisible,
  sliceIndex,
  setSliceIndex,
  playing,
  togglePlay,
  plan4d,
  planning,
  runPlan4D,
  error,
  timeVarying,
}: {
  manifest: SeriesManifest | null
  field: SeriesField
  setField: (next: SeriesField) => void
  fieldVisible: boolean
  setFieldVisible: (next: boolean) => void
  sliceIndex: number
  setSliceIndex: (next: number) => void
  playing: boolean
  togglePlay: () => void
  plan4d: Plan4DResponse | null
  planning: boolean
  runPlan4D: () => void
  error: string | null
  timeVarying: boolean
}) {
  const sun = manifest?.sun[sliceIndex] ?? null
  const hours = manifest ? sliceIndex * manifest.slice_hours : 0
  const shadowReason = cleanShadowReason(manifest?.shadow_model.reason)

  return (
    <div className="lp-time-card">
      <div className="lp-time-row">
        <button type="button" className="lp-time-play" onClick={togglePlay}
          disabled={!manifest || !timeVarying}>
          {playing ? '❚❚' : '▶'}
        </button>

        <input
          className="lp-time-slider"
          type="range"
          min={0}
          max={manifest ? manifest.slices - 1 : 0}
          value={sliceIndex}
          onChange={(event) => setSliceIndex(Number(event.target.value))}
          disabled={!manifest}
        />

        <span className="lp-time-clock">+{hours.toFixed(1)} h</span>

        {/* The field is a layer, so it is switched on like one. It used to
            paint itself over the terrain the moment ANALYZE mounted, which
            made the same DEM look like a darker place than it had been one
            tab earlier -- a measurement nobody had asked to see, arriving as
            what looked like the lighting being turned off. */}
        <label className="lp-time-layer-toggle">
          <input
            type="checkbox"
            checked={fieldVisible}
            onChange={(event) => setFieldVisible(event.target.checked)}
          />
          Layer
        </label>

        <select
          className="lp-time-field"
          value={field}
          onChange={(event) => setField(event.target.value as SeriesField)}
          disabled={!fieldVisible}
        >
          <option value="shadow">Shadow</option>
          <option value="surface_temp_c">Surface temp</option>
        </select>

        <button type="button" className="lp-time-plan" onClick={runPlan4D} disabled={planning}>
          {planning ? 'Planning…' : 'Plan through time'}
        </button>
      </div>

      {/* The honesty gate. A static cube gets said out loud, not animated.
          The reason comes from the response rather than being guessed at:
          the usual cause is a request with no epoch, not a missing cache. It
          goes through cleanShadowReason first -- when the backend has no SPICE
          kernels loaded the field arrives carrying the whole CSPICE error
          banner, and a toolkit dump in the dock is an environment error shown
          to an operator, which section 29 rules out. */}
      {/* Stated as a fact, not as a warning. There is nothing the operator can
          do about a static cube, and a caution colour that is always on and
          never resolves is how an interface teaches that its warnings can be
          ignored. The warning tone is reserved for what needs acting on. */}
      {manifest && !timeVarying ? (
        <p className="lp-time-note">
          No time series — this cube does not vary with time, so it is not
          animated.
          {shadowReason ? ` ${shadowReason}` : ''}
        </p>
      ) : null}

      {sun ? (
        <p className="lp-time-note">
          Sun: {sun.elevation_deg.toFixed(2)}° elevation ·{' '}
          {sun.azimuth_grid_deg.toFixed(1)}° grid azimuth · {sun.utc}
        </p>
      ) : null}

      {plan4d ? (
        <p className="lp-time-verdict">
          {plan4d.metrics.wait_steps > 0 ? (
            <>
              <strong>The planner chose to wait.</strong> {plan4d.metrics.wait_steps} wait
              step(s), {plan4d.metrics.move_steps} move step(s); arrival at{' '}
              {plan4d.metrics.arrival_hours?.toFixed(1) ?? '—'} h over a{' '}
              {plan4d.horizon_hours.toFixed(0)} h window.
            </>
          ) : (
            <>
              No waiting: {plan4d.metrics.move_steps} move step(s).{' '}
              {plan4d.shadow_model.model === 'static'
                ? 'The cube was static, so waiting could not have helped.'
                : 'Waiting would not have paid off on this route.'}
            </>
          )}
        </p>
      ) : null}

      {error ? (
        <p className="lp-time-note lp-time-warn">{cleanShadowReason(error) ?? error}</p>
      ) : null}
    </div>
  )
}
