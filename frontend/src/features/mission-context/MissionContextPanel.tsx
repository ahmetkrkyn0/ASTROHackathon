import { useFocusTelemetry } from '../../mission/MissionContext'
import { capabilityValue } from '../../mission/capability'
import { useCellDetail } from './useCellDetail'
import './mission-context.css'

/**
 * What the pointer is over.
 *
 * This panel used to carry four sections and now carries one. The three that
 * went:
 *
 *  - "Mission context" -- sector, resolution, extent, system state. Every value
 *    was fixed for the session or already stated elsewhere: the extent and the
 *    resolution are printed on the scale bar under the map, and the system
 *    state is the top bar's `Mission LOCKED`. It was a card restating chrome.
 *  - "Active raster layer" -- the name of the layer currently drawn. The layer
 *    picker sits on the map with that name in it, so this was the same word
 *    twice on one screen, one of them 900px from the control that sets it.
 *  - "No route analysed yet" -- an empty state that rendered unconditionally.
 *    It sat above a solved route's full analysis telling the operator no route
 *    had been analysed, with a checklist ticking off the two points they had
 *    just placed. Wrong, not merely redundant.
 *
 * What stays is the only thing here that answers a question the operator is
 * actually asking: where is the pointer, and what is under it. The feature is
 * still registered as `mission-context` -- the id is placement, and renaming it
 * would edit a test about which rail this mounts in to say nothing new.
 *
 * The measured-products block below is the same question with better data, so
 * it extends this inspector rather than opening a second one. Nothing appears
 * unless the backend actually sent it: a deployment with no roughness cache
 * shows the five live values and no more, which is the truth.
 */
export default function MissionContextPanel() {
  const focus = useFocusTelemetry()
  const detail = useCellDetail()
  const cell = capabilityValue(detail)

  // Fields the backend omits or nulls when their layer is not loaded. `null`
  // and absent both mean "this deployment cannot say", which is why neither
  // gets a row: an empty row would imply the question was asked and answered.
  const roughnessM = cell?.roughness_m ?? null
  const fRoughness = cell?.f_roughness ?? null
  const inPsr = cell?.in_psr ?? null
  const haven = cell?.safe_haven ?? null
  const havenReason = cell?.safe_haven_model?.reason ?? null
  const hasMeasured = roughnessM !== null || inPsr !== null
  const survival = cell?.survival ?? null
  const dwell = cell?.thermal_dwell ?? null

  return (
    <div className="lp-panel-content">
      <section className="lp-panel-section">
        <div className="lp-section-header-row">
          <span className="lp-meta-label">Surface picker telemetry</span>
        </div>

        <div className="lp-telemetry-mono-grid">
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">Pixel [row, col]</span>
            <span className="lp-mono-val">{focus.row}, {focus.col}</span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">Latitude</span>
            <span className="lp-mono-val">
              {Number.isFinite(focus.lat) ? `${focus.lat.toFixed(4)}°` : '--'}
            </span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">Longitude</span>
            <span className="lp-mono-val">
              {Number.isFinite(focus.lon) ? `${focus.lon.toFixed(4)}°` : '--'}
            </span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">Elevation</span>
            <span className="lp-mono-val">
              {focus.altitudeM !== null ? `${focus.altitudeM.toFixed(1)} m` : '--'}
            </span>
          </div>
          <div className="lp-telemetry-mono-cell">
            <span className="lp-mono-label">Surface temp</span>
            <span className="lp-mono-val">
              {focus.thermalC !== null ? `${focus.thermalC.toFixed(1)} °C` : '--'}
            </span>
          </div>
        </div>
      </section>

      {/* C4. Both values come from NASA products, so the block says so: the
          provenance is the reason to trust these two numbers over a model's. */}
      {hasMeasured && (
        <section className="lp-panel-section">
          <div className="lp-section-header-row">
            <span className="lp-meta-label">Measured products</span>
            <span className="lp-provenance-chip">MEASURED</span>
          </div>

          <div className="lp-telemetry-mono-grid">
            {roughnessM !== null && (
              <div className="lp-telemetry-mono-cell">
                <span className="lp-mono-label">Roughness</span>
                <span className="lp-mono-val">{roughnessM.toFixed(2)} m</span>
              </div>
            )}
            {fRoughness !== null && (
              <div className="lp-telemetry-mono-cell">
                <span className="lp-mono-label">Roughness criterion</span>
                <span className="lp-mono-val">{fRoughness.toFixed(3)}</span>
              </div>
            )}
            {inPsr !== null && (
              <div className="lp-telemetry-mono-cell">
                <span className="lp-mono-label">In PSR</span>
                <span className="lp-mono-val">{inPsr ? 'Yes' : 'No'}</span>
              </div>
            )}
          </div>

          {/* The claim boundary, beside the number rather than in a tooltip.
              A 100 m block statistic printed to two decimals on a 5 m cell
              invites being read as this cell's own roughness. */}
          <p className="lp-cell-note">
            LOLA LDRM, a 100 m baseline posted at 50 m/px: this is the covering
            pixel’s statistic, not the cell’s own roughness. PSR is NASA’s
            measured mask — evidence, not a forbidden region.
          </p>
        </section>
      )}

      {/* A1. Present only with a mission epoch; without one the backend says
          why and that sentence is shown instead of the block. */}
      {haven && (
        <section className="lp-panel-section">
          <div className="lp-section-header-row">
            <span className="lp-meta-label">Safe haven</span>
          </div>

          <div className="lp-telemetry-mono-grid">
            <div className="lp-telemetry-mono-cell">
              <span className="lp-mono-label">Is a haven</span>
              <span className="lp-mono-val">{haven.is_safe_haven ? 'Yes' : 'No'}</span>
            </div>
            <div className="lp-telemetry-mono-cell">
              <span className="lp-mono-label">Time to haven</span>
              {/*
                null means NO REACHABLE HAVEN. Not zero hours -- zero means the
                cell IS one, the opposite statement. The two must never render
                the same, so the unreachable case gets words rather than a
                number and the row is deliberately wider than the others.
              */}
              <span
                className={`lp-mono-val ${
                  haven.time_to_safe_haven_h === null ? 'is-unreachable' : ''
                }`}
              >
                {haven.time_to_safe_haven_h === null
                  ? 'No reachable haven'
                  : `${haven.time_to_safe_haven_h.toFixed(1)} h`}
              </span>
            </div>
            {haven.max_dark_hours_without_dte_h !== null && (
              <div className="lp-telemetry-mono-cell">
                <span className="lp-mono-label">Longest dark, no DTE</span>
                <span className="lp-mono-val">
                  {haven.max_dark_hours_without_dte_h.toFixed(0)} h
                </span>
              </div>
            )}
            {haven.earth_below_hours !== null && (
              <div className="lp-telemetry-mono-cell">
                <span className="lp-mono-label">Earth below horizon</span>
                <span className="lp-mono-val">{haven.earth_below_hours.toFixed(0)} h</span>
              </div>
            )}
            {haven.h_max_shadow_h !== null && (
              <div className="lp-telemetry-mono-cell">
                <span className="lp-mono-label">Rover shadow limit</span>
                <span className="lp-mono-val">{haven.h_max_shadow_h.toFixed(0)} h</span>
              </div>
            )}
          </div>
        </section>
      )}

      {/* B1. Present only when an epoch and a goal exist -- the leg safe set
          is defined against the goal. */}
      {survival && (
        <section className="lp-panel-section">
          <div className="lp-section-header-row">
            <span className="lp-meta-label">Survival</span>
            <span className="lp-model-chip">MODEL</span>
          </div>

          <div className="lp-telemetry-mono-grid">
            <div className="lp-telemetry-mono-cell">
              <span className="lp-mono-label">P(safe)</span>
              {/*
                Zero is a real answer here, not missing data: the policy found
                no action from this block that reaches the safe set. Coloured
                so it is not skimmed as a small number.
              */}
              <span
                className={`lp-mono-val ${survival.p_safe === 0 ? 'is-unreachable' : ''}`}
              >
                {survival.p_safe === 0
                  ? 'Cannot reach safety'
                  : survival.p_safe.toFixed(3)}
              </span>
            </div>
            <div className="lp-telemetry-mono-cell">
              <span className="lp-mono-label">Best action</span>
              {/* The code's own name from the backend. Never derived here:
                  this is the one place the exact direction is legible. */}
              <span className="lp-mono-val">{survival.best_action_name}</span>
            </div>
            <div className="lp-telemetry-mono-cell">
              <span className="lp-mono-label">Coarse block</span>
              <span className="lp-mono-val">
                {survival.block[0]}, {survival.block[1]}
              </span>
            </div>
            <div className="lp-telemetry-mono-cell">
              <span className="lp-mono-label">Horizon</span>
              <span className="lp-mono-val">{survival.horizon_hours.toFixed(1)} h</span>
            </div>
          </div>

          <p className="lp-cell-note">
            A {survival.coarsen}x block, not this 5 m cell: the policy is solved
            at {survival.coarsen * 5} m. Safe set “{survival.safe_set}”, at{' '}
            {(survival.soc_frac * 100).toFixed(0)}% charge.
          </p>
        </section>
      )}

      {/* C6. Needs only an epoch. */}
      {dwell && (
        <section className="lp-panel-section">
          <div className="lp-section-header-row">
            <span className="lp-meta-label">Thermal dwell</span>
            <span className="lp-model-chip is-uncal">UNCALIBRATED</span>
          </div>

          <div className="lp-telemetry-mono-grid">
            <div className="lp-telemetry-mono-cell">
              <span className="lp-mono-label">Max dwell</span>
              {/*
                `open_ended` first. Where it is true the number was clipped to
                the lookahead, so it is a floor: "at least 24 h", not "24 h".
              */}
              <span className="lp-mono-val">
                {dwell.max_dwell_h === null
                  ? '--'
                  : dwell.open_ended
                    ? `≥ ${dwell.max_dwell_h.toFixed(2)} h`
                    : `${dwell.max_dwell_h.toFixed(2)} h`}
              </span>
            </div>
            <div className="lp-telemetry-mono-cell">
              <span className="lp-mono-label">Limit reached</span>
              <span className="lp-mono-val">
                {dwell.open_ended
                  ? 'None in window'
                  : `${dwell.side ?? '--'} · ${dwell.component ?? '--'}`}
              </span>
            </div>
            <div className="lp-telemetry-mono-cell">
              <span className="lp-mono-label">Envelope</span>
              <span className="lp-mono-val">
                {dwell.envelope.lo_c}–{dwell.envelope.hi_c} °C
              </span>
            </div>
            <div className="lp-telemetry-mono-cell">
              <span className="lp-mono-label">Starting inner</span>
              <span className="lp-mono-val">{dwell.initial_inner_c.toFixed(1)} °C</span>
            </div>
          </div>

          <p className="lp-cell-note">
            {dwell.open_ended
              ? `Never leaves the envelope inside the ${dwell.lookahead_h} h lookahead, so the figure is a floor.`
              : `Measured against a ${dwell.lookahead_h} h lookahead at ${dwell.slice_hours} h steps.`}{' '}
            The regolith lag behind it is {dwell.thermal_lag_validity.toLowerCase()} — no
            hardware measurement stands behind the time constant.
          </p>
        </section>
      )}

      {/* Why the block above is missing, in the backend's own words. Shown
          rather than swallowed: an operator who cannot see the haven verdict
          should be told it needs an epoch, not left to wonder. */}
      {!haven && havenReason && (
        <section className="lp-panel-section">
          <div className="lp-section-header-row">
            <span className="lp-meta-label">Safe haven</span>
          </div>
          <p className="lp-cell-note">{havenReason}</p>
        </section>
      )}
    </div>
  )
}
