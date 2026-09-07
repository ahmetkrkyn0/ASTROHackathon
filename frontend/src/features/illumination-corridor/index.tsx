import { useEffect, useMemo } from 'react'

import { useOverlays } from '../../overlay/useOverlays'
import { capabilityMessage, capabilityValue } from '../../mission/capability'
import { CORRIDOR_FIELDS, corridorSliceCommand, sliceCellCount } from './overlays'
import { useIlluminationCorridor } from './useIlluminationCorridor'
import './illumination-corridor.css'

const OVERLAY_ID = 'illumination-corridor'

/**
 * A2, in the Systems & Evidence drawer.
 *
 * The layer half only. `corridor.enforced` is false, and the panel says so
 * plainly: a corridor drawn on the map without that line would imply the route
 * on screen respected it, which it did not. Section 9's rule for an unfinished
 * tier is to ship the read-only layer and not the half-built constraint --
 * half a constraint produces a wrong route, half a layer shows less.
 */
export function IlluminationCorridor() {
  const state = useIlluminationCorridor()
  const overlays = useOverlays()
  const manifest = capabilityValue(state.manifest)
  const message = capabilityMessage(state.manifest)
  const remedy = state.manifest.status === 'unavailable' ? state.manifest.remedy : null

  const range = useMemo(() => {
    const entry = manifest?.fields[state.fieldId]
    return { min: entry?.min ?? 0, max: entry?.max ?? 1 }
  }, [manifest, state.fieldId])

  // MEMOISED: register keys off array identity, and the command carries a
  // whole converted slice.
  const commands = useMemo(() => {
    if (!state.enabled || !state.cube) return []
    const command = corridorSliceCommand(state.fieldId, state.cube, state.sliceIndex, range)
    return command ? [command] : []
  }, [range, state.cube, state.enabled, state.fieldId, state.sliceIndex])

  useEffect(() => overlays.register(OVERLAY_ID, commands), [overlays, commands])

  const block = manifest?.corridor
  const cells =
    state.cube && state.fieldId !== 'dwell_hours'
      ? sliceCellCount(state.cube, state.sliceIndex)
      : null
  const isStatic = manifest?.shadow_model.model === 'static'

  return (
    <section className="rail-section">
      <p className="panel-kicker">Illumination corridor</p>

      <label className="ic-toggle">
        <input
          type="checkbox"
          checked={state.enabled}
          onChange={(event) => state.setEnabled(event.target.checked)}
          disabled={state.needsEpoch}
        />
        <span>Show on map</span>
      </label>

      {state.needsEpoch && (
        <p className="ic-note">
          Needs a mission epoch. A corridor is defined slice by slice against
          where the Sun is, so there is nothing to compute until the mission
          clock is set.
        </p>
      )}

      {state.enabled && !state.needsEpoch && (
        <div className="ic-fields" role="group" aria-label="Corridor field">
          {CORRIDOR_FIELDS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              className={`ic-field-btn ${state.fieldId === entry.id ? 'is-active' : ''}`}
              onClick={() => state.setFieldId(entry.id)}
              title={entry.blurb}
            >
              {entry.label}
            </button>
          ))}
        </div>
      )}

      {state.enabled && (
        <p className="ic-blurb">
          {CORRIDOR_FIELDS.find((entry) => entry.id === state.fieldId)?.blurb}
        </p>
      )}

      {manifest && block && (
        <>
          {/*
            The constraint status, first and unmissable. A corridor drawn on a
            map beside a route invites the reading that the route stayed in it.
          */}
          {!block.enforced && (
            <p className="ic-note ic-unenforced">
              Not enforced. The planner was not gated on this corridor — the
              route on the map may leave it.
            </p>
          )}

          <dl className="ic-facts">
            <div>
              <dt>Corridor voxels</dt>
              <dd className="ic-mono">
                {block.voxels.corridor.toLocaleString()}
                <span className="ic-sub">
                  of {block.voxels.traversable.toLocaleString()} traversable
                </span>
              </dd>
            </div>
            <div>
              <dt>Pruned away</dt>
              <dd className="ic-mono">
                {(block.voxels.pruned_fraction * 100).toFixed(1)}%
                <span className="ic-sub">of lit &amp; passable</span>
              </dd>
            </div>
            <div>
              <dt>Components</dt>
              <dd className="ic-mono">
                {block.components.count}
                <span className="ic-sub">
                  largest {(block.components.largest_fraction * 100).toFixed(0)}%
                </span>
              </dd>
            </div>
            <div>
              <dt>Slice</dt>
              <dd className="ic-mono">
                {state.sliceIndex + 1} / {manifest.n_slices}
                <span className="ic-sub">
                  {manifest.slice_hours} h each
                  {manifest.slice_hours_source === 'auto' ? ', derived' : ''}
                </span>
              </dd>
            </div>
          </dl>

          {/* The cube's whole reason for existing: it changes between slices.
              A count that moves with the clock says that without watching. */}
          {cells !== null && (
            <p className="ic-note">
              <span className="ic-mono">{cells.toLocaleString()}</span> blocks in this
              slice, from the {manifest.horizon_hours} h horizon.
            </p>
          )}

          {isStatic && (
            <p className="ic-note">
              Static shadow model: the cube still arrives, and it carries no
              guarantee. {manifest.shadow_model.reason ?? ''}
            </p>
          )}

          {/* The backend's own definitions, quoted. A corridor is only as
              meaningful as the rule that built it. */}
          <p className="ic-note ic-rule">
            <strong>Lit rule ({block.lit_rule}):</strong> {block.lit_rule_definition}
          </p>
          <p className="ic-note ic-rule">
            <strong>Pruning:</strong> {block.pruning}
          </p>
        </>
      )}

      {state.loadingCube && <p className="ic-note">Loading cube…</p>}
      {state.cubeError && <p className="ic-note is-error">{state.cubeError}</p>}
      {message && !state.needsEpoch && (
        <p className={`ic-note ${state.manifest.status === 'error' ? 'is-error' : ''}`}>
          {message}
        </p>
      )}
      {remedy && <code className="ic-remedy">{remedy}</code>}
    </section>
  )
}

export default IlluminationCorridor
