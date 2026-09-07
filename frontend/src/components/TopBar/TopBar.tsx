import React from 'react'

// Tipin sahibi mission katmani: kayit bir feature'in hangi modlarda
// gorunecegini buna bakarak suzuyor. Buradan yeniden disa aciliyor cunku
// App.tsx bugun tipi TopBar'dan aliyor ve o import Task 7'ye kadar calismali.
import type { MissionMode } from '../../mission/types'

export type { MissionMode }

/**
 * The empty node in the bar that Mission Report portals its launcher into.
 *
 * Exported so the feature and the bar name the same thing once. The bar does
 * not import the report: a feature is registered, never wired in by the shell,
 * and this keeps that true while still letting one live up here.
 */
export const REPORT_LAUNCHER_SLOT_ID = 'lp-topbar-report-slot'

interface TopBarProps {
  mode: MissionMode
  onModeChange: (mode: MissionMode) => void
  hasRoute: boolean
  missionStatus: string
  dataLinkActive: boolean
  isSolving?: boolean
  systemsOpen?: boolean
  onToggleSystems?: () => void
}

/**
 * The 52px mission bar.
 *
 * Two working modes, not a pipeline. The bar used to carry a three-stage
 * wizard (fleet, surface map, route analysis) plus four telemetry badges and a
 * UTC clock, which put nine boxes above a cockpit whose whole point is the
 * viewport. The design canvas puts one segmented control on the left and two
 * mono readouts on the right, and nothing else: the mission's state, and
 * whether the link is up.
 *
 * ANALYZE is disabled until a route exists. Disabled rather than hidden, with
 * ROUTE REQUIRED spelled out beside it -- a mode that vanishes reads as a bug,
 * and a mode that lies about being available is worse.
 */
export const TopBar: React.FC<TopBarProps> = ({
  mode,
  onModeChange,
  hasRoute,
  missionStatus,
  dataLinkActive,
  isSolving = false,
  systemsOpen = false,
  onToggleSystems,
}) => {
  return (
    <header className="lp-topbar">
      <div className="lp-topbar-left">
        <button
          type="button"
          className="lp-brand"
          onClick={() => onModeChange('plan')}
          title="Back to mission planning"
        >
          LUNAPATH
        </button>

        <div className="lp-mode-switch" role="group" aria-label="Mission mode">
          <button
            type="button"
            className={`lp-mode-btn ${mode === 'plan' ? 'is-active' : ''}`}
            onClick={() => onModeChange('plan')}
            disabled={isSolving}
          >
            PLAN
          </button>
          <button
            type="button"
            className={`lp-mode-btn ${mode === 'analyze' ? 'is-active' : ''}`}
            onClick={() => hasRoute && onModeChange('analyze')}
            disabled={!hasRoute || isSolving}
            title={
              hasRoute
                ? 'Inspect trajectory engineering metrics'
                : 'Generate a route first to unlock Mission Analysis'
            }
          >
            ANALYZE
          </button>
        </div>

        {!hasRoute && <span className="lp-route-required">Route required</span>}
      </div>

      <div className="lp-topbar-right">
        {/* Where Mission Report mounts itself.
        
            The report is registered in globalOverlay -- it owns a full-screen
            modal, which is not a bar control -- but its launcher belongs up
            here beside Systems rather than floating over the terrain. An empty
            anchor plus a portal is what lets those two live in one feature
            without the bar importing it, and without the button being placed
            by a fixed offset that every change to the readouts beside it would
            break. */}
        <div id={REPORT_LAUNCHER_SLOT_ID} className="lp-topbar-report-slot" />

        {onToggleSystems && (
          <button
            type="button"
            className={`lp-systems-toggle ${systemsOpen ? 'is-active' : ''}`}
            onClick={onToggleSystems}
            title="ROS bridge, reality check, provenance, corridor, pose loop and replan triggers"
          >
            Systems
          </button>
        )}

        <span className="lp-topbar-meta">
          Mission{' '}
          <span className={`lp-mission-status ${isSolving ? 'is-solving' : 'is-nominal'}`}>
            {isSolving ? 'SOLVING' : missionStatus}
          </span>
        </span>

        <span className="lp-topbar-meta">
          Data link
          <i className={`lp-link-dot ${dataLinkActive ? 'is-online' : 'is-offline'}`} />
          <span className={dataLinkActive ? 'lp-link-live' : 'lp-link-down'}>
            {dataLinkActive ? 'ACTIVE' : 'SYNCING'}
          </span>
        </span>
      </div>
    </header>
  )
}

export default TopBar
