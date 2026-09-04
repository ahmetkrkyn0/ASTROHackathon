import type { ReferenceMissions, RouteStatistics } from '../../net/types'
import './mission-validation.css'

export function MissionValidationPanel({
  reference,
  stats,
  ourDrivingRateMPerDay,
  loading,
  error,
}: {
  reference: ReferenceMissions | null
  stats: RouteStatistics | null
  ourDrivingRateMPerDay: number | null
  loading: boolean
  error: string | null
}) {
  if (loading) return <p className="lp-val-note">Loading published mission figures…</p>
  if (error) return <p className="lp-val-note lp-val-warn">{error}</p>
  if (!reference) return null

  return (
    <div className="lp-val-card">
      <table className="lp-val-table">
        <thead>
          <tr>
            <th>Mission</th>
            <th>Distance</th>
            <th>Rate</th>
            <th>As of</th>
          </tr>
        </thead>
        <tbody>
          {reference.missions.map((mission) => (
            <tr key={mission.mission}>
              <td>{mission.mission}</td>
              <td>{(mission.total_distance_m / 1000).toFixed(2)} km</td>
              <td>{mission.lower_bound_rate_m_per_calendar_day.toFixed(2)} m/day</td>
              <td>{mission.as_of}</td>
            </tr>
          ))}
          {stats ? (
            <tr className="lp-val-ours">
              <td>This route</td>
              <td>{stats.waypoint_count} waypoints</td>
              <td>
                {ourDrivingRateMPerDay === null
                  ? '—'
                  : `${ourDrivingRateMPerDay.toFixed(0)} m/day`}
              </td>
              <td>driving only</td>
            </tr>
          ) : null}
        </tbody>
      </table>

      {/* The caveat travels with the numbers. Without it the rate column
          reads as a driving speed, which it is not. */}
      <p className="lp-val-caveat">{reference.note}</p>

      {/* And the note alone is not enough here: the two rates differ by five
          orders of magnitude because they measure different things, so the
          row above says "driving only" and this says why. */}
      {stats && ourDrivingRateMPerDay !== null ? (
        <p className="lp-val-caveat">
          This route&rsquo;s rate is its simulated traverse clock only — it excludes
          the lunar nights the published rates are averaged over, so the two
          columns are not the same measurement and the larger number is not a
          faster rover.
        </p>
      ) : null}

      {stats ? (
        <>
          <h4 className="lp-val-subhead">Slope distribution</h4>
          <ul className="lp-val-hist">
            {stats.slope_histogram.map((bin) => (
              <li key={`${bin.bin_low_deg}-${bin.bin_high_deg}`}>
                <span className="lp-val-bin">
                  {bin.bin_low_deg}–{bin.bin_high_deg}°
                </span>
                <span className="lp-val-track">
                  {/* pct comes from the backend; recomputing count/total here
                      would disagree with it wherever it rounds. */}
                  <span className="lp-val-fill" style={{ width: `${bin.pct}%` }} />
                </span>
                <span className="lp-val-count">{bin.count}</span>
              </li>
            ))}
          </ul>

          <h4 className="lp-val-subhead">Risk mix</h4>
          <ul className="lp-val-risk">
            {Object.entries(stats.risk_breakdown_pct).map(([level, pct]) => (
              <li key={level}>
                <span>{level}</span>
                <span>{pct.toFixed(1)}%</span>
              </li>
            ))}
          </ul>

          <p className="lp-val-temps">
            Surface temperature along route:{' '}
            {stats.min_surface_temp_c === null || stats.max_surface_temp_c === null
              ? 'unknown'
              : `${stats.min_surface_temp_c.toFixed(1)} °C to ${stats.max_surface_temp_c.toFixed(1)} °C`}
          </p>
        </>
      ) : (
        <p className="lp-val-note">Plan a route to compare it against these missions.</p>
      )}
    </div>
  )
}
