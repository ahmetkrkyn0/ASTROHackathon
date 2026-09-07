/**
 * The formal safety block, read off a route result.
 *
 * Feature D3. Every planned route is checked against twelve mission and safety
 * requirements written in NASA FRET's structured English and translated to STL,
 * and each one comes back with a robustness value: rho >= 0 is a margin,
 * rho < 0 is a violation, and |rho| is the margin in the requirement's own unit
 * -- hours, degrees C, percentage points, degrees, metres.
 *
 * It arrives on `/api/plan`, `/api/plan-4d`, `/api/compare` and
 * `/api/plan-multi` without being asked for, so nothing here fetches anything.
 * The plan is explicit that this must not sit behind a button: if the result is
 * present it is shown.
 *
 * THE CLAIM BOUNDARY IS PART OF THE DATA. The backend ships `monitor.claim`
 * with every response and it says what this is: the planned trace was checked
 * by runtime monitoring, and NOT proven by model checking. The words "formally
 * proven" and "model checked" must not appear anywhere in this feature, and the
 * backend's own sentence is displayed rather than paraphrased so the boundary
 * cannot drift as the UI is edited.
 *
 * FOUR STATES, NOT TWO. A requirement that could not be tested is not a pass.
 * The contract distinguishes an inapplicable requirement (the signal is not in
 * a 2-D trace; the goal was never reached, so arrival SOC has no scope; the
 * rover has no thermal envelope) from a pending one (an online prefix has not
 * decided yet) from a satisfied one. Collapsing any of those into "OK" is
 * exactly the failure this feature exists to avoid.
 */

/** Where a requirement ended up. */
export type MarginState =
  | 'satisfied'
  | 'violated'
  /** rho is exactly 0: met, with nothing left over. */
  | 'boundary'
  /** Not decided yet -- an online prefix that has not reached the goal. */
  | 'pending'
  /** Not testable on this trace or this rover. Never a pass. */
  | 'not-applicable'

export interface RequirementView {
  id: string
  /** The backend's short name, e.g. `shadow_endurance`. */
  name: string
  /** `safety` or `mission`. Only safety-class rows feed `min_margin`. */
  requirementClass: string
  state: MarginState
  /**
   * Robustness. Null when the margin is unbounded in either direction --
   * `openEnded` says which. Never coerced to 0: a requirement with no finite
   * margin is not a requirement with no margin.
   */
  rho: number | null
  unit: string | null
  /** rho over its own scale. A comparison key only, never a percentage. */
  rhoNormalized: number | null
  /** True: margin is +infinity. False with rho null and violated: -infinity. */
  openEnded: boolean
  /** Why it could not be tested, when the backend gave a reason. */
  reason: string | null
  /** FRETISH sentence -- the requirement in structured English. */
  fretish: string | null
  /** Where the margin was smallest. */
  worstAt: { hours: number | null; row: number | null; col: number | null } | null
}

export interface SafetyMarginsView {
  /** satisfied / violated / pending / not_evaluated, straight from the backend. */
  verdict: string
  requirements: RequirementView[]
  nApplicable: number | null
  nViolated: number | null
  violatedIds: string[]
  /** Smallest normalised margin among finite safety-class requirements. */
  minMargin: { id: string; rho: number | null; unit: string | null } | null
  /** The backend's own claim sentence. Displayed verbatim. */
  claim: string | null
  /** Which monitor ran, and whether the second one agreed. */
  engine: string | null
  crossCheckMaxDiff: number | null
  /** 2d / 4d / telemetry, and whether the trace was complete. */
  traceKind: string | null
  traceComplete: boolean | null
}

function str(source: Record<string, unknown>, key: string): string | null {
  const value = source[key]
  return typeof value === 'string' ? value : null
}

function num(source: Record<string, unknown>, key: string): number | null {
  const value = source[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function obj(source: Record<string, unknown> | null, key: string): Record<string, unknown> | null {
  if (!source) return null
  const value = source[key]
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

/**
 * Which of the five states a requirement is in.
 *
 * Order matters. `applicable: false` is checked before anything else, because
 * such a row still carries a `satisfied` of null and reading that as "not
 * violated" is how an untested requirement becomes a green tick.
 */
function stateOf(entry: Record<string, unknown>): MarginState {
  if (entry.applicable === false) return 'not-applicable'
  if (entry.pending === true) return 'pending'
  if (entry.satisfied === false) return 'violated'
  if (entry.boundary === true) return 'boundary'
  if (entry.satisfied === true) return 'satisfied'
  // satisfied null with nothing else set: the backend has not decided, and
  // this is not the place to decide for it.
  return 'pending'
}

/**
 * Read the block, or null when the response carries none.
 *
 * Null and "present but empty" are different: a compare result whose
 * simulation was dropped has no field at all, and drawing an empty panel for
 * it would report twelve requirements as untested when none were asked for.
 */
export function readSafetyMargins(result: unknown): SafetyMarginsView | null {
  const root = obj(result as Record<string, unknown> | null, 'safety_margins')
  if (!root) return null

  const monitor = obj(root, 'monitor')
  const trace = obj(monitor, 'trace')
  const crossCheck = obj(monitor, 'cross_check')
  const minMargin = obj(root, 'min_margin')

  const rawRequirements = Array.isArray(root.requirements) ? root.requirements : []
  const requirements: RequirementView[] = rawRequirements
    .filter((entry): entry is Record<string, unknown> =>
      typeof entry === 'object' && entry !== null)
    .map((entry) => {
      const worst = obj(entry, 'worst_at')
      return {
        id: str(entry, 'id') ?? '??',
        name: str(entry, 'name') ?? '',
        requirementClass: str(entry, 'class') ?? 'safety',
        state: stateOf(entry),
        rho: num(entry, 'rho'),
        unit: str(entry, 'unit'),
        rhoNormalized: num(entry, 'rho_normalized'),
        openEnded: entry.open_ended === true,
        reason: str(entry, 'reason'),
        fretish: str(entry, 'fretish'),
        worstAt: worst
          ? { hours: num(worst, 'hours'), row: num(worst, 'row'), col: num(worst, 'col') }
          : null,
      }
    })

  return {
    verdict: str(root, 'verdict') ?? 'not_evaluated',
    requirements,
    nApplicable: num(root, 'n_applicable'),
    nViolated: num(root, 'n_violated'),
    violatedIds: Array.isArray(root.violated)
      ? root.violated.filter((id): id is string => typeof id === 'string')
      : [],
    minMargin: minMargin
      ? {
          id: str(minMargin, 'id') ?? '??',
          rho: num(minMargin, 'rho'),
          unit: str(minMargin, 'unit'),
        }
      : null,
    claim: monitor ? str(monitor, 'claim') : null,
    engine: monitor ? str(monitor, 'engine') : null,
    crossCheckMaxDiff: crossCheck ? num(crossCheck, 'max_abs_diff') : null,
    traceKind: trace ? str(trace, 'kind') : null,
    traceComplete: trace && typeof trace.complete === 'boolean' ? trace.complete : null,
  }
}

/**
 * The margin as text.
 *
 * The two unbounded cases are the reason this is not `rho.toFixed(2)`.
 * An open-ended margin is not a big number and must not be printed as one;
 * an unbounded violation is not a small one.
 */
export function formatMargin(requirement: RequirementView): string {
  if (requirement.rho === null) {
    if (requirement.openEnded) return 'No limit reached'
    if (requirement.state === 'violated') return 'Unbounded violation'
    return '--'
  }
  const unit = requirement.unit ? ` ${requirement.unit}` : ''
  const sign = requirement.rho > 0 ? '+' : ''
  return `${sign}${requirement.rho.toFixed(2)}${unit}`
}
