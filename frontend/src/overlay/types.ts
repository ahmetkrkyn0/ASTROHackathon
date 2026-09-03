import type { PixelPoint } from '../grid/geo'

export type { PixelPoint }

export type RampName = 'viridis' | 'magma' | 'thermal' | 'grayReverse'

export interface OverlayStyle {
  color: string
  /** Canvas line width in device pixels. Default 2. */
  lineWidth?: number
  /** 0-1. Default 1. */
  opacity?: number
  /** Marker radius for `points`, in device pixels. Default 4. */
  radius?: number
  /** Dash pattern, e.g. [6, 4]. Omit for a solid line. */
  dash?: number[]
}

/**
 * One thing a feature module wants drawn on the map.
 *
 * Every coordinate is a FINE grid pixel ({row, col}). A module holding CRS
 * metres or coarse pixels converts with grid/geo.ts before registering.
 * The canvas knows no other unit, and 3-D will consume this same list.
 */
export type OverlayLayer =
  | { kind: 'polyline'; id: string; points: PixelPoint[]; style: OverlayStyle }
  | {
      kind: 'ribbon'
      id: string
      center: PixelPoint[]
      /** One half-width per centre point, already in FINE PIXELS. */
      halfWidthPx: number[]
      style: OverlayStyle
    }
  | { kind: 'points'; id: string; points: PixelPoint[]; style: OverlayStyle }
  | {
      kind: 'field'
      id: string
      data: Float32Array
      rows: number
      cols: number
      /** [min, max] the ramp maps across. NaN cells are left transparent. */
      domain: [number, number]
      ramp: RampName
      opacity: number
    }
