import { MAX_AI_MESSAGES, type AiChatMessage, type PlanResponse, type PlanWeights } from './api'

/**
 * The read-only view of the mission the chat panel is allowed to send.
 *
 * Values only. No setter crosses this boundary: the panel cannot move the
 * start or goal, change the rover, re-plan, or clear the route the operator
 * is looking at. That is the point -- an assistant that could silently change
 * the displayed route while answering a question about it would be worse than
 * no assistant.
 */
export interface AiMissionSnapshot {
  start: [number, number] | null
  goal: [number, number] | null
  roverId: string
  weights: PlanWeights
  focusedCell: { row: number; col: number } | null
  currentPlan: SanitizedPlan | null
}

interface Quantity {
  value: number
  unit: string
}

export interface SanitizedPlan {
  distance?: Quantity
  energy?: Quantity
  max_continuous_shadow?: Quantity
  min_battery?: Quantity
  final_battery?: Quantity
  elapsed?: Quantity
  max_slope?: Quantity
  waypoint_count?: number
  total_recharges?: number
  critical_steps_count?: number
  high_or_above_steps_count?: number
  stranded?: boolean
  metrics?: Record<string, unknown>
  edges_rejected?: Record<string, number>
  execution?: Record<string, unknown>
}

/** A number the assistant may state, or nothing at all. */
function quantity(value: number | null | undefined, unit: string): Quantity | undefined {
  if (typeof value !== 'number' || !Number.isFinite(value)) return undefined
  return { value, unit }
}

/**
 * Reduce a plan result to the fields the assistant may reason over.
 *
 * The server sanitizes again -- this is not the security boundary -- but
 * trimming here keeps the route geometry off the wire entirely. The waypoint
 * array is several hundred objects on a real route and answers none of the
 * questions this first cut can ask.
 *
 * Three fields are deliberately absent. astar_metrics.total_energy_wh and
 * total_shadow_hours are always null, so energy comes from
 * summary.total_energy_consumed_wh and continuous shadow from
 * summary.max_continuous_shadow_h. summary.total_shadow_exposure has no
 * documented unit, so it cannot be stated at all.
 */
export function sanitizePlanForAi(plan: PlanResponse | null): SanitizedPlan | null {
  if (!plan) return null

  const { summary, astar_metrics: metrics } = plan
  const out: SanitizedPlan = {}

  const distance = quantity(summary?.total_distance_km, 'km')
  if (distance) out.distance = distance
  const energy = quantity(summary?.total_energy_consumed_wh, 'Wh')
  if (energy) out.energy = energy
  const shadow = quantity(summary?.max_continuous_shadow_h, 'h')
  if (shadow) out.max_continuous_shadow = shadow
  const minBattery = quantity(summary?.min_battery_pct, '%')
  if (minBattery) out.min_battery = minBattery
  const finalBattery = quantity(summary?.final_battery_pct, '%')
  if (finalBattery) out.final_battery = finalBattery
  const elapsed = quantity(summary?.total_elapsed_hours, 'h')
  if (elapsed) out.elapsed = elapsed
  const maxSlope = quantity(summary?.max_slope_deg, 'deg')
  if (maxSlope) out.max_slope = maxSlope

  if (typeof summary?.waypoint_count === 'number') out.waypoint_count = summary.waypoint_count
  if (typeof summary?.total_recharges === 'number') out.total_recharges = summary.total_recharges
  if (typeof summary?.critical_steps_count === 'number') {
    out.critical_steps_count = summary.critical_steps_count
  }
  if (typeof summary?.high_or_above_steps_count === 'number') {
    out.high_or_above_steps_count = summary.high_or_above_steps_count
  }
  if (typeof summary?.stranded === 'boolean') out.stranded = summary.stranded

  if (metrics) {
    const picked: Record<string, unknown> = {}
    // computation_time_ms is excluded: it differs between identical runs, so
    // reporting it as a change would be noise dressed as a finding.
    for (const key of [
      'total_distance_m',
      'max_segment_slope_deg',
      'max_cell_slope_deg',
      'min_surface_temp_c',
      'max_surface_temp_c',
      'total_weighted_cost',
      'total_weighted_cost_cells_only',
      'barrier_share',
      'cost_units',
      'path_length_nodes',
      'nodes_expanded',
    ] as const) {
      const value = metrics[key]
      if (value !== undefined && value !== null) picked[key] = value
    }
    if (Object.keys(picked).length > 0) out.metrics = picked

    // Populated on successful runs too, which is what makes "why is the route
    // winding?" answerable from evidence rather than from a guess.
    if (metrics.edges_rejected && Object.keys(metrics.edges_rejected).length > 0) {
      out.edges_rejected = metrics.edges_rejected
    }
  }

  if (plan.execution) {
    out.execution = {
      stranded: plan.execution.stranded,
      truncated: plan.execution.truncated,
      reason: plan.execution.reason,
    }
  }

  return out
}

/**
 * The cell the assistant may treat as chosen.
 *
 * Deliberately NOT the map's hover cell. onHoverCellChange fires as the pointer
 * moves and clears on leave, so a hover cell is a transient pointer position,
 * not a selection: it would make the assistant's answer depend on where the
 * mouse happened to rest, and it would make a "analyse the selected cell"
 * suggestion appear and vanish under the operator's hand.
 *
 * Start and goal are set by an explicit click and persist, so they are the only
 * stable cell context this app has. The preference order mirrors the map's own
 * focusPoint rule (goal, then start), and the result is null when neither has
 * been placed -- fail closed, rather than inventing a focus.
 */
export function stableFocusCell(
  start: [number, number] | null,
  goal: [number, number] | null,
): { row: number; col: number } | null {
  const point = goal ?? start
  return point ? { row: point[0], col: point[1] } : null
}

/**
 * The most recent messages that will fit in one request.
 *
 * ChatRequest caps a request at MAX_AI_MESSAGES and 422s past it, so a long
 * local conversation has to be trimmed before it is sent. The window is a plain
 * tail slice: no summarization and no model call, because either would put text
 * nobody wrote into the history the router reads.
 *
 * The tail is what keeps the request valid in the other direction too -- the
 * server requires the last message to be the user's question, and the newest
 * message always survives a tail slice.
 */
export function windowMessages(
  messages: AiChatMessage[],
  limit: number = MAX_AI_MESSAGES,
): AiChatMessage[] {
  return limit > 0 && messages.length > limit ? messages.slice(-limit) : messages
}

export function buildMissionSnapshot(input: {
  start: [number, number] | null
  goal: [number, number] | null
  roverId: string
  weights: PlanWeights
  focusedCell: { row: number; col: number } | null
  plan: PlanResponse | null
}): AiMissionSnapshot {
  return {
    start: input.start,
    goal: input.goal,
    roverId: input.roverId,
    weights: input.weights,
    focusedCell: input.focusedCell,
    currentPlan: sanitizePlanForAi(input.plan),
  }
}
