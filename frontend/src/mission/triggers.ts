import type { TriggerId } from '../net/types'

export interface TelemetryField {
  key: string
  label: string
  /** A sensible starting value so the form is usable without guesswork. */
  initial: number
  step: number
}

/**
 * What each trigger needs, mirroring _TRIGGER_INPUTS
 * (replan_triggers.py:144-157). A key that does not match makes the backend
 * report the trigger as skipped -- not as failing.
 */
export const TRIGGER_FIELDS: Record<TriggerId, { label: string; fields: TelemetryField[] }> = {
  soc_deviation: {
    label: 'State of charge deviation',
    fields: [
      { key: 'actual_soc', label: 'Actual SoC', initial: 0.62, step: 0.01 },
      { key: 'planned_soc', label: 'Planned SoC', initial: 0.7, step: 0.01 },
    ],
  },
  inner_temperature: {
    label: 'Inner temperature',
    fields: [
      { key: 'actual_inner_c', label: 'Actual inner °C', initial: -8, step: 1 },
      { key: 'predicted_inner_c', label: 'Predicted inner °C', initial: -5, step: 1 },
    ],
  },
  time_drift: {
    label: 'Schedule drift',
    fields: [{ key: 'drift_minutes', label: 'Drift (min)', initial: 12, step: 1 }],
  },
  corridor_violation: {
    label: 'Corridor violation',
    fields: [
      { key: 'lateral_offset_m', label: 'Lateral offset (m)', initial: 12, step: 1 },
      { key: 'half_width_m', label: 'Corridor half-width (m)', initial: 20, step: 1 },
    ],
  },
  comm_window: {
    label: 'Comm window',
    fields: [
      { key: 'comm_minutes_remaining', label: 'Earth visibility left (min)', initial: 45, step: 5 },
    ],
  },
  localization_uncertainty: {
    label: 'Localization uncertainty',
    fields: [
      { key: 'localization_covariance_m', label: 'Position 1σ (m)', initial: 6, step: 1 },
      { key: 'half_width_m', label: 'Corridor half-width (m)', initial: 20, step: 1 },
    ],
  },
  slip_accumulation: {
    label: 'Slip accumulation',
    fields: [
      { key: 'map_progress_m', label: 'Map progress (m)', initial: 180, step: 10 },
      { key: 'odometer_claim_m', label: 'Odometer claim (m)', initial: 210, step: 10 },
    ],
  },
}

export const TRIGGER_IDS = Object.keys(TRIGGER_FIELDS) as TriggerId[]

/**
 * A telemetry reading, or the absence of one.
 *
 * '' is not zero. A blank field means the rover did not report that value,
 * and it is dropped from the request so the backend lists the trigger as
 * skipped. Sending 0 instead would have the check run against a number
 * nobody measured -- and 0 is a perfectly plausible SoC.
 */
export type TelemetryValue = number | ''

/** Every distinct telemetry key, deduplicated -- half_width_m feeds two triggers. */
export function initialTelemetry(): Record<string, TelemetryValue> {
  const out: Record<string, TelemetryValue> = {}
  for (const id of TRIGGER_IDS) {
    for (const field of TRIGGER_FIELDS[id].fields) {
      out[field.key] = field.initial
    }
  }
  return out
}

/** Drops the blanks, so an unreported value is absent rather than zero. */
export function telemetryPayload(
  form: Record<string, TelemetryValue>,
): Record<string, number> {
  const out: Record<string, number> = {}
  for (const [key, value] of Object.entries(form)) {
    if (value !== '' && Number.isFinite(value)) out[key] = value as number
  }
  return out
}
