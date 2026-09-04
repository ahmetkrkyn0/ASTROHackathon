import type { Corridor } from '../../net/types'
import type { SegmentRow } from './useCorridor'
import './corridor.css'

function narrowest(segments: SegmentRow[]): SegmentRow | null {
  return segments.reduce<SegmentRow | null>(
    (best, row) => (best === null || row.halfWidthM < best.halfWidthM ? row : best),
    null,
  )
}

export function CorridorPanel({
  corridor,
  segments,
  error,
}: {
  corridor: Corridor | null
  segments: SegmentRow[]
  error: string | null
}) {
  if (error) return <p className="lp-corridor-note lp-corridor-warn">{error}</p>

  // build_corridor rejects a path shorter than two waypoints, and the plan
  // response carries corridor: null in that case -- say so rather than
  // rendering an empty table that looks like a corridor with no segments.
  if (!corridor) {
    return (
      <p className="lp-corridor-note">
        No corridor. Plan a route first — a corridor needs at least two waypoints.
      </p>
    )
  }

  const tightest = narrowest(segments)

  return (
    <div className="lp-corridor-card">
      <div className="lp-corridor-head">
        <span className="lp-corridor-id" title="Echo this back to /api/pose">
          {corridor.corridor_id}
        </span>
        <span className="lp-corridor-count">{segments.length} segments</span>
      </div>

      {tightest ? (
        <p className="lp-corridor-tight">
          Narrowest point: <strong>{tightest.halfWidthM.toFixed(1)} m</strong> of
          lateral room at segment {tightest.index}
        </p>
      ) : null}

      <div className="lp-corridor-scroll">
        <table className="lp-corridor-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Half-width</th>
              <th>Slope cap</th>
              <th>Energy</th>
              <th>Thermal</th>
            </tr>
          </thead>
          <tbody>
            {segments.map((row) => (
              <tr key={row.index}>
                <td>{row.index}</td>
                <td>{row.halfWidthM.toFixed(1)} m</td>
                <td>{row.maxSlopeDeg.toFixed(1)}°</td>
                <td>{row.energyWh.toFixed(1)} Wh</td>
                <td>{row.thermalKs.toFixed(0)} K·s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
