import { Icon, type IconName } from '../../components/Fleet/SpecIcons'
import { Meter, Readout, type Tone } from '../../components/Instrument'
import { formatMargin, readSafetyMargins } from '../safety-margins/safetyMargins'
import { readRouteModel } from '../route-model/routeModel'
import type { ReportCopy } from '../../i18n/reportCopy'

/**
 * The evidence behind the rail's numbers.
 *
 * These blocks ship with every plan response and each carries eighty to a
 * hundred and twenty words of qualification: what the slip curve is anchored
 * to and what it is not, why CVaR of MODEL distributions is not a measured
 * risk, why a LOLA block statistic is not the roughness of the cell it is
 * painted on. All of it matters and none of it belongs in a 288px rail.
 *
 * But a report is not an excuse for a wall of text either. Every claim here is
 * a FRAMED, LABELLED block rather than a paragraph, so a reader scanning for
 * "what is this number allowed to mean" finds it by shape; the requirements
 * table carries the same margin meter the rail does, so the two read as one
 * document; and the backend's own words are never paraphrased, because that is
 * how a claim boundary drifts.
 */

const TONE_BY_STATE: Record<string, Tone> = {
  satisfied: 'ok',
  boundary: 'warn',
  violated: 'bad',
  pending: 'muted',
  'not-applicable': 'muted',
}

/** A claim, a scope or a reason, framed and labelled so it can be found. */
function Note({
  label,
  icon,
  tone,
  children,
}: {
  label: string
  icon: IconName
  tone?: 'claim' | 'scope' | 'absent'
  children: React.ReactNode
}) {
  return (
    <div className={`lp-ev-note is-${tone ?? 'claim'}`}>
      <span className="lp-ev-note-label">
        <Icon name={icon} />
        {label}
      </span>
      <p className="lp-ev-note-body">{children}</p>
    </div>
  )
}

/** Every requirement, with the sentence it was written as. */
export function SafetyEvidence({ plan, t }: { plan: unknown; t: ReportCopy }) {
  const view = readSafetyMargins(plan)
  if (!view) return null

  const met = view.nApplicable !== null ? view.nApplicable - (view.nViolated ?? 0) : null
  const untested = view.requirements.filter((r) => r.state === 'not-applicable').length

  return (
    <div className="lp-ev">
      <div className="lp-ev-head">
        <Readout
          label={view.verdict === 'satisfied' ? 'All requirements met' : 'Requirements violated'}
          value={met !== null ? `${met}/${view.nApplicable}` : '--'}
          unit="met"
          tone={view.verdict === 'satisfied' ? 'ok' : 'bad'}
          sub={untested > 0 ? `${untested} ${t.evidence.untested}` : undefined}
        />
        <p className="lp-ev-meta">
          {t.evidence.monitor}: {view.engine ?? '--'}
          {view.crossCheckMaxDiff !== null ? ` · cross-check Δ ${view.crossCheckMaxDiff}` : ''}
          {view.traceKind ? ` · ${view.traceKind}` : ''}
          {view.traceComplete === false ? ' · incomplete' : ''}
        </p>
      </div>

      <div className="lp-report-table-wrap">
        <table className="lp-report-table lp-ev-table">
          <thead>
            <tr>
              <th>{t.evidence.requirement}</th>
              <th className="lp-ev-num">{t.evidence.margin}</th>
              <th className="lp-ev-meter-col">&nbsp;</th>
              <th className="lp-ev-num">{t.evidence.worstAt}</th>
            </tr>
          </thead>
          <tbody>
            {view.requirements.map((requirement) => {
              const untestable =
                requirement.state === 'not-applicable' || requirement.state === 'pending'
              const rho = requirement.rhoNormalized
              return (
                <tr key={requirement.id} className={`is-${requirement.state}`}>
                  <td>
                    <span className="lp-ev-id">{requirement.id}</span>
                    {/* The FRETISH sentence is the requirement. The short name
                        alone leaves the reader to guess what was checked. */}
                    <span className="lp-ev-fretish">
                      {requirement.fretish ?? requirement.name.replace(/_/g, ' ')}
                    </span>
                    {requirement.state === 'not-applicable' && requirement.reason ? (
                      <span className="lp-ev-reason">{requirement.reason}</span>
                    ) : null}
                  </td>
                  <td className="lp-ev-num">
                    {untestable ? '--' : formatMargin(requirement)}
                  </td>
                  <td className="lp-ev-meter-col">
                    {/* The same axis the rail draws, so the two are one
                        document rather than two readings of one route. */}
                    <Meter
                      fraction={untestable || rho === null ? 0 : Math.max(-1, Math.min(1, rho))}
                      origin={0.5}
                      tone={TONE_BY_STATE[requirement.state] ?? 'muted'}
                      ticks={4}
                      clamped={rho !== null && Math.abs(rho) > 1}
                    />
                  </td>
                  <td className="lp-ev-num">
                    {requirement.worstAt?.hours != null
                      ? `${requirement.worstAt.hours.toFixed(2)} h`
                      : '--'}
                    {requirement.worstAt?.row != null && requirement.worstAt?.col != null
                      ? ` · ${requirement.worstAt.row},${requirement.worstAt.col}`
                      : ''}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {view.claim ? (
        <Note label={t.evidence.claimBoundary} icon="shield">{view.claim}</Note>
      ) : null}
    </div>
  )
}

/** Slip, risk, roughness, survival and thermal: what each is, and is not. */
export function CostModelEvidence({ plan, t }: { plan: unknown; t: ReportCopy }) {
  const view = readRouteModel(plan)
  const blocks: Array<{
    title: string
    icon: IconName
    validity: string[]
    claim: string | null
    reason: string | null
    scope?: string | null
    references: string[]
  }> = []

  if (view.slip) {
    blocks.push({
      title: 'Slip', icon: 'climb',
      validity: [view.slip.validity ?? 'MODEL'],
      claim: view.slip.claim,
      reason: view.slip.applied ? null : view.slip.reason,
      references: view.slip.references,
    })
  }
  if (view.risk) {
    blocks.push({
      title: 'Risk appetite (CVaR)', icon: 'levels',
      validity: [view.risk.validity ?? 'MODEL'],
      claim: view.risk.claim, reason: null, scope: view.risk.scope, references: [],
    })
  }
  if (view.roughness) {
    blocks.push({
      title: 'Roughness', icon: 'terrain',
      // Two labels, kept apart: the product is measured, turning it into a
      // cost is a model.
      validity: [
        view.roughness.validity ?? 'MEASURED',
        ...(view.roughness.scaleValidity ? [`scale ${view.roughness.scaleValidity}`] : []),
      ],
      claim: view.roughness.claim,
      reason: view.roughness.applied ? null : view.roughness.reason,
      references: view.roughness.references,
    })
  }
  if (view.survival) {
    blocks.push({
      title: 'Execution survival', icon: 'shield',
      validity: [view.survival.validity ?? 'MODEL'],
      claim: view.survival.claim,
      reason: view.survival.applied ? null : view.survival.reason,
      references: view.survival.failureSource ? [view.survival.failureSource] : [],
    })
  }
  if (view.thermal) {
    blocks.push({
      title: 'Thermal dwell', icon: 'thermal',
      // The weaker label last: a model with no calibration behind it is a
      // further step from a measurement than a model is.
      validity: [
        view.thermal.validity ?? 'MODEL',
        ...(view.thermal.lagValidity ? [`lag ${view.thermal.lagValidity}`] : []),
      ],
      claim: view.thermal.claim, reason: null, references: [],
    })
  }
  if (blocks.length === 0) return null

  return (
    <div className="lp-ev">
      {blocks.map((block) => (
        <section key={block.title} className="lp-ev-block">
          <header className="lp-ev-block-head">
            <Icon name={block.icon} className="lp-ev-block-icon" />
            <h5>{block.title}</h5>
            <span className="lp-ev-validity">
              {block.validity.map((level) => (
                <i
                  key={level}
                  className={`lp-ev-chip ${
                    level.toUpperCase().includes('UNCALIBRATED')
                      ? 'is-uncalibrated'
                      : level.toUpperCase().startsWith('MEASURED')
                        ? 'is-measured'
                        : 'is-model'
                  }`}
                >
                  {level}
                </i>
              ))}
            </span>
          </header>

          {block.scope ? (
            <Note label={t.evidence.scope} icon="target" tone="scope">{block.scope}</Note>
          ) : null}
          {/* Why a block did not count is evidence too: the backend's reason
              names the cache file and the script that builds it. */}
          {block.reason ? (
            <Note label={t.evidence.notApplied} icon="info" tone="absent">{block.reason}</Note>
          ) : null}
          {block.claim ? (
            <Note label={t.evidence.claimBoundary} icon="shield">{block.claim}</Note>
          ) : null}

          {block.references.length > 0 ? (
            <ul className="lp-ev-refs">
              <li className="lp-ev-refs-label">{t.evidence.sources}</li>
              {block.references.map((reference) => (
                <li key={reference}>{reference}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ))}
    </div>
  )
}
