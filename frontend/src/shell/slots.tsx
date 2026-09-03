import { FeatureHost } from './FeatureHost'

/**
 * The five integration points App.tsx offers features.
 *
 * These are the stable names in the cockpit's composition. They take no
 * children: what mounts where is decided in features/registry.ts, so adding a
 * feature never edits this file or App.tsx.
 */

/** Left rail, below the existing mission controls. */
export function LeftRailSlot() {
  return <FeatureHost slot="leftRail" />
}

/** Right rail, below Mission Snapshot. */
export function RightRailSlot() {
  return <FeatureHost slot="rightRail" />
}

/** The strip under the map stage. */
export function BottomDock() {
  return <FeatureHost slot="bottomDock" />
}

/** Absolutely-positioned HUD layer over the map. */
export function CanvasOverlaySlot() {
  return <FeatureHost slot="canvasOverlay" />
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
