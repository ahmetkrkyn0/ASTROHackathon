import React, {
  useRef,
  useEffect,
  useCallback,
  useState,
  forwardRef,
  useImperativeHandle,
} from 'react'
import type { Waypoint } from './api'
import { slopeToRgb, blockedOverlay, riskToHex } from './colormap'

// ── Constants ──────────────────────────────────────────────────────────────────
// Internal canvas resolution matches the 500×500 grid exactly.
// The canvas element is scaled down via CSS to fit the viewport.
const CANVAS_SIZE = 500
const DOWNSAMPLE = 2   // must match the downsample used when fetching layers

export type ClickMode = 'start' | 'goal' | 'idle'

// ── Types ──────────────────────────────────────────────────────────────────────

interface Props {
  slopeGrid: (number | null)[][] | null
  traversableGrid: (number | null)[][] | null
  waypoints: Waypoint[] | null
  start: [number, number] | null   // [row, col] in 500×500 space
  goal: [number, number] | null
  clickMode: ClickMode
  onCellClick: (row: number, col: number) => void
}

export interface MapCanvasHandle {
  startAnimation: () => void
}

// ── Component ──────────────────────────────────────────────────────────────────

const MapCanvas = forwardRef<MapCanvasHandle, Props>(function MapCanvas(
  { slopeGrid, traversableGrid, waypoints, start, goal, clickMode, onCellClick },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const baseImageRef = useRef<ImageData | null>(null)
  const animFrameRef = useRef<number>(0)
  const [animStep, setAnimStep] = useState<number | null>(null)

  // ── Build base ImageData from grid layers ──────────────────────────────────

  useEffect(() => {
    if (!slopeGrid || !traversableGrid) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!

    const arrH = slopeGrid.length       // 250 when downsample=2
    const arrW = slopeGrid[0]?.length ?? 0
    const cellPx = CANVAS_SIZE / arrH   // pixels per array cell = 2

    const imageData = ctx.createImageData(CANVAS_SIZE, CANVAS_SIZE)

    for (let ar = 0; ar < arrH; ar++) {
      for (let ac = 0; ac < arrW; ac++) {
        const slope = slopeGrid[ar][ac]
        const traversable = traversableGrid[ar][ac]

        let color = slopeToRgb(slope)
        if (traversable === 0 || traversable === null) {
          color = blockedOverlay(color)
        }

        // Fill cellPx × cellPx canvas pixels for this array cell
        const baseRow = Math.round(ar * cellPx)
        const baseCol = Math.round(ac * cellPx)
        for (let dr = 0; dr < cellPx; dr++) {
          for (let dc = 0; dc < cellPx; dc++) {
            const cr = baseRow + dr
            const cc = baseCol + dc
            if (cr >= CANVAS_SIZE || cc >= CANVAS_SIZE) continue
            const idx = (cr * CANVAS_SIZE + cc) * 4
            imageData.data[idx]     = color[0]
            imageData.data[idx + 1] = color[1]
            imageData.data[idx + 2] = color[2]
            imageData.data[idx + 3] = 255
          }
        }
      }
    }

    baseImageRef.current = imageData
    redraw(ctx, null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slopeGrid, traversableGrid])

  // ── Redraw whenever overlay state changes ──────────────────────────────────

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !baseImageRef.current) return
    const ctx = canvas.getContext('2d')!
    redraw(ctx, animStep)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waypoints, start, goal, animStep])

  // ── Rover animation ────────────────────────────────────────────────────────

  const startAnimation = useCallback(() => {
    if (!waypoints || waypoints.length === 0) return
    cancelAnimationFrame(animFrameRef.current)
    let step = 0

    const tick = () => {
      step++
      if (step >= waypoints.length) {
        setAnimStep(waypoints.length - 1)
        return
      }
      setAnimStep(step)
      // ~30fps regardless of monitor refresh rate
      animFrameRef.current = requestAnimationFrame(() =>
        setTimeout(tick, 33),
      ) as unknown as number
    }

    setAnimStep(0)
    animFrameRef.current = requestAnimationFrame(() =>
      setTimeout(tick, 33),
    ) as unknown as number
  }, [waypoints])

  useImperativeHandle(ref, () => ({ startAnimation }), [startAnimation])

  useEffect(() => {
    return () => cancelAnimationFrame(animFrameRef.current)
  }, [])

  // ── Core render function ───────────────────────────────────────────────────

  const redraw = (ctx: CanvasRenderingContext2D, currentStep: number | null) => {
    if (baseImageRef.current) {
      ctx.putImageData(baseImageRef.current, 0, 0)
    } else {
      ctx.fillStyle = '#080810'
      ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE)
    }

    if (waypoints && waypoints.length > 1) {
      const drawUpTo = currentStep ?? waypoints.length - 1

      // Path segments — color by risk level
      for (let i = 1; i <= drawUpTo; i++) {
        const prev = waypoints[i - 1]
        const curr = waypoints[i]
        ctx.strokeStyle = riskToHex(curr.risk_level)
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(prev.col, prev.row)   // canvas: x = col, y = row
        ctx.lineTo(curr.col, curr.row)
        ctx.stroke()
      }

      // Rover dot at current animation step
      if (currentStep !== null && currentStep < waypoints.length) {
        const roverWp = waypoints[currentStep]
        ctx.fillStyle = '#ffffff'
        ctx.beginPath()
        ctx.arc(roverWp.col, roverWp.row, 4, 0, Math.PI * 2)
        ctx.fill()
        ctx.strokeStyle = riskToHex(roverWp.risk_level)
        ctx.lineWidth = 1.5
        ctx.stroke()
      }
    }

    drawMarker(ctx, start, '#00e676', 'S')
    drawMarker(ctx, goal,  '#ff1744', 'G')
  }

  // ── Click handling ─────────────────────────────────────────────────────────

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (clickMode === 'idle') return
      const canvas = canvasRef.current!
      const rect = canvas.getBoundingClientRect()
      const scaleX = CANVAS_SIZE / rect.width
      const scaleY = CANVAS_SIZE / rect.height
      const col = Math.floor((e.clientX - rect.left) * scaleX)
      const row = Math.floor((e.clientY - rect.top)  * scaleY)
      if (col < 0 || col >= CANVAS_SIZE || row < 0 || row >= CANVAS_SIZE) return
      onCellClick(row, col)
    },
    [clickMode, onCellClick],
  )

  // ── Cursor label overlay (canvas tooltip) ─────────────────────────────────

  const cursorLabel =
    clickMode === 'start' ? 'Click to set START' :
    clickMode === 'goal'  ? 'Click to set GOAL'  : ''

  return (
    <div style={{ position: 'relative', display: 'inline-block', width: '100%' }}>
      <canvas
        ref={canvasRef}
        width={CANVAS_SIZE}
        height={CANVAS_SIZE}
        onClick={handleClick}
        style={{
          width: '100%',
          maxWidth: '600px',
          display: 'block',
          cursor: clickMode !== 'idle' ? 'crosshair' : 'default',
          border: '1px solid #2a2a5a',
          imageRendering: 'pixelated',
        }}
      />
      {cursorLabel && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            left: 8,
            background: 'rgba(0,0,0,0.7)',
            color: clickMode === 'start' ? '#00e676' : '#ff1744',
            padding: '3px 8px',
            fontSize: 11,
            fontFamily: 'monospace',
            pointerEvents: 'none',
            border: `1px solid ${clickMode === 'start' ? '#00e676' : '#ff1744'}`,
          }}
        >
          {cursorLabel}
        </div>
      )}
      {!slopeGrid && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#5a5a8a',
            fontSize: 13,
            fontFamily: 'monospace',
            background: '#080810',
            maxWidth: 600,
          }}
        >
          Loading lunar surface data...
        </div>
      )}
    </div>
  )
})

export default MapCanvas

// ── Helpers ────────────────────────────────────────────────────────────────────

function drawMarker(
  ctx: CanvasRenderingContext2D,
  pos: [number, number] | null,
  color: string,
  label: string,
) {
  if (!pos) return
  const [row, col] = pos

  ctx.save()
  ctx.shadowColor = color
  ctx.shadowBlur = 8

  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(col, row, 6, 0, Math.PI * 2)
  ctx.fill()

  ctx.shadowBlur = 0
  ctx.fillStyle = '#000'
  ctx.font = 'bold 8px monospace'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(label, col, row)

  ctx.restore()
}

export { DOWNSAMPLE }
