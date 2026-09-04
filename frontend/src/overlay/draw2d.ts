import { magmaToRgb, thermalToRgb, viridisToRgb, grayReverseToRgb } from '../colormap'
import type { RGB } from '../colormap'
import type { OverlayLayer, PixelPoint, RampName } from './types'

/**
 * The four ramps a module may ask for, at their REAL signature.
 *
 * colormap.ts's ramps are (value, min, max) => RGB and normalise inside;
 * they are not (t) => rgb. An overlay has already normalised against its
 * own domain, so every ramp here is called on the unit interval:
 * toRgb(t, 0, 1). thermalToRgb's fourth `lut?` parameter is deliberately
 * not passed -- an equalisation LUT belongs to the base map, not to an
 * overlay whose domain the module chose itself.
 */
const RAMPS: Record<RampName, (value: number | null, min: number, max: number) => RGB> = {
  viridis: viridisToRgb,
  magma: magmaToRgb,
  thermal: thermalToRgb,
  grayReverse: grayReverseToRgb,
}

/**
 * Draw every registered overlay onto the map canvas.
 *
 * `gridRows` is the LOADED GRID's row count -- never the canvas size. The
 * canvas is a fixed square (CANVAS_SIZE) whatever the grid's size and the
 * base map is painted at cellPx = CANVAS_SIZE / rows (MapCanvas.tsx:459),
 * so passing anything but the real row count puts every overlay out of
 * register with the map underneath it. That the shipped 500x500 grid makes
 * the two numbers equal today is a coincidence, not a contract.
 */
export function drawOverlays(
  ctx: CanvasRenderingContext2D,
  layers: OverlayLayer[],
  gridRows: number,
  canvasSize: number,
): void {
  if (!layers.length || gridRows <= 0) return
  const scale = canvasSize / gridRows

  for (const layer of layers) {
    ctx.save()
    switch (layer.kind) {
      case 'field':
        drawField(ctx, layer, canvasSize)
        break
      case 'ribbon':
        drawRibbon(ctx, layer, scale)
        break
      case 'polyline':
        drawPolyline(ctx, layer, scale)
        break
      case 'points':
        drawPoints(ctx, layer, scale)
        break
    }
    ctx.restore()
  }
}

function applyStroke(
  ctx: CanvasRenderingContext2D,
  style: { color: string; lineWidth?: number; opacity?: number; dash?: number[] },
): void {
  ctx.globalAlpha = style.opacity ?? 1
  ctx.strokeStyle = style.color
  ctx.lineWidth = style.lineWidth ?? 2
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.setLineDash(style.dash ?? [])
}

function drawPolyline(
  ctx: CanvasRenderingContext2D,
  layer: Extract<OverlayLayer, { kind: 'polyline' }>,
  scale: number,
): void {
  if (layer.points.length < 2) return
  applyStroke(ctx, layer.style)
  ctx.beginPath()
  layer.points.forEach((point, index) => {
    const x = (point.col + 0.5) * scale
    const y = (point.row + 0.5) * scale
    if (index === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.stroke()
}

function drawPoints(
  ctx: CanvasRenderingContext2D,
  layer: Extract<OverlayLayer, { kind: 'points' }>,
  scale: number,
): void {
  ctx.globalAlpha = layer.style.opacity ?? 1
  ctx.fillStyle = layer.style.color
  const radius = layer.style.radius ?? 4
  for (const point of layer.points) {
    ctx.beginPath()
    ctx.arc((point.col + 0.5) * scale, (point.row + 0.5) * scale, radius, 0, Math.PI * 2)
    ctx.fill()
  }
}

/**
 * The two edges of a corridor ribbon, one point per centre point.
 *
 * Exported and pure because this is the maths that draws a plausible band
 * when it is wrong: a flipped perpendicular swaps the edges, a dropped
 * clamp pinches the ribbon shut at the goal, and both still look like a
 * corridor on screen. See draw2d.test.ts.
 */
export function ribbonEdges(
  center: PixelPoint[],
  halfWidthPx: number[],
): { left: PixelPoint[]; right: PixelPoint[] } {
  const left: PixelPoint[] = []
  const right: PixelPoint[] = []

  for (let i = 0; i < center.length; i++) {
    const prev = center[Math.max(0, i - 1)]
    const next = center[Math.min(center.length - 1, i + 1)]
    const dRow = next.row - prev.row
    const dCol = next.col - prev.col
    const length = Math.hypot(dRow, dCol)
    if (length === 0) {
      // A repeated waypoint has no direction to be perpendicular to.
      // Collapsing to the centre keeps the polygon closed; dividing by
      // zero would put NaN into the path and blank the entire fill.
      left.push(center[i])
      right.push(center[i])
      continue
    }
    // Perpendicular in grid space: (dRow, dCol) -> (-dCol, dRow).
    const nRow = -dCol / length
    const nCol = dRow / length
    // half_width_m is per SEGMENT and so N-1 long against N centre points
    // (corridor.py:126). The last vertex reuses the last segment's width;
    // falling off the end to 0 would taper the corridor to a point exactly
    // at the goal, where the width matters most.
    const w = halfWidthPx[Math.min(i, halfWidthPx.length - 1)] ?? 0
    left.push({ row: center[i].row + nRow * w, col: center[i].col + nCol * w })
    right.push({ row: center[i].row - nRow * w, col: center[i].col - nCol * w })
  }

  return { left, right }
}

/**
 * A corridor is one filled band, not a stack of per-segment quads: drawn
 * segment by segment the shared edges overlap and a translucent fill goes
 * visibly darker at every joint. Walking the left side forward and the
 * right side back closes a single polygon instead.
 */
function drawRibbon(
  ctx: CanvasRenderingContext2D,
  layer: Extract<OverlayLayer, { kind: 'ribbon' }>,
  scale: number,
): void {
  const { center, halfWidthPx } = layer
  if (center.length < 2) return

  const { left, right } = ribbonEdges(center, halfWidthPx)

  ctx.globalAlpha = layer.style.opacity ?? 0.25
  ctx.fillStyle = layer.style.color
  ctx.beginPath()
  left.forEach((point, index) => {
    const x = (point.col + 0.5) * scale
    const y = (point.row + 0.5) * scale
    if (index === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  for (let i = right.length - 1; i >= 0; i--) {
    ctx.lineTo((right[i].col + 0.5) * scale, (right[i].row + 0.5) * scale)
  }
  ctx.closePath()
  ctx.fill()
}

/**
 * A field value's position on its ramp, or null for "draw nothing".
 *
 * NaN is the backend's only no-data value (binary_format.nodata) and has to
 * stay transparent: clamping it into the domain would paint missing data as
 * the coldest real value in the field, which reads as a measurement. Any
 * non-finite value is treated the same way, for the same reason.
 * Exported and pure -- see draw2d.test.ts.
 */
export function normaliseToDomain(
  value: number,
  domain: [number, number],
): number | null {
  if (!Number.isFinite(value)) return null
  const [min, max] = domain
  const span = max - min
  // A flat field is not an error: every cell sits at the bottom of the ramp
  // rather than dividing by zero into NaN.
  if (span === 0) return 0
  return Math.min(1, Math.max(0, (value - min) / span))
}

/**
 * A scalar field painted over the base map.
 *
 * Built as ImageData at the field's own resolution and blitted through an
 * offscreen canvas, so a 250x250 time slice scales up to the 500 px canvas
 * without the caller resampling anything. NaN is the backend's only
 * no-data value and stays fully transparent.
 */
function drawField(
  ctx: CanvasRenderingContext2D,
  layer: Extract<OverlayLayer, { kind: 'field' }>,
  canvasSize: number,
): void {
  const { data, rows, cols, domain, ramp, opacity } = layer
  if (data.length !== rows * cols) return

  const toRgb = RAMPS[ramp]
  const image = new ImageData(cols, rows)

  for (let i = 0; i < data.length; i++) {
    const offset = i * 4
    const t = normaliseToDomain(data[i], domain)
    if (t === null) {
      image.data[offset + 3] = 0
      continue
    }
    // The ramp's own (value, min, max) signature, on the unit interval the
    // line above just produced. One argument does not compile; the raw
    // value would normalise twice, against a domain the module never chose.
    const [r, g, b] = toRgb(t, 0, 1)
    image.data[offset] = r
    image.data[offset + 1] = g
    image.data[offset + 2] = b
    image.data[offset + 3] = 255
  }

  const scratch = document.createElement('canvas')
  scratch.width = cols
  scratch.height = rows
  const scratchCtx = scratch.getContext('2d')
  if (!scratchCtx) return
  scratchCtx.putImageData(image, 0, 0)

  ctx.globalAlpha = opacity
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(scratch, 0, 0, canvasSize, canvasSize)
}
