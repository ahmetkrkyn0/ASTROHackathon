import React, { useEffect, useState } from 'react'

export type MissionMode = 'fleet' | 'plan' | 'analyze'

interface TopBarProps {
  mode: MissionMode
  onModeChange: (mode: MissionMode) => void
  hasRoute: boolean
  missionStatus: string
  dataLinkActive: boolean
  resolutionM?: number
  gridDimensions?: [number, number]
  isSolving?: boolean
  leftOpen?: boolean
  onToggleLeft?: () => void
  rightOpen?: boolean
  onToggleRight?: () => void
  hudOpen?: boolean
  onToggleHud?: () => void
}

export const TopBar: React.FC<TopBarProps> = ({
  mode,
  onModeChange,
  hasRoute,
  missionStatus,
  dataLinkActive,
  resolutionM = 5,
  gridDimensions = [500, 500],
  isSolving = false,
  leftOpen = true,
  onToggleLeft,
  rightOpen = true,
  onToggleRight,
  hudOpen = true,
  onToggleHud,
}) => {
  const [utcTime, setUtcTime] = useState('')

  useEffect(() => {
    const updateClock = () => {
      const now = new Date()
      const hours = String(now.getUTCHours()).padStart(2, '0')
      const minutes = String(now.getUTCMinutes()).padStart(2, '0')
      const seconds = String(now.getUTCSeconds()).padStart(2, '0')
      setUtcTime(`${hours}:${minutes}:${seconds} UTC`)
    }

    updateClock()
    const timer = window.setInterval(updateClock, 1000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <header className="lp-topbar">
      <div className="lp-topbar-left">
        <div className="lp-brand" onClick={() => onModeChange('fleet')} style={{ cursor: 'pointer' }} title="Go to Fleet Selection">
          <span className="lp-brand-title">LUNAPATH</span>
          <span className="lp-brand-tag">SOUTH POLE WORKSTATION</span>
        </div>

        {/* Dashboard Panels Quick Toggles (Visible during Map & Analysis modes) */}
        {mode !== 'fleet' && (
          <div className="lp-layout-toggles" role="group" aria-label="Workstation Layout Controls">
            {onToggleLeft && (
              <button
                type="button"
                className={`lp-layout-btn ${leftOpen ? 'is-active' : ''}`}
                onClick={onToggleLeft}
                title={leftOpen ? 'Hide Left Planning Panel' : 'Show Left Planning Panel'}
              >
                <span className="lp-layout-icon">◨</span>
                <span>Plan Deck</span>
              </button>
            )}

            {onToggleHud && (
              <button
                type="button"
                className={`lp-layout-btn ${hudOpen ? 'is-active' : ''}`}
                onClick={onToggleHud}
                title={hudOpen ? 'Hide On-Canvas Telemetry HUD' : 'Show On-Canvas Telemetry HUD'}
              >
                <span className="lp-layout-icon">📍</span>
                <span>HUD</span>
              </button>
            )}

            {onToggleRight && (
              <button
                type="button"
                className={`lp-layout-btn ${rightOpen ? 'is-active' : ''}`}
                onClick={onToggleRight}
                title={rightOpen ? 'Hide Right Context Inspector' : 'Show Right Context Inspector'}
              >
                <span className="lp-layout-icon">◧</span>
                <span>Inspector</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── 3-Stage Mission Workflow Navigation ── */}
      <nav className="lp-topbar-nav" aria-label="Mission Pipeline Navigation">
        <button
          type="button"
          className={`lp-mode-btn ${mode === 'fleet' ? 'is-active' : ''}`}
          onClick={() => onModeChange('fleet')}
          disabled={isSolving}
        >
          <span className="lp-mode-dot" />
          <span>1. ROVER FLEET</span>
        </button>

        <button
          type="button"
          className={`lp-mode-btn ${mode === 'plan' ? 'is-active' : ''}`}
          onClick={() => onModeChange('plan')}
          disabled={isSolving}
        >
          <span className="lp-mode-dot" />
          <span>2. SURFACE MAP</span>
        </button>

        <button
          type="button"
          className={`lp-mode-btn ${mode === 'analyze' ? 'is-active' : ''}`}
          onClick={() => hasRoute && onModeChange('analyze')}
          disabled={!hasRoute || isSolving}
          title={!hasRoute ? 'Generate a surface route first to unlock Mission Analysis' : 'Inspect trajectory engineering metrics'}
        >
          <span className="lp-mode-dot" />
          <span>3. ROUTE ANALYSIS</span>
          {!hasRoute && <span className="lp-mode-lock-hint">Locked</span>}
        </button>
      </nav>

      <div className="lp-topbar-right">
        <div className="lp-telemetry-badge">
          <span className="lp-meta-label">Grid</span>
          <span className="lp-meta-val">
            {gridDimensions[0]}×{gridDimensions[1]} · {resolutionM}m/px
          </span>
        </div>

        <div className="lp-telemetry-badge">
          <span className="lp-meta-label">Stage</span>
          <span className={`lp-meta-val ${isSolving ? 'is-solving' : 'is-nominal'}`}>
            {isSolving ? 'SOLVING' : mode === 'fleet' ? 'FLEET READY' : missionStatus}
          </span>
        </div>

        <div className="lp-telemetry-badge">
          <span className="lp-meta-label">Data Link</span>
          <span className={`lp-meta-val lp-status-pill ${dataLinkActive ? 'is-online' : 'is-offline'}`}>
            <span className="lp-pulse-dot" />
            {dataLinkActive ? 'ACTIVE' : 'SYNCING'}
          </span>
        </div>

        <div className="lp-telemetry-badge lp-clock-badge">
          <span className="lp-clock-readout">{utcTime || '--:--:-- UTC'}</span>
        </div>
      </div>
    </header>
  )
}

export default TopBar
