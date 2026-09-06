import { Icon, type IconName } from '../../components/Fleet/SpecIcons'
import { formatMargin, type MarginState, type RequirementView, type SafetyMarginsView } from './safetyMargins'
import './safety-margins.css'

/**
 * The rail readout: a verdict, the tightest margin, and twelve rows that are
 * drawn rather than listed.
 *
 * `rho_normalized` is the contract's own comparison key -- robustness over the
 * requirement's scale -- which means the twelve values are directly comparable
 * to one another and to zero. That is a chart, not a column of numbers, so the
 * rows carry a bar that diverges from a shared centre: right of it is margin,
 * left of it is violation, and how far tells you by how much. Reading "which
 * one is tight" off twelve right-aligned figures was work the eye should not
 * have to do.
 *
 * The evidence is not here. Each requirement's FRETISH sentence, the monitor
 * provenance and the claim boundary are in the mission report, where the
 * measure is wide enough to read them.
 */

const STATE_META: Record<MarginState, { icon: IconName; label: string }> = {
  satisfied: { icon: 'check', label: 'Margin' },
  boundary: { icon: 'target', label: 'At limit' },
  violated: { icon: 'error', label: 'Violated' },
  pending: { icon: 'clock', label: 'Undecided' },
  'not-applicable': { icon: 'help', label: 'Not checked' },
}

const VERDICT_META: Record<string, { icon: IconName; text: string }> = {
  satisfied: { icon: 'check', text: 'ALL REQUIREMENTS MET' },
  violated: { icon: 'warning', text: 'REQUIREMENTS VIOLATED' },
  pending: { icon: 'clock', text: 'VERDICT PENDING' },
  not_evaluated: { icon: 'help', text: 'NOT EVALUATED' },
}

/**
 * Half-width of the bar, as a fraction of the track. A normalised margin of 1
 * fills its side; anything past that is clamped and flagged, because a bar
 * that keeps growing stops being comparable and a violation at -2.6 would
 * otherwise dwarf every other row into invisibility.
 */
function barWidth(rhoNormalized: number | null): number {
  if (rhoNormalized === null) return 0
  return Math.min(Math.abs(rhoNormalized), 1) * 50
}

function Requirement({ requirement }: { requirement: RequirementView }) {
  const meta = STATE_META[requirement.state]
  const untested = requirement.state === 'not-applicable'
  const rho = requirement.rhoNormalized
  const width = barWidth(rho)
  const negative = rho !== null && rho < 0
  const clamped = rho !== null && Math.abs(rho) > 1

  return (
    <li className={`lp-margin-row is-${requirement.state}`}>
      <Icon name={meta.icon} className="lp-margin-icon" />
      <span className="lp-margin-id">{requirement.id}</span>
      <span className="lp-margin-name">{requirement.name.replace(/_/g, ' ')}</span>
      <span className="lp-margin-value">
        {untested ? meta.label : formatMargin(requirement)}
      </span>

      {/* The bar spans the row under the label. A shared centre line is what
          makes twelve requirements in five different units comparable at a
          glance -- it is the only thing they have in common. */}
      <span className="lp-margin-track" aria-hidden="true">
        <span className="lp-margin-zero" />
        {width > 0 ? (
          <span
            className={`lp-margin-bar ${negative ? 'is-negative' : 'is-positive'} ${clamped ? 'is-clamped' : ''}`}
            style={negative
              ? { right: '50%', width: `${width}%` }
              : { left: '50%', width: `${width}%` }}
          />
        ) : null}
      </span>
    </li>
  )
}

export function SafetyMarginsPanel({ view }: { view: SafetyMarginsView }) {
  const verdict = VERDICT_META[view.verdict] ?? { icon: 'help' as IconName, text: view.verdict.toUpperCase() }
  const untested = view.requirements.filter((r) => r.state === 'not-applicable').length
  const met = view.nApplicable !== null ? view.nApplicable - (view.nViolated ?? 0) : null

  return (
    <div className="lp-margins">
      <div className={`lp-margins-verdict is-${view.verdict}`}>
        <Icon name={verdict.icon} className="lp-margins-verdict-icon" />
        <span className="lp-margins-verdict-text">{verdict.text}</span>
        {met !== null ? (
          <span className="lp-margins-count">
            <b>{met}</b>/{view.nApplicable}
          </span>
        ) : null}
      </div>

      {/* A verdict of "met" says nothing about how nearly it was not, and this
          margin is the number an operator actually plans against. */}
      {view.minMargin ? (
        <p className="lp-margins-tightest">
          <Icon name="target" />
          <span className="lp-margins-tightest-label">Tightest</span>
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
            <Icon name="help" />
            {untested} untested — which is not passed.
          </span>
        ) : null}
        <span className="lp-margins-report">
          <Icon name="report" />
          Requirement text and claim in the mission report.
        </span>
      </p>
    </div>
  )
}
