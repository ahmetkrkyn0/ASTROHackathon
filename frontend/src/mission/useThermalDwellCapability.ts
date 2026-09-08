/**
 * Whether THIS rover's thermal envelope can be enforced as a planner
 * constraint -- spec 5.1, asked per rover rather than per deployment.
 *
 * `require_thermal_dwell` is the one advanced constraint whose availability
 * turns on the vehicle rather than on a cache: the model relaxes the inner
 * temperature toward each block's surface target with the rover's own
 * `thermal_tau_s`, and LUVMI-M does not publish one. Asking the backend to
 * enforce it there is a 422, so the control has to be dark before it is
 * pressed.
 *
 * The rover id is NOT hard-coded here, and that is the point. `thermal_tau_s`
 * is published under `declared_only` in the rover catalogue, a block whose
 * own documentation says it is "published for reference, read by nothing" --
 * reading it as an input would make a liar of that label and would put the
 * frontend in the business of deciding what the thermal model needs. Instead
 * this asks the endpoint that owns the question and repeats its answer:
 *
 *     luvmi_m     dwell_model.model  = "unavailable"
 *                 dwell_model.reason = "rover declares no thermal_tau_s: the
 *                                       inner-temperature lag cannot be timed
 *                                       (no regolith constant is substituted
 *                                       for the vehicle's)"
 *     nasa_viper  dwell_model.model  = "inner_temperature_first_order_lag_v1"
 *
 * which is exactly the `{ model, reason }` shape `capability.ts` exists to
 * fold, so the operator is shown the backend's sentence and not ours.
 */

import { useEffect, useState } from 'react'

import { fetchThermalEnvelope } from '../net/analysis'
import { isModelUnavailable } from './capability'

export interface ThermalDwellCapability {
  /** True only once the backend has confirmed this rover has a dwell model. */
  ready: boolean
  /** Why not, in the backend's own words. Null while loading or when ready. */
  reason: string | null
  /** The envelope's own default start temperature, for display. */
  initialInnerC: number | null
}

const LOADING: ThermalDwellCapability = {
  ready: false,
  reason: null,
  initialInnerC: null,
}

export function useThermalDwellCapability(roverId: string): ThermalDwellCapability {
  const [capability, setCapability] = useState<ThermalDwellCapability>(LOADING)

  useEffect(() => {
    const controller = new AbortController()
    setCapability(LOADING)

    fetchThermalEnvelope({ roverId }, controller.signal)
      .then((envelope) => {
        if (controller.signal.aborted) return
        if (isModelUnavailable(envelope.dwell_model)) {
          setCapability({
            ready: false,
            reason:
              envelope.dwell_model.reason ??
              'This rover declares no thermal lag, so the envelope cannot be timed.',
            initialInnerC: null,
          })
          return
        }
        setCapability({ ready: true, reason: null, initialInnerC: envelope.initial_inner_c })
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        // A failed probe is not a missing capability, and must not read like
        // one: the remedy for "the request failed" is not "run a script".
        setCapability({
          ready: false,
          reason:
            cause instanceof Error
              ? `The thermal envelope could not be read: ${cause.message}`
              : 'The thermal envelope could not be read.',
          initialInnerC: null,
        })
      })

    return () => controller.abort()
  }, [roverId])

  return capability
}
