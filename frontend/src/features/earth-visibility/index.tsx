import { capabilityMessage, capabilityValue } from '../../mission/capability'
import { readCommWindow } from './format'
import { useEarthVisibility } from './useEarthVisibility'
import './earth-visibility.css'

/**
 * A4, in the Systems & Evidence drawer.
 *
 * Two readouts over one epoch: the link at the cell under the pointer, and the
 * site's link fraction over a synodic month. The second is what makes the
 * first legible -- at 88.6 degrees south with an eighteen-degree ridge to the
 * north, the Earth is below the horizon over 90% of the time, and a single
 * "no signal" reading without that context looks like a fault.
 *
 * The `earth_visibility` raster lives in the analysis-layer toggles, not here:
 * it is a long-run average rather than a moment, and it answers no question
 * about time.
 */
export function EarthVisibility() {
  const state = useEarthVisibility()
  const series = capabilityValue(state.series)
  const window_ = capabilityValue(state.window)
  const seriesMessage = capabilityMessage(state.series)
  const windowMessage = capabilityMessage(state.window)
  const reading = window_ ? readCommWindow(window_) : null
  const slice = series?.earth[state.sliceIndex] ?? null
  const isStatic = series?.earth_model.model === 'static'

  return (
    <section className="rail-section">
      <p className="panel-kicker">Earth visibility</p>

      {state.needsEpoch && (
        <p className="ev-note">
          Needs a mission epoch. Where the Earth sits depends on when you ask,
          so there is nothing to compute until the mission clock is set.
        </p>
      )}

      {/* The link at the cell under the pointer. */}
      {reading && window_ && (
        <div className="ev-window">
          <p className={`ev-headline ${window_.visible_now ? 'is-up' : 'is-down'}`}>
            {reading.headline}
          </p>
          <p className="ev-detail">{reading.detail}</p>

          <dl className="ev-facts">
            <div>
              <dt>Earth elevation</dt>
              <dd className="ev-mono">{window_.earth_elevation_deg.toFixed(2)}°</dd>
            </div>
            <div>
              <dt>Terrain horizon</dt>
              <dd className="ev-mono">{window_.horizon_deg.toFixed(2)}°</dd>
            </div>
            <div>
              <dt>Azimuth</dt>
              <dd className="ev-mono">{window_.earth_azimuth_true_deg.toFixed(1)}°</dd>
            </div>
            <div>
              <dt>Cell</dt>
              <dd className="ev-mono">
                {window_.row}, {window_.col}
              </dd>
            </div>
          </dl>

          {/*
            A bounded answer is a different claim from an unbounded one, and
            the difference is not visible in the number. Said outright.
          */}
          {reading.bounded && (
            <p className="ev-note">
              Bounded by a {(window_.searched_hours / 24).toFixed(0)}-day search at{' '}
              {window_.step_minutes.toFixed(0)}-minute steps. A change beyond that
              horizon is not reported — it is not ruled out.
            </p>
          )}
        </div>
      )}

      {/* The site over a synodic month. */}
      {series && (
        <div className="ev-series">
          <p className="ev-sub">
            Link fraction across the site
            {/* The epoch the slices are counted from. Without it the strip is
                a shape with no date on it. */}
            {series.start_utc && (
              <span className="ev-epoch"> from {series.start_utc.slice(0, 10)}</span>
            )}
          </p>

          {/*
            One bar per slice, height = share of the grid with a link. The
            current slice is marked rather than the strip being cropped to it:
            the shape of the month is the point, and a single slice's number
            without it is unreadable.
          */}
          <div className="ev-strip" role="img" aria-label="Earth link fraction per day">
            {series.earth.map((entry) => (
              <span
                key={entry.index}
                className={`ev-bar ${entry.index === state.sliceIndex ? 'is-current' : ''}`}
                style={{ height: `${Math.max(entry.visible_fraction * 100, 1.5)}%` }}
                title={`${entry.utc.slice(0, 10)} — ${(entry.visible_fraction * 100).toFixed(1)}%`}
              />
            ))}
          </div>

          {slice && (
            <p className="ev-detail">
              <span className="ev-mono">{(slice.visible_fraction * 100).toFixed(1)}%</span> of
              the site has a link on {slice.utc.slice(0, 10)}, with the Earth at{' '}
              <span className="ev-mono">{slice.elevation_deg.toFixed(2)}°</span>.
            </p>
          )}

          {/* Real data that does not vary with time is not missing data, but
              a timeline drawn from it would imply variation it does not have. */}
          {isStatic && (
            <p className="ev-note">
              Static model: no epoch behind these slices, so every one repeats
              the long-run layer. {series.earth_model.reason ?? ''}
            </p>
          )}
        </div>
      )}

      {seriesMessage && !state.needsEpoch && (
        <p className={`ev-note ${state.series.status === 'error' ? 'is-error' : ''}`}>
          {seriesMessage}
        </p>
      )}
      {windowMessage && state.window.status === 'error' && (
        <p className="ev-note is-error">{windowMessage}</p>
      )}
    </section>
  )
}

export default EarthVisibility
