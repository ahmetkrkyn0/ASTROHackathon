import type { Dispatch, SetStateAction } from 'react'
import type { ClickMode, MapViewMode } from '../MapCanvas'
import type { PlanResponse, PlanWeights, RoverEntry } from '../api'

/**
 * A fine-grid cell index, as the cockpit has always carried one.
 *
 * Row 0 is the north edge and col 0 the west edge, matching the backend's
 * `georeference.row_axis` / `col_axis`. This is the only coordinate space the
 * mission layer publishes: CRS metres and coarse pixels stay behind whichever
 * module produced them.
 */
export type Cell = [row: number, col: number]

/** The same cell as an object, which is the shape the overlay contract uses. */
export interface CellRef {
  row: number
  col: number
}

export interface GridMeta {
  rows: number
  cols: number
  /** Effective pitch of the loaded grid, in metres per cell. */
  resolutionM: number
}

/**
 * A UI view-mode id -- NOT a backend layer name.
 *
 * Three of the seven differ from what `fetchLayer` wants: `surface` is the
 * `elevation` layer, `shadow` is `shadow_ratio`, and `traversability` is
 * `traversable`. Passing one of these to `fetchLayer` gets a 404 or, worse, a
 * plausible different grid. The id -> layer-name mapping is App's and stays
 * App's; a feature that needs a layer names that layer explicitly.
 */
export type ViewModeId = MapViewMode

export type MapDimension = '2d' | '3d'

/**
 * Hangi asamada oldugumuz: hangar, planlama, analiz.
 *
 * Kaydin `modes` alani buna bakar, yani tipin sahibi mission katmani. `TopBar`
 * onu yalnizca degistirir; tanimi orada tutmak, bir feature'in "hangi modda
 * gorunurum" sorusunu cevaplamak icin bir bilesene bagimli olmasi demekti.
 *
 * `fleet` bir slot degil: o modda kokpitin tamami `FleetSelectionView` ile yer
 * degistiriyor. Kabuk hangar/kokpit karari verir, slot'lar kokpitin icindedir.
 */
export type MissionMode = 'fleet' | 'plan' | 'analyze'

/**
 * The readout under the map's coordinate block.
 *
 * Published by `useFocusTelemetry`, never by `useMission`: it follows the
 * pointer and the route-playback head, so it is not the telemetry of any
 * stable selection.
 */
export interface FocusTelemetry {
  row: number
  col: number
  lat: number
  lon: number
  altitudeM: number | null
  thermalC: number | null
  resolutionM: number
  spanKm: number
}

/**
 * Everything the cockpit publishes to features, values only.
 *
 * No setter crosses THIS boundary. `App.tsx` remains the owner of every field
 * here; the context republishes what it already has, so a feature reads the
 * same mission the operator is looking at without a second fetch and without a
 * second source of truth.
 *
 * Writing is a separate contract: see `MissionActions` below, published through
 * its own context so a snapshot stays a snapshot.
 */
export interface MissionValue {
  gridMeta: GridMeta | null
  roverId: string
  /**
   * The selected rover's catalogue entry, or null before it has loaded.
   *
   * Not a duplicate of `roverId`, and the difference matters at startup:
   * `roverId` is set from the first render and is what a request carries,
   * while this stays null until /api/rovers answers. A feature that sends the
   * rover somewhere uses the id; one that shows its mass, capacity or slope
   * limit needs this and has to handle the null.
   */
  rover: RoverEntry | null
  /**
   * The complete rover catalogue fetched by App, for the mission setup selector.
   *
   * This is distinct from `rover`: the selected entry gives one rover's
   * specifications, while the setup panel needs the whole list to let the
   * operator change that selection without another fetch.
   */
  rovers: RoverEntry[]
  weights: PlanWeights
  start: Cell | null
  goal: Cell | null
  /** The raw backend response, uncropped. */
  planResult: PlanResponse | null
  /**
   * Which target, if any, the next map click places.
   *
   * It is a value rather than an action because the setup panel must show
   * which picker is armed; `setClickMode` stays in MissionActions so the
   * panel cannot own a second click-placement state.
   */
  clickMode: ClickMode
  /**
   * True while the route request is in flight.
   *
   * A route control reads this to disable repeat submissions and describe the
   * active solve, while App remains the sole owner of the request lifecycle.
   */
  isSolving: boolean
  /**
   * The latest terrain-layer load failure, if a layer could not be published.
   *
   * It belongs with mission data because a later feature may explain an
   * unavailable layer, but no panel infers a broader mission status from it.
   */
  layerError: string | null
  /**
   * A cell the operator selected as a cell, in its own right.
   *
   * Always null today: this cockpit has no such control. Start and goal are
   * placed by mode-scoped clicks and mean "route from here" / "route to here",
   * not "inspect this"; the hover cell is a pointer position, not a selection.
   * Publishing either under this name would tell every future feature that a
   * generic selection exists when none does.
   *
   * A feature that wants today's analysis focus asks for it by name --
   * `selectStableAnalysisCell` in ./selectors -- which says in its own name
   * that it is a policy and not a selection.
   */
  selectedCell: Cell | null
  activeViewMode: ViewModeId
  dimension: MapDimension
  /**
   * Which stage the cockpit is in.
   *
   * Published here rather than passed to each slot as a prop: the registry
   * decides visibility from it, so `FeatureHost` reads it and `App.tsx` writes
   * `<LeftRailSlot />` without knowing that a slot's contents depend on the
   * stage at all.
   */
  missionMode: MissionMode
}

/**
 * Volatile values needed by route-analysis, deliberately separate from the
 * stable 15-field MissionValue snapshot.
 */
export interface MissionRuntime {
  routePlaybackStep: number | null
  payloadW: number
  heaterW: number
}

/**
 * What a feature may ask the cockpit to do.
 *
 * A SEPARATE context from MissionValue, not extra fields on it, and the split
 * carries the same weight as the MissionValue/FocusTelemetry one. MissionValue
 * is a snapshot: it changes when the mission changes, and a feature reading it
 * re-renders with it. These never change. Putting them on the value would give
 * every reader a dependency on a dozen function identities and make the memo
 * that builds it responsible for keeping them all stable.
 *
 * The chatbot branch published no actions because its only feature reads and
 * never writes. ai-scene's panels are the cockpit's controls -- pick a rover,
 * move a weight, plan a route -- so registering them needs a way to write that
 * does not go back through props.
 *
 * Every member is memoised, so none of them changes identity on a bare
 * re-render and a feature may put one in an effect's dependency list without
 * arming a loop. Most never change at all; the few that close over mission
 * state -- `planRoute` reads the endpoints, the weights and the rover -- change
 * when that state does, which is when a dependent effect should re-run anyway.
 */
export interface MissionActions {
  /** Also adopts the rover's default weights, as the hangar does. */
  selectRover: (rover: RoverEntry) => void
  setWeights: (weights: PlanWeights) => void
  /** Arms the next map click to place start, goal, or nothing. */
  setClickMode: (mode: ClickMode) => void
  /** No-op unless both endpoints are placed and no request is in flight. */
  planRoute: () => void
  /** Clears endpoints, route and error. Keeps the selected rover. */
  resetMission: () => void
  setMissionMode: (mode: MissionMode) => void
  /**
   * The playback cursor; null shows the route at rest.
   *
   * A state setter rather than a plain callback, because the playback loop
   * derives the next step from the previous one and passes an updater
   * function to do it. App already hands over exactly that; the narrower
   * `(step: number | null) => void` described less than what was being
   * passed.
   */
  setPlaybackStep: Dispatch<SetStateAction<number | null>>
  setPayloadW: (watts: number) => void
  setHeaterW: (watts: number) => void
  setViewMode: (mode: ViewModeId) => void
  setDimension: (dimension: MapDimension) => void
  toggleHud: () => void
}
