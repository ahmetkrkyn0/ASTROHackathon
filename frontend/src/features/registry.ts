import type { ComponentType } from 'react'
import type { MissionMode } from '../mission/types'

/**
 * Where a feature mounts.
 *
 * Four of these come from the team's frontend structure note. `globalOverlay`
 * is ours: a floating, application-level utility is neither a rail panel nor a
 * layer drawn on the map, and forcing one into either slot is how the assistant
 * ended up wired directly into App.tsx in the first place.
 *
 * `fleet` is deliberately NOT a slot. In that mode the whole cockpit is
 * replaced by the hangar view, which is a shell decision, not a rail. Inventing
 * a `stage` slot with exactly one occupant would be an abstraction over one
 * example.
 */
export type FeatureSlot =
  | 'leftRail'
  | 'rightRail'
  | 'bottomDock'
  | 'canvasOverlay'
  | 'globalOverlay'

export interface FeatureRegistration {
  /** Stable, unique, and used as the React key. */
  id: string
  slot: FeatureSlot
  /** The feature's public entrypoint. Nothing else about it is imported here. */
  Component: ComponentType
  /**
   * Modes this feature appears in. OMITTED MEANS EVERY MODE.
   *
   * The distinction between an omitted list and an empty one is load-bearing:
   * an empty array hides the feature everywhere, which is never what someone
   * means by leaving the field off. The two are kept apart rather than
   * collapsed, and selectFeatures' tests pin that down.
   */
  modes?: readonly MissionMode[]
}

/**
 * Every mounted feature, in render order within a slot.
 *
 * Deliberately a plain array evaluated at module load: no dynamic discovery, no
 * manifests, no lazy loading, no service locator. Adding a feature is one entry
 * here, which is the whole point -- App.tsx knows the slots, not the features,
 * so two people adding two unrelated features touch this line and nothing else.
 *
 * Empty while the shell is being assembled. Each feature's own task adds its
 * entry, which is also what makes those tasks independently reviewable.
 */
export const FEATURES: readonly FeatureRegistration[] = []

/**
 * The features one slot shows in one mode, in registration order.
 *
 * A pure function rather than a hook so it can be tested without a DOM -- this
 * project has neither jsdom nor testing-library, so logic that stays inside a
 * component is logic nothing can check. Slot and mode are the whole of the
 * placement contract, and both ways it can be wrong are quiet: the wrong slot
 * puts a panel in the other rail, and the wrong mode makes one appear during a
 * stage it has no data for.
 */
export function selectFeatures(
  features: readonly FeatureRegistration[],
  slot: FeatureSlot,
  mode: MissionMode,
): readonly FeatureRegistration[] {
  return features.filter(
    (feature) =>
      feature.slot === slot && (feature.modes === undefined || feature.modes.includes(mode)),
  )
}
