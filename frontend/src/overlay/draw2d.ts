import type { CellRef } from '../mission/types'
import type { FieldRamp, OverlayCommand, OverlayStyle } from './types'

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
  commands: readonly OverlayCommand[],
  gridRows: number,
  canvasSize: number,
): void {
  if (!commands.length || gridRows <= 0) return
  const scale = canvasSize / gridRows

  for (const command of commands) {
    ctx.save()
    switch (command.kind) {
      case 'field':
        drawField(ctx, command, canvasSize)
        break
      case 'ribbon':
        drawRibbon(ctx, command, scale)
        break
      case 'polyline':
        drawPolyline(ctx, command, scale)
        break
      case 'points':
        drawPoints(ctx, command, scale)
        break
    }
    ctx.restore()
  }
}

function applyStroke(ctx: CanvasRenderingContext2D, style: OverlayStyle): void {
  ctx.globalAlpha = style.opacity ?? 1
  ctx.strokeStyle = style.color
  ctx.lineWidth = style.widthPx ?? 2
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.setLineDash(style.dash ?? [])
}

function drawPolyline(
  ctx: CanvasRenderingContext2D,
  command: Extract<OverlayCommand, { kind: 'polyline' }>,
  scale: number,
): void {
  if (command.points.length < 2) return
  applyStroke(ctx, command.style)
  ctx.beginPath()
  command.points.forEach((point, index) => {
    const x = (point.col + 0.5) * scale
    const y = (point.row + 0.5) * scale
    if (index === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.stroke()
}

function drawPoints(
  ctx: CanvasRenderingContext2D,
  command: Extract<OverlayCommand, { kind: 'points' }>,
  scale: number,
): void {
  ctx.globalAlpha = command.style.opacity ?? 1
  ctx.fillStyle = command.style.color
  const radius = command.style.radiusPx ?? 4
  for (const point of command.points) {
    ctx.beginPath()
    ctx.arc((point.col + 0.5) * scale, (point.row + 0.5) * scale, radius, 0, Math.PI * 2)
    ctx.fill()
  }
}

/**
 * One half-width per centre point.
 *
 * The command allows a scalar, because a fixed-width sleeve is a real thing
 * to ask for, but ribbonEdges takes the array: the per-point form is the one
 * the corridor actually produces and the one the tests pin down. Expanding
 * here rather than inside ribbonEdges keeps that maths on a single shape.
 */
function widthsFor(command: Extract<OverlayCommand, { kind: 'ribbon' }>): number[] {
  const { halfWidthCells, points } = command
  return typeof halfWidthCells === 'number'
    ? new Array<number>(points.length).fill(halfWidthCells)
    : halfWidthCells
}

/**
 * The two edges of a corridor ribbon, one point per centre point.
 *
 * Exported and pure because this is the maths that draws a plausible band
 * when it is wrong: a flipped perpendicular swaps the edges, a dropped
 * clamp pinches the ribbon shut at the goal, and both still look like a
 * corridor on screen. See draw2d.test.ts.
 *
 * Widths are in CELLS, the same space as the points; the scale to canvas
 * pixels happens at draw time, once, for both.
 */
export function ribbonEdges(
  center: CellRef[],
  halfWidths: number[],
): { left: CellRef[]; right: CellRef[] } {
  const left: CellRef[] = []
  const right: CellRef[] = []

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
    const w = halfWidths[Math.min(i, halfWidths.length - 1)] ?? 0
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
  command: Extract<OverlayCommand, { kind: 'ribbon' }>,
  scale: number,
): void {
  const center = command.points
  if (center.length < 2) return

  const { left, right } = ribbonEdges(center, widthsFor(command))

  ctx.globalAlpha = command.style.opacity ?? 0.25
  ctx.fillStyle = command.style.color
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
 * A colour from a field's own ramp, at `t` on the unit interval.
 *
 * The command carries its stops rather than the name of a ramp, so this is
 * the only thing between a normalised value and a pixel. Exported and pure
 * for the usual reason: every way it can be wrong still paints a plausible
 * picture. Reversed stops invert the reading, an off-by-one on the band
 * index shifts every colour one step, and skipping the round leaves
 * fractional channels that Canvas truncates -- a whole layer one unit dark.
 *
 * Stops are evenly spaced across [0, 1], matching FieldRamp's contract.
 */
export function sampleRamp(
  colors: FieldRamp['colors'],
  t: number,
): [number, number, number] {
  const lastIndex = colors.length - 1
  if (lastIndex <= 0) {
    const [r, g, b] = colors[0]
    return [r, g, b]
  }

  const scaled = Math.min(1, Math.max(0, t)) * lastIndex
  // Clamped one short of the end so t === 1 reads the LAST band at frac 1
  // rather than indexing past the final stop.
  const lower = Math.min(lastIndex - 1, Math.floor(scaled))
  const frac = scaled - lower
  const from = colors[lower]
  const to = colors[lower + 1]

  return [
    Math.round(from[0] + (to[0] - from[0]) * frac),
    Math.round(from[1] + (to[1] - from[1]) * frac),
    Math.round(from[2] + (to[2] - from[2]) * frac),
  ]
}

/**
 * A scalar field painted over the base map.
 *
 * Built as ImageData at the field's own resolution and blitted through an
 * offscreen canvas, so a 250x250 time slice scales up to the 500 px canvas
 * without the caller resampling anything. A null cell is not zero: it stays
 * fully transparent, so whatever the map already drew shows through.
 */
function drawField(
  ctx: CanvasRenderingContext2D,
  command: Extract<OverlayCommand, { kind: 'field' }>,
  canvasSize: number,
): void {
  const { values, rows, cols, ramp } = command
  if (values.length !== rows * cols) return
  // Fail closed rather than inventing a colour: a ramp with no stops is a
  // caller bug, and painting it black would read as a measurement.
  if (ramp.colors.length === 0) return

  const domain: [number, number] = [ramp.min, ramp.max]
  const image = new ImageData(cols, rows)

  for (let i = 0; i < values.length; i++) {
    const offset = i * 4
    const raw = values[i]
    // null is the contract's absence marker; NaN can still arrive inside a
    // number, and normaliseToDomain rejects it for the same reason.
    const t = raw === null ? null : normaliseToDomain(raw, domain)
    if (t === null) {
      image.data[offset + 3] = 0
      continue
    }
    const [r, g, b] = sampleRamp(ramp.colors, t)
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

  ctx.globalAlpha = command.style?.opacity ?? 1
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(scratch, 0, 0, canvasSize, canvasSize)
}
