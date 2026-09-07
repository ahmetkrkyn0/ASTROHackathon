import type { ComponentType } from 'react'
import type { IconName } from '../components/Fleet/SpecIcons'
import type { MissionMode } from '../mission/types'
import { MissionConstraints } from './mission-constraints'
import { MissionContextFeature } from './mission-context'
import { MissionSnapshot } from './mission-snapshot'
import { Assistant } from './assistant'
import { Benchmark } from './benchmark'
import { CorridorFeature } from './corridor'
import { CostExplain } from './cost-explain'
import { LayerPicker } from './layer-picker'
import { LayerProvenance } from './layer-provenance'
import { MapLegend } from './map-legend'
import { MissionReport } from './mission-report'
import { MissionSetup } from './mission-setup'
import { MissionValidation } from './mission-validation'
import { Playback } from './playback'
import { ProfileCompare } from './profile-compare'
import { PoseLoop } from './pose-loop'
import { Replan } from './replan'
import { RosShowcase } from './ros-showcase'
import { RouteAnalysis } from './route-analysis'
import { RiskSweep } from './risk-sweep'
import { RouteModel } from './route-model'
import { SafetyMargins } from './safety-margins'
import { TimeAxis } from './time-axis'
import { Uncertainty } from './uncertainty'
import { AnalysisLayers } from './analysis-layers'
import { CoarseFields } from './coarse-fields'
import { EarthVisibility } from './earth-visibility'
import { IlluminationCorridor } from './illumination-corridor'
import { PsrValidationPanel } from './psr-validation'
import { SafeHaven } from './safe-haven'
import { ThermalEnvelopePanel } from './thermal-envelope'
import { SolvingIndicator } from './solving-indicator'
import { StressTest } from './stress-test'

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
  | 'statusBar'
  | 'globalOverlay'

/**
 * The two surfaces a rail/dock feature can live on.
 *
 * `primary` is the default cockpit: the task and the context you work with
 * while planning and reviewing a route. `systems` is the "Systems & Evidence"
 * drawer -- the panels that prove the stack is real (ROS bridge, reality
 * check, provenance, corridor, pose loop, replan triggers) but are not part of
 * the moment-to-moment task. Splitting them is what keeps the default cockpit
 * from being nine competing cards. Omitted means `primary`, for the same
 * reason an omitted `modes` means every mode: nobody hides a panel by leaving
 * the field off.
 */
export type FeatureGroup = 'primary' | 'systems'

/**
 * Which tab of the analyze rail a feature belongs to.
 *
 * The rail holds eleven panels once the twelve backend features are in it, and
 * a column you scroll for two screens to reach the stress test is a column
 * nobody scrolls. Tabs keep every panel in the right column -- which is where
 * they belong, beside the map they are about -- without stacking them.
 *
 * Four rather than one per feature, grouped by the question being asked:
 *
 *   route     what was planned, and what does a cell cost
 *   safety    is it sound, and under which model was that decided
 *   analysis  the jobs that re-price it: clones, Monte Carlo, risk sweep
 *   compare   this route against others, and LunaPath against the outside
 */
export type RailTab = 'route' | 'safety' | 'analysis' | 'compare'

export const RAIL_TABS: ReadonlyArray<{ id: RailTab; label: string; icon: IconName }> = [
  { id: 'route', label: 'Route', icon: 'route' },
  { id: 'safety', label: 'Safety', icon: 'shield' },
  { id: 'analysis', label: 'Analysis', icon: 'analytics' },
  { id: 'compare', label: 'Compare', icon: 'balance' },
]

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
  /**
   * Which surface the feature lives on. OMITTED MEANS `primary` (the rails).
   * `systems` moves it out of the rails and into the Systems & Evidence
   * drawer; the feature keeps its `slot` for ordering, but the drawer renders
   * it in a flat grid rather than in that rail.
   */
  group?: FeatureGroup
  /**
   * Which analyze-rail tab this sits in. Only meaningful for `rightRail` +
   * `primary`; omitted means the feature is not tabbed and renders above the
   * tab bar, which is how a permanent readout stays permanent.
   */
  tab?: RailTab
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
  // Analyze only, though App.tsx once rendered it in both branches. It is a
  // readout -- sector, resolution, extent, and whatever the pointer is over --
  // and while a route is being placed the operator is looking at the map, not
  // at a column describing it. Restricting it is what empties the right rail
  // in plan, which is the point: plan gets the wider map.
  { id: 'mission-context', slot: 'rightRail', Component: MissionContextFeature, modes: ['analyze'], tab: 'route' },
  // Plan only: meaningful after the hangar's rover selection is complete.
  { id: 'mission-setup', slot: 'leftRail', Component: MissionSetup, modes: ['plan'] },
  // Registered for no mode, which is how a feature is retired without being
  // deleted. It was analyze's left rail: a locked read-only echo of the rover,
  // the two endpoints and the four weights -- all of it already reported by
  // the right rail's analysis, and none of it editable here. Analyze now runs
  // with the left rail gone entirely and the map that much wider.
  //
  // Its one control, "Edit & Replan", was `setMissionMode('plan')` and nothing
  // else -- exactly what the top bar's PLAN tab does. That tab is enabled
  // throughout analyze, so removing this panel takes no route back with it.
  { id: 'mission-snapshot', slot: 'leftRail', Component: MissionSnapshot, modes: [] },
  { id: 'route-analysis', slot: 'rightRail', Component: RouteAnalysis, modes: ['analyze'], tab: 'route' },
  // Analyze only, and NOT in the systems drawer: the twelve requirements are
  // checked on every route whether anyone asks or not, and the plan is
  // explicit that a result which exists must be visible rather than parked
  // behind a control. It renders nothing when a response carries no block, so
  // an older backend costs the rail nothing.
  { id: 'safety-margins', slot: 'rightRail', Component: SafetyMargins, modes: ['analyze'], tab: 'safety' },
  // Slip, risk appetite, roughness, survival and thermal dwell -- five blocks
  // that also arrive unasked, kept as ONE panel with labelled sections rather
  // than five cards.
  //
  // In the drawer, unlike the safety margins above. This panel answers "how
  // was the cost arrived at, and under what model", which is the drawer's own
  // definition: it proves the stack is real without being part of the
  // moment-to-moment task of reading a route. Keeping it in the primary rail
  // took analyze from four permanent panels to six, which is the direction
  // the theme-preservation gate exists to stop.
  { id: 'route-model', slot: 'rightRail', Component: RouteModel, modes: ['analyze'], tab: 'safety' },
  // analyze only, from App.tsx's `missionMode === 'analyze' && planResult`
  // guard. Only the mode half becomes a registration: the bar already
  // renders nothing without waypoints, so knowing what an empty route looks
  // like stays inside the feature.
  //
  // statusBar, not canvasOverlay: it used to float over the terrain because
  // the bottom dock was in-flow under the map and the two fought for the same
  // space. The status strip is the design's home for the transport, beside the
  // scale and the risk legend it reads against.
  { id: 'playback', slot: 'statusBar', Component: Playback, modes: ['analyze'] },
  // The bottom dock's first in-flow occupant, and the reason it had to
  // become a real strip under the map.
  { id: 'time-axis', slot: 'bottomDock', Component: TimeAxis, modes: ['analyze'] },
  // No modes: App.tsx rendered both of these inside the map stage, which the
  // fleet branch replaces wholesale, so plan and analyze are every stage they
  // could appear in. Registration order is paint order within a slot, and the
  // solving indicator covers the map while a route is being solved, so it
  // comes after the picker it may draw over.
  { id: 'layer-picker', slot: 'canvasOverlay', Component: LayerPicker },
  // Scale and risk key, over the terrain rather than under it: both describe
  // what the map is showing, so they belong on the thing they describe rather
  // than in a band the eye has to leave it to read.
  { id: 'map-legend', slot: 'canvasOverlay', Component: MapLegend },
  // Additive overlays, beside the base-layer radio rather than inside it.
  // A view mode replaces what the map is; these sit on top of whatever it
  // already is, and several can be on at once -- which is also the only way
  // to draw the PSR mask over our own shadow layer, the comparison the
  // measured product exists to support.
  { id: 'analysis-layers', slot: 'canvasOverlay', Component: AnalysisLayers },
  { id: 'solving-indicator', slot: 'canvasOverlay', Component: SolvingIndicator },
  // The first two features to come back from the parking lot, and the only
  // two that needed no retyping: neither draws an overlay and neither reads a
  // mission field that changed name.
  //
  // These six are the "Systems & Evidence" set: they demonstrate the stack is
  // real -- the ROS bridge, layer provenance, the reality-check against flown
  // missions, the corridor, the pose loop, the replan triggers -- but none is
  // part of the moment-to-moment task of placing and reading a route. group:
  // 'systems' pulls them out of the rails and into the drawer, which is what
  // takes the default cockpit from nine competing cards down to task+context.
  { id: 'ros-showcase', slot: 'leftRail', Component: RosShowcase, group: 'systems' },
  { id: 'layer-provenance', slot: 'leftRail', Component: LayerProvenance, group: 'systems' },
  // Plan only: it asks what would force a new route from where the rover is,
  // which is a question about a route still being decided.
  { id: 'replan', slot: 'leftRail', Component: Replan, modes: ['plan'], group: 'systems' },
  // Plan only, and in the drawer: these change how a route is ranked and when
  // it is feasible, but the moment-to-moment task is still a rover and two
  // endpoints. An operator who never opens the drawer gets exactly the product
  // that existed before the constraints did.
  { id: 'mission-constraints', slot: 'leftRail', Component: MissionConstraints, modes: ['plan'], group: 'systems' },
  // Beside layer provenance, and read with it: one says where a layer came
  // from, the other how far our own shadow model agrees with the measured
  // product. The number it publishes is one it can fail, which is what
  // makes the PSR overlay evidence rather than decoration.
  {
    id: 'psr-validation',
    slot: 'leftRail',
    Component: PsrValidationPanel,
    group: 'systems',
  },
  // A1. In the drawer with the other evidence panels rather than in a rail:
  // it owns a map overlay, but the survival rule behind it and the share of
  // the window that can reach no haven are the parts worth reading, and
  // neither belongs in the moment-to-moment work of placing a route.
  { id: 'safe-haven', slot: 'leftRail', Component: SafeHaven, group: 'systems' },
  // A4, next to A1 because they answer the same question from two sides:
  // a haven is somewhere to wait out the dark, and the dark is defined by
  // where the Earth is. Both read the one mission clock.
  {
    id: 'earth-visibility',
    slot: 'leftRail',
    Component: EarthVisibility,
    group: 'systems',
  },
  // B1 and C6, together because they share a coarse grid and a legend
  // slot, and because neither is a terrain layer: both are model output
  // over a mission epoch and a rover state, and two of their four fields
  // are categorical rather than scalar.
  { id: 'coarse-fields', slot: 'leftRail', Component: CoarseFields, group: 'systems' },
  // C6's other half, and not a map: the axes are Sun elevation and slope
  // along the Sun's azimuth, so a bin is a geometry rather than a place.
  // It sits beside the dwell field because the two answer the same
  // question from opposite ends -- where survivable, and what kind of
  // ground is survivable at all.
  {
    id: 'thermal-envelope',
    slot: 'leftRail',
    Component: ThermalEnvelopePanel,
    group: 'systems',
  },
  // A2. NOT the `corridor` feature above -- that is the route corridor, a
  // ribbon around a planned path. This is the lit-and-connected volume over
  // time, and it is the layer half only: the planner is not gated on it.
  {
    id: 'illumination-corridor',
    slot: 'leftRail',
    Component: IlluminationCorridor,
    group: 'systems',
  },
  // Plan only: it asks what would force a new route from where the rover is,
  // which is a question about a route still being decided.
  { id: 'mission-validation', slot: 'rightRail', Component: MissionValidation, group: 'systems' },
  { id: 'corridor', slot: 'rightRail', Component: CorridorFeature, group: 'systems' },
  { id: 'pose-loop', slot: 'rightRail', Component: PoseLoop, group: 'systems' },
  // Analyze only, and in the drawer: a post-route analysis that takes seconds
  // and needs a preprocessing cache many deployments will not have. It never
  // blocks the route -- an unavailable ensemble costs this panel and nothing
  // else.
  { id: 'uncertainty', slot: 'rightRail', Component: Uncertainty, modes: ['analyze'], tab: 'analysis' },
  { id: 'stress-test', slot: 'rightRail', Component: StressTest, modes: ['analyze'], tab: 'analysis' },
  { id: 'risk-sweep', slot: 'rightRail', Component: RiskSweep, modes: ['analyze'], tab: 'analysis' },
  // Offline evidence, so it belongs to no mission mode: the figures are the
  // same in plan and analyze because an external validation result does not
  // depend on the route on screen.
  { id: 'benchmark', slot: 'rightRail', Component: Benchmark, modes: ['analyze'], tab: 'compare' },
  // Analyze only. The cost under the pointer is worth reading in both modes,
  // but it is the last primary occupant of the right rail, and leaving it
  // registered in plan would keep a 288px column open for one hover readout.
  { id: 'cost-explain', slot: 'rightRail', Component: CostExplain, modes: ['analyze'], tab: 'route' },
  // Floating, not railed: the assistant opens over the mission and has to
  // keep working with both rails collapsed.
  { id: 'assistant', slot: 'globalOverlay', Component: Assistant },
  // Analyze only, and floating for the same reason the assistant is: the
  // report covers the whole cockpit once the rover has arrived, so it is
  // neither a rail panel nor a layer on the map. It renders nothing until a
  // route exists, so the mode filter is the only guard it needs.
  { id: 'mission-report', slot: 'globalOverlay', Component: MissionReport, modes: ['analyze'] },
  // Analyze only: it compares a route that already exists against alternative
  // weightings, which is a question asked after one has been planned.
  { id: 'profile-compare', slot: 'rightRail', Component: ProfileCompare, modes: ['analyze'], tab: 'compare' },
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
  group: FeatureGroup = 'primary',
): readonly FeatureRegistration[] {
  return features.filter(
    (feature) =>
      feature.slot === slot &&
      (feature.modes === undefined || feature.modes.includes(mode)) &&
      (feature.group ?? 'primary') === group,
  )
}

/**
 * The Systems & Evidence drawer's contents for one mode, in registration
 * order. Slot-agnostic on purpose: the drawer lays these out in a flat grid,
 * so a feature's `slot` still orders it but does not place it in a rail. Mirror
 * of selectFeatures' mode rule -- omitted modes means every mode, an empty
 * array means none.
 */
export function selectSystemsFeatures(
  features: readonly FeatureRegistration[],
  mode: MissionMode,
): readonly FeatureRegistration[] {
  return features.filter(
    (feature) =>
      feature.group === 'systems' &&
      (feature.modes === undefined || feature.modes.includes(mode)),
  )
}
