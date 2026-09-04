import { createContext, useContext } from 'react'
import type { PlanResponse, PlanWeights } from '../api'
import type { CellTelemetryResponse } from '../net/types'

export type MapViewMode =
  | 'surface'
  | 'thermal'
  | 'cost'
  | 'shadow'
  | 'traversability'
  | 'slope'
  | 'aspect'

/**
 * What App.tsx ALREADY owns, published read-only.
 *
 * Nothing new lives here. A feature module keeps its own state in its own
 * hook; this exists so nine modules can read the cockpit's current
 * selection without App.tsx growing nine more useStates.
 */
export interface MissionState {
  gridMeta: { rows: number; cols: number; resolutionM: number } | null
  roverId: string
  weights: PlanWeights
  start: [number, number] | null
  goal: [number, number] | null
  /** The FULL /api/plan response -- corridor, route_statistics and execution included. */
  planResult: PlanResponse | null
  /**
   * The cell under the pointer, NOT a click selection. App publishes its
   * hover state here because that is what drives /api/cell-telemetry today;
   * a module that wants a sticky selection has to hold it itself.
   */
  hoverCell: [number, number] | null
  /** The RAW /api/cell-telemetry response, cost_breakdown and layer_validity included. */
  cellTelemetry: CellTelemetryResponse | null
  activeLayer: MapViewMode
  dimension: '2d' | '3d'
}

export interface MissionActions {
  setStart: (cell: [number, number] | null) => void
  setGoal: (cell: [number, number] | null) => void
}

export type MissionValue = MissionState & MissionActions

export const MissionContext = createContext<MissionValue | null>(null)

export function useMission(): MissionValue {
  const ctx = useContext(MissionContext)
  if (!ctx) {
    throw new Error('useMission must be used inside <MissionProvider>')
  }
  return ctx
}
