import { describe, expect, it } from 'vitest'
import { clampOffset, KEEP_VISIBLE } from './useDraggableWindow'

/**
 * The window at rest: 394px wide, near the bottom-right of a 1440x900 screen,
 * which is where assistant.css puts it.
 */
const BASE = { left: 1030, top: 204, width: 394 }
const VIEW = { width: 1440, height: 900 }

describe('clampOffset', () => {
  it('leaves a drag that stays on screen alone', () => {
    expect(clampOffset({ x: -300, y: -100 }, BASE, VIEW)).toEqual({ x: -300, y: -100 })
  })

  it('keeps a sliver on screen when dragged off the left', () => {
    // Far enough left to put the whole window past the edge.
    const { x } = clampOffset({ x: -5000, y: 0 }, BASE, VIEW)
    // The window's right edge lands exactly KEEP_VISIBLE from the left edge.
    expect(BASE.left + x + BASE.width).toBe(KEEP_VISIBLE)
  })

  it('keeps a sliver on screen when dragged off the right', () => {
    const { x } = clampOffset({ x: 5000, y: 0 }, BASE, VIEW)
    expect(BASE.left + x).toBe(VIEW.width - KEEP_VISIBLE)
  })

  it('stops the header at the top edge rather than past it', () => {
    // The header IS the drag handle, so the top must stay fully reachable --
    // this edge clamps to 0, not to KEEP_VISIBLE past the edge like the others.
    const { y } = clampOffset({ x: 0, y: -5000 }, BASE, VIEW)
    expect(BASE.top + y).toBe(0)
  })

  it('keeps a sliver on screen when dragged off the bottom', () => {
    const { y } = clampOffset({ x: 0, y: 5000 }, BASE, VIEW)
    expect(BASE.top + y).toBe(VIEW.height - KEEP_VISIBLE)
  })

  it('pulls a window back inside a viewport that just got smaller', () => {
    // Dragged right on a wide screen, then the browser is made narrow. Re-
    // clamping the SAME offset against the new viewport is what recovers it.
    const dragged = clampOffset({ x: 200, y: 0 }, BASE, VIEW)
    expect(dragged.x).toBe(200)

    const narrow = { width: 900, height: 600 }
    const recovered = clampOffset(dragged, BASE, narrow)
    expect(BASE.left + recovered.x).toBe(narrow.width - KEEP_VISIBLE)
  })

  it('clamps both axes independently', () => {
    const { x, y } = clampOffset({ x: -5000, y: 5000 }, BASE, VIEW)
    expect(BASE.left + x + BASE.width).toBe(KEEP_VISIBLE)
    expect(BASE.top + y).toBe(VIEW.height - KEEP_VISIBLE)
  })

  it('treats the resting position as reachable in both directions', () => {
    // Zero must survive a clamp, or "Yerine al" could not put the window back.
    expect(clampOffset({ x: 0, y: 0 }, BASE, VIEW)).toEqual({ x: 0, y: 0 })
  })
})
