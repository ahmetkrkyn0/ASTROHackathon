export type RGB = [number, number, number]

/**
 * Slope-based colormap reflecting traversability risk.
 *   0–5°  : dark teal  (safe)
 *   5–10° : olive green
 *  10–15° : yellow
 *  15–20° : orange
 *  20–25° : red-orange
 *  ≥25°   : dark red   (impassable hard block)
 *  null   : near-black (no data)
 */
export function slopeToRgb(deg: number | null): RGB {
  if (deg === null || !isFinite(deg)) return [15, 15, 25]
  if (deg >= 25) return [90, 5, 5]
  if (deg >= 20) return [190, 40, 0]
  if (deg >= 15) return [210, 110, 0]
  if (deg >= 10) return [190, 180, 20]
  if (deg >= 5)  return [80, 150, 60]
  return [30, 85, 70]
}

/**
 * Blocked cell overlay color (traversable === 0).
 * Mixes base color toward dark red to visually mark impassable areas.
 */
export function blockedOverlay(base: RGB): RGB {
  return [
    Math.round(base[0] * 0.25 + 90),
    Math.round(base[1] * 0.1),
    Math.round(base[2] * 0.1),
  ]
}

/**
 * Risk level → CSS hex color for path segment drawing.
 */
export function riskToHex(level: string): string {
  switch (level.toUpperCase()) {
    case 'LOW':      return '#00e676'
    case 'MEDIUM':   return '#ffea00'
    case 'HIGH':     return '#ff6d00'
    case 'CRITICAL': return '#ff1744'
    default:         return '#ffffff'
  }
}

/**
 * Battery percentage → CSS hex color for UI indicators.
 */
export function batteryToHex(pct: number): string {
  if (pct > 50) return '#00e676'
  if (pct > 25) return '#ffea00'
  if (pct > 10) return '#ff6d00'
  return '#ff1744'
}

/**
 * Linear interpolation between two RGB values.
 */
export function lerpRgb(a: RGB, b: RGB, t: number): RGB {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ]
}
