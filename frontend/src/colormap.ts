export type RGB = [number, number, number]

// ── Slope colormap (thermal mode) ─────────────────────────────────────────────

export function slopeToRgb(deg: number | null): RGB {
  if (deg === null || !isFinite(deg)) return [15, 15, 25]
  if (deg >= 25) return [90, 5, 5]
  if (deg >= 20) return [190, 40, 0]
  if (deg >= 15) return [210, 110, 0]
  if (deg >= 10) return [190, 180, 20]
  if (deg >= 5)  return [80, 150, 60]
  return [30, 85, 70]
}

export function blockedOverlay(base: RGB): RGB {
  return [
    Math.round(base[0] * 0.25 + 90),
    Math.round(base[1] * 0.1),
    Math.round(base[2] * 0.1),
  ]
}

// ── Risk / battery colors ─────────────────────────────────────────────────────

export function riskToHex(level: string): string {
  switch (level.toUpperCase()) {
    case 'LOW':      return '#00e676'
    case 'MEDIUM':   return '#ffea00'
    case 'HIGH':     return '#ff6d00'
    case 'CRITICAL': return '#ff1744'
    default:         return '#ffffff'
  }
}

export function batteryToHex(pct: number): string {
  if (pct > 50) return '#00e676'
  if (pct > 25) return '#ffea00'
  if (pct > 10) return '#ff6d00'
  return '#ff1744'
}

export function lerpRgb(a: RGB, b: RGB, t: number): RGB {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ]
}

// ── Regolith colormap (surface mode) ──────────────────────────────────────────
// From visualize_processed_data.py LUNAR_REGOLITH_CMAP
// LRO / regolit: neutral gray-beige tones, no terrain greens

const REGOLITH_STOPS: RGB[] = [
  [5, 5, 6],         // #050506
  [21, 21, 23],       // #151517
  [42, 41, 40],       // #2a2928
  [69, 66, 62],       // #45423e
  [92, 88, 82],       // #5c5852
  [122, 116, 108],    // #7a746c
  [154, 146, 136],    // #9a9288
  [184, 175, 164],    // #b8afa4
  [212, 205, 195],    // #d4cdc3
]

export function elevationToRegolith(t: number): RGB {
  const clamped = Math.max(0, Math.min(1, t))
  const idx = clamped * (REGOLITH_STOPS.length - 1)
  const lo = Math.floor(idx)
  const hi = Math.min(lo + 1, REGOLITH_STOPS.length - 1)
  return lerpRgb(REGOLITH_STOPS[lo], REGOLITH_STOPS[hi], idx - lo)
}

// ── Hillshade (matches Python: azimuth=292, altitude=6.5, vert_exag=2.2) ─────

export function computeHillshade(
  grid: (number | null)[][],
  r: number,
  c: number,
  azDeg = 292,
  altDeg = 6.5,
  vertExag = 2.2,
): number {
  const rows = grid.length
  const cols = grid[0]?.length ?? 0
  const get = (rr: number, cc: number): number => {
    rr = Math.max(0, Math.min(rows - 1, rr))
    cc = Math.max(0, Math.min(cols - 1, cc))
    return grid[rr]?.[cc] ?? 0
  }
  // Sobel gradient
  const dzdx =
    ((get(r - 1, c + 1) + 2 * get(r, c + 1) + get(r + 1, c + 1)) -
     (get(r - 1, c - 1) + 2 * get(r, c - 1) + get(r + 1, c - 1))) / 8
  const dzdy =
    ((get(r + 1, c - 1) + 2 * get(r + 1, c) + get(r + 1, c + 1)) -
     (get(r - 1, c - 1) + 2 * get(r - 1, c) + get(r - 1, c + 1))) / 8

  const az = (azDeg * Math.PI) / 180
  const alt = (altDeg * Math.PI) / 180
  const slope = Math.atan(Math.sqrt(dzdx * dzdx + dzdy * dzdy) * vertExag)
  const aspect = Math.atan2(-dzdy, dzdx)

  let shade =
    Math.cos(slope) * Math.sin(alt) +
    Math.sin(slope) * Math.cos(alt) * Math.cos(az - aspect)
  // Soft blend (similar to matplotlib "soft" blend_mode)
  return Math.max(0, Math.min(1, shade * 0.65 + 0.35))
}

// ── Coordinate conversion (Lunar South Polar Stereographic -> approx lon/lat)

const MOON_R = 1737400
const ORIGIN_X = 156000
const ORIGIN_Y = 28000
const CELL_M = 80

export function pixelToApproxLonLat(
  row: number,
  col: number,
): { lon: number; lat: number } {
  const x = ORIGIN_X + col * CELL_M
  const y = ORIGIN_Y + row * CELL_M
  const rho = Math.sqrt(x * x + y * y)
  if (rho < 1e-10) return { lon: 0, lat: -90 }
  const c = 2 * Math.atan2(rho, 2 * MOON_R)
  return {
    lon: +((Math.atan2(x, y) * 180) / Math.PI).toFixed(4),
    lat: +((Math.asin(-Math.cos(c)) * 180) / Math.PI).toFixed(4),
  }
}
