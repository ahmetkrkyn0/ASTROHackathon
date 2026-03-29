export type RGB = [number, number, number]

const THERMAL_STOPS: RGB[] = [
  [23, 68, 77],
  [42, 108, 99],
  [104, 144, 79],
  [183, 187, 61],
  [226, 173, 31],
  [213, 103, 18],
  [185, 48, 11],
  [122, 13, 8],
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

export function thermalToRgb(value: number | null, min: number, max: number): RGB {
  if (value === null || !Number.isFinite(value)) {
    return [12, 14, 20]
  }

  return sampleStops(THERMAL_STOPS, normalize(value, min, max))
}

export function elevationToRegolith(t: number): RGB {
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
