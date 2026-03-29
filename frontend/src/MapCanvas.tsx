import React, {
  useRef,
  useEffect,
  useCallback,
  useState,
  forwardRef,
  useImperativeHandle,
} from 'react'
import type { Waypoint } from './api'
import {
  buildEqualizationLut,
  computeHillshade,
  riskToHex,
  shadeRegolith,
  thermalToRgb,
  tintRgb,
  elevationToRegolith,
} from './colormap'

const CANVAS_SIZE = 500
const DOWNSAMPLE = 2

export type ClickMode = 'start' | 'goal' | 'idle'
export type MapViewMode = 'surface' | 'thermal'

interface Props {
  elevationGrid: (number | null)[][] | null
  thermalGrid: (number | null)[][] | null
  traversableGrid: (number | null)[][] | null
  waypoints: Waypoint[] | null
  start: [number, number] | null
  goal: [number, number] | null
  clickMode: ClickMode
  viewMode: MapViewMode
  resolutionM: number
  onCellClick: (row: number, col: number) => void
  onAnimationStepChange?: (step: number | null) => void
}

export interface MapCanvasHandle {
  startAnimation: () => void
}

const MapCanvas = forwardRef<MapCanvasHandle, Props>(function MapCanvas(
  {
    elevationGrid,
    thermalGrid,
    traversableGrid,
    waypoints,
    start,
    goal,
    clickMode,
    viewMode,
    resolutionM,
    onCellClick,
    onAnimationStepChange,
  },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const baseImageRef = useRef<ImageData | null>(null)
  const animationTimerRef = useRef<number | null>(null)
  const [animStep, setAnimStep] = useState<number | null>(null)

  const stopAnimation = useCallback(() => {
    if (animationTimerRef.current !== null) {
      window.clearTimeout(animationTimerRef.current)
      animationTimerRef.current = null
    }
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) {
      return
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) {
      return
    }

    const imageData = buildBaseImage({
      ctx,
      viewMode,
      elevationGrid,
      thermalGrid,
      traversableGrid,
      resolutionM,
    })

    baseImageRef.current = imageData
    redraw(ctx, imageData, waypoints, start, goal, animStep)
  }, [elevationGrid, resolutionM, thermalGrid, traversableGrid, viewMode])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) {
      return
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) {
      return
    }

    redraw(ctx, baseImageRef.current, waypoints, start, goal, animStep)
  }, [animStep, goal, start, waypoints])

  useEffect(() => {
    if (!waypoints || waypoints.length === 0) {
      setAnimStep(null)
      stopAnimation()
    }
  }, [stopAnimation, waypoints])

  useEffect(() => {
    onAnimationStepChange?.(animStep)
  }, [animStep, onAnimationStepChange])

  const startAnimation = useCallback(() => {
    if (!waypoints || waypoints.length === 0) {
      return
    }

    stopAnimation()
    let nextStep = 0
    setAnimStep(0)

    const tick = () => {
      nextStep += 1
      if (nextStep >= waypoints.length) {
        setAnimStep(waypoints.length - 1)
        animationTimerRef.current = null
        return
      }

      setAnimStep(nextStep)
      animationTimerRef.current = window.setTimeout(tick, 33)
    }

    animationTimerRef.current = window.setTimeout(tick, 66)
  }, [stopAnimation, waypoints])

  useImperativeHandle(ref, () => ({ startAnimation }), [startAnimation])

  useEffect(() => {
    return () => stopAnimation()
  }, [stopAnimation])

  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLCanvasElement>) => {
      if (clickMode === 'idle') {
        return
      }

      const canvas = canvasRef.current
      if (!canvas) {
        return
      }

      const rect = canvas.getBoundingClientRect()
      const scaleX = CANVAS_SIZE / rect.width
      const scaleY = CANVAS_SIZE / rect.height
      const col = Math.floor((event.clientX - rect.left) * scaleX)
      const row = Math.floor((event.clientY - rect.top) * scaleY)

      if (col < 0 || col >= CANVAS_SIZE || row < 0 || row >= CANVAS_SIZE) {
        return
      }

      onCellClick(row, col)
    },
    [clickMode, onCellClick],
  )

  const cursorLabel =
    clickMode === 'start' ? 'Click to set START' :
    clickMode === 'goal' ? 'Click to set GOAL' :
    ''

  const loading = viewMode === 'surface'
    ? !elevationGrid || !traversableGrid
    : !thermalGrid || !traversableGrid

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <canvas
        ref={canvasRef}
        width={CANVAS_SIZE}
        height={CANVAS_SIZE}
        onClick={handleClick}
        style={{
          width: '100%',
          height: '100%',
          border: '1px solid rgba(160, 160, 255, 0.2)',
          background: '#030408',
          boxShadow: '0 24px 64px rgba(0, 0, 0, 0.45)',
          cursor: clickMode === 'idle' ? 'default' : 'crosshair',
          imageRendering: viewMode === 'surface' ? 'auto' : 'pixelated',
        }}
      />

      {cursorLabel && (
        <div
          style={{
            position: 'absolute',
            top: 12,
            left: 12,
            padding: '5px 9px',
            background: 'rgba(5, 5, 10, 0.72)',
            border: `1px solid ${clickMode === 'start' ? '#00e676' : '#ff1744'}`,
            color: clickMode === 'start' ? '#00e676' : '#ff1744',
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 10,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            pointerEvents: 'none',
          }}
        >
          {cursorLabel}
        </div>
      )}

      {loading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(3, 4, 8, 0.86)',
            color: '#c7c5d3',
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 12,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
          }}
        >
          Loading lunar grid...
        </div>
      )}
    </div>
  )
})

export default MapCanvas
export { DOWNSAMPLE }

function redraw(
  ctx: CanvasRenderingContext2D,
  baseImage: ImageData | null,
  waypoints: Waypoint[] | null,
  start: [number, number] | null,
  goal: [number, number] | null,
  currentStep: number | null,
) {
  if (baseImage) {
    ctx.putImageData(baseImage, 0, 0)
  } else {
    ctx.fillStyle = '#030408'
    ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE)
  }

  if (waypoints && waypoints.length > 1) {
    const drawUpTo = currentStep ?? waypoints.length - 1

    ctx.save()
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.shadowColor = 'rgba(0, 0, 0, 0.55)'
    ctx.shadowBlur = 12

    for (let index = 1; index <= drawUpTo; index += 1) {
      const previous = waypoints[index - 1]
      const current = waypoints[index]
      ctx.strokeStyle = riskToHex(current.risk_level)
      ctx.lineWidth = 2.6
      ctx.beginPath()
      ctx.moveTo(previous.col, previous.row)
      ctx.lineTo(current.col, current.row)
      ctx.stroke()
    }

    ctx.restore()

    if (currentStep !== null && currentStep < waypoints.length) {
      const rover = waypoints[currentStep]
      ctx.save()
      ctx.fillStyle = '#f5f7ff'
      ctx.shadowColor = 'rgba(255, 255, 255, 0.55)'
      ctx.shadowBlur = 14
      ctx.beginPath()
      ctx.arc(rover.col, rover.row, 4.4, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0
      ctx.strokeStyle = riskToHex(rover.risk_level)
      ctx.lineWidth = 1.4
      ctx.stroke()
      ctx.restore()
    }
  }

  drawMarker(ctx, start, '#00e676', 'S')
  drawMarker(ctx, goal, '#ff1744', 'G')
}

function buildBaseImage({
  ctx,
  viewMode,
  elevationGrid,
  thermalGrid,
  traversableGrid,
  resolutionM,
}: {
  ctx: CanvasRenderingContext2D
  viewMode: MapViewMode
  elevationGrid: (number | null)[][] | null
  thermalGrid: (number | null)[][] | null
  traversableGrid: (number | null)[][] | null
  resolutionM: number
}): ImageData | null {
  if (!traversableGrid || traversableGrid.length === 0 || traversableGrid[0].length === 0) {
    return null
  }

  if (viewMode === 'surface') {
    return buildSurfaceImage(ctx, elevationGrid, traversableGrid, resolutionM)
  }

  return buildThermalImage(ctx, thermalGrid, traversableGrid)
}

function buildThermalImage(
  ctx: CanvasRenderingContext2D,
  thermalGrid: (number | null)[][] | null,
  traversableGrid: (number | null)[][],
): ImageData | null {
  if (!thermalGrid || thermalGrid.length === 0 || thermalGrid[0].length === 0) {
    return null
  }

  const imageData = ctx.createImageData(CANVAS_SIZE, CANVAS_SIZE)
  const range = getFiniteRange(thermalGrid)
  const lut = buildEqualizationLut(thermalGrid, range.min, range.max)
  const rows = thermalGrid.length
  const cols = thermalGrid[0].length
  const cellPx = CANVAS_SIZE / rows

  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const value = thermalGrid[row][col]
      const traversable = traversableGrid[row]?.[col]

      let color = thermalToRgb(value, range.min, range.max, lut)
      if (traversable !== 1) {
        color = tintRgb(color, [96, 14, 10], 0.24)
      }

      paintCell(imageData, row, col, cellPx, color)
    }
  }

  return imageData
}

function buildSurfaceImage(
  ctx: CanvasRenderingContext2D,
  elevationGrid: (number | null)[][] | null,
  traversableGrid: (number | null)[][],
  resolutionM: number,
): ImageData | null {
  if (!elevationGrid || elevationGrid.length === 0 || elevationGrid[0].length === 0) {
    return null
  }

  const imageData = ctx.createImageData(CANVAS_SIZE, CANVAS_SIZE)
  const range = getFiniteRange(elevationGrid)
  const lut = buildEqualizationLut(elevationGrid, range.min, range.max)
  const rows = elevationGrid.length
  const cols = elevationGrid[0].length
  const cellPx = CANVAS_SIZE / rows
  const effectiveResolution = resolutionM * DOWNSAMPLE

  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const value = elevationGrid[row][col]
      const traversable = traversableGrid[row]?.[col]

      let color: [number, number, number]

      if (typeof value === 'number' && Number.isFinite(value)) {
        const base = elevationToRegolith(value, lut, range.min, range.max)
        const shade = computeHillshade(elevationGrid, row, col, effectiveResolution)
        color = shadeRegolith(base, shade)
      } else {
        color = [8, 8, 11]
      }

      if (traversable !== 1) {
        color = tintRgb(color, [18, 18, 24], 0.22)
      }

      paintCell(imageData, row, col, cellPx, color)
    }
  }

  return imageData
}

function paintCell(
  imageData: ImageData,
  row: number,
  col: number,
  cellPx: number,
  color: [number, number, number],
) {
  const baseRow = Math.round(row * cellPx)
  const baseCol = Math.round(col * cellPx)

  for (let rowOffset = 0; rowOffset < cellPx; rowOffset += 1) {
    for (let colOffset = 0; colOffset < cellPx; colOffset += 1) {
      const canvasRow = baseRow + rowOffset
      const canvasCol = baseCol + colOffset

      if (canvasRow >= CANVAS_SIZE || canvasCol >= CANVAS_SIZE) {
        continue
      }

      const pixelIndex = (canvasRow * CANVAS_SIZE + canvasCol) * 4
      imageData.data[pixelIndex] = color[0]
      imageData.data[pixelIndex + 1] = color[1]
      imageData.data[pixelIndex + 2] = color[2]
      imageData.data[pixelIndex + 3] = 255
    }
  }
}

function getFiniteRange(grid: (number | null)[][]): { min: number; max: number } {
  let min = Number.POSITIVE_INFINITY
  let max = Number.NEGATIVE_INFINITY

  for (const row of grid) {
    for (const value of row) {
      if (typeof value === 'number' && Number.isFinite(value)) {
        min = Math.min(min, value)
        max = Math.max(max, value)
      }
    }
  }

  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
    return { min: 0, max: 1 }
  }

  return { min, max }
}

function drawMarker(
  ctx: CanvasRenderingContext2D,
  position: [number, number] | null,
  color: string,
  label: string,
) {
  if (!position) {
    return
  }

  const [row, col] = position

  ctx.save()
  ctx.shadowColor = color
  ctx.shadowBlur = 16

  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(col, row, 7, 0, Math.PI * 2)
  ctx.fill()

  ctx.shadowBlur = 0
  ctx.fillStyle = '#050507'
  ctx.font = 'bold 8px IBM Plex Mono, monospace'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(label, col, row + 0.5)
  ctx.restore()
}
