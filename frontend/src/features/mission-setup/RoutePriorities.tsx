import React, { useEffect, useRef, useState } from 'react'
import type { PlanWeights } from '../../api'
import { Icon, type IconName } from '../../components/Fleet/SpecIcons'
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

/* Each weight carries the sentence that explains it. These used to live in a
   `title` attribute, which RoutePriorities already learned (see the profile
   description below) reaches neither touch nor keyboard -- so they are rendered
   into a panel behind an info button instead. Each says what raising and
   lowering the number actually does, because "avoids steep inclines" tells you
   what the hazard is and nothing about what the control does. */
const WEIGHT_CONTROLS: Array<{
  key: keyof PlanWeights
  label: string
  icon: IconName
  desc: string
}> = [
  {
    key: 'w_slope',
    label: 'Slope Safety',
    icon: 'slope',
    desc: 'How hard the solver works to avoid steep ground. Raise it and the route detours around inclines and crater rims; lower it and it takes the shorter, steeper line.',
  },
  {
    key: 'w_energy',
    label: 'Energy Use',
    icon: 'energy',
    desc: 'What battery drain costs the route. Raise it to favour flatter, shorter traverses that arrive with charge to spare; lower it when arrival time matters more than the power budget.',
  },
  {
    key: 'w_shadow',
    label: 'Shadow Exposure',
    icon: 'shadow',
    desc: 'How strongly the route avoids permanently shadowed ground. Raise it to keep the rover in sunlight for power and warmth; lower it when the science target sits inside a cold trap.',
  },
  {
    key: 'w_thermal',
    label: 'Thermal Risk',
    icon: 'thermal',
    desc: 'How strongly the route avoids extreme cold. Raise it to keep the rover inside its survival temperature band; lower it to accept colder ground for a shorter path.',
  },
]

/* A glyph per preset, keyed by the id /api/profiles returns. Unknown ids fall
   back to the balance scales rather than rendering nothing, so a profile added
   on the backend still gets a card. */
const PROFILE_ICONS: Record<string, IconName> = {
  balanced: 'balance',
  energy_saver: 'eco',
  fast_recon: 'speed',
  shadow_traverse: 'shadow',
}

/** The range both the slider and the typed box are held to. */
const WEIGHT_MIN = 0
const WEIGHT_MAX = 2

const clampWeight = (n: number) => Math.min(WEIGHT_MAX, Math.max(WEIGHT_MIN, n))

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

  /* Which weight's explanation is showing. One at a time: four open panels
     would push the deploy button off the bottom of the dock. */
  const [openInfo, setOpenInfo] = useState<keyof PlanWeights | null>(null)

  /* What the user is part-way through typing. Binding the box straight to the
     weight fights them -- clearing it to type a fresh number parses as NaN, and
     "0." is not a number yet -- so the draft holds the raw string while the box
     is being edited and the mission only ever takes values that parse. */
  const [draft, setDraft] = useState<Partial<Record<keyof PlanWeights, string>>>({})

  const slidersRef = useRef<HTMLDivElement | null>(null)

  /* An open panel closes on Escape or on a click outside the weights, the two
     ways anyone tries to dismiss something like this. */
  useEffect(() => {
    if (!openInfo) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpenInfo(null)
    }
    const onPointerDown = (e: MouseEvent) => {
      if (!slidersRef.current?.contains(e.target as Node)) setOpenInfo(null)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onPointerDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onPointerDown)
    }
  }, [openInfo])

  const handleWeightChange = (key: keyof PlanWeights, val: number) => {
    setWeights({ ...weights, [key]: val })
  }

  const handleTyped = (key: keyof PlanWeights, raw: string) => {
    setDraft((d) => ({ ...d, [key]: raw }))
    const n = parseFloat(raw)
    if (Number.isFinite(n)) handleWeightChange(key, clampWeight(n))
  }

  /* Leaving the box swaps what was typed for what the mission actually holds,
     which is where an out-of-range entry visibly becomes the clamped value. */
  const handleTypedBlur = (key: keyof PlanWeights) => {
    setDraft((d) => {
      const next = { ...d }
      delete next[key]
      return next
    })
  }

  return (
    <div className="lp-priorities">
      {/* Mission profile presets (GET /api/profiles). Selecting one writes
          its four weights into the sliders below; its constraints ride along
          as read-only context. */}
      {/* ── Step one: which profile ── */}
      <div className="lp-priorities-presets">
        <div className="lp-dock-step">
          <span className="lp-step-index">1</span>
          <span className="lp-step-name">Mission profile</span>
        </div>
        <p className="lp-step-hint">
          Choose an operational profile. This sets the base behaviour for the A* route solver.
        </p>

        {profiles && Object.keys(profiles).length > 0 && (
          <div className="lp-profile-block">
            {/* Cards rather than pills. A pill row named four profiles and
                described none of them, so the one sentence that separates
                "Energy Saver" from "Fast Recon" only appeared after you had
                already committed to one. The backend sends that sentence; it
                belongs on the thing you are choosing between. */}
            <div className="lp-profile-cards" role="group" aria-label="Mission profile presets">
              {Object.entries(profiles).map(([id, profile]) => {
                const isActive = id === activeId
                return (
                  <button
                    key={id}
                    type="button"
                    className={`lp-profile-card ${isActive ? 'is-active' : ''}`}
                    style={{ '--profile-color': profile.color } as React.CSSProperties}
                    onClick={() => applyProfile(id)}
                    aria-pressed={isActive}
                  >
                    <Icon name={PROFILE_ICONS[id] ?? 'balance'} className="lp-profile-card-icon" />
                    <span className="lp-profile-card-name">{profile.name}</span>
                    <span className="lp-profile-card-desc">{profile.description}</span>
                  </button>
                )
              })}
            </div>

            {/* The limits the chosen profile carries, and -- the part that
                matters -- whether each is a wall the search will not cross or a
                number checked once the route already exists. */}
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

      {/* ── Step two: how hard each factor pulls ── */}
      <div className="lp-priorities-weights">
        <div className="lp-dock-step">
          <span className="lp-step-index">2</span>
          <span className="lp-step-name">Route priorities</span>
        </div>
        <p className="lp-step-hint">
          Adjust the relative importance of each factor. Higher values make the A* solver work
          harder to avoid that hazard.
        </p>

        <div className="lp-priority-sliders" ref={slidersRef}>
          {WEIGHT_CONTROLS.map(({ key, label, icon, desc }) => {
            const val = weights[key]
            const isOpen = openInfo === key
            const infoId = `lp-weight-info-${key}`
            return (
              <div key={key} className="lp-slider-block">
                {/* Label, slider and value on one line. Stacked, four weights
                    were eight rows and the number sat above the control it
                    described rather than beside it. */}
                <div className="lp-slider-row">
                  <span className="lp-slider-label">
                    <Icon name={icon} />
                    {label}
                    <button
                      type="button"
                      className={`lp-info-btn ${isOpen ? 'is-open' : ''}`}
                      onClick={() => setOpenInfo(isOpen ? null : key)}
                      aria-expanded={isOpen}
                      aria-controls={infoId}
                      aria-label={`What ${label} controls`}
                    >
                      <Icon name="info" />
                    </button>
                  </span>
                  <input
                    type="range"
                    className="lp-range-input"
                    min={WEIGHT_MIN}
                    max={WEIGHT_MAX}
                    /* 0.01, as in the rail this moved from: useMissionProfiles
                       matches a preset within 0.011, so a coarser step would
                       report a freshly applied profile as "Custom". */
                    step={0.01}
                    value={val}
                    onChange={(e) => handleWeightChange(key, parseFloat(e.target.value))}
                    aria-label={`${label} weight`}
                  />

                  {/* A box you can type into, not a printed number. The slider
                      is for a feel; this is for the value a profile actually
                      specifies, which nobody hits by dragging. */}
                  <input
                    type="number"
                    className="lp-weight-input"
                    min={WEIGHT_MIN}
                    max={WEIGHT_MAX}
                    step={0.001}
                    value={draft[key] ?? val.toFixed(3)}
                    onChange={(e) => handleTyped(key, e.target.value)}
                    onBlur={() => handleTypedBlur(key)}
                    aria-label={`${label} weight, exact value`}
                  />
                </div>

                {isOpen && (
                  <p className="lp-info-pop" id={infoId} role="note">
                    {desc}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default RoutePriorities
