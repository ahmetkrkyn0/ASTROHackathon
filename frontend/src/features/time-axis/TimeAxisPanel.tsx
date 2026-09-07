import type { Plan4DResponse, SeriesManifest } from '../../net/types'
import { cleanShadowReason } from './reason'
import type { PlanConstraints, SeriesField } from './useTimeAxis'
import './time-axis.css'

/**
 * The three forward constraints A owns, with what each needs.
 *
 * `needs` names a capability id rather than a layer name: A1 and A2 are
 * built from the horizon cube, not from a manifest layer, so "is it there"
 * is a different question for each and the hook answers it.
 */
const CONSTRAINT_CONTROLS: Array<{
  key: keyof PlanConstraints
  label: string
  title: string
  needs: string
}> = [
  {
    key: 'requireEarthVisibility',
    label: 'Earth link',
    title: 'Every drive step must arrive in a cell that can see Earth. Waiting is never restricted.',
    needs: 'earth-visibility',
  },
  {
    key: 'requireSafeHaven',
    label: 'Haven deadline',
    title: 'The rover must always be able to reach a safe haven before the Earth sets.',
    needs: 'safe-haven',
  },
  {
    key: 'requireIlluminationCorridor',
    label: 'Stay lit',
    title: 'The route must stay inside the continuously illuminated corridor.',
    needs: 'illumination-corridor',
  },
]

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
  constraints,
  toggleConstraint,
  constraintAvailable,
  constraintReasons,
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
  constraints: PlanConstraints
  toggleConstraint: (key: keyof PlanConstraints) => void
  constraintAvailable: Readonly<Record<string, boolean>>
  constraintReasons: Readonly<Record<string, string | null>>
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

      {/*
        The forward constraints, beside the button that sends them.

        All three default off, and an off constraint adds no field to the
        request at all -- not `false`, which would override a documented
        backend default. One whose data is missing is disabled and says so,
        because sending the flag anyway earns a 422 that reads like a bug.
      */}
      <div className="lp-time-constraints">
        <span className="lp-time-constraints-label">Require</span>
        {CONSTRAINT_CONTROLS.map(({ key, label, title, needs }) => {
          const ready = constraintAvailable[needs] === true
          return (
            <button
              key={key}
              type="button"
              className={`lp-time-constraint ${constraints[key] ? 'is-on' : ''}`}
              onClick={() => toggleConstraint(key)}
              disabled={!ready}
              aria-pressed={constraints[key]}
              title={title}
            >
              {label}
            </button>
          )
        })}
      </div>

      {/*
        Why a control is dark, in visible text rather than a tooltip.

        This panel already learned that lesson once: RoutePriorities moved its
        weight explanations out of `title` because a tooltip reaches neither
        touch nor keyboard. A disabled button with a hidden reason is the same
        mistake with higher stakes -- the operator cannot even hover it to find
        out, and the honest answer here is usually "the backend degraded",
        not "you are missing a file".

        Deduplicated: `safe-haven` and `illumination-corridor` share one cause,
        and printing it twice would read as two separate problems.
      */}
      {(() => {
        const blocked = CONSTRAINT_CONTROLS.filter(
          (control) => constraintReasons[control.needs] !== null,
        )
        if (blocked.length === 0) return null
        const byReason = new Map<string, string[]>()
        for (const control of blocked) {
          const reason = constraintReasons[control.needs] as string
          byReason.set(reason, [...(byReason.get(reason) ?? []), control.label])
        }
        return (
          <div className="lp-time-constraint-notes">
            {[...byReason.entries()].map(([reason, labels]) => (
              <p key={reason} className="lp-time-constraint-note">
                <strong>{labels.join(' · ')}</strong> {reason}
              </p>
            ))}
          </div>
        )
      })()}

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
