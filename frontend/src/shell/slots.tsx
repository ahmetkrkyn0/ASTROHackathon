import { FeatureHost } from './FeatureHost'
import { RailTabs } from './RailTabs'

/**
 * The six integration points App.tsx offers features.
 *
 * These are the stable names in the cockpit's composition. They take no
 * children: what mounts where is decided in features/registry.ts, so adding a
 * feature never edits this file or App.tsx.
 */

/** Left rail, below the existing mission controls. */
export function LeftRailSlot() {
  return <FeatureHost slot="leftRail" />
}

/**
 * Right rail. Tabbed, because analyze fills it with eleven panels and a
 * two-screen scroll is not a column anyone reads to the bottom of.
 *
 * RailTabs still asks the registry what belongs here, so adding a feature is
 * still one line in registry.ts -- it just carries a tab now.
 */
export function RightRailSlot() {
  return <RailTabs />
}

/** The strip under the map stage. */
export function BottomDock() {
  return <FeatureHost slot="bottomDock" />
}

/**
 * The 44px status strip along the bottom of the shell, beside the scale and
 * the risk legend. In-flow and outside the map, so nothing mounted here covers
 * the terrain it describes.
 */
export function StatusBarSlot() {
  return <FeatureHost slot="statusBar" />
}

/**
 * Absolutely positioned over the map, so its parent must be a containing
 * block. App.tsx gives the map shell an inline `position: relative` for
 * exactly this: without a positioned ancestor this sizes itself against the
 * stage and sits over the rails instead of over the map.
 *
 * The only slot that wraps. The other five emit a bare fragment, which is what
 * keeps an unfilled slot invisible to layout -- but a HUD layer has to
 * establish its own box, and `pointer-events: none` is what stops that box
 * from swallowing clicks meant for the map underneath it.
 */
export function CanvasOverlaySlot() {
  return (
    <div
      className="lp-slot lp-slot-canvas"
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
    >
      <FeatureHost slot="canvasOverlay" />
    </div>
  )
}

/**
 * Application-level floating utilities.
 *
 * Rendered as a direct child of `.app-shell`, immediately before the toast
 * stack. Both facts are load-bearing: `shell.css` moves the toasts clear of an
 * open assistant with a sibling combinator, which needs the assistant's markup
 * to share a parent with the toast stack and to precede it.
 */
export function GlobalOverlaySlot() {
  return <FeatureHost slot="globalOverlay" />
}
