import React from 'react'
import type { PlanWeights } from '../../api'
import { useMission, useMissionActions } from '../../mission/MissionContext'
import type { ProfileConstraints } from '../../net/types'
import { useMissionProfiles } from './useMissionProfiles'

/**
 * How the solver is told what to care about: a preset, its constraints, and
 * the four weights underneath them.
 *
 * This lived in the left rail, beside a drawn route, which made the weights
 * look like something you tune against the line on the map. They are not:
 * /api/plan consumes them at solve time, so changing one after a route exists
 * describes a different route than the one on screen. The hangar is where the
 * mission is configured before there is any terrain to argue with, so this is
 * where they belong now, and the cockpit reports them read-only.
 *
 * It reads the mission context rather than taking props because the hangar and
 * the rail both render inside MissionProvider, and there is exactly one set of
 * weights either of them could mean.
 */

const WEIGHT_CONTROLS: Array<{
  key: keyof PlanWeights
  label: string
  desc: string
}> = [
  { key: 'w_slope', label: 'Slope Safety', desc: 'Avoids steep inclines and cliff edges' },
  { key: 'w_energy', label: 'Energy Use', desc: 'Minimizes battery kWh draw during transit' },
  { key: 'w_shadow', label: 'Shadow Exposure', desc: 'Avoids permanently shadowed cold traps' },
  { key: 'w_thermal', label: 'Thermal Risk', desc: 'Steers clear of extreme cryogenic zones' },
]

/** Display order + formatting for the four constraints a profile carries. */
const CONSTRAINT_CONTROLS: Array<{
  key: keyof ProfileConstraints
  label: string
  format: (v: number) => string
}> = [
  { key: 'max_slope_deg', label: 'Max Slope', format: (v) => `${v.toFixed(0)}°` },
  { key: 'max_shadow_h', label: 'Max Shadow', format: (v) => `${v.toFixed(0)} h` },
  { key: 'max_energy_wh', label: 'Energy Budget', format: (v) => `${v.toFixed(0)} Wh` },
  { key: 'min_soc', label: 'Min SoC', format: (v) => `${(v * 100).toFixed(0)}%` },
]

export const RoutePriorities: React.FC = () => {
  const { weights } = useMission()
  const { setWeights } = useMissionActions()
  const { profiles, activeId, applyProfile, loading: profilesLoading } = useMissionProfiles()
  const activeProfile = activeId && profiles ? profiles[activeId] : null

  const handleWeightChange = (key: keyof PlanWeights, val: number) => {
    setWeights({ ...weights, [key]: val })
  }

  return (
    <div className="lp-priorities">
      {/* Mission profile presets (GET /api/profiles). Selecting one writes
          its four weights into the sliders below; its constraints ride along
          as read-only context. */}
      <div className="lp-priorities-presets">
        {profiles && Object.keys(profiles).length > 0 && (
          <div className="lp-profile-block">
            <div className="lp-profile-head">
              <span className="lp-profile-caption">Mission profile</span>
              <span className={`lp-profile-active-tag ${activeProfile ? '' : 'is-custom'}`}>
                {activeProfile ? activeProfile.name : 'Custom'}
              </span>
            </div>

            <div className="lp-profile-chips" role="group" aria-label="Mission profile presets">
              {Object.entries(profiles).map(([id, profile]) => {
                const isActive = id === activeId
                return (
                  <button
                    key={id}
                    type="button"
                    className={`lp-profile-chip ${isActive ? 'is-active' : ''}`}
                    style={{ '--profile-color': profile.color } as React.CSSProperties}
                    onClick={() => applyProfile(id)}
                    title={profile.description}
                    aria-pressed={isActive}
                  >
                    <span className="lp-profile-dot" />
                    {profile.name}
                  </button>
                )
              })}
            </div>

            {/* `title` alone reached neither touch nor keyboard, so the one
                sentence that distinguishes four profiles was invisible to a
                user who had not hovered each chip in turn. The backend
                already sends it. */}
            {activeProfile?.description && (
              <p className="lp-profile-desc">{activeProfile.description}</p>
            )}

            {activeProfile && (
              <div className="lp-profile-constraints">
                {CONSTRAINT_CONTROLS.map(({ key, label, format }) => {
                  const enforced = activeProfile.constraint_handling[key] === 'enforced_in_search'
                  return (
                    <div key={key} className="lp-profile-constraint">
                      <span className="lp-constraint-label">{label}</span>
                      <strong className="lp-constraint-value">
                        {format(activeProfile.constraints[key])}
                      </strong>
                      <span
                        className={`lp-constraint-badge ${enforced ? 'is-enforced' : 'is-verified'}`}
                        title={
                          enforced
                            ? 'Enforced in search: the A* solver refuses cells that violate this limit.'
                            : 'Verified after simulation: checked against the simulated route; a plan can exceed it.'
                        }
                      >
                        {enforced ? 'IN SEARCH' : 'POST-SIM'}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
        {profilesLoading && !profiles && (
          <p className="lp-section-explainer">Loading mission profiles…</p>
        )}
      </div>

      <div className="lp-priorities-weights">
        <p className="lp-section-explainer">
          Higher priority weights force the A* solver to penalize and circumvent that hazard more aggressively.
        </p>

        <div className="lp-priority-sliders">
          {WEIGHT_CONTROLS.map(({ key, label, desc }) => {
            const val = weights[key]
            return (
              <div key={key} className="lp-slider-block">
                <div className="lp-slider-head">
                  <span className="lp-slider-label">{label}</span>
                  <span className="lp-slider-number">{val.toFixed(3)}</span>
                </div>
                <input
                  type="range"
                  className="lp-range-input"
                  min={0}
                  max={2}
                  /* 0.01, as in the rail this moved from: useMissionProfiles
                     matches a preset within 0.011, so a coarser step would
                     report a freshly applied profile as "Custom". */
                  step={0.01}
                  value={val}
                  onChange={(e) => handleWeightChange(key, parseFloat(e.target.value))}
                  title={desc}
                />
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default RoutePriorities
