/**
 * What the planner charged this route, and under which model.
 *
 * Three blocks that arrive with every plan response and were being discarded:
 * slip (C3), risk appetite (B2) and measured roughness (C4). One feature
 * rather than three panels, because each is three to six numbers and the plan
 * warns in as many words against turning new backend capability into a stack
 * of permanent cards. Their boundaries stay visible as three labelled
 * sections; what they do not get is three separate homes in the rail.
 *
 * EVERY NUMBER CARRIES ITS VALIDITY. That is a house rule, not a preference:
 * a figure shown without its label is a figure the reader is free to take as
 * measured. The three blocks are not the same kind of thing --
 *
 *   slip       MODEL. Anchored to Yutu-2's measurement and VIPER's design
 *              constraint, which does not make the curve a measurement.
 *   risk       MODEL. A transform of MODEL-labelled distributions. Not a
 *              measured risk, and alpha = 0.5 is not the mean.
 *   roughness  MEASURED, from NASA LOLA -- with scale_validity MODEL, because
 *              the number is a 100 m baseline block statistic and NOT the
 *              roughness of the cell it is drawn on.
 *
 * -- and flattening them to one confidence is the specific misreading this
 * module exists to prevent.
 */

export interface SlipView {
  applied: boolean
  /** Always MODEL. The backend never labels this MEASURED. */
  validity: string | null
  meanSlip: number | null
  maxSlip: number | null
  maxSlipSlopeDeg: number | null
  /** Sum d/(1-s) over sum d: how much further the wheels turn than the ground. */
  distanceFactor: number | null
  /** What slip added to THIS route. */
  extraHours: number | null
  extraDrawnWh: number | null
  claim: string | null
  reason: string | null
  /** Literature the curve is anchored to. Shown in the report, not the rail. */
  references: string[]
}

export interface RiskView {
  applied: boolean
  validity: string | null
  /** Null when no alpha was sent: nominal, and the grid is bit-identical. */
  alpha: number | null
  multiplier: number | null
  /** Where alpha reached. Displayed, because it is the whole caveat. */
  scope: string | null
  meanSlipMu: number | null
  meanSlipCvar: number | null
  hours: number | null
  riskAdjustedHours: number | null
  drawnWh: number | null
  riskAdjustedDrawnWh: number | null
  claim: string | null
}

export interface RoughnessView {
  applied: boolean
  /** MEASURED -- this is a real NASA product. */
  validity: string | null
  /** MODEL -- how the measurement is turned into a cost. Kept separate. */
  scaleValidity: string | null
  product: string | null
  baselineM: number | null
  resolutionM: number | null
  weight: number | null
  meanRoughnessM: number | null
  maxRoughnessM: number | null
  /** Null when the PSR layer is not loaded. Null is not zero. */
  cellsInPsr: number | null
  claim: string | null
  reason: string | null
  references: string[]
}

export interface RouteModelView {
  slip: SlipView | null
  risk: RiskView | null
  roughness: RoughnessView | null
}

function obj(source: unknown, key: string): Record<string, unknown> | null {
  if (typeof source !== 'object' || source === null) return null
  const value = (source as Record<string, unknown>)[key]
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function num(source: Record<string, unknown> | null, key: string): number | null {
  if (!source) return null
  const value = source[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function strings(source: Record<string, unknown> | null, key: string): string[] {
  if (!source) return []
  const value = source[key]
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : []
}

function str(source: Record<string, unknown> | null, key: string): string | null {
  if (!source) return null
  const value = source[key]
  return typeof value === 'string' ? value : null
}

export function readRouteModel(result: unknown): RouteModelView {
  const slipRoot = obj(result, 'slip_model')
  const riskRoot = obj(result, 'risk')
  const roughRoot = obj(result, 'roughness')

  const slipRoute = obj(slipRoot, 'route')
  const riskRoute = obj(riskRoot, 'route')
  const roughRoute = obj(roughRoot, 'route')

  return {
    slip: slipRoot
      ? {
          applied: slipRoot.applied === true,
          validity: str(slipRoot, 'validity'),
          meanSlip: num(slipRoute, 'mean_slip'),
          maxSlip: num(slipRoute, 'max_slip'),
          maxSlipSlopeDeg: num(slipRoute, 'max_slip_slope_deg'),
          distanceFactor: num(slipRoute, 'distance_factor'),
          extraHours: num(slipRoute, 'extra_hours'),
          extraDrawnWh: num(slipRoute, 'extra_drawn_wh'),
          claim: str(slipRoot, 'claim'),
          reason: str(slipRoot, 'reason'),
          references: strings(slipRoot, 'references'),
        }
      : null,
    risk: riskRoot
      ? {
          applied: riskRoot.applied === true,
          validity: str(riskRoot, 'validity'),
          // Null means no alpha was sent, which is nominal. It does NOT mean
          // 0.5: CVaR at 0.5 is mu + 0.798 sigma, not the mean.
          alpha: num(riskRoot, 'alpha'),
          multiplier: num(riskRoot, 'multiplier'),
          scope: str(riskRoot, 'scope'),
          meanSlipMu: num(riskRoute, 'mean_slip_mu'),
          meanSlipCvar: num(riskRoute, 'mean_slip_cvar'),
          hours: num(riskRoute, 'hours'),
          riskAdjustedHours: num(riskRoute, 'risk_adjusted_hours'),
          drawnWh: num(riskRoute, 'drawn_wh'),
          riskAdjustedDrawnWh: num(riskRoute, 'risk_adjusted_drawn_wh'),
          claim: str(riskRoot, 'claim'),
        }
      : null,
    roughness: roughRoot
      ? {
          applied: roughRoot.applied === true,
          validity: str(roughRoot, 'validity'),
          scaleValidity: str(roughRoot, 'scale_validity'),
          product: str(roughRoot, 'product'),
          baselineM: num(roughRoot, 'baseline_m'),
          resolutionM: num(roughRoot, 'resolution_m'),
          weight: num(roughRoot, 'weight'),
          meanRoughnessM: num(roughRoute, 'mean_roughness_m'),
          maxRoughnessM: num(roughRoute, 'max_roughness_m'),
          // Absent when the PSR mask is not loaded. Reading that as zero would
          // report "no cells in permanent shadow" for a route nobody checked.
          cellsInPsr: num(roughRoute, 'cells_in_psr'),
          claim: str(roughRoot, 'claim'),
          reason: str(roughRoot, 'reason'),
          references: strings(roughRoot, 'references'),
        }
      : null,
  }
}

/** True when there is nothing worth drawing. */
export function isEmpty(view: RouteModelView): boolean {
  return !view.slip && !view.risk && !view.roughness
}
