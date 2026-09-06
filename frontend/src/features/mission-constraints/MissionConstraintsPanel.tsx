import { Icon } from '../../components/Fleet/SpecIcons'
import {
  PLAN_REQUEST_CONTRIBUTORS,
  setConstraint,
  useConstraint,
  usePlanConstraints,
  type PlanRequestContributor,
} from '../plan-request'
import './mission-constraints.css'

/**
 * The advanced planner constraints, in one panel.
 *
 * One panel for all of them rather than one per feature: the backend now takes
 * seven of these and seven cards would be exactly the rail clutter the
 * integration plan warns against. The panel has no per-constraint code either
 * -- it renders whatever the contributor registry describes -- so the next one
 * is an append to that list and nothing here changes.
 *
 * The footer states what the panel is for: with everything off, the request is
 * byte-for-byte the one this product has always sent. That is worth saying on
 * screen, because an operator has no other way to know that a row of switches
 * set to off is not quietly steering their route.
 */

function ConstraintRow({ contributor }: { contributor: PlanRequestContributor }) {
  const state = useConstraint(contributor.id)
  const { control } = contributor

  return (
    <li className={`lp-mc-row ${state.enabled ? 'is-on' : ''}`}>
      <label className="lp-mc-toggle">
        <input
          type="checkbox"
          checked={state.enabled}
          onChange={(event) =>
            setConstraint(contributor.id, { ...state, enabled: event.target.checked })
          }
        />
        <span className="lp-mc-switch" aria-hidden="true" />
        <span className="lp-mc-label">{contributor.label}</span>
      </label>

      {/* The hint is always readable, on or off: the decision it informs is
          whether to switch the thing on. */}
      <p className="lp-mc-hint">{contributor.hint}</p>

      {state.enabled && control.kind === 'number' ? (
        <div className="lp-mc-control">
          <input
            type="range"
            min={control.min}
            max={control.max}
            step={control.step}
            value={typeof state.value === 'number' ? state.value : control.initial}
            onChange={(event) =>
              setConstraint(contributor.id, {
                enabled: true,
                value: Number(event.target.value),
              })
            }
          />
          <output className="lp-mc-value">
            {typeof state.value === 'number' ? state.value.toFixed(3) : control.initial.toFixed(3)}
            {control.unit ?? ''}
          </output>
        </div>
      ) : null}

      {state.enabled && control.kind === 'choice' ? (
        <div className="lp-mc-control">
          <select
            className="lp-mc-select"
            value={typeof state.value === 'string' ? state.value : control.initial}
            onChange={(event) =>
              setConstraint(contributor.id, { enabled: true, value: event.target.value })
            }
          >
            {control.options.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
      ) : null}
    </li>
  )
}

export function MissionConstraintsPanel() {
  const fields = usePlanConstraints()
  const active = Object.keys(fields).length

  return (
    <div className="lp-mc">
      <ul className="lp-mc-list">
        {PLAN_REQUEST_CONTRIBUTORS.map((contributor) => (
          <ConstraintRow key={contributor.id} contributor={contributor} />
        ))}
      </ul>

      <p className={`lp-mc-foot ${active > 0 ? 'is-active' : ''}`}>
        <Icon name={active > 0 ? 'tune' : 'check'} />
        <span>
          {active > 0
            ? `${active} field${active === 1 ? '' : 's'} added to the plan request.`
            : 'None enabled — the plan request is unchanged.'}
        </span>
      </p>
    </div>
  )
}
