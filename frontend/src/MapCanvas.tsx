import React, {
  useRef,
  useEffect,
  useCallback,
  useState,
} from 'react'
import type { Waypoint } from './api'
import { drawOverlays } from './overlay/draw2d'
import type { OverlayCommand } from './overlay/types'
import { useOverlayCommands } from './overlay/useOverlays'
import {
  aspectToRgb,
  computeHillshade,
  grayReverseToRgb,
  lunarRegolithToRgb,
  magmaToRgb,
  riskToHex,
  riskToDash,
  rdYlGnToRgb,
  shadeRegolith,
  thermalToRgb,
  viridisToRgb,
  START_MINT,
  GOAL_CORAL,
  ROUTE_CYAN,
} from './colormap'

/**
 * How long the planned route takes to sweep onto the map, in milliseconds.
 * Fixed for the whole route rather than per waypoint, so route length does
 * not change how long the answer takes to appear.
 */
const ROUTE_REVEAL_MS = 1100

const CANVAS_SIZE = 500
// Full resolution. fetchLayer reads the binary float32 layer, which carries
// the whole 500x500 grid in 1.00 MB and is exempt from the MAX_LAYER_CELLS
// ceiling that caps the JSON representation at a 256x256 preview. Rendering
// is resolution-agnostic anyway -- cellPx is CANVAS_SIZE / rows and the
// hillshade reads effectiveResolution -- and the click mapping is in canvas
// pixels, which equal full-resolution grid indices at CANVAS_SIZE 500.
const DOWNSAMPLE = 1

export type ClickMode = 'start' | 'goal' | 'idle'
export type MapViewMode =
  | 'surface'
  | 'thermal'
  | 'cost'
  | 'shadow'
  | 'traversability'
  | 'slope'
  | 'aspect'

interface Props {
  elevationGrid: (number | null)[][] | null
  slopeGrid: (number | null)[][] | null
  aspectGrid: (number | null)[][] | null
  shadowGrid: (number | null)[][] | null
  thermalGrid: (number | null)[][] | null
  costGrid: (number | null)[][] | null
  traversableGrid: (number | null)[][] | null
  waypoints: Waypoint[] | null
  start: [number, number] | null
  goal: [number, number] | null
  clickMode: ClickMode
  viewMode: MapViewMode
  resolutionM: number
  onCellClick: (row: number, col: number) => void
  /**
   * Playback cursor, owned by App's single mission clock -- see
   * mission/playbackClock.ts. The map runs no timer of its own. It used to:
   * it stepped a waypoint every 33 ms while the transport bar stepped one
   * every 50 ms and the 3D view compressed the whole traverse into a fixed
   * 10-45 second window, so the same route finished at three different
   * times and none of them was the rover's speed.
   */
  playbackStep: number | null
  onHoverCellChange?: (cell: [number, number] | null) => void
}

function MapCanvas({
  elevationGrid,
  slopeGrid,
  aspectGrid,
  shadowGrid,
  thermalGrid,
  costGrid,
  traversableGrid,
  waypoints,
  start,
  goal,
  clickMode,
  viewMode,
  resolutionM,
  onCellClick,
  playbackStep,
  onHoverCellChange,
}: Props) {
  // The marks features registered, read here rather than passed down: App
  // renders OverlayProvider and so cannot consume it, and the hook falls back
  // to one shared empty list outside a provider, which keeps this canvas
  // usable on its own.
  const overlays = useOverlayCommands()

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const baseImageRef = useRef<ImageData | null>(null)
  const [hoverCell, setHoverCell] = useState<[number, number] | null>(null)

  // The loaded grid's own row count, not CANVAS_SIZE. Every layer is
  // fetched at the same downsample, so elevation's shape is the grid's
  // shape. Zero before the first fetch lands, and drawOverlays draws
  // nothing at zero -- there is no base map to be out of register with yet.
  const gridRows = elevationGrid?.length ?? 0
  const gridCols = elevationGrid?.[0]?.length ?? 0

  // How much of the planned line has been drawn in.
  //
  // This is a ROUTE REVEAL, not the drive -- two different things that used
  // to share one counter, which is how the map ended up either crawling for
  // twenty minutes before showing the route it had found, or racing the
  // rover marker along at a hundred times its own speed. The line is the
  // planner's answer and wants to be legible immediately; the marker is the
  // rover and belongs on the mission clock. So: the line sweeps in over a
  // fixed budget no matter how long the route is, and then stays.
  const [revealStep, setRevealStep] = useState(0)
  useEffect(() => {
    if (!waypoints || waypoints.length === 0) {
      setRevealStep(0)
      return
    }
    const total = waypoints.length - 1
    // Time-based rather than one timeout per waypoint, so a 40-node route
    // and a 400-node one take the same moment to appear.
    let frame = 0
    let startedAt: number | null = null
    const tick = (timestamp: number) => {
      if (startedAt === null) startedAt = timestamp
      const progress = Math.min(1, (timestamp - startedAt) / ROUTE_REVEAL_MS)
      setRevealStep(Math.round(progress * total))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [waypoints])

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
      slopeGrid,
      aspectGrid,
      shadowGrid,
      thermalGrid,
      costGrid,
      traversableGrid,
      resolutionM,
    })

    baseImageRef.current = imageData
    redraw(ctx, imageData, waypoints, start, goal, revealStep, playbackStep, hoverCell, gridRows, overlays)
    // Overlay degerleri (waypoints/start/goal/animStep/hoverCell/overlays)
    // bilerek bagimlilikta degil: onlari bir sonraki efekt yeniden ciziyor.
    // Buraya eklemek, her hover'da -- ve her overlay degisikliginde, yani
    // zaman kaydiricisinin her adiminda -- taban goruntuyu bastan uretmek
    // demek olurdu. Bu efekt kostugunda closure zaten o render'in guncel
    // degerlerini tasir; gridRows da elevationGrid'den turedigi icin
    // asagidaki listede zaten temsil ediliyor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aspectGrid, costGrid, elevationGrid, resolutionM, shadowGrid, slopeGrid, thermalGrid, traversableGrid, viewMode])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) {
      return
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) {
      return
    }

    redraw(ctx, baseImageRef.current, waypoints, start, goal, revealStep, playbackStep, hoverCell, gridRows, overlays)
  }, [playbackStep, goal, gridRows, hoverCell, overlays, revealStep, start, waypoints])

  useEffect(() => {
    onHoverCellChange?.(hoverCell)
  }, [hoverCell, onHoverCellChange])

  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current
      if (!canvas) {
        return
      }

      const cell = getCanvasCell(canvas, event.clientX, event.clientY)
      if (!cell || clickMode === 'idle') {
        return
      }

      onCellClick(cell[0], cell[1])
    },
    [clickMode, onCellClick],
  )

  const handleMouseMove = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) {
      return
    }

    const nextCell = getCanvasCell(canvas, event.clientX, event.clientY)
    setHoverCell((current) => {
      if (!nextCell) {
        return null
      }
      if (current && current[0] === nextCell[0] && current[1] === nextCell[1]) {
        return current
      }
      return nextCell
    })
  }, [])

  const handleMouseLeave = useCallback(() => {
    setHoverCell(null)
  }, [])

  /**
   * Placing an endpoint from the keyboard.
   *
   * Until this existed the application's primary task -- put a Start and a
   * Goal on the terrain -- could only be done with a mouse: the canvas had a
   * click handler and nothing else, so keyboard and screen-reader users could
   * not use LunaPath at all (WCAG 2.1.1, Level A).
   *
   * The cursor is `hoverCell`, deliberately the same state the pointer writes.
   * That state already draws the crosshair on the canvas and already feeds the
   * LAT/LON/ALT readout through onHoverCellChange, so driving it from the
   * keyboard makes both follow the keys with no second code path to keep in
   * register -- and no second definition of where "here" is.
   *
   * Shift multiplies the step because a 500-cell grid is 500 keypresses wide
   * at one cell per press, which is a working alternative in name only.
   */
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLCanvasElement>) => {
      if (gridRows === 0 || gridCols === 0) {
        return
      }

      const step = event.shiftKey ? 10 : 1
      const delta: Record<string, [number, number]> = {
        ArrowUp: [-step, 0],
        ArrowDown: [step, 0],
        ArrowLeft: [0, -step],
        ArrowRight: [0, step],
      }
      const move = delta[event.key]

      if (move) {
        // The arrows scroll the page by default, which would drag the map out
        // of view on the first keypress.
        event.preventDefault()
        setHoverCell((current) => {
          const [row, col] = current ?? [Math.floor(gridRows / 2), Math.floor(gridCols / 2)]
          return [
            Math.min(gridRows - 1, Math.max(0, row + move[0])),
            Math.min(gridCols - 1, Math.max(0, col + move[1])),
          ]
        })
        return
      }

      if (event.key === 'Enter' || event.key === ' ') {
        // Space scrolls too, and on a focused element it is the conventional
        // partner to Enter for "activate".
        event.preventDefault()
        if (clickMode === 'idle' || !hoverCell) {
          return
        }
        onCellClick(hoverCell[0], hoverCell[1])
      }
    },
    [clickMode, gridCols, gridRows, hoverCell, onCellClick],
  )

  /**
   * Focus has to land somewhere visible.
   *
   * Tabbing to a map whose cursor is null would show nothing at all and read
   * as a dead control, so focus seeds the cursor at the centre of the grid --
   * but only when the pointer has not already put it somewhere.
   */
  const handleFocus = useCallback(() => {
    if (gridRows === 0 || gridCols === 0) {
      return
    }
    setHoverCell((current) => current ?? [Math.floor(gridRows / 2), Math.floor(gridCols / 2)])
  }, [gridCols, gridRows])

  const loading =
    viewMode === 'surface' ? !elevationGrid :
    viewMode === 'thermal' ? !thermalGrid :
    viewMode === 'cost' ? !costGrid :
    viewMode === 'shadow' ? !shadowGrid :
    viewMode === 'traversability' ? !traversableGrid :
    viewMode === 'slope' ? !slopeGrid :
    !aspectGrid

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
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onKeyDown={handleKeyDown}
        onFocus={handleFocus}
        /* role="application" tells a screen reader to stop intercepting the
           arrow keys and hand them to this element, which is what makes the
           cursor movable at all. It is the right role precisely because the
           arrows here mean "move the cursor over the terrain" and not "move
           to the next item". */
        tabIndex={0}
        role="application"
        aria-label={
          clickMode === 'idle'
            ? 'Terrain map. Arrow keys move the cursor, hold Shift to move ten cells at a time.'
            : `Terrain map. Arrow keys move the cursor, hold Shift to move ten cells at a time. Press Enter to place ${clickMode === 'start' ? 'Start' : 'Goal'} at the cursor.`
        }
        /* Deliberately NOT `map-canvas`: App.css already owns that name with an
           `aspect-ratio: 1/1` and a `calc(100vh - 130px)` cap, and borrowing it
           for a cursor squared the terrain and took ~500px off its width. */
        className={
          clickMode === 'start'
            ? 'lp-map-pick-start'
            : clickMode === 'goal'
              ? 'lp-map-pick-goal'
              : undefined
        }
        style={{
          width: '100%',
          height: '100%',
          border: '1px solid rgba(186, 175, 245, 0.2)',
          background: '#05070d',
          boxShadow: '0 24px 64px rgba(0, 0, 0, 0.45)',
          imageRendering: viewMode === 'traversability' || viewMode === 'cost' ? 'pixelated' : 'auto',
        }}
      />

      <p className="lp-visually-hidden" aria-live="polite">
        {hoverCell ? `Cursor at row ${hoverCell[0]}, column ${hoverCell[1]}.` : ''}
      </p>

      {loading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(5, 7, 13, 0.86)',
            color: '#c8cddb',
            fontFamily: "var(--font-data)",
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
}

export default MapCanvas
export { DOWNSAMPLE }

function redraw(
  ctx: CanvasRenderingContext2D,
  baseImage: ImageData | null,
  waypoints: Waypoint[] | null,
  start: [number, number] | null,
  goal: [number, number] | null,
  /** How much of the planned line has swept in; see revealStep. */
  revealStep: number,
  /** Where the rover is on the mission clock; see the playbackStep prop. */
  roverStep: number | null,
  hoverCell: [number, number] | null,
  gridRows: number,
  overlays?: readonly OverlayCommand[],
) {
  if (baseImage) {
    ctx.putImageData(baseImage, 0, 0)
  } else {
    ctx.fillStyle = '#05070d'
    ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE)
  }

  // Before the route and the markers: a field overlay is a backdrop, and the
  // planned route must stay readable on top of it.
  if (overlays && overlays.length) {
    drawOverlays(ctx, overlays, gridRows, CANVAS_SIZE)
  }

  if (waypoints && waypoints.length > 1) {
    const drawUpTo = Math.min(waypoints.length - 1, Math.max(revealStep, roverStep ?? 0))

    ctx.save()
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.shadowColor = 'rgba(0, 0, 0, 0.55)'
    ctx.shadowBlur = 12

    // Runs of one risk level, not one path per segment.
    //
    // The segment between two waypoints is about a cell long, and a dash
    // pattern restarted on every one of those would draw the same first dash
    // every time -- four identical lines wearing four colours, which is the
    // problem the pattern exists to solve. Stroking the whole run as a single
    // path lets the pattern actually repeat and be recognised.
    ctx.lineWidth = 2.8
    let runStart = 1
    for (let index = 1; index <= drawUpTo; index += 1) {
      const level = waypoints[index].risk_level
      // Ground already covered reads at full strength, the road ahead is held
      // back. Without this the whole route looks identical the moment the
      // reveal finishes and the marker is the only thing saying how far along
      // the rover actually is.
      const covered = roverStep === null || index <= roverStep
      const isLastSegment = index === drawUpTo
      // A run therefore ends at the rover as well as where the risk level
      // changes: one path cannot carry two alpha values.
      //
      // isLastSegment stays first in the chain -- it short-circuits the
      // waypoints[index + 1] read, which is undefined on the final segment.
      const runEnds =
        isLastSegment || waypoints[index + 1].risk_level !== level || index === roverStep

      if (!runEnds) {
        continue
      }

      // Cyan is the calm trajectory; a risk colour is a departure from it, so
      // LOW keeps the base line and the other three announce themselves.
      ctx.strokeStyle = level === 'LOW' ? ROUTE_CYAN : riskToHex(level)
      ctx.setLineDash(riskToDash(level))
      ctx.globalAlpha = covered ? 1 : 0.42
      ctx.beginPath()
      ctx.moveTo(waypoints[runStart - 1].col, waypoints[runStart - 1].row)
      for (let step = runStart; step <= index; step += 1) {
        ctx.lineTo(waypoints[step].col, waypoints[step].row)
      }
      ctx.stroke()

      // A severe stretch has to be findable, not just readable once found.
      // The marker sits where the run begins and is drawn solid, so it
      // survives whatever the dash pattern is doing.
      if (level === 'HIGH' || level === 'CRITICAL') {
        ctx.save()
        ctx.setLineDash([])
        ctx.fillStyle = riskToHex(level)
        ctx.strokeStyle = '#05070d'
        ctx.lineWidth = 1
        const wp = waypoints[runStart - 1]
        const size = level === 'CRITICAL' ? 4.6 : 3.8
        ctx.beginPath()
        // Triangle for CRITICAL, square for HIGH: two shapes nobody has to
        // compare against a legend to tell apart.
        if (level === 'CRITICAL') {
          ctx.moveTo(wp.col, wp.row - size)
          ctx.lineTo(wp.col + size, wp.row + size * 0.8)
          ctx.lineTo(wp.col - size, wp.row + size * 0.8)
          ctx.closePath()
        } else {
          ctx.rect(wp.col - size / 2, wp.row - size / 2, size, size)
        }
        ctx.fill()
        ctx.stroke()
        ctx.restore()
      }

      runStart = index + 1
    }

    ctx.globalAlpha = 1
    ctx.setLineDash([])
    ctx.restore()

    if (roverStep !== null && roverStep < waypoints.length) {
      const rover = waypoints[roverStep]
      ctx.save()
      ctx.fillStyle = '#e7eaf1'
      ctx.shadowColor = ROUTE_CYAN
      ctx.shadowBlur = 14
      ctx.beginPath()
      ctx.arc(rover.col, rover.row, 4.8, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0
      ctx.strokeStyle = ROUTE_CYAN
      ctx.lineWidth = 1.6
      ctx.stroke()
      ctx.restore()
    }
  }

  drawMarker(ctx, start, START_MINT, 'S')
  drawMarker(ctx, goal, GOAL_CORAL, 'G')
  drawHoverCrosshair(ctx, hoverCell)
}

function getCanvasCell(
  canvas: HTMLCanvasElement,
  clientX: number,
  clientY: number,
): [number, number] | null {
  const rect = canvas.getBoundingClientRect()
  const scaleX = CANVAS_SIZE / rect.width
  const scaleY = CANVAS_SIZE / rect.height
  const col = Math.floor((clientX - rect.left) * scaleX)
  const row = Math.floor((clientY - rect.top) * scaleY)

  if (col < 0 || col >= CANVAS_SIZE || row < 0 || row >= CANVAS_SIZE) {
    return null
  }

  return [row, col]
}

function drawHoverCrosshair(
  ctx: CanvasRenderingContext2D,
  hoverCell: [number, number] | null,
) {
  if (!hoverCell) {
    return
  }

  const [row, col] = hoverCell
  const x = col + 0.5
  const y = row + 0.5

  ctx.save()
  ctx.strokeStyle = 'rgba(186, 175, 245, 0.18)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(x, 0)
  ctx.lineTo(x, CANVAS_SIZE)
  ctx.moveTo(0, y)
  ctx.lineTo(CANVAS_SIZE, y)
  ctx.stroke()

  ctx.strokeStyle = 'rgba(231, 234, 241, 0.92)'
  ctx.lineWidth = 1.2
  ctx.beginPath()
  ctx.moveTo(x - 8, y)
  ctx.lineTo(x + 8, y)
  ctx.moveTo(x, y - 8)
  ctx.lineTo(x, y + 8)
  ctx.stroke()

  ctx.fillStyle = '#e7eaf1'
  ctx.beginPath()
  ctx.arc(x, y, 1.8, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

function buildBaseImage({
  ctx,
  viewMode,
  elevationGrid,
  slopeGrid,
  aspectGrid,
  shadowGrid,
  thermalGrid,
  costGrid,
  traversableGrid,
  resolutionM,
}: {
  ctx: CanvasRenderingContext2D
  viewMode: MapViewMode
  elevationGrid: (number | null)[][] | null
  slopeGrid: (number | null)[][] | null
  aspectGrid: (number | null)[][] | null
  shadowGrid: (number | null)[][] | null
  thermalGrid: (number | null)[][] | null
  costGrid: (number | null)[][] | null
  traversableGrid: (number | null)[][] | null
  resolutionM: number
}): ImageData | null {
  switch (viewMode) {
    case 'surface':
      return buildSurfaceImage(ctx, elevationGrid, resolutionM)
    case 'thermal':
      return buildScalarImage(ctx, thermalGrid, (value, range) => thermalToRgb(value, range.min, range.max))
    case 'cost':
      return buildScalarImage(ctx, costGrid, (value, range) => viridisToRgb(value, range.min, range.max))
    case 'shadow':
      return buildScalarImage(ctx, shadowGrid, (value, range) => grayReverseToRgb(value, range.min, range.max))
    case 'traversability':
      return buildTraversabilityImage(ctx, traversableGrid)
    case 'slope':
      return buildScalarImage(ctx, slopeGrid, (value, range) => magmaToRgb(value, range.min, range.max))
    case 'aspect':
      return buildAspectImage(ctx, aspectGrid)
    default:
      return null
  }
}

function buildScalarImage(
  ctx: CanvasRenderingContext2D,
  grid: (number | null)[][] | null,
  colorize: (value: number | null, range: { min: number; max: number }) => [number, number, number],
): ImageData | null {
  if (!grid || grid.length === 0 || grid[0].length === 0) {
    return null
  }

  const imageData = ctx.createImageData(CANVAS_SIZE, CANVAS_SIZE)
  const range = getFiniteRange(grid)
  const rows = grid.length
  const cellPx = CANVAS_SIZE / rows

  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < grid[row].length; col += 1) {
      paintCell(imageData, row, col, cellPx, colorize(grid[row][col], range))
    }
  }

  return imageData
}

function buildTraversabilityImage(
  ctx: CanvasRenderingContext2D,
  traversableGrid: (number | null)[][] | null,
): ImageData | null {
  return buildScalarImage(ctx, traversableGrid, (value) => rdYlGnToRgb(value, 0, 1))
}

function buildAspectImage(
  ctx: CanvasRenderingContext2D,
  aspectGrid: (number | null)[][] | null,
): ImageData | null {
  if (!aspectGrid || aspectGrid.length === 0 || aspectGrid[0].length === 0) {
    return null
  }

  const imageData = ctx.createImageData(CANVAS_SIZE, CANVAS_SIZE)
  const rows = aspectGrid.length
  const cellPx = CANVAS_SIZE / rows

  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < aspectGrid[row].length; col += 1) {
      paintCell(imageData, row, col, cellPx, aspectToRgb(aspectGrid[row][col]))
    }
  }

  return imageData
}

function buildSurfaceImage(
  ctx: CanvasRenderingContext2D,
  elevationGrid: (number | null)[][] | null,
  resolutionM: number,
): ImageData | null {
  if (!elevationGrid || elevationGrid.length === 0 || elevationGrid[0].length === 0) {
    return null
  }

  const imageData = ctx.createImageData(CANVAS_SIZE, CANVAS_SIZE)
  const range = getFiniteRange(elevationGrid)
  const rows = elevationGrid.length
  const cellPx = CANVAS_SIZE / rows
  const effectiveResolution = resolutionM * DOWNSAMPLE

  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < elevationGrid[row].length; col += 1) {
      const value = elevationGrid[row][col]
      const color =
        typeof value === 'number' && Number.isFinite(value)
          ? shadeRegolith(lunarRegolithToRgb(value, range.min, range.max), computeHillshade(elevationGrid, row, col, effectiveResolution))
          : ([8, 8, 11] as [number, number, number])

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
  ctx.fillStyle = '#05070d'
  ctx.font = 'bold 8px "Azeret Mono", ui-monospace, monospace'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(label, col, row + 0.5)
  ctx.restore()
}
