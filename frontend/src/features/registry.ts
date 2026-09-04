import type { ComponentType } from 'react'
import type { MissionMode } from '../mission/types'
import { MissionContextFeature } from './mission-context'
import { MissionSnapshot } from './mission-snapshot'
import { CorridorFeature } from './corridor'
import { LayerPicker } from './layer-picker'
import { LayerProvenance } from './layer-provenance'
import { MissionSetup } from './mission-setup'
import { MissionValidation } from './mission-validation'
import { Playback } from './playback'
import { ProfileCompare } from './profile-compare'
import { PoseLoop } from './pose-loop'
import { Replan } from './replan'
import { RosShowcase } from './ros-showcase'
import { RouteAnalysis } from './route-analysis'
import { TimeAxis } from './time-axis'
import { SolvingIndicator } from './solving-indicator'

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
 * Filled one task at a time as the shell is assembled, which is what makes
 * those tasks independently reviewable.
 */
export const FEATURES: readonly FeatureRegistration[] = [
  // No modes: App.tsx used to render this panel in both plan and analyze branches.
  { id: 'mission-context', slot: 'rightRail', Component: MissionContextFeature },
  // Plan only: meaningful after the hangar's rover selection is complete.
  { id: 'mission-setup', slot: 'leftRail', Component: MissionSetup, modes: ['plan'] },
  // analyze only. App.tsx rendered this as the else-branch of
  // `missionMode === 'plan' ? MissionSetupPanel : MissionSnapshotPanel`, and
  // fleet replaces the whole cockpit, so analyze was the only stage it ever
  // appeared in. Leaving modes off would put it beside the setup panel in
  // plan -- the exact quiet mistake the filter exists to make explicit.
  { id: 'mission-snapshot', slot: 'leftRail', Component: MissionSnapshot, modes: ['analyze'] },
  { id: 'route-analysis', slot: 'rightRail', Component: RouteAnalysis, modes: ['analyze'] },
  // analyze only, from App.tsx's `missionMode === 'analyze' && planResult`
  // guard. Only the mode half becomes a registration: the bar already
  // renders nothing without waypoints, so knowing what an empty route looks
  // like stays inside the feature.
  //
  // canvasOverlay rather than bottomDock, decided when time-axis arrived:
  // the bar is absolutely positioned and floats over the map, so in the
  // bottom strip it simply covered whatever in-flow feature was there.
  { id: 'playback', slot: 'canvasOverlay', Component: Playback, modes: ['analyze'] },
  // The bottom dock's first in-flow occupant, and the reason it had to
  // become a real strip under the map.
  { id: 'time-axis', slot: 'bottomDock', Component: TimeAxis, modes: ['analyze'] },
  // No modes: App.tsx rendered both of these inside the map stage, which the
  // fleet branch replaces wholesale, so plan and analyze are every stage they
  // could appear in. Registration order is paint order within a slot, and the
  // solving indicator covers the map while a route is being solved, so it
  // comes after the picker it may draw over.
  { id: 'layer-picker', slot: 'canvasOverlay', Component: LayerPicker },
  { id: 'solving-indicator', slot: 'canvasOverlay', Component: SolvingIndicator },
  // The first two features to come back from the parking lot, and the only
  // two that needed no retyping: neither draws an overlay and neither reads a
  // mission field that changed name.
  { id: 'ros-showcase', slot: 'leftRail', Component: RosShowcase },
  { id: 'layer-provenance', slot: 'leftRail', Component: LayerProvenance },
  // Plan only: it asks what would force a new route from where the rover is,
  // which is a question about a route still being decided.
  { id: 'replan', slot: 'leftRail', Component: Replan, modes: ['plan'] },
  { id: 'mission-validation', slot: 'rightRail', Component: MissionValidation },
  { id: 'corridor', slot: 'rightRail', Component: CorridorFeature },
  { id: 'pose-loop', slot: 'rightRail', Component: PoseLoop },
  // Analyze only: it compares a route that already exists against alternative
  // weightings, which is a question asked after one has been planned.
  { id: 'profile-compare', slot: 'rightRail', Component: ProfileCompare, modes: ['analyze'] },
]

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
