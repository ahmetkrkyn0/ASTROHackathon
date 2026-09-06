import { Icon, type IconName } from '../../components/Fleet/SpecIcons'
import { formatMargin, type MarginState, type RequirementView, type SafetyMarginsView } from './safetyMargins'
import './safety-margins.css'

/** Icon and wording per state. Four outcomes, not two. */
const STATE_META: Record<MarginState, { icon: IconName; label: string }> = {
  satisfied: { icon: 'check', label: 'Margin' },
  boundary: { icon: 'warning', label: 'At limit' },
  violated: { icon: 'error', label: 'Violated' },
  pending: { icon: 'clock', label: 'Undecided' },
  'not-applicable': { icon: 'help', label: 'Not checked' },
}

const VERDICT_LABEL: Record<string, string> = {
  satisfied: 'ALL REQUIREMENTS MET',
  violated: 'REQUIREMENTS VIOLATED',
  pending: 'VERDICT PENDING',
  not_evaluated: 'NOT EVALUATED',
}

function Requirement({ requirement }: { requirement: RequirementView }) {
  const meta = STATE_META[requirement.state]
  return (
    <li className={`lp-margin-row is-${requirement.state}`}>
      <span className="lp-margin-icon"><Icon name={meta.icon} /></span>
      <span className="lp-margin-id">{requirement.id}</span>
      <span className="lp-margin-name">{requirement.name.replace(/_/g, ' ')}</span>
      <span className="lp-margin-value">
        {requirement.state === 'not-applicable' ? meta.label : formatMargin(requirement)}
      </span>
      {/* The reason a requirement could not be tested is the whole content of
          that row -- without it "Not checked" is indistinguishable from an
          oversight. */}
      {requirement.state === 'not-applicable' && requirement.reason ? (
        <span className="lp-margin-reason">{requirement.reason}</span>
      ) : null}
    </li>
  )
}

export function SafetyMarginsPanel({ view }: { view: SafetyMarginsView }) {
  const verdict = VERDICT_LABEL[view.verdict] ?? view.verdict.toUpperCase()
  const untested = view.requirements.filter((r) => r.state === 'not-applicable').length

  return (
    <div className="lp-margins">
      <div className={`lp-margins-verdict is-${view.verdict}`}>
        <span className="lp-margins-verdict-text">{verdict}</span>
        {view.nApplicable !== null ? (
          <span className="lp-margins-count">
            {(view.nApplicable - (view.nViolated ?? 0))}/{view.nApplicable} met
          </span>
        ) : null}
      </div>

      {/* The tightest requirement, named. A verdict of "satisfied" says nothing
          about how nearly it was not, and that margin is the number an
          operator actually plans against. */}
      {view.minMargin ? (
        <p className="lp-margins-tightest">
          Tightest margin <b>{view.minMargin.id}</b>
          {view.minMargin.rho !== null ? (
            <span className="lp-margins-tightest-value">
              {view.minMargin.rho > 0 ? '+' : ''}
              {view.minMargin.rho.toFixed(2)}
              {view.minMargin.unit ? ` ${view.minMargin.unit}` : ''}
            </span>
          ) : null}
        </p>
      ) : null}

      <ul className="lp-margins-list">
        {view.requirements.map((requirement) => (
          <Requirement key={requirement.id} requirement={requirement} />
        ))}
      </ul>

      {untested > 0 ? (
        <p className="lp-margins-note">
          {untested} requirement{untested === 1 ? '' : 's'} could not be tested on this
          trace. Untested is not passed.
        </p>
      ) : null}

      {/* Verbatim, and not optional. This sentence is the difference between
          what this feature does and what it would be misread as doing. */}
      {view.claim ? (
        <p className="lp-margins-claim">
          <Icon name="info" />
          <span>{view.claim}</span>
        </p>
      ) : null}

      <p className="lp-margins-provenance">
        {view.engine ? `Monitor ${view.engine}` : 'Monitor'}
        {view.crossCheckMaxDiff !== null
          ? ` · cross-checked, max diff ${view.crossCheckMaxDiff}`
          : ''}
        {view.traceKind ? ` · ${view.traceKind} trace` : ''}
        {view.traceComplete === false ? ' · incomplete' : ''}
      </p>
    </div>
  )
}
