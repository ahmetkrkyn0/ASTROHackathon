import { MAX_AI_MESSAGES, type AiChatMessage } from '../../api/assistant'
import type { PlanResponse, PlanWeights } from '../../api'

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
  shadow_limit?: Quantity
  min_battery?: Quantity
  final_battery?: Quantity
  elapsed?: Quantity
  max_slope?: Quantity
  waypoint_count?: number
  total_recharges?: number
  critical_steps_count?: number
  high_or_above_steps_count?: number
  peak_power_exceeded_steps?: number
  stranded?: boolean
  stranded_at_step?: number
  // boolean | null on the backend, where null means the rover has no shadow
  // limit. Copied only when it is a real boolean, so an absent limit stays
  // absent rather than arriving as a false that reads like a measurement.
  shadow_limit_exceeded?: boolean
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
  const shadowLimit = quantity(summary?.shadow_limit_h, 'h')
  if (shadowLimit) out.shadow_limit = shadowLimit
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
  if (typeof summary?.peak_power_exceeded_steps === 'number') {
    out.peak_power_exceeded_steps = summary.peak_power_exceeded_steps
  }
  if (typeof summary?.stranded === 'boolean') out.stranded = summary.stranded
  if (typeof summary?.stranded_at_step === 'number') {
    out.stranded_at_step = summary.stranded_at_step
  }
  if (typeof summary?.shadow_limit_exceeded === 'boolean') {
    out.shadow_limit_exceeded = summary.shadow_limit_exceeded
  }

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
    // The node counts travel because a truncated-execution verdict has to be
    // able to state both sides of "40 of 90 nodes are drivable"; without them
    // the backend registers the finding with no quantity to name.
    out.execution = {
      stranded: plan.execution.stranded,
      truncated: plan.execution.truncated,
      reason: plan.execution.reason,
      planned_nodes: plan.execution.planned_nodes,
      executable_nodes: plan.execution.executable_nodes,
    }
  }

  return out
}

// The stable-focus rule that used to live here is now
// mission/selectors.ts::selectStableAnalysisCell. It is mission semantics, not
// assistant semantics, and the mission layer may not import a feature -- so it
// moved rather than being called across the boundary. Nothing about the rule
// changed: still goal-then-start, still never the hover cell.

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
