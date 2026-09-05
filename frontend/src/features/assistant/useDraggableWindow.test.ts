import { describe, expect, it } from 'vitest'
import { clampOffset, KEEP_VISIBLE, shouldStartDrag } from './useDraggableWindow'

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

  describe('the launcher, which is smaller than KEEP_VISIBLE', () => {
    // 46px square at right:16 / bottom:56 on the same 1440x900 screen. The
    // element is narrower than the margin the clamp keeps on screen, which is
    // the case that would break a clamp written as "keep KEEP_VISIBLE px of
    // the element inside" rather than in terms of its edges.
    const LAUNCHER = { left: 1378, top: 798, width: 46 }

    it('never lets the button leave the viewport on any edge', () => {
      const corners = [
        { x: -5000, y: 0 },
        { x: 5000, y: 0 },
        { x: 0, y: -5000 },
        { x: 0, y: 5000 },
      ]

      for (const corner of corners) {
        const { x, y } = clampOffset(corner, LAUNCHER, VIEW)
        const left = LAUNCHER.left + x
        const top = LAUNCHER.top + y

        expect(left + LAUNCHER.width).toBeGreaterThanOrEqual(0)
        expect(left).toBeLessThanOrEqual(VIEW.width)
        expect(top).toBeGreaterThanOrEqual(0)
        expect(top).toBeLessThanOrEqual(VIEW.height)
      }
    })

    it('keeps the whole button on screen at the left edge', () => {
      // KEEP_VISIBLE (64) exceeds the button's width (46), so the left clamp
      // lands it fully inside rather than half off.
      const { x } = clampOffset({ x: -5000, y: 0 }, LAUNCHER, VIEW)
      expect(LAUNCHER.left + x).toBeGreaterThanOrEqual(0)
    })
  })
})

/**
 * The smallest thing that answers closest(): this project has no jsdom, and
 * the predicate only ever asks whether a control sits between the target and
 * the handle. A node knows its parent and whether it is a control.
 */
function node(tag: string, parent: Element | null = null): Element {
  const self = {
    tagName: tag.toUpperCase(),
    parentElement: parent,
    closest(selector: string): Element | null {
      const tags = selector.split(',').map((s) => s.trim().toUpperCase())
      let current: Element | null = self as unknown as Element
      while (current) {
        if (tags.includes(current.tagName)) return current
        current = (current as unknown as { parentElement: Element | null }).parentElement
      }
      return null
    },
  }
  return self as unknown as Element
}

describe('shouldStartDrag', () => {
  it('drags when the handle is itself the control pressed', () => {
    // The regression this exists for. The launcher IS a <button>, and a guard
    // written as closest('button') without excluding the handle matched it on
    // every press -- so the button could never be dragged, only clicked.
    const launcher = node('button')
    expect(shouldStartDrag(launcher, launcher)).toBe(true)
  })

  it('drags from a press on plain content inside the handle', () => {
    const header = node('header')
    const title = node('h2', header)
    expect(shouldStartDrag(title, header)).toBe(true)
  })

  it('does not drag from a press on a control inside the handle', () => {
    // "Yeni sohbet" and minimize live in the chat header and must keep their
    // own clicks.
    const header = node('header')
    const button = node('button', header)
    expect(shouldStartDrag(button, header)).toBe(false)
  })

  it('does not drag from a press on a control nested deeper', () => {
    const header = node('header')
    const button = node('button', header)
    const icon = node('span', button)
    expect(shouldStartDrag(icon, header)).toBe(false)
  })

  it('drags from an element inside a handle that is itself a button', () => {
    // The launcher's <svg> is inside the button. The nearest control is the
    // handle, so this is still a drag.
    const launcher = node('button')
    const svg = node('svg', launcher)
    expect(shouldStartDrag(svg, launcher)).toBe(true)
  })

  it('refuses a press with no target', () => {
    expect(shouldStartDrag(null, node('header'))).toBe(false)
  })
})
