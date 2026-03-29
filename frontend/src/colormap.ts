export type RGB = [number, number, number]

const COOLWARM_STOPS: RGB[] = [
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

export function riskToHex(level: string): string {
  switch (level.toUpperCase()) {
    case 'LOW':
      return '#00e676'
    case 'MEDIUM':
      return '#ffea00'
    case 'HIGH':
      return '#ff6d00'
    case 'CRITICAL':
      return '#ff1744'
    default:
      return '#ffffff'
  }
}

export function batteryToHex(percent: number): string {
  if (percent > 50) {
    return '#00e676'
  }
  if (percent > 25) {
    return '#ffea00'
  }
  if (percent > 10) {
    return '#ff6d00'
  }
  return '#ff1744'
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
 * Grid verisi üzerinden histogram equalization LUT'u oluşturur.
 * Sonuç: her bin için [0,1] arası eşitlenmiş değer dizisi.
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

  // CDF oluştur
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
