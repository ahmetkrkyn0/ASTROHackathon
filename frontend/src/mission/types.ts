import type { MapViewMode } from '../MapCanvas'
import type { PlanResponse, PlanWeights } from '../api'

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
 * No setter crosses this boundary in this pass. `App.tsx` remains the owner of
 * every field here; the context republishes what it already has, so a feature
 * reads the same mission the operator is looking at without a second fetch and
 * without a second source of truth.
 */
export interface MissionValue {
  gridMeta: GridMeta | null
  roverId: string
  weights: PlanWeights
  start: Cell | null
  goal: Cell | null
  /** The raw backend response, uncropped. */
  planResult: PlanResponse | null
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
}
