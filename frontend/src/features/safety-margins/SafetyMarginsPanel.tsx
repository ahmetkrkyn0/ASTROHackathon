import { Icon, type IconName } from '../../components/Fleet/SpecIcons'
import { Divide, Meter, Readout, type Tone } from '../../components/Instrument'
import { formatMargin, type MarginState, type RequirementView, type SafetyMarginsView } from './safetyMargins'
import './safety-margins.css'

/**
 * The twelve formal requirements, as an instrument.
 *
 * One headline -- how many of the applicable requirements this route meets --
 * and everything else sized under it. Before, the verdict, the tightest margin
 * and twelve rows were all the same weight, so there was nothing to read
 * first.
 *
 * The rows are a chart, not a list. `rho_normalized` is the contract's own
 * comparison key, which makes twelve requirements measured in hours, degrees C,
 * percentage points, degrees and metres directly comparable to one another and
 * to zero. They share one axis with a marked origin: right is margin, left is
 * violation, and the scale is drawn once at the top rather than repeated
 * twelve times.
 */

const STATE_META: Record<MarginState, { icon: IconName; label: string; tone: Tone }> = {
  satisfied: { icon: 'check', label: 'Margin', tone: 'ok' },
  boundary: { icon: 'target', label: 'At limit', tone: 'warn' },
  violated: { icon: 'error', label: 'Violated', tone: 'bad' },
  pending: { icon: 'clock', label: 'Undecided', tone: 'muted' },
  'not-applicable': { icon: 'help', label: 'Not checked', tone: 'muted' },
}

const VERDICT: Record<string, { text: string; tone: Tone }> = {
  satisfied: { text: 'All requirements met', tone: 'ok' },
  violated: { text: 'Requirements violated', tone: 'bad' },
  pending: { text: 'Verdict pending', tone: 'warn' },
  not_evaluated: { text: 'Not evaluated', tone: 'muted' },
}

function Requirement({ requirement }: { requirement: RequirementView }) {
  const meta = STATE_META[requirement.state]
  const untested = requirement.state === 'not-applicable' || requirement.state === 'pending'
  const rho = requirement.rhoNormalized

  return (
    <li className={`lp-margin-row is-${requirement.state}`}>
      <Icon name={meta.icon} className="lp-margin-icon" />
      <span className="lp-margin-id">{requirement.id}</span>
      <span className="lp-margin-name">{requirement.name.replace(/_/g, ' ')}</span>
      <span className="lp-margin-value">
        {untested ? meta.label : formatMargin(requirement)}
      </span>
      <div className="lp-margin-meter">
        {/* An untested requirement gets an empty axis rather than a zero-length
            bar: no margin was measured, and a bar of any length would claim
            one was. */}
        <Meter
          fraction={untested || rho === null ? 0 : Math.max(-1, Math.min(1, rho))}
          origin={0.5}
          tone={meta.tone}
          ticks={4}
          clamped={rho !== null && Math.abs(rho) > 1}
        />
      </div>
    </li>
  )
}

export function SafetyMarginsPanel({ view }: { view: SafetyMarginsView }) {
  const verdict = VERDICT[view.verdict] ?? { text: view.verdict, tone: 'muted' as Tone }
  const untested = view.requirements.filter((r) => r.state === 'not-applicable').length
  const met = view.nApplicable !== null ? view.nApplicable - (view.nViolated ?? 0) : null

  return (
    <div className="lp-margins">
      <Readout
        label={verdict.text}
        value={met !== null ? `${met}/${view.nApplicable}` : '--'}
        unit="met"
        tone={verdict.tone}
        sub={
          view.minMargin ? (
            <>
              Tightest <b className="lp-margins-tight-id">{view.minMargin.id}</b>
              {view.minMargin.rho !== null ? (
                <>
                  {' '}
                  {view.minMargin.rho > 0 ? '+' : ''}
                  {view.minMargin.rho.toFixed(2)}
                  {view.minMargin.unit ? ` ${view.minMargin.unit}` : ''}
                </>
              ) : null}
            </>
          ) : null
        }
      />

      <Divide label="Robustness" />

      {/* Drawn once, not twelve times: every row shares this axis. */}
      <div className="lp-margins-axis" aria-hidden="true">
        <span>violation</span>
        <span className="lp-margins-axis-zero">0</span>
        <span>margin</span>
      </div>

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
