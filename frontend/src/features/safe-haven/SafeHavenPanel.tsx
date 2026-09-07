import { capabilityMessage, capabilityValue } from '../../mission/capability'
import { SAFE_HAVEN_VIEWS, type SafeHavenState } from './useSafeHaven'

/**
 * A1, in the Systems & Evidence drawer.
 *
 * A safe haven is a claim about survival, so the panel leads with the rule the
 * backend applied and the rover it applied it for, not with the map. The
 * numbers underneath are what that rule found on this window: a tenth of the
 * traversable ground, and a fifth of the grid with no reachable haven at all.
 * Both of those are the finding.
 */
export function SafeHavenPanel({
  enabled,
  setEnabled,
  view,
  setView,
  manifest,
  field,
  needsEpoch,
}: SafeHavenState) {
  const data = capabilityValue(manifest)
  const manifestMessage = capabilityMessage(manifest)
  const fieldMessage = capabilityMessage(field)
  const remedy = manifest.status === 'unavailable' ? manifest.remedy : null

  return (
    <section className="rail-section">
      <p className="panel-kicker">Safe haven</p>

      <label className="sh-toggle">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
          disabled={needsEpoch}
        />
        <span>Show on map</span>
      </label>

      {/*
        No epoch, no haven -- said plainly rather than by disabling a control
        with no explanation.

        The mission clock is seeded, so this branch is normally unreachable. It
        stays because the clock is a value anything can set, and a cleared one
        must degrade to a sentence rather than to an empty map that looks like
        a site with no havens in it.
      */}
      {needsEpoch && (
        <p className="sh-note">
          Needs a mission epoch. A safe haven is defined against the Earth’s and
          the Sun’s motion over a synodic month, so there is nothing to compute
          until the mission clock is set.
        </p>
      )}

      {enabled && !needsEpoch && (
        <div className="sh-views" role="group" aria-label="Safe haven field">
          {SAFE_HAVEN_VIEWS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              className={`sh-view-btn ${view === entry.id ? 'is-active' : ''}`}
              onClick={() => setView(entry.id)}
              title={entry.blurb}
            >
              {entry.label}
            </button>
          ))}
        </div>
      )}

      {enabled && (
        <p className="sh-blurb">
          {SAFE_HAVEN_VIEWS.find((entry) => entry.id === view)?.blurb}
        </p>
      )}

      {data && (
        <>
          <dl className="sh-facts">
            <div>
              <dt>Havens</dt>
              <dd className="sh-mono">
                {data.safe_haven_cells.toLocaleString()} cells
                <span className="sh-sub">
                  {(data.safe_haven_fraction * 100).toFixed(1)}% of traversable
                </span>
              </dd>
            </div>
            <div>
              <dt>Earth below</dt>
              <dd className="sh-mono">
                {(data.earth_below_fraction * 100).toFixed(1)}%
                <span className="sh-sub">of the {data.span_hours.toFixed(0)} h window</span>
              </dd>
            </div>
            <div>
              <dt>Rover shadow limit</dt>
              <dd className="sh-mono">
                {data.h_max_shadow_h.toFixed(0)} h
                <span className="sh-sub">{data.rover_name}</span>
              </dd>
            </div>
            <div>
              <dt>Sampling</dt>
              <dd className="sh-mono">
                {data.n_steps} steps
                <span className="sh-sub">every {data.step_hours.toFixed(1)} h</span>
              </dd>
            </div>
            {/*
              Which epoch this map is. Everything above is a function of it,
              and an operator who cannot see it cannot tell a haven map for
              next May from one for today.
            */}
            {data.start_utc && (
              <div>
                <dt>Epoch</dt>
                <dd className="sh-mono">
                  {data.start_utc.slice(0, 10)}
                  <span className="sh-sub">{data.start_utc.slice(11, 16)} UTC</span>
                </dd>
              </div>
            )}
          </dl>

          {/*
            The share of the grid that CAN reach a haven, published because its
            complement is the finding: on this window roughly a fifth of cells
            cannot reach one at all, and those are exactly the cells the map
            leaves unpainted. Without this line an operator would have to infer
            that from an absence.
          */}
          {typeof data.safe_haven_model.time_to_haven_finite_fraction === 'number' && (
            <p className="sh-note">
              {(
                (1 - (data.safe_haven_model.time_to_haven_finite_fraction as number)) *
                100
              ).toFixed(1)}
              % of cells can reach no haven at all. Those are drawn blank on the
              time-to-haven view — not as zero hours, which would mean the
              opposite.
            </p>
          )}

          {typeof data.safe_haven_model.rule === 'string' && (
            <p className="sh-note sh-rule">{data.safe_haven_model.rule as string}</p>
          )}
        </>
      )}

      {/* Why there is nothing to show, in the backend's own words. */}
      {manifestMessage && !needsEpoch && (
        <p className={`sh-note ${manifest.status === 'error' ? 'is-error' : ''}`}>
          {manifestMessage}
        </p>
      )}
      {remedy && <code className="sh-remedy">{remedy}</code>}

      {/* A manifest can be fine while one field's payload is not. */}
      {fieldMessage && field.status === 'error' && (
        <p className="sh-note is-error">{fieldMessage}</p>
      )}
    </section>
  )
}
