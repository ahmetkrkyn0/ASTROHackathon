import { capabilityMessage, capabilityValue } from '../../mission/capability'
import { COARSE_FIELDS } from './fields'
import { categoryCounts } from './overlays'
import type { CoarseFieldsState } from './useCoarseFields'

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

/**
 * B1 survival and C6 thermal dwell, in the Systems & Evidence drawer.
 *
 * Both are MODEL, and the dwell's thermal lag is UNCALIBRATED on top of that.
 * Those two labels are the first thing the panel says, not a footnote: every
 * number below is the output of a model whose time constant nobody has
 * measured against hardware, and a reader who takes the dwell hours as
 * measured is reading something the backend never claimed.
 */
export function CoarseFieldsPanel({
  enabled,
  setEnabled,
  fieldId,
  setFieldId,
  spec,
  survival,
  dwell,
  field,
  needsEpoch,
  needsGoal,
  tHours,
}: CoarseFieldsState) {
  const survivalData = capabilityValue(survival)
  const dwellData = capabilityValue(dwell)
  const fieldData = capabilityValue(field)
  const survivalMessage = capabilityMessage(survival)
  const dwellMessage = capabilityMessage(dwell)

  const counts =
    fieldData && spec.render.mode === 'categorical'
      ? categoryCounts(fieldData, spec.render.categories)
      : null
  const total = counts
    ? Object.entries(counts).reduce((sum, [, n]) => sum + n, 0)
    : 0

  return (
    <section className="rail-section">
      <p className="panel-kicker">Survival &amp; dwell</p>

      <p className="cf-provenance">
        <span className="cf-badge cf-badge-model">MODEL</span>
        <span className="cf-badge cf-badge-uncal">LAG UNCALIBRATED</span>
      </p>

      <label className="cf-toggle">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
          disabled={needsEpoch}
        />
        <span>Show on map</span>
      </label>

      {needsEpoch && (
        <p className="cf-note">
          Needs a mission epoch. Both are computed against where the Sun is, so
          there is nothing to compute until the mission clock is set.
        </p>
      )}

      {enabled && !needsEpoch && (
        <div className="cf-fields" role="group" aria-label="Coarse field">
          {COARSE_FIELDS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              className={`cf-field-btn ${fieldId === entry.id ? 'is-active' : ''}`}
              onClick={() => setFieldId(entry.id)}
              title={entry.blurb}
            >
              {entry.label}
            </button>
          ))}
        </div>
      )}

      {enabled && (
        <>
          <p className="cf-blurb">{spec.blurb}</p>
          <p className="cf-limit">{spec.limit}</p>
          {/* Which moment these fields are. Both endpoints take t_hours and
              both ride the one mission clock, so the number moves with the
              illumination series and the corridor rather than sitting at
              zero while they advance. */}
          <p className="cf-blurb">
            At <span className="cf-mono">T+{tHours.toFixed(1)} h</span> on the
            mission clock.
          </p>
        </>
      )}

      {/*
        A legend with counts. Without them a colour covering three blocks out
        of fifteen thousand reads like a region -- which is exactly the case
        for `wait` on this window.
      */}
      {counts && spec.render.mode === 'categorical' && (
        <dl className="cf-legend">
          {spec.render.categories.map((category) => {
            const n = counts[category.key] ?? 0
            return (
              <div key={category.key} className={n === 0 ? 'is-empty' : ''}>
                <dt>
                  <span
                    className="cf-swatch"
                    style={{
                      background: `rgb(${category.color[0]}, ${category.color[1]}, ${category.color[2]})`,
                    }}
                    aria-hidden="true"
                  />
                  {category.label}
                </dt>
                <dd className="cf-mono">
                  {n.toLocaleString()}
                  {total > 0 && <span className="cf-sub">{pct(n / total)}</span>}
                </dd>
                {category.note && <p className="cf-cat-note">{category.note}</p>}
              </div>
            )
          })}
          {counts.__unknown > 0 && (
            <div>
              <dt>Unrecognised code</dt>
              <dd className="cf-mono">{counts.__unknown.toLocaleString()}</dd>
              <p className="cf-cat-note">
                The backend returned a code this build does not know. Reported
                rather than dropped.
              </p>
            </div>
          )}
        </dl>
      )}

      {/* B1 summary. */}
      {survivalData && (
        <dl className="cf-facts">
          <div>
            <dt>Mean P(safe)</dt>
            <dd className="cf-mono">{survivalData.summary.mean_p_safe.toFixed(3)}</dd>
          </div>
          <div>
            <dt>At least 0.95</dt>
            <dd className="cf-mono">{pct(survivalData.summary.fraction_at_least_0_95)}</dd>
          </div>
          <div>
            <dt>Exactly zero</dt>
            {/*
              The finding, not a footnote: nearly a third of traversable blocks
              have no action that reaches the safe set. Given its own emphasis
              so it is not read as one statistic among four.
            */}
            <dd className="cf-mono is-alarm">{pct(survivalData.summary.fraction_zero)}</dd>
          </div>
          <div>
            <dt>Blocks</dt>
            <dd className="cf-mono">
              {survivalData.summary.traversable_blocks.toLocaleString()}
              <span className="cf-sub">traversable, 20 m blocks</span>
            </dd>
          </div>
        </dl>
      )}

      {survivalData && (
        <p className="cf-note">
          {pct(survivalData.summary.fraction_zero)} of traversable blocks can reach
          the safe set with no action at all — drawn as “No action helps”, not as
          a low probability.
        </p>
      )}

      {/* C6 summary. */}
      {dwellData && (
        <dl className="cf-facts">
          <div>
            <dt>Median dwell</dt>
            <dd className="cf-mono">
              {dwellData.summary.finite_median_h.toFixed(2)} h
              <span className="cf-sub">
                p5 {dwellData.summary.finite_p5_h.toFixed(2)} · p95{' '}
                {dwellData.summary.finite_p95_h.toFixed(2)}
              </span>
            </dd>
          </div>
          <div>
            <dt>Cold-limited</dt>
            <dd className="cf-mono">{pct(dwellData.summary.fraction_cold_limited)}</dd>
          </div>
          <div>
            <dt>Hot-limited</dt>
            <dd className="cf-mono">{pct(dwellData.summary.fraction_hot_limited)}</dd>
          </div>
          <div>
            <dt>Open-ended</dt>
            <dd className="cf-mono">
              {pct(dwellData.summary.fraction_unlimited)}
              <span className="cf-sub">clipped to {dwellData.summary.lookahead_h} h</span>
            </dd>
          </div>
        </dl>
      )}

      {dwellData && (
        <p className="cf-note">
          Open-ended blocks never leave the envelope inside the{' '}
          {dwellData.summary.lookahead_h} h lookahead, so their dwell reads{' '}
          {dwellData.summary.lookahead_h} h as a floor — “at least”, not “exactly”.
        </p>
      )}

      {/* Missing inputs and failures, in the backend's words where there are any. */}
      {enabled && needsGoal && !needsEpoch && (
        <p className="cf-note">
          Survival needs a goal: the safe set is the leg to it. Place a goal on
          the map and P(safe) and Best action will load. Thermal dwell does not
          need one and is shown already.
        </p>
      )}
      {survivalMessage && !needsEpoch && !needsGoal && (
        <p className={`cf-note ${survival.status === 'error' ? 'is-error' : ''}`}>
          {survivalMessage}
        </p>
      )}
      {dwellMessage && !needsEpoch && (
        <p className={`cf-note ${dwell.status === 'error' ? 'is-error' : ''}`}>
          {dwellMessage}
        </p>
      )}
    </section>
  )
}
