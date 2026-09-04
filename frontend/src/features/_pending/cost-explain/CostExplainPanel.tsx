import type { CostRow } from './useCostExplain'
import './cost-explain.css'

export function CostExplainPanel({
  rows,
  total,
  impassable,
  impassableBy,
  cell,
}: {
  rows: CostRow[]
  total: number | null
  impassable: boolean
  impassableBy: string[]
  cell: [number, number] | null
}) {
  if (!cell || rows.length === 0) {
    return (
      <p className="lp-cost-note">
        Hover a cell on the map to see what makes it expensive.
      </p>
    )
  }

  return (
    <div className="lp-cost-card">
      <div className="lp-cost-head">
        <span className="lp-cost-cell">
          row {cell[0]} · col {cell[1]}
        </span>
        {impassable ? (
          <span className="lp-cost-verdict lp-cost-impassable">Impassable</span>
        ) : (
          <span className="lp-cost-verdict">
            {total === null ? 'unknown' : total.toFixed(3)}
          </span>
        )}
      </div>

      {impassable ? (
        impassableBy.length > 0 ? (
          <p className="lp-cost-reason">
            Closed by <strong>{impassableBy.join(', ')}</strong>. This cell costs
            infinity — no route can cross it.
          </p>
        ) : (
          // Every component came back finite and the cell is still closed:
          // the traversability gate rejected it, or one of its source layers
          // has no value here (costmap.py:66-75). Naming a cost component
          // would be wrong -- none of them is the reason.
          <p className="lp-cost-reason">
            Closed by the traversability gate, not by a cost component — the
            cell is off-limits or a source layer has no value here. No route
            can cross it.
          </p>
        )
      ) : null}

      <ul className="lp-cost-bars">
        {rows.map((row) => (
          <li key={row.key} className="lp-cost-bar-row">
            <span className="lp-cost-label">
              {row.label}
              <em className="lp-cost-weight">w {row.weight.toFixed(3)}</em>
            </span>

            <span className="lp-cost-track">
              {/* A null contribution is never drawn as a zero-length bar --
                  infinity is the largest value there is, not the smallest. */}
              {row.value === null ? (
                <span className="lp-cost-fill lp-cost-fill-inf" style={{ width: '100%' }} />
              ) : (
                <span
                  className="lp-cost-fill"
                  style={{ width: `${Math.min(100, row.share * 100)}%` }}
                />
              )}
            </span>

            <span className="lp-cost-value">
              {row.value === null ? '∞' : row.value.toFixed(3)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
