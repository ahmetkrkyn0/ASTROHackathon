import React from 'react'

/**
 * Mount points for feature modules.
 *
 * They are deliberately plain wrappers: adding a phase to the cockpit is
 * putting its <Module /> inside one of these, which is a one-line diff in
 * App.tsx and therefore a one-line merge conflict at worst.
 */

export function LeftRailSlot({ children }: { children?: React.ReactNode }) {
  if (!children) return null
  return <div className="lp-slot lp-slot-left">{children}</div>
}

export function RightRailSlot({ children }: { children?: React.ReactNode }) {
  if (!children) return null
  return <div className="lp-slot lp-slot-right">{children}</div>
}

export function BottomDock({ children }: { children?: React.ReactNode }) {
  if (!children) return null
  return <div className="lp-slot lp-slot-dock">{children}</div>
}

/**
 * Absolutely positioned over the canvas, so its parent must be a containing
 * block. App.tsx gives .map-canvas-shell an inline `position: relative` for
 * exactly this -- App.css is off limits, and without a positioned ancestor
 * this would size itself against .map-stage and sit over the overlays
 * instead of over the map.
 */
export function CanvasOverlaySlot({ children }: { children?: React.ReactNode }) {
  if (!children) return null
  return (
    <div
      className="lp-slot lp-slot-canvas"
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
    >
      {children}
    </div>
  )
}
