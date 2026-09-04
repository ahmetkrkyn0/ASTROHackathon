import type { ReplanResponse } from '../../net/types'
import { TRIGGER_FIELDS, TRIGGER_IDS, type TelemetryValue } from '../../mission/triggers'
import type { TriggerRow } from './useReplan'
import './replan.css'

const STATUS_LABEL = {
  fired: 'Fired',
  clear: 'Clear',
  unchecked: 'Not checked',
} as const

export function ReplanPanel({
  form,
  setField,
  submit,
  result,
  busy,
  error,
  rows,
}: {
  form: Record<string, TelemetryValue>
  setField: (key: string, value: TelemetryValue) => void
  submit: (force: boolean) => void
  result: ReplanResponse | null
  busy: boolean
  error: string | null
  rows: TriggerRow[]
}) {
  // Deduplicated: half_width_m feeds both corridor_violation and
  // localization_uncertainty, and two inputs writing one key would fight.
  const seen = new Set<string>()

  return (
    <div className="lp-replan-card">
      <p className="lp-replan-hint">
        Leave a field blank to report that value as unavailable — the check
        that needs it comes back “Not checked”, not “Clear”.
      </p>

      <div className="lp-replan-form">
        {TRIGGER_IDS.flatMap((id) =>
          TRIGGER_FIELDS[id].fields
            .filter((field) => {
              if (seen.has(field.key)) return false
              seen.add(field.key)
              return true
            })
            .map((field) => (
              <label key={field.key} className="lp-replan-field">
                <span>{field.label}</span>
                <input
                  type="number"
                  step={field.step}
                  value={form[field.key] ?? ''}
                  placeholder="not reported"
                  // '' is kept as '', not coerced to 0: an empty box means the
                  // value was never measured, and telemetryPayload drops it
                  // so the backend can say the check did not run.
                  onChange={(event) =>
                    setField(
                      field.key,
                      event.target.value === '' ? '' : Number(event.target.value),
                    )
                  }
                />
              </label>
            )),
        )}
      </div>

      <div className="lp-replan-actions">
        <button type="button" disabled={busy} onClick={() => submit(false)}>
          {busy ? 'Evaluating…' : 'Evaluate triggers'}
        </button>
        <button type="button" disabled={busy} onClick={() => submit(true)}>
          Force replan
        </button>
      </div>

      {error ? <p className="lp-replan-note lp-replan-warn">{error}</p> : null}

      {result ? (
        <>
          <p className="lp-replan-verdict">
            {result.replanned
              ? `Replanned — ${result.triggers.length} trigger(s) fired`
              : (result.reason ?? 'No replan trigger fired')}
          </p>

          <ul className="lp-replan-list">
            {rows.map((row) => (
              <li key={row.id} className={`lp-replan-row lp-replan-${row.status}`}>
                <span className="lp-replan-name">{TRIGGER_FIELDS[row.id].label}</span>
                <span className="lp-replan-status">{STATUS_LABEL[row.status]}</span>
                {row.detail ? <span className="lp-replan-detail">{row.detail}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}
