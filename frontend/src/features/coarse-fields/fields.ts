/**
 * The coarse analysis fields -- B1 survival and C6 thermal dwell.
 *
 * Separate from `analysis-layers` because these are not layers of the terrain.
 * They are computed at `coarsen = 4` (125x125 at 20 m, against the fine grid's
 * 500x500 at 5 m), they depend on a mission epoch, a rover state of charge and
 * a goal, and two of them are **categorical**. A toggle list that mixed them
 * with the measured rasters would imply they answer the same kind of question.
 *
 * The categorical part is the load-bearing bit. `best_action` and `side` arrive
 * with `units: "code"`. A `FieldRamp` interpolates between its stops, so
 * drawing a code field through one produces colours for values between two
 * codes -- half "wait", half "drive north" -- which is not an action the policy
 * ever returned. So a categorical field is published as **one single-colour
 * mask per category**, and interpolation becomes structurally impossible:
 * there is nothing between two separate masks to interpolate.
 */

import {
  DWELL_STOPS,
  P_SAFE_STOPS,
  ACTION_DRIVE_RGB,
  ACTION_WAIT_RGB,
  ACTION_SAFE_RGB,
  ACTION_NONE_RGB,
  SIDE_COLD_RGB,
  SIDE_HOT_RGB,
  SIDE_INSIDE_RGB,
  type RGB,
} from '../../colormap'

export type CoarseFieldId =
  | 'p_safe'
  | 'best_action'
  | 'max_dwell_h'
  | 'side'

/** Which endpoint a field comes from. They take different parameters. */
export type CoarseSource = 'survival' | 'thermal-dwell'

/**
 * One category of a code field: the codes it covers and its colour.
 *
 * `codes` is a list rather than a range because the eight direction codes
 * (0-7) collapse into one category while 8, 254 and 255 each stand alone --
 * the numeric distance between codes carries no meaning, which is the whole
 * reason a ramp is wrong here.
 */
export interface FieldCategory {
  readonly key: string
  readonly label: string
  readonly codes: readonly number[]
  readonly color: RGB
  readonly note?: string
}

export type CoarseRender =
  | { mode: 'ramp'; stops: RGB[] }
  | { mode: 'categorical'; categories: readonly FieldCategory[] }

export interface CoarseFieldSpec {
  readonly id: CoarseFieldId
  readonly source: CoarseSource
  readonly label: string
  readonly blurb: string
  readonly limit: string
  readonly render: CoarseRender
  readonly opacity: number
}

/**
 * `best_action`, in four categories rather than eleven colours.
 *
 * The backend returns 0-7 for the eight compass moves, 8 for wait, 254 for
 * "already in the safe set" and 255 for "no action helps". Eight direction
 * colours on a 125x125 field would be unreadable noise, and the direction of a
 * single block is a cell-card question (`best_action_name`) rather than a map
 * question. What the map can usefully say is which KIND of decision the policy
 * made, which is these four.
 */
const ACTION_CATEGORIES: readonly FieldCategory[] = [
  {
    key: 'safe',
    label: 'Already safe',
    codes: [254],
    color: ACTION_SAFE_RGB,
    note: 'In the safe set. Nothing to do.',
  },
  {
    key: 'drive',
    label: 'Drive',
    codes: [0, 1, 2, 3, 4, 5, 6, 7],
    color: ACTION_DRIVE_RGB,
    note: 'Move. The direction is in the cell card, not on the map.',
  },
  {
    key: 'wait',
    label: 'Wait',
    codes: [8],
    color: ACTION_WAIT_RGB,
    note: 'Hold position; waiting beats moving from here.',
  },
  {
    key: 'none',
    label: 'No action helps',
    codes: [255],
    color: ACTION_NONE_RGB,
    note: 'Impassable, out of charge, or already certain. P_safe is 0 or 1.',
  },
]

/** `side`: 0 does not leave the envelope, 1 cold, 2 hot. */
const SIDE_CATEGORIES: readonly FieldCategory[] = [
  {
    key: 'inside',
    label: 'Stays inside',
    codes: [0],
    color: SIDE_INSIDE_RGB,
    note: 'Never leaves the envelope within the lookahead. Dwell is open-ended.',
  },
  { key: 'cold', label: 'Cold limit', codes: [1], color: SIDE_COLD_RGB },
  { key: 'hot', label: 'Hot limit', codes: [2], color: SIDE_HOT_RGB },
]

export const COARSE_FIELDS: readonly CoarseFieldSpec[] = [
  {
    id: 'p_safe',
    source: 'survival',
    label: 'P(safe)',
    blurb: 'Chance the rover reaches the safe set from this block.',
    limit:
      'A computed policy (MODEL), not an observation. Needs an epoch, a state of charge and a goal.',
    render: { mode: 'ramp', stops: P_SAFE_STOPS },
    opacity: 0.6,
  },
  {
    id: 'best_action',
    source: 'survival',
    label: 'Best action',
    blurb: 'What the recovery policy would do from each block.',
    limit: 'Categorical, not a scale. Drawn as four discrete kinds, never as a gradient.',
    render: { mode: 'categorical', categories: ACTION_CATEGORIES },
    opacity: 0.62,
  },
  {
    id: 'max_dwell_h',
    source: 'thermal-dwell',
    label: 'Max dwell',
    blurb: 'Hours a rover arriving now may stand here before leaving its envelope.',
    limit:
      'MODEL, and the thermal lag behind it is UNCALIBRATED. Blocks at the lookahead were clipped, not measured.',
    render: { mode: 'ramp', stops: DWELL_STOPS },
    opacity: 0.6,
  },
  {
    id: 'side',
    source: 'thermal-dwell',
    label: 'Envelope side',
    blurb: 'Which limit the inner temperature reaches first.',
    limit: 'Categorical. "Stays inside" is why a dwell reads 24 h — it is a floor, not a value.',
    render: { mode: 'categorical', categories: SIDE_CATEGORIES },
    opacity: 0.62,
  },
]

export function coarseFieldById(id: CoarseFieldId): CoarseFieldSpec {
  const spec = COARSE_FIELDS.find((entry) => entry.id === id)
  if (!spec) throw new Error(`unknown coarse field: ${id}`)
  return spec
}
