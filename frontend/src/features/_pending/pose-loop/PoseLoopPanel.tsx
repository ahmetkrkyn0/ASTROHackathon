import type { PoseSource } from '../../net/pose'
import { TRIGGER_FIELDS } from '../../mission/triggers'
import type { Corridor, PoseResponse } from '../../net/types'
import type { PoseForm, PoseTriggerRow } from './usePoseLoop'
import './pose-loop.css'

const STATUS_LABEL = { fired: 'Fired', clear: 'Clear', unchecked: 'Not checked' } as const

export function PoseLoopPanel({
  form,
  setField,
  seedFromCorridor,
  submit,
  result,
  busy,
  error,
  rows,
  corridor,
}: {
  form: PoseForm
  setField: <K extends keyof PoseForm>(key: K, value: PoseForm[K]) => void
  seedFromCorridor: (index: number) => void
  submit: () => void
  result: PoseResponse | null
  busy: boolean
  error: string | null
  rows: PoseTriggerRow[]
  corridor: Corridor | null
}) {
  const fix = result?.corridor_fix
  // The backend's own verdict, not a comparison recomputed here: it decides
  // `inside` against the half-width at the segment the pose projected onto,
  // and a second opinion would disagree with it exactly at the boundary.
  const outside = fix ? !fix.inside : false

  return (
    <div className="lp-pose-card">
      {!corridor ? (
        <p className="lp-pose-note">
          No active corridor. Plan a route first — a pose is only meaningful
          against the route the rover is driving.
        </p>
      ) : null}

      <div className="lp-pose-form">
        <label className="lp-pose-field">
          <span>Easting x_m</span>
          <input type="number" step={5} value={form.x_m}
            onChange={(e) => setField('x_m', Number(e.target.value))} />
        </label>
        <label className="lp-pose-field">
          <span>Northing y_m</span>
          <input type="number" step={5} value={form.y_m}
            onChange={(e) => setField('y_m', Number(e.target.value))} />
        </label>
        <label className="lp-pose-field">
          <span>Heading (grid °)</span>
          <input type="number" step={5} value={form.heading_deg}
            onChange={(e) => setField('heading_deg', Number(e.target.value))} />
        </label>
        <label className="lp-pose-field">
          <span>Position 1σ (m)</span>
          <input type="number" step={1} min={0} value={form.covariance_m}
            onChange={(e) => setField('covariance_m', Number(e.target.value))} />
        </label>
        <label className="lp-pose-field">
          <span>Heading 1σ (°)</span>
          <input type="number" step={1} min={0} value={form.heading_covariance_deg}
            onChange={(e) => setField('heading_covariance_deg', Number(e.target.value))} />
        </label>
        <label className="lp-pose-field">
          <span>Odometer claim (m)</span>
          <input type="number" step={10} min={0} value={form.distance_travelled_m}
            onChange={(e) => setField('distance_travelled_m', Number(e.target.value))} />
        </label>

        {/* A free-text source would 422. These five are the whole vocabulary
            (pose.py:50-56), and which one is chosen changes how much the
            backend trusts the fix. */}
        <label className="lp-pose-field lp-pose-wide">
          <span>Source</span>
          <select value={form.source}
            onChange={(e) => setField('source', e.target.value as PoseSource)}>
            <option value="dead_reckoning">dead_reckoning</option>
            <option value="visual_odometry">visual_odometry</option>
            <option value="lidar_odometry">lidar_odometry</option>
            <option value="skyline_fix">skyline_fix (absolute)</option>
            <option value="sun_sensor">sun_sensor (absolute)</option>
          </select>
        </label>
      </div>

      <div className="lp-pose-actions">
        <button type="button" disabled={!corridor}
          onClick={() => seedFromCorridor(Math.floor((corridor?.waypoints.length ?? 1) / 2))}>
          Seed from route
        </button>
        <button type="button" disabled={busy || !corridor} onClick={submit}>
          {busy ? 'Locating…' : 'Evaluate pose'}
        </button>
      </div>

      {error ? <p className="lp-pose-note lp-pose-warn">{error}</p> : null}

      {result && fix ? (
        <>
          <div className={`lp-pose-verdict lp-pose-${result.recommended_action}`}>
            {result.recommended_action.replace(/_/g, ' ')}
          </div>

          <dl className="lp-pose-facts">
            <div>
              <dt>Lateral offset</dt>
              <dd className={outside ? 'lp-pose-bad' : undefined}>
                {fix.lateral_offset_m.toFixed(1)} m
              </dd>
            </div>
            <div>
              <dt>Half-width here</dt>
              <dd>{fix.half_width_at_pose_m.toFixed(1)} m</dd>
            </div>
            <div>
              <dt>Along track</dt>
              <dd>{fix.along_track_m.toFixed(1)} m</dd>
            </div>
            <div>
              <dt>Segment</dt>
              <dd>
                {fix.segment_index} · {(fix.progress_fraction * 100).toFixed(0)}%
              </dd>
            </div>
          </dl>

          <ul className="lp-pose-list">
            {rows.map((row) => (
              <li key={row.id} className={`lp-pose-row lp-pose-${row.status}`}>
                <span>{TRIGGER_FIELDS[row.id].label}</span>
                <span className="lp-pose-status">{STATUS_LABEL[row.status]}</span>
                {row.detail ? <span className="lp-pose-detail">{row.detail}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}
