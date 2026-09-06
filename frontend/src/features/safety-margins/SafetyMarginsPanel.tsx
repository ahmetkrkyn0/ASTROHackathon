import { Icon, type IconName } from '../../components/Fleet/SpecIcons'
import { formatMargin, type MarginState, type RequirementView, type SafetyMarginsView } from './safetyMargins'
import './safety-margins.css'

/**
 * The rail readout: a verdict, the tightest margin, and twelve rows.
 *
 * Deliberately NOT the evidence. The backend ships a claim boundary, a FRETISH
 * sentence per requirement and a monitor provenance block, and all of it is
 * worth reading -- in the mission report, which is a document. Pasted into a
 * 288 px rail it was three paragraphs of prose above the numbers it was meant
 * to qualify, which is how a caveat stops being read at all.
 *
 * What survives here is what an operator scans: did it pass, by how little,
 * and which requirement is the tight one.
 */

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
  const untested = requirement.state === 'not-applicable'
  return (
    <li className={`lp-margin-row is-${requirement.state}`}>
      <Icon name={meta.icon} className="lp-margin-icon" />
      <span className="lp-margin-id">{requirement.id}</span>
      <span className="lp-margin-name">{requirement.name.replace(/_/g, ' ')}</span>
      <span className="lp-margin-value">
        {untested ? meta.label : formatMargin(requirement)}
      </span>
    </li>
  )
}

export function SafetyMarginsPanel({ view }: { view: SafetyMarginsView }) {
  const verdict = VERDICT_LABEL[view.verdict] ?? view.verdict.toUpperCase()
  const untested = view.requirements.filter((r) => r.state === 'not-applicable').length
  const met = view.nApplicable !== null ? view.nApplicable - (view.nViolated ?? 0) : null

  return (
    <div className="lp-margins">
      <div className={`lp-margins-verdict is-${view.verdict}`}>
        <span className="lp-margins-verdict-text">{verdict}</span>
        {met !== null ? (
          <span className="lp-margins-count">{met}/{view.nApplicable}</span>
        ) : null}
      </div>

      {/* A verdict of "met" says nothing about how nearly it was not, and this
          margin is the number an operator actually plans against. */}
      {view.minMargin ? (
        <p className="lp-margins-tightest">
          <span>Tightest</span>
          <b>{view.minMargin.id}</b>
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

      <p className="lp-margins-foot">
        {untested > 0 ? (
          <span className="lp-margins-untested">
            {untested} untested, which is not passed.
          </span>
        ) : null}
        {/* One line, not a paragraph: the claim boundary and the requirement
            texts are in the report, and saying so is what keeps them findable
            without putting them here. */}
        <span>Runtime monitoring — full requirements and claim in the report.</span>
      </p>
    </div>
  )
}
