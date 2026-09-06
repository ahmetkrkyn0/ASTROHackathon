import { formatMargin, readSafetyMargins } from '../safety-margins/safetyMargins'
import { readRouteModel } from '../route-model/routeModel'
import type { ReportCopy } from '../../i18n/reportCopy'

/**
 * The evidence behind the rail's numbers.
 *
 * These blocks -- the twelve FRETISH requirements, and the claim boundaries on
 * slip, risk and roughness -- ship with every plan response and each carries
 * eighty to a hundred and twenty words of qualification: what the slip curve
 * is anchored to and what it is not, why CVaR of MODEL distributions is not a
 * measured risk, why a LOLA block statistic is not the roughness of the cell
 * it is painted on.
 *
 * All of it matters and none of it belongs in a 288 px rail, where it read as
 * three paragraphs of prose stacked above the six numbers it was meant to
 * qualify. A report is a document: it is where a sentence that long is
 * actually read, and where a reader has already chosen to go deeper.
 *
 * The backend's own words throughout. Paraphrasing a claim boundary is how it
 * drifts.
 */

/** Every requirement, with the sentence it was written as. */
export function SafetyEvidence({ plan, t }: { plan: unknown; t: ReportCopy }) {
  const view = readSafetyMargins(plan)
  if (!view) return null

  return (
    <div className="lp-ev">
      <table className="lp-ev-table">
        <thead>
          <tr>
            <th>{t.evidence.requirement}</th>
            <th className="lp-ev-num">{t.evidence.margin}</th>
            <th className="lp-ev-num">{t.evidence.worstAt}</th>
          </tr>
        </thead>
        <tbody>
          {view.requirements.map((requirement) => (
            <tr key={requirement.id} className={`is-${requirement.state}`}>
              <td>
                <span className="lp-ev-id">{requirement.id}</span>
                {/* The FRETISH sentence is the requirement. Showing the short
                    name alone leaves the reader to guess what was checked. */}
                <span className="lp-ev-fretish">
                  {requirement.fretish ?? requirement.name.replace(/_/g, ' ')}
                </span>
                {requirement.state === 'not-applicable' ? (
                  <span className="lp-ev-reason">
                    {requirement.reason ?? t.evidence.untested}
                  </span>
                ) : null}
              </td>
              <td className="lp-ev-num">
                {requirement.state === 'not-applicable' ? '--' : formatMargin(requirement)}
              </td>
              <td className="lp-ev-num">
                {requirement.worstAt?.hours !== null && requirement.worstAt
                  ? `${requirement.worstAt.hours!.toFixed(2)} h`
                  : '--'}
                {requirement.worstAt?.row !== null && requirement.worstAt?.col !== null && requirement.worstAt
                  ? ` · ${requirement.worstAt.row},${requirement.worstAt.col}`
                  : ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {view.claim ? (
        <p className="lp-ev-claim">
          <span className="lp-ev-claim-label">{t.evidence.claimBoundary}</span>
          {view.claim}
        </p>
      ) : null}

      <p className="lp-ev-meta">
        {t.evidence.monitor}: {view.engine ?? '--'}
        {view.crossCheckMaxDiff !== null ? ` · cross-check Δ ${view.crossCheckMaxDiff}` : ''}
        {view.traceKind ? ` · ${view.traceKind}` : ''}
        {view.traceComplete === false ? ' · incomplete' : ''}
      </p>
    </div>
  )
}

/** Slip, risk and roughness: what each is, and what each is not. */
export function CostModelEvidence({ plan, t }: { plan: unknown; t: ReportCopy }) {
  const view = readRouteModel(plan)
  const blocks: Array<{
    title: string
    validity: string
    claim: string | null
    reason: string | null
    scope?: string | null
    references: string[]
  }> = []

  if (view.slip) {
    blocks.push({
      title: 'Slip',
      validity: view.slip.validity ?? 'MODEL',
      claim: view.slip.claim,
      reason: view.slip.applied ? null : view.slip.reason,
      references: view.slip.references,
    })
  }
  if (view.risk) {
    blocks.push({
      title: 'Risk appetite (CVaR)',
      validity: view.risk.validity ?? 'MODEL',
      claim: view.risk.claim,
      reason: null,
      scope: view.risk.scope,
      references: [],
    })
  }
  if (view.roughness) {
    blocks.push({
      title: 'Roughness',
      validity: `${view.roughness.validity ?? 'MEASURED'}${
        view.roughness.scaleValidity ? ` · scale ${view.roughness.scaleValidity}` : ''
      }`,
      claim: view.roughness.claim,
      reason: view.roughness.applied ? null : view.roughness.reason,
      references: view.roughness.references,
    })
  }
  if (view.survival) {
    blocks.push({
      title: 'Execution survival',
      validity: view.survival.validity ?? 'MODEL',
      claim: view.survival.claim,
      reason: view.survival.applied ? null : view.survival.reason,
      references: view.survival.failureSource ? [view.survival.failureSource] : [],
    })
  }
  if (view.thermal) {
    blocks.push({
      title: 'Thermal dwell',
      // Both labels, and the weaker one last: a model with no calibration is
      // a further step from a measurement than a model is.
      validity: `${view.thermal.validity ?? 'MODEL'}${
        view.thermal.lagValidity ? ` · lag ${view.thermal.lagValidity}` : ''
      }`,
      claim: view.thermal.claim,
      reason: null,
      references: [],
    })
  }
  if (blocks.length === 0) return null

  return (
    <div className="lp-ev">
      {blocks.map((block) => (
        <section key={block.title} className="lp-ev-block">
          <header className="lp-ev-block-head">
            <h5>{block.title}</h5>
            <span className="lp-ev-validity">{block.validity}</span>
          </header>
          {block.scope ? (
            <p className="lp-ev-scope">
              <span className="lp-ev-claim-label">{t.evidence.scope}</span>
              {block.scope}
            </p>
          ) : null}
          {/* Why a block did not count is evidence too: the backend's reason
              names the cache file and the script that builds it. */}
          {block.reason ? (
            <p className="lp-ev-scope">
              <span className="lp-ev-claim-label">{t.evidence.notApplied}</span>
              {block.reason}
            </p>
          ) : null}
          {block.claim ? <p className="lp-ev-claim">{block.claim}</p> : null}
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
