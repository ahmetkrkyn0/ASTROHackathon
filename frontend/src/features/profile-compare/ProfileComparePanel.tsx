import React from 'react'
import { Icon } from '../../components/Fleet/SpecIcons'
import type { ProfileResult } from '../../net/types'
import { readConstraints } from './useProfileCompare'
import './profile-compare.css'

function metric(result: ProfileResult, key: string): string {
  const value = result.metrics[key]
  return typeof value === 'number' ? value.toFixed(1) : '—'
}

function str(source: Record<string, unknown> | null, key: string): string | null {
  const value = source?.[key]
  return typeof value === 'string' ? value : null
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
  const recommendation = str(comparison, 'recommendation')

  /* Which profile wins on what, straight from /api/compare. The badge is not a
     judgement this panel makes -- `safest_profile` is the backend's own word,
     and the recommendation sentence below names the same id. */
  const safest = str(comparison, 'safest_profile')
  const efficient = str(comparison, 'most_efficient_profile')
  const shortest = str(comparison, 'shortest_profile')

  const strengthOf = (id: string): string | null => {
    if (id === safest) return 'Safest envelope'
    if (id === efficient) return 'Lowest weighted cost'
    if (id === shortest) return 'Shortest path'
    return null
  }

  return (
    <div className="lp-compare-card">
      <button type="button" className="lp-compare-run" disabled={busy} onClick={run}>
        <Icon name="balance" />
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
        const strength = strengthOf(result.profile_id)

        return (
          <div
            key={result.profile_id}
            className="lp-compare-row"
            style={{ '--profile-color': result.color } as React.CSSProperties}
          >
            <div className="lp-compare-head">
              <span className="lp-compare-swatch" style={{ background: result.color }} />
              <span className="lp-compare-name">
                {result.profile_name ?? result.profile_id}
              </span>
              {result.profile_id === safest ? (
                <span className="lp-compare-badge">RECOMMENDED</span>
              ) : null}
            </div>

            {/* A profile that failed is shown as failed. Dropping the row
                would make four profiles silently become three. */}
            {result.error ? (
              <p className="lp-compare-error">{result.error}</p>
            ) : (
              <>
                <dl className="lp-compare-metrics">
                  <div><dt>Distance</dt><dd>{metric(result, 'total_distance_m')} m</dd></div>
                  <div><dt>Cost</dt><dd>{metric(result, 'total_weighted_cost')}</dd></div>
                  <div><dt>Max slope</dt><dd>{metric(result, 'max_slope_deg')}°</dd></div>
                  <div><dt>Nodes</dt><dd>{metric(result, 'path_length_nodes')}</dd></div>
                </dl>

                {/* One status line, so the four cards can be compared down the
                    column rather than read one at a time. A clean profile says
                    so and adds what it is best at; a failing one leads with
                    which limit it broke. */}
                {violated.length > 0 ? (
                  <p className="lp-compare-status is-bad">
                    <Icon name="warning" />
                    Violates: {violated.map((c) => c.name).join(', ')}
                  </p>
                ) : (
                  <p className="lp-compare-status is-good">
                    <Icon name="check" />
                    No violations
                    {strength ? <span className="lp-compare-strength">· {strength}</span> : null}
                  </p>
                )}

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
