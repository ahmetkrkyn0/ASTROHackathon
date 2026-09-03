import { cellSizePx, cellToCanvasXY, type CanvasGeometry } from '../mission/geo'
import type { FieldCommand, FieldRamp, OverlayCommand, OverlayStyle } from './types'

/**
 * Draw feature overlay commands onto the 2-D map canvas.
 *
 * The whole point of this file is that MapCanvas never grows feature-specific
 * drawing code again: a feature publishes commands, this translates them, and
 * the renderer stays generic. An empty list returns before touching the
 * context, so an unused overlay layer costs nothing and changes nothing.
 */
export function drawOverlayCommands(
  ctx: CanvasRenderingContext2D,
  commands: readonly OverlayCommand[],
  geometry: CanvasGeometry,
) {
  if (commands.length === 0) {
    return
  }

  for (const command of commands) {
    ctx.save()
    switch (command.kind) {
      case 'polyline':
        drawPolyline(ctx, command.points, command.style, geometry)
        break
      case 'ribbon':
        drawRibbon(ctx, command.points, command.halfWidthCells, command.style, geometry)
        break
      case 'points':
        drawPoints(ctx, command.points, command.style, geometry)
        break
      case 'field':
        drawField(ctx, command, geometry)
        break
    }
    ctx.restore()
  }
}

function applyStroke(ctx: CanvasRenderingContext2D, style: OverlayStyle) {
  ctx.globalAlpha = style.opacity ?? 1
  ctx.strokeStyle = style.color
  ctx.lineWidth = style.widthPx ?? 2
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.setLineDash(style.dash ?? [])
}

function drawPolyline(
  ctx: CanvasRenderingContext2D,
  points: { row: number; col: number }[],
  style: OverlayStyle,
  geometry: CanvasGeometry,
) {
  if (points.length < 2) {
    return
  }

  applyStroke(ctx, style)
  ctx.beginPath()
  points.forEach((cell, index) => {
    const [x, y] = cellToCanvasXY(cell, geometry)
    if (index === 0) {
      ctx.moveTo(x, y)
    } else {
      ctx.lineTo(x, y)
    }
  })
  ctx.stroke()
}

/**
 * A band around a centreline, offset along each vertex's segment normal.
 *
 * Widths are given in cells and converted here, so a corridor keeps its ground
 * width whatever the canvas is scaled to.
 */
function drawRibbon(
  ctx: CanvasRenderingContext2D,
  points: { row: number; col: number }[],
  halfWidthCells: number | number[],
  style: OverlayStyle,
  geometry: CanvasGeometry,
) {
  if (points.length < 2) {
    return
  }

  const { widthPx: cellWidthPx, heightPx: cellHeightPx } = cellSizePx(geometry)
  const pxPerCell = (cellWidthPx + cellHeightPx) / 2
  const xy = points.map((cell) => cellToCanvasXY(cell, geometry))
  const halfWidthAt = (index: number) =>
    (Array.isArray(halfWidthCells)
      ? (halfWidthCells[index] ?? halfWidthCells[halfWidthCells.length - 1] ?? 0)
      : halfWidthCells) * pxPerCell

  const left: Array<[number, number]> = []
  const right: Array<[number, number]> = []

  for (let index = 0; index < xy.length; index += 1) {
    const previous = xy[Math.max(index - 1, 0)]
    const next = xy[Math.min(index + 1, xy.length - 1)]
    const dx = next[0] - previous[0]
    const dy = next[1] - previous[1]
    const length = Math.hypot(dx, dy) || 1
    // Unit normal of the local tangent.
    const nx = -dy / length
    const ny = dx / length
    const half = halfWidthAt(index)
    const [x, y] = xy[index]
    left.push([x + nx * half, y + ny * half])
    right.push([x - nx * half, y - ny * half])
  }

  ctx.globalAlpha = style.opacity ?? 0.28
  ctx.fillStyle = style.color
  ctx.beginPath()
  left.forEach(([x, y], index) => (index === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)))
  for (let index = right.length - 1; index >= 0; index -= 1) {
    ctx.lineTo(right[index][0], right[index][1])
  }
  ctx.closePath()
  ctx.fill()

  if (style.widthPx) {
    applyStroke(ctx, style)
    ctx.stroke()
  }
}

function drawPoints(
  ctx: CanvasRenderingContext2D,
  points: { row: number; col: number }[],
  style: OverlayStyle,
  geometry: CanvasGeometry,
) {
  ctx.globalAlpha = style.opacity ?? 1
  ctx.fillStyle = style.color
  const radius = style.radiusPx ?? 3.5

  for (const cell of points) {
    const [x, y] = cellToCanvasXY(cell, geometry)
    ctx.beginPath()
    ctx.arc(x, y, radius, 0, Math.PI * 2)
    ctx.fill()
  }
}

/**
 * Paint a scalar grid.
 *
 * Composited through an offscreen canvas rather than one fillRect per cell: a
 * 500x500 field is 250 000 rectangles, and the alpha has to apply to the layer
 * as a whole rather than accumulate where cells touch.
 */
function drawField(
  ctx: CanvasRenderingContext2D,
  command: FieldCommand,
  geometry: CanvasGeometry,
) {
  const { rows, cols, values, ramp } = command
  if (rows <= 0 || cols <= 0 || values.length < rows * cols) {
    return
  }

  const layer = document.createElement('canvas')
  layer.width = cols
  layer.height = rows
  const layerCtx = layer.getContext('2d')
  if (!layerCtx) {
    return
  }

  const image = layerCtx.createImageData(cols, rows)
  for (let index = 0; index < rows * cols; index += 1) {
    const value = values[index]
    // null is "impassable" or "no data" depending on the layer, never zero, so
    // it is left transparent rather than painted as the ramp's low end.
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      continue
    }
    const [r, g, b] = sampleRamp(ramp, value)
    const pixel = index * 4
    image.data[pixel] = r
    image.data[pixel + 1] = g
    image.data[pixel + 2] = b
    image.data[pixel + 3] = 255
  }
  layerCtx.putImageData(image, 0, 0)

  ctx.globalAlpha = command.style?.opacity ?? 0.65
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(layer, 0, 0, geometry.canvasSize, geometry.canvasSize)
}

function sampleRamp(ramp: FieldRamp, value: number): [number, number, number] {
  const { min, max, colors } = ramp
  if (colors.length === 0) {
    return [0, 0, 0]
  }
  if (colors.length === 1 || max <= min) {
    return colors[0]
  }

  const t = Math.min(Math.max((value - min) / (max - min), 0), 1)
  const scaled = t * (colors.length - 1)
  const lower = Math.floor(scaled)
  const upper = Math.min(lower + 1, colors.length - 1)
  const mix = scaled - lower

  return [
    Math.round(colors[lower][0] + (colors[upper][0] - colors[lower][0]) * mix),
    Math.round(colors[lower][1] + (colors[upper][1] - colors[lower][1]) * mix),
    Math.round(colors[lower][2] + (colors[upper][2] - colors[lower][2]) * mix),
  ]
}
