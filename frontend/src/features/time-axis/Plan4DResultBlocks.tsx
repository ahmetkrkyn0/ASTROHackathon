import type { Plan4DResponse, PlanSurvival, PlanThermalDwell } from '../../net/types'

/**
 * What the advanced constraints actually reported, beside the button that
 * asked for them.
 *
 * A control that changes the request and shows nothing back is half a
 * feature: the operator switches on a failure-probability limit, the route
 * comes back, and there is no way to tell whether the limit bound anything or
 * whether the field could even be built. Both of those are states the backend
 * reports precisely, so they are shown precisely.
 *
 * In this file rather than a Systems panel of its own: the 4-D result lives in
 * `useTimeAxis`'s own state, and lifting it into shared state so another
 * feature could read it would be the cross-feature plumbing the integration
 * plan forbids (§31.7). The panel imports one component; nothing else moves.
 *
 * THREE STATES, NEVER COLLAPSED. `requested: false` is not `applied: false`
 * is not an error. Saying "no survival data" for all three would report a
 * healthy backend as broken and an unasked question as an answer.
 */
export function Plan4DResultBlocks({ plan4d }: { plan4d: Plan4DResponse }) {
  const survival = plan4d.survival
  const thermal = plan4d.thermal_dwell

  // A deployment that predates these blocks sends neither, and gets nothing
  // rather than a row of dashes claiming they came back empty.
  if (!survival && !thermal) return null

  return (
    <div className="lp-time-blocks">
      {survival ? <SurvivalBlock survival={survival} /> : null}
      {thermal ? <ThermalBlock thermal={thermal} /> : null}
    </div>
  )
}

function SurvivalBlock({ survival }: { survival: PlanSurvival }) {
  if (!survival.requested) return null

  if (!survival.route) {
    return (
      <p className="lp-time-block lp-time-block-idle">
        <strong>Survival</strong> — not computed for this route.{' '}
        {survival.reason ?? 'The backend gave no reason.'}
      </p>
    )
  }

  const route = survival.route
  const failure = route.execution_failure_probability

  return (
    <div className="lp-time-block">
      <p className="lp-time-block-head">
        <strong>Survival</strong>
        <span className="lp-time-badge">{survival.validity}</span>
        {survival.applied ? (
          <span className="lp-time-badge is-on">β enforced {fmt(survival.beta, 3)}</span>
        ) : (
          <span className="lp-time-badge">reported only</span>
        )}
      </p>
      <ul className="lp-time-block-list">
        <li>
          Execution failure probability <b>{fmt(failure, 4)}</b>
          {survival.applied && typeof failure === 'number' && typeof survival.beta === 'number'
            ? failure <= survival.beta
              ? ' — within the limit.'
              : ' — over the limit.'
            : ''}
        </li>
        <li>Lowest P_safe along the route <b>{fmt(route.min_recovery_prob, 4)}</b></li>
        {/*
          A count, and labelled as one. `moves_refused` is how many edges the
          chance constraint threw out, not a fraction and not a rate: dividing
          it by anything would invent a denominator the backend never quoted.
        */}
        <li>
          Moves refused by the limit <b>{route.moves_refused}</b>{' '}
          {route.moves_refused === 0 ? '(the limit bound nothing here)' : '(a count, not a rate)'}
        </li>
        {survival.safe_set_definition ? (
          <li className="lp-time-block-note">Safe set — {survival.safe_set_definition}</li>
        ) : null}
      </ul>
      {survival.claim ? <p className="lp-time-block-claim">{survival.claim}</p> : null}
    </div>
  )
}

function ThermalBlock({ thermal }: { thermal: PlanThermalDwell }) {
  if (!thermal.requested) return null

  const unavailable = thermal.dwell_model?.model === 'unavailable'
  if (unavailable || !thermal.route) {
    return (
      <p className="lp-time-block lp-time-block-idle">
        <strong>Thermal envelope</strong> — not computed for this route.{' '}
        {thermal.dwell_model?.reason ?? 'The backend gave no reason.'}
      </p>
    )
  }

  const route = thermal.route
  const inner = route.inner

  return (
    <div className="lp-time-block">
      <p className="lp-time-block-head">
        <strong>Thermal envelope</strong>
        {/*
          Both labels, always. The model is a MODEL and its lag constant is
          UNCALIBRATED; showing the temperatures without them would let a
          reader take an integrated curve for a thermal qualification, which
          the integration plan rules out in as many words.
        */}
        <span className="lp-time-badge">{thermal.validity}</span>
        <span className="lp-time-badge">lag {thermal.thermal_lag_validity}</span>
        {thermal.applied ? <span className="lp-time-badge is-on">enforced</span> : null}
      </p>
      <ul className="lp-time-block-list">
        {thermal.envelope ? (
          <li>
            Envelope <b>{fmt(thermal.envelope.lo_c, 1)} to {fmt(thermal.envelope.hi_c, 1)} °C</b>{' '}
            ({thermal.envelope.lo_component}) · start {fmt(thermal.initial_inner_c, 1)} °C
          </li>
        ) : null}
        {inner ? (
          <li>
            Inner temperature <b>{fmt(inner.min_c, 1)} to {fmt(inner.max_c, 1)} °C</b>
            {inner.states_outside !== null && inner.states_outside > 0
              ? ` — ${inner.states_outside} state(s) outside the envelope${
                  inner.side ? ` on the ${inner.side} side` : ''
                }.`
              : ' — inside the envelope for every state.'}
          </li>
        ) : null}
        <li>
          Tightest dwell margin <b>{fmt(route.min_dwell_margin_h, 2)} h</b>
          {route.open_ended_states ? ` · ${route.open_ended_states} open-ended stay(s)` : ''}
        </li>
      </ul>
      {/*
        The assumption, in the backend's own words, whenever it was used.
        `heater_source` is non-null exactly for `thermostat_assumed`, so this
        cannot appear beside a result that did not rest on it.
      */}
      {thermal.heater_source ? (
        <p className="lp-time-block-assumption">
          <strong>ASSUMPTION</strong> — {thermal.heater_source}
        </p>
      ) : null}
      {thermal.claim ? <p className="lp-time-block-claim">{thermal.claim}</p> : null}
    </div>
  )
}

/**
 * A number, or an em dash.
 *
 * Null is not zero anywhere in this product, and a thermal margin of 0.00 h
 * means the rover is exactly at its limit while a missing one means nobody
 * measured. Printing both as "0.00" would be the more dangerous of the two
 * mistakes.
 */
function fmt(value: number | null | undefined, digits: number): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—'
}
