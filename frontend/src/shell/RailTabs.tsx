import { useMemo, useState } from 'react'
import { FEATURES, RAIL_TABS, selectFeatures, type RailTab } from '../features/registry'
import { useMission } from '../mission/MissionContext'
import { readSafetyMargins } from '../features/safety-margins/safetyMargins'
import { Icon } from '../components/Fleet/SpecIcons'

/**
 * The analyze rail, in four tabs.
 *
 * Eleven panels live in this column once the twelve backend features are in
 * it, and a column you scroll for two screens to reach the stress test is a
 * column nobody scrolls. Everything stays in the right rail -- beside the map
 * it is about, which is the whole reason it is a rail -- and the tabs stop it
 * being a scroll.
 *
 * A FINDING COUNT ON THE TAB, because the failure mode of tabs is hiding
 * something that needed attention. Safety carries the number of violated
 * requirements, so a route that breaks two of them says so on a tab the
 * operator has not opened. Anything that can be missed behind a tab has to be
 * announced by it.
 *
 * The tab is not in the URL and does not persist across a re-plan: the rail is
 * a way of reading one route, and the honest default when a new route arrives
 * is the one that says what it is.
 */
export function RailTabs() {
  const mission = useMission()
  const [active, setActive] = useState<RailTab>('route')

  const byTab = useMemo(() => {
    const all = selectFeatures(FEATURES, 'rightRail', mission.missionMode)
    const map = new Map<RailTab, typeof all>()
    for (const tab of RAIL_TABS) {
      map.set(tab.id, all.filter((feature) => feature.tab === tab.id))
    }
    return map
  }, [mission.missionMode])

  /** Untabbed rightRail features render above the bar and stay visible. */
  const pinned = useMemo(
    () => selectFeatures(FEATURES, 'rightRail', mission.missionMode).filter((f) => !f.tab),
    [mission.missionMode],
  )

  // The only badge worth carrying: how many safety requirements this route
  // breaks. A count of zero is not drawn -- a badge that is always there stops
  // being read as an alert.
  const violations = useMemo(() => {
    const margins = readSafetyMargins(mission.planResult)
    return margins?.nViolated && margins.nViolated > 0 ? margins.nViolated : null
  }, [mission.planResult])

  const shown = byTab.get(active) ?? []

  return (
    <>
      {pinned.map(({ id, Component }) => (
        <Component key={id} />
      ))}

      <div className="lp-rail-tabs" role="tablist" aria-label="Analysis">
        {RAIL_TABS.map((tab) => {
          const count = byTab.get(tab.id)?.length ?? 0
          const badge = tab.id === 'safety' ? violations : null
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active === tab.id}
              className={`lp-rail-tab ${active === tab.id ? 'is-active' : ''} ${
                badge ? 'has-finding' : ''
              }`}
              onClick={() => setActive(tab.id)}
              disabled={count === 0}
            >
              <Icon name={tab.icon} />
              <span className="lp-rail-tab-label">{tab.label}</span>
              {badge ? <span className="lp-rail-tab-badge">{badge}</span> : null}
            </button>
          )
        })}
      </div>

      <div className="lp-rail-panels" role="tabpanel">
        {shown.map(({ id, Component }) => (
          <Component key={id} />
        ))}
      </div>
    </>
  )
}
