export type RGB = [number, number, number]

/** Exported for the overlay contract, whose field command carries its stops. */
export const COOLWARM_STOPS: RGB[] = [
  [59, 76, 192],
  [98, 130, 234],
  [141, 176, 254],
  [184, 208, 249],
  [221, 221, 221],
  [243, 199, 166],
  [237, 156, 122],
  [214, 96, 77],
  [180, 4, 38],
]

const MAGMA_STOPS: RGB[] = [
  [0, 0, 4],
  [27, 16, 69],
  [80, 18, 123],
  [129, 37, 129],
  [181, 54, 122],
  [229, 80, 100],
  [251, 135, 97],
  [254, 194, 135],
  [252, 253, 191],
]

const VIRIDIS_STOPS: RGB[] = [
  [68, 1, 84],
  [71, 44, 122],
  [59, 81, 139],
  [44, 113, 142],
  [33, 144, 141],
  [39, 173, 129],
  [92, 200, 99],
  [170, 220, 50],
  [253, 231, 37],
]

const RDYLGN_STOPS: RGB[] = [
  [165, 0, 38],
  [215, 48, 39],
  [244, 109, 67],
  [253, 174, 97],
  [254, 224, 139],
  [217, 239, 139],
  [166, 217, 106],
  [102, 189, 99],
  [26, 150, 65],
]

const REGOLITH_STOPS: RGB[] = [
  [5, 5, 6],
  [21, 21, 23],
  [42, 41, 40],
  [69, 66, 62],
  [92, 88, 82],
  [122, 116, 108],
  [154, 146, 136],
  [184, 175, 164],
  [212, 205, 195],
]

const MOON_RADIUS_M = 1737400
const DEFAULT_ORIGIN_X = 176000
const DEFAULT_ORIGIN_Y = 48000
const DEFAULT_RESOLUTION_M = 80

export const START_MINT = '#5fe3b0'
export const GOAL_CORAL = '#ed856e'
/** The trajectory itself, not a risk reading. */
export const ROUTE_CYAN = '#4fd8f0'
export const LAVENDER_ACCENT = '#baaff5'

/**
 * The risk ramp, mirroring --risk-* in App.css.
 *
 * Written out because canvas strokeStyle and THREE.Color take a string, not a
 * CSS variable. The two must move together; App.css carries the derivation
 * and the measurements behind these four values.
 */
export function riskToHex(level: string): string {
  switch (level.toUpperCase()) {
    case 'LOW':
      return '#4a8fd8'
    case 'MEDIUM':
      return '#e3d548'
    case 'HIGH':
      return '#d69770'
    case 'CRITICAL':
      return '#ed4b3d'
    default:
      return '#8b94a6'
  }
}

/**
 * The dash pattern that carries risk alongside its colour.
 *
 * Colour alone cannot do this job. Four steps on one colour channel have a
 * measured ceiling of ~42 separation under the traffic-light metaphor, and
 * the ramp we can actually ship reaches 27.8 -- better than the 15.4 it
 * replaces, still not enough to be the only channel. The guidance is explicit:
 * do not rely solely on colour.
 *
 * The progression is a metaphor rather than four arbitrary patterns: the line
 * breaks up more as the risk rises. Solid ground, then gaps, then barely
 * holding together. Someone who cannot see any of the four colours still reads
 * the severity order off the line.
 *
 * Lengths are canvas units at the 2.8px stroke the route is drawn with; they
 * are deliberately far apart so the patterns survive a short segment.
 */
export function riskToDash(level: string): number[] {
  switch (level.toUpperCase()) {
    case 'LOW':
      return []
    case 'MEDIUM':
      return [10, 5]
    case 'HIGH':
      return [4, 4]
    case 'CRITICAL':
      return [1.5, 3.5]
    default:
      return []
  }
}

/** The same patterns as an SVG stroke-dasharray, for the legend. */
export function riskToDashArray(level: string): string {
  const dash = riskToDash(level)
  return dash.length ? dash.join(' ') : 'none'
}

/**
 * Battery state of charge, on the risk ramp.
 *
 * Deliberately the same four values and the same four thresholds the backend
 * uses to derive risk_level (simulation.py `_risk_level`): a battery at 20%
 * IS a HIGH-risk rover, and showing that reading in a colour the risk ramp
 * does not use would be the same defect the legend had -- one meaning, two
 * colours.
 */
export function batteryToHex(percent: number): string {
  if (percent > 50) {
    return riskToHex('LOW')
  }
  if (percent > 25) {
    return riskToHex('MEDIUM')
  }
  if (percent > 10) {
    return riskToHex('HIGH')
  }
  return riskToHex('CRITICAL')
}

export function thermalToRgb(value: number | null, min: number, max: number, lut?: number[]): RGB {
  if (value === null || !Number.isFinite(value)) {
    return [12, 14, 20]
  }

  const t = lut
    ? lookupEqualized(value, min, max, lut)
    : normalize(value, min, max)
  return sampleStops(COOLWARM_STOPS, t)
}

export function elevationToRegolith(t: number, lut?: number[], min?: number, max?: number): RGB {
  if (lut && min !== undefined && max !== undefined) {
    return sampleStops(REGOLITH_STOPS, clamp01(lookupEqualized(t, min, max, lut)))
  }
  return sampleStops(REGOLITH_STOPS, clamp01(t))
}

export function shadeRegolith(base: RGB, shade: number): RGB {
  const normalizedShade = clamp01(shade)
  const signedShade = normalizedShade * 2 - 1

  return [
    shadeChannel(base[0], signedShade),
    shadeChannel(base[1], signedShade),
    shadeChannel(base[2], signedShade),
  ]
}

export function tintRgb(base: RGB, overlay: RGB, strength: number): RGB {
  return [
    Math.round(base[0] + (overlay[0] - base[0]) * clamp01(strength)),
    Math.round(base[1] + (overlay[1] - base[1]) * clamp01(strength)),
    Math.round(base[2] + (overlay[2] - base[2]) * clamp01(strength)),
  ]
}

export function lunarRegolithToRgb(value: number | null, min: number, max: number): RGB {
  if (value === null || !Number.isFinite(value)) {
    return [8, 8, 11]
  }
  return sampleStops(REGOLITH_STOPS, normalize(value, min, max))
}

export function magmaToRgb(value: number | null, min: number, max: number): RGB {
  if (value === null || !Number.isFinite(value)) {
    return [8, 8, 11]
  }
  return sampleStops(MAGMA_STOPS, normalize(value, min, max))
}

export function viridisToRgb(value: number | null, min: number, max: number): RGB {
  if (value === null || !Number.isFinite(value)) {
    return [8, 8, 11]
  }
  return sampleStops(VIRIDIS_STOPS, normalize(value, min, max))
}

export function rdYlGnToRgb(value: number | null, min: number, max: number): RGB {
  if (value === null || !Number.isFinite(value)) {
    return [8, 8, 11]
  }
  return sampleStops(RDYLGN_STOPS, normalize(value, min, max))
}

export function grayReverseToRgb(value: number | null, min: number, max: number): RGB {
  if (value === null || !Number.isFinite(value)) {
    return [8, 8, 11]
  }
  const channel = Math.round(255 * (1 - clamp01(normalize(value, min, max))))
  return [channel, channel, channel]
}

/**
 * Analysis-overlay ramps.
 *
 * Separate from the base-map ramps above because they are `FieldRamp` data for
 * the overlay contract, not `(value) => RGB` functions: a callback would be a
 * new identity every render, which is exactly what makes an overlay
 * registration effect loop forever.
 */

/**
 * Roughness, in metres. Cool where the ground is smooth, hot where it is not.
 *
 * Amber rather than red at the top: this is a fifth cost criterion, not a
 * hazard. LDRM roughness never makes a cell impassable, and a red field over
 * the map would say it did.
 */
export const ROUGHNESS_STOPS: RGB[] = [
  [26, 42, 58],
  [37, 92, 112],
  [88, 148, 130],
  [176, 178, 106],
  [226, 160, 74],
  [232, 118, 62],
]

/**
 * Earth visibility, as a fraction of the sampled span.
 *
 * Dark where the Earth never rises, bright cyan where the link is always
 * geometrically possible. Deliberately the route colour family: a link window
 * is an operational affordance, not a warning.
 */
export const EARTH_VISIBILITY_STOPS: RGB[] = [
  [14, 18, 28],
  [24, 54, 78],
  [34, 104, 132],
  [58, 164, 186],
  [110, 216, 232],
]

/**
 * Time to the nearest reachable Safe Haven, in hours. Short is safe.
 *
 * There is no stop for "unreachable" and there must not be one. That value
 * arrives as NaN, becomes null on the way to the overlay, and is left
 * unpainted -- a cell with no reachable haven is not the far end of this ramp,
 * it is off it entirely. Giving it the darkest colour would put it on the same
 * axis as "eighteen hours away", which is a different statement.
 */
export const TIME_TO_HAVEN_STOPS: RGB[] = [
  [95, 227, 176],
  [140, 208, 140],
  [206, 200, 104],
  [226, 150, 84],
  [214, 96, 77],
]

/**
 * P(traversable) across NASA's 100 DEM clones.
 *
 * Diverging on purpose, with the uncertain middle the loudest part. 0 and 1
 * are both CERTAIN -- certainly impassable, certainly passable -- and the
 * interesting cells are the 0.05..0.95 band where the clones disagree. A
 * monotonic ramp would make "certainly impassable" the eye-catching end and
 * bury the only thing this layer adds over `traversable`.
 */
export const P_TRAVERSABLE_STOPS: RGB[] = [
  [70, 32, 44],
  [140, 70, 62],
  [214, 158, 84],
  [140, 152, 96],
  [58, 122, 96],
]

/**
 * A standard deviation, in the layer's own unit. Quiet where the ensemble
 * agrees, bright where it does not.
 *
 * Shared by all three sigma layers so that `slope_sigma` (our ensemble, DERIVED)
 * and `slope_sigma_nasa` (NASA's error model, MODEL) are read on the same scale
 * of colour. They are not on the same scale of NUMBER -- their ranges differ by
 * a factor of three -- and each ramp is domained on its own layer's measured
 * min and max, which the provenance badge beside it explains.
 */
export const SIGMA_STOPS: RGB[] = [
  [18, 24, 36],
  [40, 66, 96],
  [92, 106, 140],
  [168, 142, 148],
  [232, 196, 140],
]

/**
 * P(safe) from the reach-avoid policy. Red at zero, green at one.
 *
 * Zero is a real and common answer here -- 28% of traversable blocks on this
 * window -- so it gets the loudest end of the ramp rather than being left to
 * look like missing data.
 */
export const P_SAFE_STOPS: RGB[] = [
  [214, 76, 66],
  [222, 132, 78],
  [216, 186, 96],
  [150, 180, 112],
  [88, 176, 132],
]

/** Tolerable dwell, in hours. Short is the thing to notice. */
export const DWELL_STOPS: RGB[] = [
  [206, 86, 74],
  [220, 146, 84],
  [200, 190, 108],
  [128, 176, 148],
  [78, 150, 186],
]

/*
 * Categorical codes. Single colours, never ramp stops.
 *
 * These are `units: "code"` fields. Putting them through a FieldRamp would
 * produce a colour for a value between two codes -- half "wait", half "drive
 * north" -- which is not an action the policy ever returned. Each is published
 * as its own single-colour mask instead, so there is nothing to interpolate.
 */

/** best_action 254: already in the safe set. */
export const ACTION_SAFE_RGB: RGB = [95, 227, 176]
/** best_action 0-7: one of the eight compass moves. */
export const ACTION_DRIVE_RGB: RGB = [79, 216, 240]
/** best_action 8: hold position. */
export const ACTION_WAIT_RGB: RGB = [186, 175, 245]
/** best_action 255: no action reaches the safe set from here. */
export const ACTION_NONE_RGB: RGB = [196, 88, 82]

/** side 0: never leaves the envelope inside the lookahead. */
export const SIDE_INSIDE_RGB: RGB = [110, 186, 150]
/** side 1: reaches the cold limit first. */
export const SIDE_COLD_RGB: RGB = [92, 152, 226]
/** side 2: reaches the hot limit first. */
export const SIDE_HOT_RGB: RGB = [226, 128, 76]

/**
 * A2 corridor membership. Two masks, not a two-stop ramp.
 *
 * `lit_safe` is the wider set and `corridor` the pruned one inside it, so the
 * two are shades of one colour rather than two colours: they are the same
 * quantity at two stages, and a contrasting pair would read as two unrelated
 * layers.
 */
export const CORRIDOR_RGB: RGB = [120, 214, 196]
export const LIT_SAFE_RGB: RGB = [72, 138, 132]

/**
 * The PSR mask, as a single colour.
 *
 * A boolean layer is not a ramp. Two stops would paint the whole map -- the
 * zeros as much as the ones -- and PSR covers well under a percent of this
 * window; the honest rendering leaves the rest untouched. `maskValues` nulls
 * everything below threshold and this ramp then has only one value to serve,
 * so both stops are the same colour on purpose.
 */
export const PSR_MASK_RGB: RGB = [126, 122, 214]

export function aspectToRgb(value: number | null): RGB {
  if (value === null || !Number.isFinite(value)) {
    return [8, 8, 11]
  }
  return hsvToRgb(((value % 360) + 360) % 360, 1, 1)
}

export function computeHillshade(
  grid: (number | null)[][],
  row: number,
  col: number,
  resolutionM: number,
  azimuthDeg = 292,
  altitudeDeg = 6.5,
  verticalExaggeration = 2.2,
): number {
  const rows = grid.length
  const cols = grid[0]?.length ?? 0
  const center = finiteValue(grid[row]?.[col], 0)

  const read = (rowIndex: number, colIndex: number): number => {
    const clampedRow = Math.max(0, Math.min(rows - 1, rowIndex))
    const clampedCol = Math.max(0, Math.min(cols - 1, colIndex))
    return finiteValue(grid[clampedRow]?.[clampedCol], center)
  }

  const scale = Math.max(resolutionM, 1e-6) * 8
  const dzdx =
    ((read(row - 1, col + 1) + 2 * read(row, col + 1) + read(row + 1, col + 1)) -
      (read(row - 1, col - 1) + 2 * read(row, col - 1) + read(row + 1, col - 1))) /
    scale
  const dzdy =
    ((read(row + 1, col - 1) + 2 * read(row + 1, col) + read(row + 1, col + 1)) -
      (read(row - 1, col - 1) + 2 * read(row - 1, col) + read(row - 1, col + 1))) /
    scale

  const azimuth = (azimuthDeg * Math.PI) / 180
  const altitude = (altitudeDeg * Math.PI) / 180
  const slope = Math.atan(Math.sqrt(dzdx * dzdx + dzdy * dzdy) * verticalExaggeration)
  const aspect = Math.atan2(-dzdy, dzdx)

  const shade =
    Math.cos(slope) * Math.sin(altitude) +
    Math.sin(slope) * Math.cos(altitude) * Math.cos(azimuth - aspect)

  return clamp01(shade * 0.65 + 0.35)
}

export function pixelToApproxLonLat(
  row: number,
  col: number,
  options?: {
    originX?: number
    originY?: number
    resolutionM?: number
  },
): { lon: number; lat: number } {
  const originX = options?.originX ?? DEFAULT_ORIGIN_X
  const originY = options?.originY ?? DEFAULT_ORIGIN_Y
  const resolutionM = options?.resolutionM ?? DEFAULT_RESOLUTION_M
  const x = originX + col * resolutionM
  const y = originY + row * resolutionM
  const rho = Math.sqrt(x * x + y * y)

  if (rho < 1e-10) {
    return { lon: 0, lat: -90 }
  }

  const c = 2 * Math.atan2(rho, 2 * MOON_RADIUS_M)
  return {
    lon: +((Math.atan2(x, y) * 180) / Math.PI).toFixed(4),
    lat: +((Math.asin(-Math.cos(c)) * 180) / Math.PI).toFixed(4),
  }
}

// ── Histogram equalization ─────────────────────────────────────────────────

const EQ_BINS = 256

/**
 * Builds a histogram-equalisation LUT from the grid.
 * Result: one equalised value in [0,1] per bin.
 */
export function buildEqualizationLut(grid: (number | null)[][], min: number, max: number): number[] {
  const histogram = new Uint32Array(EQ_BINS)
  let totalCount = 0

  for (const row of grid) {
    for (const value of row) {
      if (typeof value === 'number' && Number.isFinite(value)) {
        const bin = Math.min(EQ_BINS - 1, Math.max(0, Math.floor(((value - min) / (max - min)) * (EQ_BINS - 1))))
        histogram[bin]++
        totalCount++
      }
    }
  }

  // Build the CDF
  const cdf = new Float64Array(EQ_BINS)
  cdf[0] = histogram[0]
  for (let i = 1; i < EQ_BINS; i++) {
    cdf[i] = cdf[i - 1] + histogram[i]
  }

  // Normalize CDF → [0, 1]
  const lut: number[] = new Array(EQ_BINS)
  const cdfMin = cdf.find(v => v > 0) ?? 0
  const denom = totalCount - cdfMin
  for (let i = 0; i < EQ_BINS; i++) {
    lut[i] = denom > 0 ? (cdf[i] - cdfMin) / denom : i / (EQ_BINS - 1)
  }

  return lut
}

function lookupEqualized(value: number, min: number, max: number, lut: number[]): number {
  const bin = Math.min(EQ_BINS - 1, Math.max(0, Math.floor(((value - min) / (max - min)) * (EQ_BINS - 1))))
  return lut[bin]
}

function sampleStops(stops: RGB[], t: number): RGB {
  const scaled = clamp01(t) * (stops.length - 1)
  const lowerIndex = Math.floor(scaled)
  const upperIndex = Math.min(lowerIndex + 1, stops.length - 1)
  const blend = scaled - lowerIndex

  return [
    Math.round(stops[lowerIndex][0] + (stops[upperIndex][0] - stops[lowerIndex][0]) * blend),
    Math.round(stops[lowerIndex][1] + (stops[upperIndex][1] - stops[lowerIndex][1]) * blend),
    Math.round(stops[lowerIndex][2] + (stops[upperIndex][2] - stops[lowerIndex][2]) * blend),
  ]
}

function hsvToRgb(h: number, s: number, v: number): RGB {
  const c = v * s
  const hh = (h / 60) % 6
  const x = c * (1 - Math.abs((hh % 2) - 1))

  let r = 0
  let g = 0
  let b = 0

  if (hh >= 0 && hh < 1) {
    r = c
    g = x
  } else if (hh < 2) {
    r = x
    g = c
  } else if (hh < 3) {
    g = c
    b = x
  } else if (hh < 4) {
    g = x
    b = c
  } else if (hh < 5) {
    r = x
    b = c
  } else {
    r = c
    b = x
  }

  const m = v - c
  return [
    Math.round((r + m) * 255),
    Math.round((g + m) * 255),
    Math.round((b + m) * 255),
  ]
}

function shadeChannel(channel: number, signedShade: number): number {
  if (signedShade >= 0) {
    return Math.round(channel + (255 - channel) * signedShade * 0.42)
  }
  return Math.round(channel * (1 + signedShade * 0.55))
}

function normalize(value: number, min: number, max: number): number {
  if (max - min < 1e-9) {
    return 0.5
  }
  return (value - min) / (max - min)
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value))
}

function finiteValue(value: number | null | undefined, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}
