import { useEffect, useState } from 'react'

import { useMission } from '../../mission/MissionContext'
import { hasMissionEpoch, missionTimeSliceIndex } from '../../mission/missionTime'
import {
  CAPABILITY_IDLE,
  CAPABILITY_LOADING,
  capabilityFromError,
  capabilityFromModel,
  capabilityMessage,
  capabilityValue,
  type Capability,
} from '../../mission/capability'
import { isDataUnavailable } from '../../net/errors'
import {
  fetchUncertaintySeries,
  type UncertaintySeriesManifest,
} from '../../net/analysis'

/** Eight slices of six hours: two days, matching the corridor's window. */
const N_SLICES = 8
const SLICE_HOURS = 6

/**
 * B3's time half -- how much the DEM clones disagree about illumination, slice
 * by slice.
 *
 * It lives under the DEM pedigree card rather than in its own feature because
 * it answers the same question the four uncertainty layers do, in time instead
 * of space: those say where the clones disagree about the ground, this says
 * when they disagree about the light.
 *
 * The interesting number is `uncertain_fraction`, not `mean`. A mean of 0.90
 * with 6% of cells uncertain is a confident answer; the same mean with 40%
 * uncertain is not, and the two are indistinguishable if only the mean is
 * shown.
 */
export function UncertaintySeriesCard() {
  const { missionTime } = useMission()
  const [state, setState] =
    useState<Capability<UncertaintySeriesManifest>>(CAPABILITY_IDLE)

  const startUtc = hasMissionEpoch(missionTime) ? missionTime.startUtc : null

  useEffect(() => {
    if (!startUtc) {
      setState(CAPABILITY_IDLE)
      return
    }
    const controller = new AbortController()
    setState(CAPABILITY_LOADING)
    fetchUncertaintySeries(
      { startUtc, nSlices: N_SLICES, sliceHours: SLICE_HOURS },
      controller.signal,
    )
      .then((response) => {
        if (controller.signal.aborted) return
        // This endpoint answers 200 even with nothing to say -- the body
        // carries `model: "unavailable"` beside a real `slices` and
        // `start_utc`. Checking `response.ok` alone would conclude it has data.
        setState(capabilityFromModel(response, response))
      })
      .catch((error: unknown) => {
        const next = capabilityFromError(error, {
          isDataUnavailable: isDataUnavailable(error),
          signal: controller.signal,
        })
        if (next) setState(next)
      })
    return () => controller.abort()
  }, [startUtc])

  const series = capabilityValue(state)
  const message = capabilityMessage(state)
  const remedy = state.status === 'unavailable' ? state.remedy : null

  if (state.status === 'idle' || state.status === 'loading') return null

  if (!series?.per_slice) {
    return (
      <div className="lp-provenance-card lp-dem-card">
        <div className="lp-provenance-head">
          <code className="lp-provenance-name">Illumination uncertainty</code>
        </div>
        <p className="lp-provenance-why">{message}</p>
        {remedy && <code className="lp-us-remedy">{remedy}</code>}
      </div>
    )
  }

  const { mean, uncertain_fraction: uncertain } = series.per_slice
  const slice = missionTimeSliceIndex(missionTime, series.slices)
  const peakUncertain = Math.max(...uncertain)

  return (
    <div className="lp-provenance-card lp-dem-card">
      <div className="lp-provenance-head">
        <code className="lp-provenance-name">Illumination uncertainty</code>
        <span className="lp-provenance-badge lp-provenance-derived">
          {series.n_clones ?? 0} clones
        </span>
      </div>

      {/*
        Two bars per slice, stacked in one column: the mean as a quiet fill and
        the uncertain fraction on top of it. Overlaid rather than side by side
        because they are not comparable magnitudes -- one is a probability, the
        other a share of cells -- and putting them in one column reads as "how
        lit, and how sure".
      */}
      <div className="lp-us-strip" role="img" aria-label="Illumination uncertainty per slice">
        {mean.map((value, index) => (
          <span
            key={index}
            className={`lp-us-col ${index === slice ? 'is-current' : ''}`}
            title={`Slice ${index + 1}: mean P ${value.toFixed(3)}, ${(uncertain[index] * 100).toFixed(1)}% uncertain`}
          >
            <span className="lp-us-mean" style={{ height: `${value * 100}%` }} />
            <span
              className="lp-us-uncertain"
              style={{ height: `${Math.max(uncertain[index] * 100, 1)}%` }}
            />
          </span>
        ))}
      </div>

      <dl className="lp-provenance-facts lp-dem-facts">
        <div>
          <dt>Mean P(lit)</dt>
          <dd>{mean[slice].toFixed(3)}</dd>
        </div>
        <div>
          <dt>Uncertain now</dt>
          <dd>{(uncertain[slice] * 100).toFixed(1)}%</dd>
        </div>
        <div>
          <dt>Worst slice</dt>
          <dd>{(peakUncertain * 100).toFixed(1)}%</dd>
        </div>
      </dl>

      <p className="lp-provenance-why">
        “Uncertain” is a cell where the clones disagree — 0.05 &lt; P &lt; 0.95.
        The mean alone cannot distinguish a confident answer from a divided one.
        {series.far_field_held_fixed &&
          typeof series.neglected_horizon_shift_deg_max === 'number' &&
          ` The far field was not cloned; the horizon shift that ignores is bounded at ${series.neglected_horizon_shift_deg_max.toFixed(3)}°.`}
      </p>
    </div>
  )
}
