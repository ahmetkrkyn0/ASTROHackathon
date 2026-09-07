import { useEffect, useMemo, useState } from 'react'

import { useMission } from '../../mission/MissionContext'
import {
  CAPABILITY_LOADING,
  capabilityFromError,
  capabilityReady,
  capabilityValue,
  capabilityMessage,
  type Capability,
} from '../../mission/capability'
import { isDataUnavailable } from '../../net/errors'
import { fetchThermalEnvelope, type ThermalEnvelope } from '../../net/analysis'
import { describeCell, envelopeMatrix, unsampledFraction } from './matrix'
import './thermal-envelope.css'

/**
 * C6 -- the rover's thermal operating envelope, as a bin matrix.
 *
 * Not a map. The axes are Sun elevation and the terrain slope along the Sun's
 * azimuth, so a bin is a *geometry* rather than a place: many blocks of the
 * site share one bin, and one block moves between bins as the Sun goes round.
 * That is the point of the chart -- it says what kind of ground is survivable
 * at what Sun angle, independently of where that ground happens to be.
 *
 * Two labels sit above it and belong to every number in it: the model is MODEL,
 * and the regolith lag inside it is UNCALIBRATED. Nobody has measured the time
 * constant against hardware.
 */
export function ThermalEnvelopePanel() {
  const { roverId } = useMission()
  const [state, setState] = useState<Capability<ThermalEnvelope>>(CAPABILITY_LOADING)

  useEffect(() => {
    const controller = new AbortController()
    setState(CAPABILITY_LOADING)
    fetchThermalEnvelope({ roverId }, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return
        setState(capabilityReady(response))
      })
      .catch((error: unknown) => {
        const next = capabilityFromError(error, {
          isDataUnavailable: isDataUnavailable(error),
          signal: controller.signal,
        })
        if (next) setState(next)
      })
    return () => controller.abort()
  }, [roverId])

  const envelope = capabilityValue(state)
  const matrix = useMemo(() => (envelope ? envelopeMatrix(envelope) : null), [envelope])
  const message = capabilityMessage(state)
  const remedy = state.status === 'unavailable' ? state.remedy : null

  if (state.status === 'loading') {
    return (
      <section className="rail-section">
        <p className="panel-kicker">Thermal envelope</p>
        <p className="te-note">Loading…</p>
      </section>
    )
  }

  if (!envelope || !matrix) {
    return (
      <section className="rail-section">
        <p className="panel-kicker">Thermal envelope</p>
        {/* A missing heat1d cache is not a failure, and no synthetic matrix is
            produced in its place -- the backend refuses to, and so does this. */}
        <p className={`te-note ${state.status === 'error' ? 'is-error' : ''}`}>{message}</p>
        {remedy && <code className="te-remedy">{remedy}</code>}
      </section>
    )
  }

  const unsampled = unsampledFraction(envelope)

  return (
    <section className="rail-section">
      <p className="panel-kicker">Thermal envelope</p>

      <p className="te-provenance">
        <span className="te-badge te-badge-model">{envelope.validity}</span>
        <span className="te-badge te-badge-uncal">LAG {envelope.thermal_lag_validity}</span>
      </p>

      <p className="te-lede">
        {envelope.rover_name} inside {envelope.envelope.lo_c}–{envelope.envelope.hi_c} °C
        (
        {envelope.envelope.lo_component === envelope.envelope.hi_component
          ? envelope.envelope.lo_component
          : `${envelope.envelope.lo_component} / ${envelope.envelope.hi_component}`}
        ), starting from {envelope.initial_inner_c} °C
        {envelope.heater_model === 'none' ? ', no heater' : `, heater ${envelope.heater_model}`}.
      </p>

      {/* The matrix. Rows are Sun elevation, high at the top; columns are slope
          along the Sun's azimuth, away on the left and toward on the right. */}
      <div className="te-chart">
        <span className="te-axis-y">{envelope.axes.el_deg.label}</span>
        <div className="te-grid-wrap">
          <div
            className="te-grid"
            style={{ gridTemplateColumns: `repeat(${matrix.cols}, 1fr)` }}
            role="img"
            aria-label={`Thermal envelope, ${matrix.rows} Sun elevation bins by ${matrix.cols} slope bins`}
          >
            {matrix.grid.flatMap((line, row) =>
              line.map((cell, col) => (
                <span
                  key={`${row}-${col}`}
                  className={`te-cell te-${cell?.verdict ?? 'absent'}`}
                  title={describeCell(cell)}
                />
              )),
            )}
          </div>
          <div className="te-scale te-scale-x">
            <span>{envelope.axes.s_par_deg.edges[0]}°</span>
            <span>0°</span>
            <span>
              {envelope.axes.s_par_deg.edges[envelope.axes.s_par_deg.edges.length - 1]}°
            </span>
          </div>
          <span className="te-axis-x">{envelope.axes.s_par_deg.label}</span>
        </div>
      </div>

      <dl className="te-legend">
        {(['unlimited', 'cold_limited', 'hot_limited', 'unsampled'] as const).map(
          (verdict) => (
            <div key={verdict}>
              <dt>
                <span className={`te-swatch te-${verdict}`} aria-hidden="true" />
                {verdict === 'unlimited'
                  ? 'Stays inside'
                  : verdict === 'cold_limited'
                    ? 'Cold limit'
                    : verdict === 'hot_limited'
                      ? 'Hot limit'
                      : 'Not sampled'}
              </dt>
              <dd className="te-mono">{envelope.counts[verdict]}</dd>
            </div>
          ),
        )}
      </dl>

      {/*
        The unsampled share, stated rather than left to be inferred from a
        blank. 29% of this matrix has no result at all: the heat1d trace never
        reached those geometries. Colouring them would have invented one, and
        omitting the number lets the coloured 71% read as the whole chart.
      */}
      <p className="te-note">
        {(unsampled * 100).toFixed(0)}% of bins are blank because the heat1d trace
        never reached that geometry — no result, not a benign one.
        {matrix.missing > 0 &&
          ` A further ${matrix.missing} bin(s) were absent from the response entirely.`}
      </p>

      <p className="te-note te-claim">{envelope.claim}</p>
    </section>
  )
}

export default ThermalEnvelopePanel
