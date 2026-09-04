import type { ProfileResult } from '../../net/types'
import { readConstraints } from './useProfileCompare'
import './profile-compare.css'

function metric(result: ProfileResult, key: string): string {
  const value = result.metrics[key]
  return typeof value === 'number' ? value.toFixed(1) : '—'
}

export function ProfileComparePanel({
  results,
  comparison,
  run,
  busy,
  error,
}: {
  results: ProfileResult[]
  comparison: Record<string, unknown> | null
  run: () => void
  busy: boolean
  error: string | null
}) {
  const recommendation =
    typeof comparison?.recommendation === 'string' ? comparison.recommendation : null

  return (
    <div className="lp-compare-card">
      <button type="button" className="lp-compare-run" disabled={busy} onClick={run}>
        {busy ? 'Comparing…' : 'Compare all profiles'}
      </button>

      {error ? <p className="lp-compare-note lp-compare-warn">{error}</p> : null}

      {/* The backend's own summary, verbatim. It states its own limits --
          "energy and shadow totals are not tracked in fast mode, so neither
          ranking is an energy claim" -- and paraphrasing would drop that. */}
      {recommendation ? (
        <p className="lp-compare-recommendation">{recommendation}</p>
      ) : null}

      {results.map((result) => {
        const constraints = readConstraints(result)
        const violated = constraints.filter((c) => c.checked && !c.satisfied)
        const unchecked = constraints.filter((c) => !c.checked && !c.enforcedInSearch)

        return (
          <div key={result.profile_id} className="lp-compare-row">
            <div className="lp-compare-head">
              <span className="lp-compare-swatch" style={{ background: result.color }} />
              <span className="lp-compare-name">
                {result.profile_name ?? result.profile_id}
              </span>
            </div>

            {/* A profile that failed is shown as failed. Dropping the row
                would make four profiles silently become three. */}
            {result.error ? (
              <p className="lp-compare-error">{result.error}</p>
            ) : (
              <>
                <dl className="lp-compare-metrics">
                  <div><dt>Distance</dt><dd>{metric(result, 'total_distance_m')} m</dd></div>
                  <div><dt>Max slope</dt><dd>{metric(result, 'max_slope_deg')}°</dd></div>
                  <div><dt>Cost</dt><dd>{metric(result, 'total_weighted_cost')}</dd></div>
                  <div><dt>Nodes</dt><dd>{metric(result, 'path_length_nodes')}</dd></div>
                </dl>

                {violated.length > 0 ? (
                  <p className="lp-compare-violated">
                    Violated: {violated.map((c) => c.name).join(', ')}
                  </p>
                ) : null}

                {unchecked.length > 0 ? (
                  <p className="lp-compare-unchecked">
                    Not checked: {unchecked.map((c) => c.name).join(', ')}
                  </p>
                ) : null}
              </>
            )}
          </div>
        )
      })}
    </div>
  )
}
