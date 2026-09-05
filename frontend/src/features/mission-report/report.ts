/**
 * The report's derivations, kept out of the component so they can be tested.
 *
 * This project has no jsdom and no testing-library, so anything left inside a
 * component is logic nothing can check. The verdict in particular is a claim
 * the operator acts on -- "this route is safe to drive" -- and it is decided
 * from eight summary fields whose interactions are easy to get quietly wrong.
 */
import type { PlanResponse, Waypoint } from '../../api'
import type { RouteStatistics, SlopeBin } from '../../net/types'

export type Verdict = 'GO' | 'GO-WITH-RISK' | 'NO-GO'

/**
 * Every finding the verdict can rest on.
 *
 * The codes exist because `backend/app/report.py` decides the same thing for
 * the assistant, and a parity test compares the two by code -- prose is not a
 * contract, and the two copies phrase their reasons differently on purpose:
 * this one carries the numbers, the backend's carries none because
 * `ai_grounding` blocks any digit it did not register.
 */
export const VERDICT_REASON_CODES = [
  'STRANDED',
  'EXECUTION_TRUNCATED',
  'SHADOW_LIMIT_EXCEEDED',
  'CRITICAL_STEPS',
  'HIGH_RISK_STEPS',
  'BATTERY_WATCH',
  'PEAK_POWER_EXCEEDED',
  'RECHARGES_REQUIRED',
  'NO_VIOLATION',
] as const

export type VerdictReasonCode = (typeof VERDICT_REASON_CODES)[number]

export interface VerdictReason {
  code: VerdictReasonCode
  /** Why, in the operator's language. */
  text: string
}

export interface VerdictResult {
  verdict: Verdict
  /** Worst finding first, blocking before warning. */
  reasons: VerdictReason[]
}

/**
 * Below this the battery reserve is close enough to matter to the verdict.
 *
 * Exported because the report's KPI colouring and its battery chart draw the
 * same line, and because the backend mirrors this literal -- the parity test
 * reads it out of this file.
 */
export const BATTERY_WATCH_PCT = 30

/**
 * The route's disposition, from the simulation summary alone.
 *
 * NO-GO is reserved for things the rover cannot survive or did not finish:
 * a stranded run, a truncated execution, a breached shadow limit, or a step
 * the risk model called CRITICAL. Everything softer degrades to GO-WITH-RISK
 * rather than to NO-GO, because a report that says NO-GO for a 28% battery
 * trough teaches the operator to ignore it.
 */
export function decideVerdict(plan: PlanResponse): VerdictResult {
  const s = plan.summary
  const blocking: VerdictReason[] = []
  const warnings: VerdictReason[] = []

  if (s.stranded) {
    blocking.push({
      code: 'STRANDED',
      text: `Rover ran out of energy at step ${s.stranded_at_step ?? '?'} — the route cannot be completed.`,
    })
  }
  if (plan.execution?.truncated) {
    blocking.push({
      code: 'EXECUTION_TRUNCATED',
      text:
        `Route truncated: ${plan.execution.executable_nodes}/${plan.execution.planned_nodes} nodes are drivable` +
        (plan.execution.reason ? ` (${plan.execution.reason}).` : '.'),
    })
  }
  if (s.shadow_limit_exceeded) {
    blocking.push({
      code: 'SHADOW_LIMIT_EXCEEDED',
      text: `Continuous shadow ${s.max_continuous_shadow_h.toFixed(1)} h against a rover limit of ${s.shadow_limit_h?.toFixed(1)} h.`,
    })
  }
  if (s.critical_steps_count > 0) {
    blocking.push({
      code: 'CRITICAL_STEPS',
      text: `${s.critical_steps_count} steps at CRITICAL risk.`,
    })
  }

  if (s.high_or_above_steps_count > 0) {
    warnings.push({
      code: 'HIGH_RISK_STEPS',
      text: `${s.high_or_above_steps_count} steps at HIGH risk or above.`,
    })
  }
  if (s.min_battery_pct < BATTERY_WATCH_PCT) {
    warnings.push({
      code: 'BATTERY_WATCH',
      text: `Battery fell to ${s.min_battery_pct.toFixed(1)}% at its lowest.`,
    })
  }
  if (s.peak_power_exceeded_steps > 0) {
    warnings.push({
      code: 'PEAK_POWER_EXCEEDED',
      text: `Peak power budget exceeded on ${s.peak_power_exceeded_steps} steps.`,
    })
  }
  if (s.total_recharges > 0) {
    warnings.push({
      code: 'RECHARGES_REQUIRED',
      text: `The route needs ${s.total_recharges} recharge stops.`,
    })
  }

  if (blocking.length > 0) return { verdict: 'NO-GO', reasons: [...blocking, ...warnings] }
  if (warnings.length > 0) return { verdict: 'GO-WITH-RISK', reasons: warnings }
  return {
    verdict: 'GO',
    reasons: [{ code: 'NO_VIOLATION', text: 'No driving constraint was violated.' }],
  }
}

/**
 * What the report asks the assistant, per verdict.
 *
 * Turkish, while the rest of the report is English, and deliberately: the
 * assistant answers only in Turkish (VERBALIZER_PROMPT), so a Turkish question
 * keeps the exchange in one language. The operator sees it in the composer
 * before sending, and a test pins all three by value.
 */
export const ASSISTANT_QUESTION: Record<Verdict, string> = {
  GO: 'Görev raporundaki karar özetini açıkla: GO kararı hangi bulgulara dayanıyor?',
  'GO-WITH-RISK':
    'Görev raporundaki karar özetini açıkla: GO-WITH-RISK kararının risk bulguları neler?',
  'NO-GO': 'Görev raporundaki karar özetini açıkla: bu rota neden NO-GO?',
}

export const VERDICT_COLOR: Record<Verdict, string> = {
  GO: 'var(--risk-low)',
  'GO-WITH-RISK': 'var(--risk-med)',
  'NO-GO': 'var(--risk-crit)',
}

export const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const
export type RiskLevel = (typeof RISK_LEVELS)[number]

/**
 * Risk shares for the stacked bar.
 *
 * Prefers the backend's own `risk_breakdown_pct` and falls back to counting
 * the waypoints. Both exist and they agree, but only the backend's is
 * rounded the way the rest of route_statistics is, and a report that
 * disagreed with the validation panel over the same route would be worse than
 * one that recomputed nothing.
 */
export function riskShares(
  waypoints: Waypoint[],
  stats: RouteStatistics | null,
): Record<RiskLevel, number> {
  const out = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 }
  if (stats?.risk_breakdown_pct) {
    for (const level of RISK_LEVELS) out[level] = stats.risk_breakdown_pct[level] ?? 0
    return out
  }
  if (waypoints.length === 0) return out
  for (const wp of waypoints) out[wp.risk_level] += 1
  for (const level of RISK_LEVELS) {
    out[level] = Number(((out[level] / waypoints.length) * 100).toFixed(2))
  }
  return out
}

/**
 * The slope histogram, from the backend when it sent one.
 *
 * The fallback bins locally against the same default edges the backend uses
 * (route_analysis.DEFAULT_SLOPE_BINS_DEG). It exists because
 * `route_statistics` is optional on PlanResponse -- an older plan still in
 * state after a reload has waypoints but no stats, and a blank panel would
 * read as "the route is flat".
 */
const DEFAULT_BINS = [0, 5, 10, 15, 20, 25]

export function slopeHistogram(waypoints: Waypoint[], stats: RouteStatistics | null): SlopeBin[] {
  if (stats?.slope_histogram?.length) return stats.slope_histogram
  if (waypoints.length === 0) return []

  const counts = new Array(DEFAULT_BINS.length - 1).fill(0)
  const last = counts.length - 1
  for (const wp of waypoints) {
    const slope = wp.slope_deg
    if (slope < DEFAULT_BINS[0]) {
      counts[0] += 1
      continue
    }
    if (slope >= DEFAULT_BINS[DEFAULT_BINS.length - 1]) {
      counts[last] += 1
      continue
    }
    for (let i = 0; i < counts.length; i += 1) {
      if (slope >= DEFAULT_BINS[i] && slope < DEFAULT_BINS[i + 1]) {
        counts[i] += 1
        break
      }
    }
  }
  return counts.map((count, i) => ({
    bin_low_deg: DEFAULT_BINS[i],
    bin_high_deg: DEFAULT_BINS[i + 1],
    count,
    pct: Number(((count / waypoints.length) * 100).toFixed(2)),
  }))
}

export interface EnergySplit {
  driveWh: number
  payloadWh: number
  heaterWh: number
}

/**
 * Where the energy went.
 *
 * `total_energy_consumed_wh` is the simulated DRIVE energy: the payload and
 * heater draws are operator-set watts that the simulation never saw, so they
 * are added here rather than carved out of the total. Carving them out would
 * silently shrink the drive figure the rest of the report quotes.
 */
export function energySplit(
  totalDriveWh: number,
  elapsedHours: number,
  payloadW: number,
  heaterW: number,
): EnergySplit {
  return {
    driveWh: totalDriveWh,
    payloadWh: Math.max(0, payloadW) * elapsedHours,
    heaterWh: Math.max(0, heaterW) * elapsedHours,
  }
}

export interface Milestone {
  title: string
  step: number
  wp: Waypoint
}

/**
 * The route's named points: both endpoints, three quarter marks, and the two
 * extremes that actually drove the verdict (steepest step, lowest battery).
 *
 * Deduplicated by step, because on a short route the steepest step is very
 * often also the halfway mark, and the table would list it twice.
 */
export function milestones(waypoints: Waypoint[]): Milestone[] {
  if (waypoints.length === 0) return []

  const picked = new Map<number, string>()
  const add = (step: number, title: string) => {
    if (!picked.has(step)) picked.set(step, title)
  }

  // Endpoints are claimed FIRST, and the order is the whole fix: on a route
  // that drains monotonically -- which is most of them -- the lowest battery
  // IS the last waypoint, and letting the extreme claim that step left the
  // table with no row called GOAL at all.
  add(0, 'START')
  add(waypoints.length - 1, 'GOAL')

  if (waypoints.length > 8) {
    for (const [frac, label] of [
      [0.25, '25%'],
      [0.5, '50%'],
      [0.75, '75%'],
    ] as const) {
      add(Math.floor(waypoints.length * frac), label)
    }
  }

  let steepest = 0
  let weakest = 0
  waypoints.forEach((wp, i) => {
    if (wp.slope_deg > waypoints[steepest].slope_deg) steepest = i
    if (wp.battery_pct < waypoints[weakest].battery_pct) weakest = i
  })
  add(steepest, 'STEEPEST')
  add(weakest, 'LOWEST BATTERY')

  return [...picked.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([step, title]) => ({ title, step, wp: waypoints[step] }))
}
